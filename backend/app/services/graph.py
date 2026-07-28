from __future__ import annotations

import logging
import re
import time
from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.core.aliases import load_default_aliases
from app.core.database import get_engine, get_readonly_engine
from app.core.llm import get_chat_model, message_text
from app.core.prompt_builder import build_system_prompt, build_user_prompt
from app.services.answer_synthesizer import synthesize_answer
from app.services.chart_spec import ChartSpec, build_chart_spec
from app.services.executor import ExecResult, execute_readonly
from app.services.response_parser import parse_response
from app.services.retrieval.lexical import retrieve
from app.services.schema_introspector import introspect_schema
from app.services.schema_serializer import serialize_schema
from app.services.sql_validator import validate_read_only

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TOP_N_TABLES = 5
SCHEMA_CHAR_BUDGET = 4000
DETAIL_LIMIT = 500

PARSE_ERROR = "PARSE_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"
UNSAFE_SQL = "UNSAFE_SQL"
EXECUTION_ERROR = "EXECUTION_ERROR"
EMPTY_RESPONSE = "EMPTY_RESPONSE"

# Mirrors response_parser's candidate extraction. If any of these match, the
# model produced something SQL-shaped that the parser still rejected — i.e. a
# validation failure, not a parse miss.
_HAS_SQL_SHAPE = re.compile(r"<sql>|```|^[ \t]*(?:SELECT|WITH)\b", re.IGNORECASE | re.MULTILINE)


class Failure(TypedDict):
    type: str
    detail: str


class PipelineState(TypedDict, total=False):
    question: str
    provider: str | None
    dry_run: bool
    schema_context: str
    tables_used: list[str]
    sql: str | None
    failure: Failure | None
    attempts: int
    exec_result: ExecResult | None
    answer: str
    chart: ChartSpec | None
    latency_ms: int


def _classify_raw(raw: str) -> str:
    if not raw or not raw.strip():
        return EMPTY_RESPONSE
    if _HAS_SQL_SHAPE.search(raw):
        return VALIDATION_ERROR
    return PARSE_ERROR


def _retry_feedback(failure: Failure) -> str:
    failure_type, detail = failure["type"], failure["detail"]

    if failure_type == VALIDATION_ERROR:
        return (
            "Previous attempt produced a query that was not read-only. "
            "Generate ONLY a SELECT or WITH query inside <sql>...</sql> tags."
        )
    if failure_type == UNSAFE_SQL:
        return (
            f"Previous attempt was rejected as unsafe: {detail} "
            "Generate ONLY a single read-only SELECT or WITH query inside <sql>...</sql> tags."
        )
    if failure_type == EMPTY_RESPONSE:
        return (
            "Previous attempt returned no content. "
            "Output your SQL strictly inside <sql>...</sql> tags."
        )
    if failure_type == EXECUTION_ERROR:
        return (
            f"Previous attempt failed to run against the database: {detail} "
            "Fix the query — check table and column names against the schema above — "
            "and output the corrected SQL inside <sql>...</sql> tags."
        )
    return (
        "Previous attempt could not be parsed. "
        "Output your SQL strictly inside <sql>...</sql> tags."
    )


def _dep(config: RunnableConfig, name: str) -> Any:
    return config["configurable"][name]


def retrieve_schema(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    engine: Engine = _dep(config, "engine")
    schema = introspect_schema(engine)
    selected = retrieve(
        state["question"],
        schema,
        aliases=_dep(config, "aliases"),
        top_n=TOP_N_TABLES,
    )
    return {
        "schema_context": serialize_schema(selected, char_budget=SCHEMA_CHAR_BUDGET),
        "tables_used": [table["name"] for table in selected],
    }


def generate_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    chat_model: BaseChatModel = _dep(config, "chat_model")
    failure = state.get("failure")
    attempts = state.get("attempts", 0) + 1

    messages = [
        SystemMessage(content=build_system_prompt()),
        HumanMessage(
            content=build_user_prompt(
                state["question"],
                state["schema_context"],
                feedback=_retry_feedback(failure) if failure else "",
            )
        ),
    ]

    raw = message_text(chat_model.invoke(messages))
    parsed = parse_response(raw)

    if parsed is None:
        failure_type = _classify_raw(raw)
        logger.warning(
            "sql generation failed",
            extra={"attempt": attempts, "failure_type": failure_type},
        )
        return {
            "attempts": attempts,
            "sql": None,
            "failure": Failure(type=failure_type, detail=raw[:DETAIL_LIMIT]),
        }

    return {"attempts": attempts, "sql": parsed.query, "failure": None}


def validate_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    result = validate_read_only(state["sql"] or "")
    if result.is_safe:
        return {"failure": None}

    logger.warning("sql rejected as unsafe", extra={"reason": result.reason})
    return {"sql": None, "failure": Failure(type=UNSAFE_SQL, detail=result.reason)}


def execute_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    engine_ro: Engine = _dep(config, "engine_ro")
    settings: Settings = _dep(config, "settings")
    try:
        result = execute_readonly(
            engine_ro,
            state["sql"],
            limit=settings.query_row_limit,
            timeout_s=settings.query_timeout_s,
        )
    except SQLAlchemyError as exc:
        detail = str(getattr(exc, "orig", exc))[:DETAIL_LIMIT]
        logger.warning("sql execution failed", extra={"detail": detail})
        return {
            "sql": None,
            "exec_result": None,
            "failure": Failure(type=EXECUTION_ERROR, detail=detail),
        }

    return {"exec_result": result, "failure": None}


def synthesize_answer_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    chat_model: BaseChatModel = _dep(config, "chat_model")
    try:
        answer = synthesize_answer(
            state["question"], state["sql"] or "", state["exec_result"], chat_model
        )
    except Exception:  # noqa: BLE001 - best effort; the rows and SQL still stand alone
        logger.exception("answer synthesis failed")
        return {"answer": ""}
    return {"answer": answer}


def build_chart_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    try:
        return {"chart": build_chart_spec(state["exec_result"])}
    except Exception:  # noqa: BLE001 - a missing chart must not fail the request
        logger.exception("chart spec generation failed")
        return {"chart": None}


def _route(state: PipelineState, on_success: str) -> str:
    if not state.get("failure"):
        return on_success
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate_sql"
    return END


def _after_generate(state: PipelineState) -> str:
    return _route(state, "validate_sql")


def _after_validate(state: PipelineState) -> str:
    # a dry run stops at validated SQL — nothing is executed, nothing is synthesized
    return _route(state, END if state.get("dry_run") else "execute_sql")


def _after_execute(state: PipelineState) -> str:
    return _route(state, "synthesize_answer")


def _build_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("retrieve_schema", retrieve_schema)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("validate_sql", validate_sql)
    builder.add_node("execute_sql", execute_sql)
    builder.add_node("synthesize_answer", synthesize_answer_node)
    builder.add_node("build_chart", build_chart_node)

    builder.add_edge(START, "retrieve_schema")
    builder.add_edge("retrieve_schema", "generate_sql")
    builder.add_conditional_edges(
        "generate_sql", _after_generate, ["validate_sql", "generate_sql", END]
    )
    builder.add_conditional_edges(
        "validate_sql", _after_validate, ["execute_sql", "generate_sql", END]
    )
    builder.add_conditional_edges(
        "execute_sql", _after_execute, ["synthesize_answer", "generate_sql", END]
    )
    # terminal tail: a failure in here degrades the response, it never retries SQL
    builder.add_edge("synthesize_answer", "build_chart")
    builder.add_edge("build_chart", END)
    return builder.compile()


GRAPH = _build_graph()


def run_pipeline(
    question: str,
    provider: str | None = None,
    *,
    dry_run: bool = False,
    chat_model: BaseChatModel | None = None,
    engine: Engine | None = None,
    engine_ro: Engine | None = None,
    settings: Settings | None = None,
) -> PipelineState:
    settings = settings or get_settings()
    started = time.perf_counter()

    state: PipelineState = GRAPH.invoke(
        {
            "question": question,
            "provider": provider,
            "dry_run": dry_run,
            "attempts": 0,
            "sql": None,
            "failure": None,
            "exec_result": None,
            "answer": "",
            "chart": None,
        },
        config={
            "configurable": {
                "chat_model": chat_model or get_chat_model(provider, settings),
                "engine": engine or get_engine(),
                "engine_ro": engine_ro or get_readonly_engine(),
                "aliases": load_default_aliases(),
                "settings": settings,
            }
        },
    )

    state["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return state

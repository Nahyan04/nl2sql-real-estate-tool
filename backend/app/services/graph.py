from __future__ import annotations

import logging
import re
import time
from typing import Any, NotRequired, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, TimeoutError as PoolTimeout

from app.config import Settings, get_settings
from app.core.database import get_engine, get_readonly_engine
from app.core.llm import get_chat_model, message_text, provider_failure
from app.core.prompt_builder import build_system_prompt, build_user_prompt
from app.services.answer_synthesizer import synthesize_answer
from app.services.chart_spec import ChartSpec, build_chart_spec
from app.services.executor import ExecResult, execute_readonly, QueryDeadlineError, ResultSizeError
from app.services.model_runtime import (
    ModelBusyError,
    ModelRuntime,
    RequestDeadlineError,
    get_model_runtime,
)
from app.services.response_parser import parse_response
from app.services.retrieval.lexical import retrieve
from app.services.schema_serializer import serialize_schema
from app.services.sql_validator import validate_product_query, product_tables_used
from app.services.product_schema import introspect_product_schema, ALIASES
from app.services.question_policy import classify_question
from app.services.query_semantics import missing_question_filters
from app.core.language import Language, LanguageChoice, resolve_language
from app.services.rental_query_plans import source_rental_plan, render_rental_plan_answer
from app.services.sales_query_plans import sales_analysis_plan, render_sales_analysis

logger = logging.getLogger(__name__)

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
_EXPLICIT_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


class Failure(TypedDict):
    type: str
    detail: str
    retry_after: NotRequired[int]
    user_message: NotRequired[str]


class PipelineState(TypedDict, total=False):
    request_id: str | None
    question: str
    language: Language
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
    outcome: str
    snapshot_id: str | None
    deadline: float
    max_attempts: int
    model_usage: dict[str, Any]
    query_method: str


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
    if failure_type == "SCOPE_ERROR":
        return (
            f"The SQL omitted explicit question filters: {detail}. "
            "Include every listed filter with AND in the WHERE clause and return corrected SQL in <sql>...</sql> tags."
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
    if failure_type == "CLARIFICATION_RETRY":
        return (
            f"Previous clarification: {detail}. The question already gives a year or reporting period. Use that period to produce SQL "
            "when the remaining scope is source-matchable. Ask for clarification only if a place "
            "or another necessary filter is genuinely ambiguous. Requests for all/each source district "
            "do not require a named place or a sales municipality. The ADREC transactions export is scoped "
            "to Abu Dhabi emirate, not multiple emirates; unknown municipality does not make the emirate "
            "ambiguous. Per-year wording requires separate yearly results. Coverage audits must preserve unmatched segments."
        )
    return (
        "Previous attempt could not be parsed. "
        "Output your SQL strictly inside <sql>...</sql> tags."
    )


def _dep(config: RunnableConfig, name: str) -> Any:
    return config["configurable"][name]


def _invoke_model(state: PipelineState, config: RunnableConfig, messages: list[Any]) -> Any:
    runtime: ModelRuntime = _dep(config, "model_runtime")
    chat_model: BaseChatModel = _dep(config, "chat_model")
    started = time.monotonic()
    with runtime.admit(state["deadline"]):
        response = chat_model.invoke(messages)
    logger.info("model call completed provider=%s elapsed_ms=%d", state.get("provider"), int((time.monotonic() - started) * 1000))
    usage = _dep(config, "model_usage")
    metadata = getattr(response, "usage_metadata", None) or {}
    usage["calls"] += 1
    usage["input_tokens"] += metadata.get("input_tokens", 0)
    usage["output_tokens"] += metadata.get("output_tokens", 0)
    model = (getattr(response, "response_metadata", None) or {}).get("model_name")
    if model:
        usage["model"] = model
    return response


def _provider_failure(exc: Exception, state: PipelineState, phase: str) -> Failure:
    failure = provider_failure(exc)
    logger.error("model failure request_id=%s phase=%s provider=%s code=%s status=%s exception_type=%s",
                 state.get("request_id"), phase, state.get("provider"), failure["type"],
                 getattr(exc, "status_code", None), type(exc).__name__)
    return Failure(**failure)


def retrieve_schema(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    engine: Engine = _dep(config, "engine")
    schema = introspect_product_schema(engine)
    selected = retrieve(
        state["question"],
        schema,
        aliases=_dep(config, "aliases"),
        top_n=TOP_N_TABLES,
    )
    return {
        "schema_context": serialize_schema(selected, char_budget=SCHEMA_CHAR_BUDGET),
        "tables_used": [table["name"] for table in selected],
        "snapshot_id": schema.get("snapshot_id"),
    }


def generate_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    failure = state.get("failure")
    attempts = state.get("attempts", 0) + 1

    if not failure:
        sales_plan = sales_analysis_plan(state["question"])
        if sales_plan:
            return {"attempts": 0, "sql": sales_plan[0], "failure": None,
                    "query_method": f"source_plan:sales_{sales_plan[1]}"}
        plan = source_rental_plan(state["question"])
        if plan:
            return {"attempts": 0, "sql": plan.sql, "failure": None,
                    "query_method": f"source_plan:{plan.kind}"}

    system_prompt = build_system_prompt() + f"\nWrite clarification or unsupported text in {state['language']}. SQL identifiers remain English."
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=build_user_prompt(
                state["question"],
                state["schema_context"],
                feedback=_retry_feedback(failure) if failure else "",
                system_prompt=system_prompt,
            )
        ),
    ]

    try:
        raw = message_text(_invoke_model(state, config, messages))
    except ModelBusyError:
        return {
            "attempts": attempts,
            "sql": None,
            "failure": Failure(
                type="MODEL_BUSY",
                detail="Model capacity is temporarily unavailable; try again shortly.",
            ),
        }
    except RequestDeadlineError:
        return {
            "attempts": attempts,
            "sql": None,
            "failure": Failure(
                type="REQUEST_TIMEOUT",
                detail="The request exceeded its total time limit.",
            ),
        }
    except Exception as exc:  # noqa: BLE001 - provider transport and SDK errors vary
        return {
            "attempts": attempts,
            "sql": None,
            "failure": _provider_failure(exc, state, "generation"),
        }
    unsupported = re.fullmatch(r"\s*<unsupported>(.*?)</unsupported>\s*", raw, re.DOTALL)
    if unsupported:
        return {"attempts": attempts, "sql": None, "failure": Failure(type="UNSUPPORTED", detail=unsupported.group(1)[:DETAIL_LIMIT])}
    clarification = re.fullmatch(r"\s*<clarification>(.*?)</clarification>\s*", raw, re.DOTALL)
    if clarification:
        if attempts < state.get("max_attempts", 1) and _EXPLICIT_YEAR.search(state["question"]):
            return {"attempts": attempts, "sql": None,
                    "failure": Failure(type="CLARIFICATION_RETRY", detail=clarification.group(1)[:DETAIL_LIMIT])}
        reason = clarification.group(1).strip()[:DETAIL_LIMIT]
        return {"attempts": attempts, "sql": None,
                "failure": Failure(type="CLARIFICATION", detail=reason, user_message=reason)}
    parsed = parse_response(raw)

    if parsed is None:
        failure_type = _classify_raw(raw)
        logger.warning("sql generation failed request_id=%s attempt=%s failure_type=%s",
                       state.get("request_id"), attempts, failure_type)
        return {
            "attempts": attempts,
            "sql": None,
            "failure": Failure(type=failure_type, detail=raw[:DETAIL_LIMIT]),
        }

    return {"attempts": attempts, "sql": parsed.query, "failure": None,
            "query_method": "model"}


def validate_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    result = validate_product_query(state["sql"] or "")
    if result.is_safe:
        missing = missing_question_filters(state["question"], state["sql"] or "")
        if missing:
            return {"sql": None, "failure": Failure(type="SCOPE_ERROR", detail=", ".join(missing))}
        return {"failure": None, "tables_used": product_tables_used(state["sql"])}

    logger.warning("sql rejected as unsafe", extra={"reason": result.reason})
    return {"sql": None, "failure": Failure(type=UNSAFE_SQL, detail=result.reason)}


def execute_sql(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    engine_ro: Engine = _dep(config, "engine_ro")
    settings: Settings = _dep(config, "settings")
    remaining = state["deadline"] - time.monotonic()
    if remaining <= 0:
        return {
            "sql": None,
            "exec_result": None,
            "failure": Failure(
                type="REQUEST_TIMEOUT",
                detail="The request exceeded its total time limit.",
            ),
        }
    request_budget_limited = remaining < settings.query_timeout_s
    try:
        result = execute_readonly(
            engine_ro,
            state["sql"],
            limit=settings.query_row_limit,
            timeout_s=min(settings.query_timeout_s, remaining),
            max_result_bytes=settings.query_result_bytes,
            max_cell_bytes=settings.query_cell_bytes,
        )
    except (PoolTimeout, QueryDeadlineError, ResultSizeError) as exc:
        kind = (
            "DATABASE_BUSY"
            if isinstance(exc, PoolTimeout)
            else "REQUEST_TIMEOUT"
            if isinstance(exc, QueryDeadlineError) and request_budget_limited
            else "QUERY_TIMEOUT"
            if isinstance(exc, QueryDeadlineError)
            else "RESULT_TOO_LARGE"
        )
        return {"sql": None, "exec_result": None, "failure": Failure(type=kind, detail="Query resource limit reached; narrow the question or try again shortly.")}
    except SQLAlchemyError as exc:
        if getattr(getattr(exc, "orig", None), "pgcode", None) in {"57014", "53300"}:
            kind = "REQUEST_TIMEOUT" if request_budget_limited else "QUERY_TIMEOUT"
            return {"sql": None, "exec_result": None, "failure": Failure(type=kind, detail="Database query timed out or capacity is unavailable.")}
        detail = str(getattr(exc, "orig", exc))[:DETAIL_LIMIT]
        logger.warning("sql execution failed request_id=%s attempt=%s sqlstate=%s exception_type=%s",
                       state.get("request_id"), state.get("attempts"), getattr(getattr(exc, "orig", None), "pgcode", None),
                       type(getattr(exc, "orig", exc)).__name__)
        return {
            "sql": None,
            "exec_result": None,
            "failure": Failure(type=EXECUTION_ERROR, detail=detail),
        }

    no_data = not result.rows or all(all(value is None for value in row) for row in result.rows)
    if state.get("query_method", "").startswith("source_plan:") and result.rows:
        no_data = no_data or all(row[0] is None for row in result.rows)
    return {
        "exec_result": result,
        "failure": None,
        "sql": result.executed_sql,
        "outcome": "no_data" if no_data else "answer",
    }


def synthesize_answer_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    if state.get("outcome") == "no_data":
        arabic = state["language"] == "ar"
        return {"answer": "لم تُرجع البيانات صفوفًا مطابقة لهذا السؤال." if arabic else "No matching data was returned for this question."}
    method = state.get("query_method", "")
    if method.startswith("source_plan:sales_"):
        return {"answer": render_sales_analysis(
            state["question"], method.removeprefix("source_plan:sales_"),
            state["exec_result"].rows, state["language"],
        )}
    if method.startswith("source_plan:"):
        return {"answer": render_rental_plan_answer(
            state["question"], method.partition(":")[2], state["exec_result"].rows,
            language=state["language"],
        )}
    try:
        answer = synthesize_answer(
            state["question"],
            state["sql"] or "",
            state["exec_result"],
            lambda messages: _invoke_model(state, config, messages),
            language=state["language"],
        )
    except (ModelBusyError, RequestDeadlineError) as exc:
        kind = "MODEL_BUSY" if isinstance(exc, ModelBusyError) else "REQUEST_TIMEOUT"
        detail = (
            "Model capacity is temporarily unavailable; try again shortly."
            if isinstance(exc, ModelBusyError)
            else "The request exceeded its total time limit."
        )
        return {"answer": "", "failure": Failure(type=kind, detail=detail)}
    except ValueError:
        return {"answer": "", "failure": Failure(type="LANGUAGE_MISMATCH", detail="Answer language did not match request.")}
    except Exception as exc:  # noqa: BLE001 - provider transport and SDK errors vary
        return {"answer": "", "failure": _provider_failure(exc, state, "synthesis")}
    return {"answer": answer}


def build_chart_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    if state.get("failure") or state.get("outcome") == "no_data":
        return {"chart": None}
    try:
        return {"chart": build_chart_spec(state["exec_result"])}
    except Exception:  # noqa: BLE001 - a missing chart must not fail the request
        logger.exception("chart spec generation failed")
        return {"chart": None}


def _route(state: PipelineState, on_success: str) -> str:
    if not state.get("failure"):
        return on_success
    if state.get("failure", {}).get("type") in {"UNSUPPORTED", "CLARIFICATION", "DATABASE_BUSY", "QUERY_TIMEOUT", "RESULT_TOO_LARGE", "MODEL_BUSY", "REQUEST_TIMEOUT", "PROVIDER_UNAVAILABLE", "PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMIT", "PROVIDER_CONFIGURATION_ERROR", "PROVIDER_REQUEST_ERROR", "LANGUAGE_MISMATCH"}:
        return END
    if state.get("attempts", 0) < state.get("max_attempts", 1):
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
    language: LanguageChoice = "auto",
    dry_run: bool = False,
    chat_model: BaseChatModel | None = None,
    engine: Engine | None = None,
    engine_ro: Engine | None = None,
    settings: Settings | None = None,
    model_runtime: ModelRuntime | None = None,
    request_id: str | None = None,
) -> PipelineState:
    settings = settings or get_settings()
    started = time.perf_counter()
    model_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "model": None}
    resolved_language = resolve_language(question, language)

    decision = classify_question(question)
    if decision:
        return {
            "question": question,
            "language": resolved_language,
            "provider": provider,
            "dry_run": dry_run,
            "attempts": 0,
            "sql": None,
            "failure": Failure(type=decision.code, detail=decision.detail),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model_usage": model_usage,
            "query_method": "policy",
        }

    state: PipelineState = GRAPH.invoke(
        {
            "question": question,
            "request_id": request_id,
            "language": resolved_language,
            "provider": provider,
            "dry_run": dry_run,
            "attempts": 0,
            "sql": None,
            "failure": None,
            "exec_result": None,
            "answer": "",
            "chart": None,
            "deadline": started + settings.request_timeout_s,
            "max_attempts": settings.model_generation_attempts,
            "query_method": "model",
        },
        config={
            "configurable": {
                "chat_model": chat_model or get_chat_model(provider, settings),
                "engine": engine or get_engine(),
                "engine_ro": engine_ro or get_readonly_engine(),
                "aliases": ALIASES,
                "settings": settings,
                "model_runtime": model_runtime or get_model_runtime(
                    settings.model_concurrency,
                    settings.model_queue_size,
                    settings.model_queue_wait_s,
                ),
                "model_usage": model_usage,
            }
        },
    )

    state["latency_ms"] = int((time.perf_counter() - started) * 1000)
    state["model_usage"] = model_usage
    return state

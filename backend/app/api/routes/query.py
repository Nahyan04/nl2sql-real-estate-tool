from __future__ import annotations

import logging
from uuid import uuid4
from dataclasses import asdict
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings
from app.core.llm import get_chat_model
from app.models.contracts import ChartSpecPayload, ErrorResponse, QueryRequest, QueryResponse
from app.services.executor import ExecResult
from app.services.answer_synthesizer import MAX_ANSWER_ROWS
from app.services.graph import run_pipeline
from app.services.query_metadata import date_conditions
from app.services.request_limiter import (
    SESSION_COOKIE,
    LimitRejected,
    LimiterUnavailable,
    RequestLimiter,
    client_ip,
    get_request_limiter,
    session_id,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ChatModelFactory = Callable[[str | None], BaseChatModel]

UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
UPSTREAM_ERROR = "UPSTREAM_ERROR"


def chat_model_factory(settings: Settings = Depends(get_settings)) -> ChatModelFactory:
    """Indirection so tests can swap the model without touching the pipeline."""
    return lambda provider: get_chat_model(provider, settings)


def _jsonable_rows(rows: list[list[Any]]) -> list[list[Any]]:
    """Postgres numerics arrive as Decimal, which Pydantic renders as a JSON
    string. Charts need numbers, so widen them here."""
    return [[float(v) if isinstance(v, Decimal) else v for v in row] for row in rows]


SAFE_FAILURE_DETAILS = {
    "PARSE_ERROR": "The model did not produce a usable query. Try a more specific question.",
    "EMPTY_RESPONSE": "The model did not produce a query. Please try again.",
    "VALIDATION_ERROR": "The generated query could not be validated. Try a narrower question.",
    "UNSAFE_SQL": "The generated query was rejected by the read-only validator.",
    "UNSUPPORTED": "The available data does not support this question as asked.",
    "CLARIFICATION": "Specify an exact period or an unambiguous source place so this question can be answered.",
    "EXECUTION_ERROR": "The query could not be completed. Try a narrower question.",
    "DATABASE_BUSY": "The database is busy. Please try again shortly.",
    "QUERY_TIMEOUT": "The query exceeded its time limit. Try a narrower question.",
    "RESULT_TOO_LARGE": "The result is too large. Add a filter or grouping.",
    "MODEL_BUSY": "The model is busy. Please try again shortly.",
    "REQUEST_TIMEOUT": "The analysis exceeded its time limit. Try a narrower question.",
    "PROVIDER_UNAVAILABLE": "The selected model provider is unavailable. Try again when it is online.",
}


def _error(
    status_code: int, error: str, detail: str, request_id: str, retry_after: int | None = None,
) -> JSONResponse:
    headers = {"X-Request-ID": request_id}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, detail=detail, request_id=request_id).model_dump(),
        headers=headers,
    )


def _failure_status(failure_type: str) -> int:
    if failure_type == "MODEL_BUSY":
        return 429
    if failure_type in {"REQUEST_TIMEOUT", "QUERY_TIMEOUT"}:
        return 504
    if failure_type == "DATABASE_BUSY":
        return 503
    if failure_type == "PROVIDER_UNAVAILABLE":
        return 503
    return 422


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def query(
    payload: QueryRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    factory: ChatModelFactory = Depends(chat_model_factory),
    limiter: RequestLimiter = Depends(get_request_limiter),
):
    request_id = uuid4().hex
    def attach_cookie(target: Response, value: str) -> None:
        target.set_cookie(
            SESSION_COOKIE, value, max_age=86_400, httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
        )

    try:
        chat_model = factory(payload.provider)
    except ValueError:
        return _error(400, UNKNOWN_PROVIDER, "That provider is not available.", request_id)

    session, fresh_session = session_id(request)
    ip = client_ip(request, settings.trusted_proxy_cidrs)
    try:
        with limiter.admit(session, ip):
            state = run_pipeline(
                payload.question,
                payload.provider,
                dry_run=payload.dry_run,
                chat_model=chat_model,
                settings=settings,
            )
    except LimitRejected as exc:
        result = _error(429, exc.code, "Request allowance reached; retry after the indicated delay.", request_id, exc.retry_after)
        if fresh_session:
            attach_cookie(result, session)
        return result
    except LimiterUnavailable:
        return _error(503, "LIMITER_UNAVAILABLE", "Requests are temporarily unavailable; try again shortly.", request_id, 5)
    except Exception as exc:  # noqa: BLE001 - one boundary for provider/database outages
        logger.error("pipeline failed request_id=%s exception_type=%s", request_id, type(exc).__name__)
        return _error(502, UPSTREAM_ERROR, "The analysis service is temporarily unavailable.", request_id)

    if fresh_session:
        attach_cookie(response, session)
    response.headers["X-Request-ID"] = request_id
    failure = state.get("failure")
    if failure:
        failure_type = failure["type"]
        logger.info("pipeline outcome request_id=%s code=%s", request_id, failure_type)
        result = _error(
            _failure_status(failure_type),
            failure_type,
            SAFE_FAILURE_DETAILS.get(failure_type, "The analysis could not be completed."),
            request_id,
            2 if failure_type == "MODEL_BUSY" else None,
        )
        if fresh_session:
            attach_cookie(result, session)
        return result

    result: ExecResult = state.get("exec_result") or ExecResult()
    chart = state.get("chart")
    answer_limited = result.truncated or result.row_count > MAX_ANSWER_ROWS
    answer = state.get("answer") or ""
    if answer_limited and not payload.dry_run:
        arabic = any("\u0600" <= character <= "\u06FF" for character in payload.question)
        if result.truncated:
            limitation = "نتيجة الاستعلام مقتطعة؛ لا تمثل بالضرورة جميع السجلات." if arabic else "The query result was truncated and may not represent all matching records."
        else:
            limitation = (
                f"استند الشرح إلى أول {MAX_ANSWER_ROWS} صفًا من النتائج المُعادة فقط."
                if arabic else f"The explanation used only the first {MAX_ANSWER_ROWS} returned rows."
            )
        answer = f"{answer} {limitation}".strip()

    return QueryResponse(
        answer=answer,
        outcome=state.get("outcome") or "answer",
        answer_limited=answer_limited,
        snapshot_id=state.get("snapshot_id"),
        date_conditions=date_conditions(state.get("sql") or ""),
        sql=state.get("sql") or "",
        columns=result.columns,
        rows=_jsonable_rows(result.rows),
        row_count=result.row_count,
        truncated=result.truncated,
        truncation_reason=result.truncation_reason,
        chart=ChartSpecPayload(**asdict(chart)) if chart else None,
        tables_used=state.get("tables_used") or [],
        retry_count=max(state.get("attempts", 1) - 1, 0),
        latency_ms=state.get("latency_ms", 0),
        provider=payload.provider or settings.llm_provider,
        query_method=state.get("query_method") or "model",
    )

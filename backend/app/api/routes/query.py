from __future__ import annotations

import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings
from app.core.llm import get_chat_model
from app.models.contracts import ChartSpecPayload, ErrorResponse, QueryRequest, QueryResponse
from app.services.executor import ExecResult
from app.services.graph import run_pipeline

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


def _error(status_code: int, error: str, detail: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, detail=detail).model_dump(),
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def query(
    payload: QueryRequest,
    settings: Settings = Depends(get_settings),
    factory: ChatModelFactory = Depends(chat_model_factory),
):
    try:
        chat_model = factory(payload.provider)
    except ValueError as exc:
        return _error(400, UNKNOWN_PROVIDER, str(exc))

    try:
        state = run_pipeline(
            payload.question,
            payload.provider,
            dry_run=payload.dry_run,
            chat_model=chat_model,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 - one boundary for provider/database outages
        logger.exception("pipeline failed")
        return _error(502, UPSTREAM_ERROR, str(exc))

    failure = state.get("failure")
    if failure:
        return _error(422, failure["type"], failure["detail"])

    result: ExecResult = state.get("exec_result") or ExecResult()
    chart = state.get("chart")

    return QueryResponse(
        answer=state.get("answer") or "",
        sql=state.get("sql") or "",
        columns=result.columns,
        rows=_jsonable_rows(result.rows),
        row_count=result.row_count,
        truncated=result.truncated,
        chart=ChartSpecPayload(**asdict(chart)) if chart else None,
        tables_used=state.get("tables_used") or [],
        retry_count=max(state.get("attempts", 1) - 1, 0),
        latency_ms=state.get("latency_ms", 0),
        provider=payload.provider or settings.llm_provider,
    )

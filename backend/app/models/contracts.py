from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    provider: str | None = None
    dry_run: bool = False


class ChartSpecPayload(BaseModel):
    type: str
    x_key: str | None = None
    y_keys: list[str] = Field(default_factory=list)
    title: str = ""


class QueryResponse(BaseModel):
    answer: str = ""
    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    chart: ChartSpecPayload | None = None
    tables_used: list[str] = Field(default_factory=list)
    retry_count: int = 0
    latency_ms: int = 0
    provider: str = ""


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""


class ExampleQuestion(BaseModel):
    id: str
    lang: str
    text: str


class ExamplesResponse(BaseModel):
    examples: list[ExampleQuestion]

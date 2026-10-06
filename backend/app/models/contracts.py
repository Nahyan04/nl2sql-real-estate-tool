from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from app.core.language import Language, LanguageChoice


class ClarificationAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    option_id: str = Field(min_length=1, max_length=80)


class ClarificationOption(BaseModel):
    id: str
    label: str


class ClarificationQuestion(BaseModel):
    id: str
    prompt: str
    options: list[ClarificationOption] = Field(min_length=2, max_length=3)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    provider: str | None = None
    language: LanguageChoice = "auto"
    dry_run: bool = False
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list, max_length=2)


class ChartSpecPayload(BaseModel):
    type: str
    x_key: str | None = None
    y_keys: list[str] = Field(default_factory=list)
    title: str = ""
    category_keys: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str = ""
    language: Language = "en"
    outcome: str = "answer"
    answer_limited: bool = False
    snapshot_id: str | None = None
    date_conditions: list[str] = Field(default_factory=list)
    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    chart: ChartSpecPayload | None = None
    tables_used: list[str] = Field(default_factory=list)
    retry_count: int = 0
    latency_ms: int = 0
    provider: str = ""
    query_method: str = "model"
    resolved_scope: list[str] = Field(default_factory=list)
    chart_note: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    request_id: str | None = None
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=2)


class ExampleQuestion(BaseModel):
    id: str
    lang: str
    text: str
    topic: str = "sales"
    title: str = ""
    featured: bool = False


class ExamplesResponse(BaseModel):
    examples: list[ExampleQuestion]

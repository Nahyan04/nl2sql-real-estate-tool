from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.api.routes.query import chat_model_factory
from app.main import app

SQL = "SELECT c.name_en, SUM(t.price_aed) AS total_aed FROM transactions t JOIN communities c ON c.id = t.community_id GROUP BY c.name_en ORDER BY total_aed DESC LIMIT 3"
NARRATIVE = "Yas Island leads with AED 9.35 billion."


class FakeChatModel:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls = 0

    def invoke(self, messages, **kwargs) -> AIMessage:
        self.calls += 1
        return AIMessage(content=self._responses.pop(0) if self._responses else "")


def _use(*responses: str):
    app.dependency_overrides[chat_model_factory] = lambda: (lambda provider: FakeChatModel(*responses))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def answering_client(client):
    _use(f"<sql>{SQL}</sql>", NARRATIVE)
    return client


def test_query_returns_the_synthesized_answer(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["answer"] == NARRATIVE


def test_query_returns_the_generated_sql(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["sql"] == SQL


def test_query_returns_columns_and_rows(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["columns"] == ["name_en", "total_aed"]
    assert body["row_count"] == 3
    assert len(body["rows"]) == 3


def test_query_serializes_numeric_values_from_postgres(answering_client) -> None:
    """Postgres hands back Decimal; it has to survive JSON encoding."""
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert isinstance(body["rows"][0][1], (int, float))


def test_query_serializes_dates_as_iso_strings(client) -> None:
    sql = "SELECT month, index_value FROM price_indices ORDER BY month LIMIT 3"
    _use(f"<sql>{sql}</sql>", NARRATIVE)
    body = client.post("/api/v1/query", json={"question": "price index"}).json()
    assert body["rows"][0][0] == "2019-01-01"


def test_query_returns_a_chart_spec(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["chart"]["type"] == "bar"
    assert body["chart"]["x_key"] == "name_en"
    assert body["chart"]["y_keys"] == ["total_aed"]


def test_query_reports_the_tables_it_used(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert "transactions" in body["tables_used"]


def test_query_reports_no_retries_on_a_clean_run(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["retry_count"] == 0


def test_query_reports_latency(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["latency_ms"] >= 0


def test_query_reports_the_provider(answering_client) -> None:
    body = answering_client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["provider"] == "anthropic"


def test_query_echoes_the_requested_provider(answering_client) -> None:
    payload = {"question": "top communities", "provider": "ollama"}
    body = answering_client.post("/api/v1/query", json=payload).json()
    assert body["provider"] == "ollama"


def test_query_counts_a_self_healed_retry(client) -> None:
    _use("<sql>DELETE FROM communities</sql>", f"<sql>{SQL}</sql>", NARRATIVE)
    body = client.post("/api/v1/query", json={"question": "top communities"}).json()
    assert body["retry_count"] == 1
    assert body["sql"] == SQL


def test_dry_run_returns_sql_without_executing(client) -> None:
    _use(f"<sql>{SQL}</sql>")
    body = client.post("/api/v1/query", json={"question": "top", "dry_run": True}).json()
    assert body["sql"] == SQL
    assert body["rows"] == []
    assert body["row_count"] == 0


def test_dry_run_returns_no_answer_or_chart(client) -> None:
    _use(f"<sql>{SQL}</sql>")
    body = client.post("/api/v1/query", json={"question": "top", "dry_run": True}).json()
    assert body["answer"] == ""
    assert body["chart"] is None


def test_unanswerable_question_returns_422(client) -> None:
    _use("I cannot help with that.", "I cannot help with that.", "I cannot help with that.")
    response = client.post("/api/v1/query", json={"question": "what is the weather"})
    assert response.status_code == 422


def test_unanswerable_question_reports_the_failure_type(client) -> None:
    _use("I cannot help with that.", "I cannot help with that.", "I cannot help with that.")
    body = client.post("/api/v1/query", json={"question": "what is the weather"}).json()
    assert body["error"] == "PARSE_ERROR"


def test_unsafe_sql_is_reported_as_a_structured_error(client) -> None:
    _use(*(["<sql>DROP TABLE communities</sql>"] * 3))
    body = client.post("/api/v1/query", json={"question": "drop everything"}).json()
    assert body["error"] == "VALIDATION_ERROR"
    assert "detail" in body


def test_unknown_provider_returns_400(client) -> None:
    response = client.post("/api/v1/query", json={"question": "hi", "provider": "openai"})
    assert response.status_code == 400
    assert response.json()["error"] == "UNKNOWN_PROVIDER"


def test_empty_question_is_rejected(client) -> None:
    assert client.post("/api/v1/query", json={"question": ""}).status_code == 422


def test_missing_question_is_rejected(client) -> None:
    assert client.post("/api/v1/query", json={}).status_code == 422


def test_examples_endpoint_returns_the_curated_gallery(client) -> None:
    examples = client.get("/api/v1/examples").json()["examples"]
    assert len(examples) >= 18


def test_examples_cover_both_languages(client) -> None:
    examples = client.get("/api/v1/examples").json()["examples"]
    assert {e["lang"] for e in examples} == {"en", "ar"}
    assert sum(e["lang"] == "en" for e in examples) >= 12
    assert sum(e["lang"] == "ar" for e in examples) >= 6


def test_every_example_has_an_id_and_text(client) -> None:
    examples = client.get("/api/v1/examples").json()["examples"]
    assert all(e["id"] and e["text"] for e in examples)


def test_example_ids_are_unique(client) -> None:
    examples = client.get("/api/v1/examples").json()["examples"]
    assert len({e["id"] for e in examples}) == len(examples)


def test_schema_endpoint_lists_the_real_tables(client) -> None:
    tables = {t["name"] for t in client.get("/api/v1/schema").json()["tables"]}
    assert {"transactions", "rental_contracts", "mortgages", "communities"} <= tables


def test_schema_endpoint_includes_columns(client) -> None:
    tables = client.get("/api/v1/schema").json()["tables"]
    transactions = next(t for t in tables if t["name"] == "transactions")
    assert "price_aed" in {c["name"] for c in transactions["columns"]}


def test_schema_endpoint_includes_foreign_keys(client) -> None:
    tables = client.get("/api/v1/schema").json()["tables"]
    transactions = next(t for t in tables if t["name"] == "transactions")
    assert "communities" in {fk["referred_table"] for fk in transactions["foreign_keys"]}


def test_health_endpoint_still_reports_the_database(client) -> None:
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}

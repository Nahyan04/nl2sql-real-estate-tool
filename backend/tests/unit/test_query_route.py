from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from app.api.routes.query import _failure_status, chat_model_factory
from app.config import Settings, get_settings
from app.main import app
from app.services.executor import ExecResult
from app.services.request_limiter import get_request_limiter

query_route = import_module("app.api.routes.query")


class PermissiveLimiter:
    def admit(self, session, ip):
        from contextlib import nullcontext
        return nullcontext()


@pytest.fixture
def client():
    app.dependency_overrides[get_request_limiter] = lambda: PermissiveLimiter()
    app.dependency_overrides[chat_model_factory] = lambda: lambda provider: object()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_model_capacity_failure_returns_too_many_requests() -> None:
    assert _failure_status("MODEL_BUSY") == 429


def test_total_request_deadline_returns_gateway_timeout() -> None:
    assert _failure_status("REQUEST_TIMEOUT") == 504


def test_pipeline_validation_failure_remains_unprocessable() -> None:
    assert _failure_status("UNSAFE_SQL") == 422


def test_unexpected_failure_does_not_expose_exception_text(client, monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("postgresql://user:secret@internal-host/private")

    monkeypatch.setattr(query_route, "run_pipeline", fail)
    response = client.post("/api/v1/query", json={"question": "How many sales?"})
    assert response.status_code == 502
    assert response.json()["error"] == "UPSTREAM_ERROR"
    assert "secret" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_pipeline_failure_does_not_expose_model_or_sql_detail(client, monkeypatch) -> None:
    monkeypatch.setattr(
        query_route,
        "run_pipeline",
        lambda *args, **kwargs: {"failure": {"type": "EXECUTION_ERROR", "detail": "SELECT private_password FROM secret_table"}},
    )
    response = client.post("/api/v1/query", json={"question": "How many sales?"})
    assert response.status_code == 422
    assert response.json()["error"] == "EXECUTION_ERROR"
    assert "private_password" not in response.text


def test_unknown_provider_has_safe_error(client) -> None:
    app.dependency_overrides[chat_model_factory] = lambda: lambda provider: (_ for _ in ()).throw(ValueError("internal model name"))
    response = client.post("/api/v1/query", json={"question": "How many sales?", "provider": "unknown"})
    assert response.status_code == 400
    assert response.json()["error"] == "UNKNOWN_PROVIDER"
    assert "internal model name" not in response.text


def test_disabled_ollama_cannot_be_called_directly(client) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql://example.invalid/test", readonly_db_password="unused", ollama_enabled=False,
    )
    response = client.post("/api/v1/query", json={"question": "How many sales?", "provider": "ollama"})
    assert response.status_code == 503
    assert response.json()["error"] == "PROVIDER_UNAVAILABLE"


def test_unconfigured_cloud_cannot_be_called_directly(client) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql://example.invalid/test", readonly_db_password="unused", anthropic_api_key=None,
    )
    response = client.post("/api/v1/query", json={"question": "How many sales?", "provider": "anthropic"})
    assert response.status_code == 503
    assert response.json()["error"] == "PROVIDER_UNAVAILABLE"


def test_malformed_direct_request_has_stable_error(client) -> None:
    response = client.post("/api/v1/query", json={"question": ""})
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_REQUEST"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_clarification_response_is_safe_and_actionable(client, monkeypatch) -> None:
    monkeypatch.setattr(query_route, "run_pipeline", lambda *args, **kwargs: {
        "failure": {"type": "CLARIFICATION", "detail": "internal source text"},
        "attempts": 0,
    })
    response = client.post("/api/v1/query", json={"question": "What were the latest sales?"})
    assert response.status_code == 422
    assert response.json()["error"] == "CLARIFICATION"
    assert "place and period" in response.json()["detail"]
    assert "internal source text" not in response.text


def test_query_result_limitation_is_added_even_if_synthesis_omits_it(client, monkeypatch) -> None:
    monkeypatch.setattr(query_route, "run_pipeline", lambda *args, **kwargs: {
        "failure": None,
        "outcome": "answer",
        "answer": "The leading district is Example.",
        "exec_result": ExecResult(columns=["district"], rows=[["Example"]], row_count=51),
        "sql": "SELECT district FROM transactions",
    })
    response = client.post("/api/v1/query", json={"question": "Show districts in 2025"})
    assert response.status_code == 200
    assert response.json()["answer_limited"] is True
    assert "first 50 returned rows" in response.json()["answer"]


def test_no_data_outcome_is_returned_with_executed_sql(client, monkeypatch) -> None:
    monkeypatch.setattr(query_route, "run_pipeline", lambda *args, **kwargs: {
        "failure": None,
        "outcome": "no_data",
        "answer": "No matching data was returned for this question.",
        "exec_result": ExecResult(columns=["sale_count"], rows=[], row_count=0),
        "sql": "SELECT sale_count FROM transactions WHERE false",
    })
    response = client.post("/api/v1/query", json={"question": "Show sales in 2035"})
    assert response.status_code == 200
    assert response.json()["outcome"] == "no_data"
    assert response.json()["sql"].startswith("SELECT")


def test_structured_clarification_choices_and_answers_cross_api(client, monkeypatch):
    captured = {}
    def pipeline(*args, **kwargs):
        captured.update(kwargs)
        return {'failure': {'type': 'CLARIFICATION', 'detail': 'Choose'},
                'clarification_questions': [{'id': 'place', 'prompt': 'Which scope?',
                    'options': [{'id': 'district', 'label': 'Al Bateen · district'},
                                {'id': 'community', 'label': 'Al Bateen · community'}]}]}
    monkeypatch.setattr(query_route, 'run_pipeline', pipeline)
    response = client.post('/api/v1/query', json={'question': 'Sales in Al Bateen in 2025?',
        'clarification_answers': [{'question_id': 'period', 'option_id': '2025'}]})
    assert response.status_code == 422
    assert len(response.json()['clarification_questions'][0]['options']) == 2
    assert captured['clarification_answers'][0].option_id == '2025'


def test_api_rejects_more_than_two_clarification_answers(client):
    response = client.post('/api/v1/query', json={'question': 'sales', 'clarification_answers':
        [{'question_id': str(i), 'option_id': 'a'} for i in range(3)]})
    assert response.status_code == 422 and response.json()['error'] == 'INVALID_REQUEST'

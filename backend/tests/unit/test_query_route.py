from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from app.api.routes.query import _failure_status, chat_model_factory
from app.main import app
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


def test_malformed_direct_request_has_stable_error(client) -> None:
    response = client.post("/api/v1/query", json={"question": ""})
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_REQUEST"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]

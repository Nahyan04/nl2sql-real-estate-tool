from app.api.routes.query import _failure_status


def test_model_capacity_failure_returns_too_many_requests() -> None:
    assert _failure_status("MODEL_BUSY") == 429


def test_total_request_deadline_returns_gateway_timeout() -> None:
    assert _failure_status("REQUEST_TIMEOUT") == 504


def test_pipeline_validation_failure_remains_unprocessable() -> None:
    assert _failure_status("UNSAFE_SQL") == 422

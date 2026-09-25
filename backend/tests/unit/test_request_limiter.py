import json
from contextlib import contextmanager

from fastapi import Request, Response

from app.api.routes.query import query
from app.config import Settings
from app.models.contracts import QueryRequest
from app.services.request_limiter import LimitRejected, client_ip, session_id


def request_for(peer: str, forwarded: str = "", cookie: str = "") -> Request:
    headers = []
    if forwarded:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({"type": "http", "method": "POST", "path": "/api/v1/query", "headers": headers, "client": (peer, 1234)})


def test_untrusted_forwarded_address_cannot_change_client_limit_key() -> None:
    request = request_for("203.0.113.10", "198.51.100.7")
    assert client_ip(request, "127.0.0.1/32") == "203.0.113.10"


def test_trusted_proxy_chain_uses_nearest_untrusted_address() -> None:
    request = request_for("127.0.0.1", "198.51.100.7, 192.0.2.8")
    assert client_ip(request, "127.0.0.1/32,192.0.2.0/24") == "198.51.100.7"
    malformed = request_for("127.0.0.1", "not-an-ip")
    assert client_ip(malformed, "127.0.0.1/32") == "127.0.0.1"


def test_session_cookie_is_random_and_reused() -> None:
    first, fresh = session_id(request_for("127.0.0.1"))
    assert fresh and len(first) == 32
    again, fresh = session_id(request_for("127.0.0.1", cookie=f"bayan_session={first}"))
    assert not fresh and again == first


def test_rejected_request_returns_retry_header_without_model_call() -> None:
    class RejectingLimiter:
        @contextmanager
        def admit(self, session, ip):
            raise LimitRejected("IP_RATE_LIMIT", 17)
            yield

    result = query(
        QueryRequest(question="Sales count?"),
        request_for("203.0.113.10"),
        Response(),
        settings=Settings(database_url="postgresql://unused/unused", readonly_db_password="unused"),
        factory=lambda _: object(),
        limiter=RejectingLimiter(),
    )
    assert result.status_code == 429
    assert result.headers["retry-after"] == "17"
    assert json.loads(result.body)["error"] == "IP_RATE_LIMIT"
    assert "bayan_session=" in result.headers["set-cookie"]

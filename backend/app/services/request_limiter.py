from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import secrets
import uuid
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.core.database import get_engine

SESSION_COOKIE = "bayan_session"
_SESSION_PATTERN = re.compile(r"[A-Za-z0-9_-]{32}")
_ADMISSION_LOCK = 563892451


class LimitRejected(Exception):
    def __init__(self, code: str, retry_after: int):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


class LimiterUnavailable(RuntimeError):
    pass


def session_id(request: Request) -> tuple[str, bool]:
    existing = request.cookies.get(SESSION_COOKIE, "")
    if _SESSION_PATTERN.fullmatch(existing):
        return existing, False
    return secrets.token_urlsafe(24), True


def client_ip(request: Request, trusted_proxy_cidrs: str) -> str:
    peer = request.client.host if request.client else ""
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return "unknown"

    try:
        trusted = [ipaddress.ip_network(value.strip()) for value in trusted_proxy_cidrs.split(",") if value.strip()]
    except ValueError:
        return str(peer_address)

    if not any(peer_address in network for network in trusted):
        return str(peer_address)

    forwarded = request.headers.get("x-forwarded-for", "")
    if not forwarded:
        return str(peer_address)
    try:
        chain = [ipaddress.ip_address(value.strip()) for value in forwarded.split(",")]
    except ValueError:
        return str(peer_address)
    for address in reversed(chain):
        if not any(address in network for network in trusted):
            return str(address)
    return str(chain[0])


def _subject(kind: str, value: str) -> str:
    return f"{kind}:{hashlib.sha256(value.encode()).hexdigest()}"


class RequestLimiter:
    def __init__(self, engine: Engine, settings: Settings):
        self.engine = engine
        self.settings = settings

    @contextmanager
    def admit(self, session: str, ip: str) -> Iterator[None]:
        lease = uuid.uuid4()
        limits = (
            (_subject("session", session), 60, self.settings.request_session_minute_limit, "SESSION_RATE_LIMIT"),
            (_subject("session", session), 86_400, self.settings.request_session_day_limit, "SESSION_DAILY_LIMIT"),
            (_subject("ip", ip), 60, self.settings.request_ip_minute_limit, "IP_RATE_LIMIT"),
            (_subject("ip", ip), 86_400, self.settings.request_ip_day_limit, "IP_DAILY_LIMIT"),
        )
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                connection.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _ADMISSION_LOCK})
                now = connection.execute(text("SELECT extract(epoch FROM clock_timestamp())::bigint")).scalar_one()
                connection.execute(text("DELETE FROM bayan_runtime.request_leases WHERE expires_at <= clock_timestamp()"))
                active = connection.execute(text("SELECT count(*) FROM bayan_runtime.request_leases")).scalar_one()
                if active >= self.settings.request_global_concurrency:
                    raise LimitRejected("SERVER_BUSY", 2)

                for subject, window, limit, code in limits:
                    start = now - now % window
                    count = connection.execute(
                        text("""INSERT INTO bayan_runtime.request_buckets
                            (subject_key, window_seconds, window_start, request_count)
                            VALUES (:subject, :window, :start, 1)
                            ON CONFLICT (subject_key, window_seconds, window_start)
                            DO UPDATE SET request_count = bayan_runtime.request_buckets.request_count + 1
                            RETURNING request_count"""),
                        {"subject": subject, "window": window, "start": start},
                    ).scalar_one()
                    if count > limit:
                        raise LimitRejected(code, max(1, start + window - now))

                connection.execute(
                    text("""INSERT INTO bayan_runtime.request_leases (lease_id, expires_at)
                        VALUES (:lease, clock_timestamp() + make_interval(secs => :ttl))"""),
                    {"lease": lease, "ttl": math.ceil(self.settings.request_timeout_s) + 10},
                )
                connection.execute(text("""DELETE FROM bayan_runtime.request_buckets
                    WHERE window_start + window_seconds < :cutoff"""), {"cutoff": now - 86_400})
        except LimitRejected:
            raise
        except SQLAlchemyError as exc:
            raise LimiterUnavailable("The shared request limiter is unavailable") from exc

        try:
            yield
        finally:
            try:
                with self.engine.begin() as connection:
                    connection.execute(text("DELETE FROM bayan_runtime.request_leases WHERE lease_id = :lease"), {"lease": lease})
            except SQLAlchemyError:
                # The lease expires if the store becomes unavailable during a request.
                pass


@lru_cache(maxsize=1)
def get_request_limiter() -> RequestLimiter:
    from app.config import get_settings

    return RequestLimiter(get_engine(), get_settings())

"""Atomic limiter checks against an explicitly disposable PostgreSQL target."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import Settings
from app.services.request_limiter import LimitRejected, RequestLimiter


def settings_for(engine, **overrides):
    return Settings(database_url=str(engine.url), readonly_db_password="unused", **overrides)


@pytest.fixture
def engine():
    url = os.environ.get("BAYAN_DISPOSABLE_STAGING_URL")
    if not url:
        pytest.skip("Explicit disposable staging target required")
    db = create_engine(url, pool_size=20, max_overflow=0)
    assert db.url.database.startswith("bayan_staging_")
    migration = Path(__file__).resolve().parents[2] / "db/bayan_runtime_v1.sql"
    with db.begin() as connection:
        connection.exec_driver_sql(migration.read_text())
        connection.execute(text("DELETE FROM bayan_runtime.request_leases"))
        connection.execute(text("DELETE FROM bayan_runtime.request_buckets"))
    yield db
    db.dispose()


def test_limits_share_state_across_instances_and_rejections_do_not_charge(engine):
    settings = settings_for(engine, request_session_minute_limit=2, request_session_day_limit=10,
                        request_ip_minute_limit=10, request_ip_day_limit=10)
    first = RequestLimiter(engine, settings)
    second = RequestLimiter(engine, settings)
    with first.admit("one", "203.0.113.1"):
        pass
    with second.admit("one", "203.0.113.1"):
        pass
    with pytest.raises(LimitRejected) as error:
        with first.admit("one", "203.0.113.1"):
            pass
    assert error.value.code == "SESSION_RATE_LIMIT"
    with second.admit("two", "203.0.113.1"):
        pass


def test_global_admission_is_shared_and_released(engine):
    limiter = RequestLimiter(engine, settings_for(engine, request_global_concurrency=1))
    other_worker = RequestLimiter(engine, settings_for(engine, request_global_concurrency=1))
    with limiter.admit("one", "203.0.113.1"):
        with pytest.raises(LimitRejected) as error:
            with other_worker.admit("two", "203.0.113.2"):
                pass
        assert error.value.code == "SERVER_BUSY"
    with other_worker.admit("two", "203.0.113.2"):
        pass


def test_concurrent_ip_limit_is_atomic(engine):
    settings = settings_for(engine, request_session_minute_limit=50, request_session_day_limit=50,
                        request_ip_minute_limit=5, request_ip_day_limit=50,
                        request_global_concurrency=20)
    limiter = RequestLimiter(engine, settings)

    def attempt(index):
        try:
            with limiter.admit(f"session-{index}", "203.0.113.1"):
                return True
        except LimitRejected:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(attempt, range(12)))
    assert sum(outcomes) == 5

"""The execution guards, exercised against real Postgres.

SQLite can stand in for result shaping, but not for the guards that matter:
role privileges and the statement timeout are Postgres behaviour.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.core.database import get_readonly_engine
from app.services.executor import execute_readonly


@pytest.fixture(scope="module")
def engine_ro():
    engine = get_readonly_engine()
    yield engine
    engine.dispose()


def test_readonly_role_can_read(engine_ro) -> None:
    result = execute_readonly(engine_ro, "SELECT count(*) AS n FROM communities")
    assert result.rows[0][0] > 0


def test_readonly_role_cannot_insert(engine_ro) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_readonly(engine_ro, "INSERT INTO communities (name_en) VALUES ('x')")


def test_readonly_role_cannot_update(engine_ro) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_readonly(engine_ro, "UPDATE communities SET name_en = 'x'")


def test_readonly_role_cannot_delete(engine_ro) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_readonly(engine_ro, "DELETE FROM communities")


def test_readonly_role_cannot_drop(engine_ro) -> None:
    with pytest.raises(ProgrammingError):
        execute_readonly(engine_ro, "DROP TABLE communities")


def test_statement_timeout_aborts_a_slow_query(engine_ro) -> None:
    started = time.monotonic()
    with pytest.raises(DBAPIError, match="statement timeout"):
        execute_readonly(engine_ro, "SELECT pg_sleep(10)", timeout_s=1)
    assert time.monotonic() - started < 5


def test_limit_is_injected_against_a_real_large_table(engine_ro) -> None:
    result = execute_readonly(engine_ro, "SELECT id FROM transactions")
    assert result.row_count == 500
    assert result.truncated is True

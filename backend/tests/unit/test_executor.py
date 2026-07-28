from __future__ import annotations

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services.executor import execute_readonly, inject_limit


def _limit_of(sql: str) -> int | None:
    import sqlglot

    limit = sqlglot.parse_one(sql, dialect="postgres").args.get("limit")
    return None if limit is None else int(limit.expression.this)


def test_inject_limit_adds_limit_when_absent() -> None:
    sql, _ = inject_limit("SELECT id FROM transactions", 500)
    assert _limit_of(sql) is not None


def test_inject_limit_fetches_one_extra_row_to_detect_truncation() -> None:
    sql, _ = inject_limit("SELECT id FROM transactions", 500)
    assert _limit_of(sql) == 501


def test_inject_limit_reports_capping_when_limit_absent() -> None:
    _, capped = inject_limit("SELECT id FROM transactions", 500)
    assert capped is True


def test_inject_limit_keeps_a_smaller_existing_limit() -> None:
    sql, capped = inject_limit("SELECT id FROM transactions LIMIT 10", 500)
    assert _limit_of(sql) == 10
    assert capped is False


def test_inject_limit_clamps_an_existing_limit_above_the_cap() -> None:
    sql, capped = inject_limit("SELECT id FROM transactions LIMIT 100000", 500)
    assert _limit_of(sql) == 501
    assert capped is True


def test_inject_limit_handles_cte_queries() -> None:
    sql, _ = inject_limit("WITH x AS (SELECT id FROM transactions) SELECT id FROM x", 500)
    assert _limit_of(sql) == 501


def test_inject_limit_handles_set_operations() -> None:
    raw = "SELECT id FROM transactions UNION SELECT id FROM communities"
    sql, _ = inject_limit(raw, 500)
    assert _limit_of(sql) == 501


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE communities",
        "INSERT INTO communities (name_en) VALUES ('x')",
        "UPDATE communities SET name_en = 'x'",
        "DELETE FROM communities",
    ],
)
def test_inject_limit_passes_unlimitable_statements_through_untouched(statement: str) -> None:
    """Validation rejects these upstream; if one ever slips past, the read-only
    role must be what stops it — not an AttributeError in here."""
    sql, capped = inject_limit(statement, 500)
    assert sql == statement
    assert capped is False


def test_returns_column_names(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id, name_en FROM communities")
    assert result.columns == ["id", "name_en"]


def test_returns_rows(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT name_en FROM communities ORDER BY id")
    assert result.rows == [["Yas Island"], ["Al Reem Island"]]


def test_row_count_matches_returned_rows(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM communities")
    assert result.row_count == len(result.rows) == 2


def test_small_result_is_not_truncated(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM communities")
    assert result.truncated is False


def test_large_result_is_truncated_to_the_cap(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM transactions")
    assert result.truncated is True
    assert result.row_count == 500


def test_result_exactly_at_the_cap_is_not_truncated(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM transactions LIMIT 500")
    assert result.row_count == 500
    assert result.truncated is False


def test_user_supplied_limit_is_never_reported_as_truncated(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM transactions LIMIT 10")
    assert result.row_count == 10
    assert result.truncated is False


def test_custom_limit_is_honoured(sqlite_engine) -> None:
    result = execute_readonly(sqlite_engine, "SELECT id FROM transactions", limit=25)
    assert result.row_count == 25
    assert result.truncated is True


def test_sql_errors_propagate_to_the_caller(sqlite_engine) -> None:
    with pytest.raises(SQLAlchemyError):
        execute_readonly(sqlite_engine, "SELECT nonexistent_column FROM communities")

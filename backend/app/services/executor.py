from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlalchemy import text
from sqlalchemy.engine import Engine

DEFAULT_LIMIT = 500
DEFAULT_TIMEOUT_S = 5


@dataclass
class ExecResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


def inject_limit(sql: str, cap: int) -> tuple[str, bool]:
    """Bound a query to `cap` rows.

    Returns the rewritten SQL and whether our cap was the binding one. When it
    is, the query asks for cap+1 rows so the caller can tell "exactly cap rows
    exist" apart from "more exist and we cut them off".
    """
    expression = sqlglot.parse_one(sql, dialect="postgres")

    # Anything that isn't a query has no LIMIT to give. validate_read_only()
    # rejects these upstream; passing one through unchanged leaves the
    # read-only role as the guard that stops it, which is the point.
    if not isinstance(expression, exp.Query):
        return sql, False

    existing = expression.args.get("limit")
    if existing is not None:
        try:
            declared = int(existing.expression.this)
        except (AttributeError, TypeError, ValueError):
            declared = None
        if declared is not None and declared <= cap:
            return expression.sql(dialect="postgres"), False

    return expression.limit(cap + 1).sql(dialect="postgres"), True


def execute_readonly(
    engine_ro: Engine,
    sql: str,
    limit: int = DEFAULT_LIMIT,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> ExecResult:
    bounded_sql, capped = inject_limit(sql, limit)

    with engine_ro.connect() as connection, connection.begin():
        if connection.dialect.name == "postgresql":
            # SET LOCAL takes no bind parameters; the int cast is what keeps it safe
            connection.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
        result = connection.execute(text(bounded_sql))
        columns = list(result.keys())
        rows = [list(row) for row in result]

    truncated = capped and len(rows) > limit
    if truncated:
        rows = rows[:limit]

    return ExecResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )

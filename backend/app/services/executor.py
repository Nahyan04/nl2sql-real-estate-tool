from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import json
import time
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
    executed_sql: str = ""
    truncation_reason: str | None = None


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
        if isinstance(existing, exp.Limit) and not existing.args.get("limit_options") and declared is not None and 0 <= declared <= cap:
            return expression.sql(dialect="postgres"), False

    return expression.limit(cap + 1).sql(dialect="postgres"), True


def execute_readonly(
    engine_ro: Engine,
    sql: str,
    limit: int = DEFAULT_LIMIT,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_result_bytes: int = 1_048_576,
    max_cell_bytes: int = 65_536,
) -> ExecResult:
    from app.services.sql_validator import validate_product_query
    if not validate_product_query(sql).is_safe:
        raise ValueError("Query is outside the fresh-data surface")
    if min(limit, timeout_s, max_result_bytes, max_cell_bytes) <= 0:
        raise ValueError("Execution limits must be positive")
    bounded_sql, _ = inject_limit(sql, limit)
    rows = []
    reason = None

    with engine_ro.connect() as connection, connection.begin():
        postgres = connection.dialect.name == "postgresql"
        if postgres:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL search_path = bayan, pg_catalog"))
            connection.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
            connection.execute(text(f"SET LOCAL idle_in_transaction_session_timeout = {int((timeout_s + 1) * 1000)}"))
        deadline = time.monotonic() + timeout_s
        statement = text(bounded_sql)
        if postgres:
            # Named cursor prevents the driver from buffering the entire result.
            statement = statement.execution_options(stream_results=True, yield_per=32)
        result = connection.execute(statement)
        try:
            columns = list(result.keys())
            used_bytes = len(json.dumps(columns, ensure_ascii=True).encode()) + 2
            if used_bytes > max_result_bytes or any(len(c.encode()) > max_cell_bytes for c in columns):
                raise ResultSizeError("Result column labels exceed the response budget")
            while reason is None:
                remaining_ms = int((deadline - time.monotonic()) * 1000)
                if remaining_ms <= 0:
                    raise QueryDeadlineError("Query exceeded its execution deadline")
                batch = result.fetchmany(32)
                if not batch:
                    break
                for record in batch:
                    if len(rows) == limit:
                        reason = "row_limit"
                        break
                    row = list(record)
                    cells = [json.dumps(value, default=_json_value, ensure_ascii=True) for value in row]
                    if any(len(value.encode()) > max_cell_bytes for value in cells):
                        reason = "cell_size"
                        break
                    row_bytes = len(("[" + ", ".join(cells) + "]").encode()) + 2
                    if used_bytes + row_bytes > max_result_bytes:
                        reason = "result_bytes"
                        break
                    rows.append(row)
                    used_bytes += row_bytes
        finally:
            result.close()

    if reason in {"cell_size", "result_bytes"} and not rows:
        raise ResultSizeError("The first row exceeds the response budget; narrow the query")
    return ExecResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=reason is not None,
        executed_sql=bounded_sql,
        truncation_reason=reason,
    )


class ResultSizeError(ValueError):
    pass


class QueryDeadlineError(TimeoutError):
    pass


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)

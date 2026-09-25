from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# GRANT and other syntax the default dialect can't fully parse fall back to a
# generic Command node, so it's blocked rather than allowed through by default.
# Into covers `SELECT ... INTO new_table` — it parses as a plain Select node
# but actually creates a table, so it must be rejected explicitly.
_UNSAFE_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Into,
)


@dataclass
class SQLValidationResult:
    is_safe: bool
    reason: str = ""


def validate_read_only(sql: str) -> SQLValidationResult:
    if len(sql) > 16_000:
        return SQLValidationResult(False, 'SQL exceeds the size limit')
    try:
        # parse() rather than parse_one() so a stacked "SELECT 1; DROP TABLE x;"
        # can't slip through by hiding a second statement after the first
        statements = [statement for statement in sqlglot.parse(sql, read="postgres") if statement is not None]
    except ParseError as exc:
        return SQLValidationResult(is_safe=False, reason=f"could not parse SQL: {exc}")

    if len(statements) != 1:
        return SQLValidationResult(is_safe=False, reason="only a single statement is allowed")

    statement = statements[0]
    # exp.Query covers Select plus set operations (UNION/INTERSECT/EXCEPT),
    # which are legitimate read-only shapes but parse to their own root types
    if not isinstance(statement, exp.Query):
        return SQLValidationResult(is_safe=False, reason="only SELECT or WITH queries are allowed")

    unsafe_node = statement.find(*_UNSAFE_NODE_TYPES)
    if unsafe_node is not None:
        return SQLValidationResult(
            is_safe=False,
            reason=f"query contains a mutating statement: {type(unsafe_node).__name__}",
        )

    return SQLValidationResult(is_safe=True)


# Deliberately small analytical function surface; expand with tests as needed.
_PRODUCT_FUNCTIONS = frozenset({
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'ROUND', 'ABS', 'NULLIF', 'COALESCE',
    'CAST', 'EXTRACT', 'TIMESTAMP_TRUNC', 'DATE_TRUNC', 'DATE', 'LOWER', 'UPPER',
    'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'LAG', 'LEAD', 'IF', 'CASE', 'AND', 'OR',
})


def validate_product_query(sql: str) -> SQLValidationResult:
    """Resolve CTE scopes before checking the physical relation allowlist."""
    from sqlglot.optimizer.scope import traverse_scope
    from app.services.product_schema import PRODUCT_RELATIONS

    basic = validate_read_only(sql)
    if not basic.is_safe:
        return basic
    try:
        statement = sqlglot.parse_one(sql, read='postgres')
        if sum(1 for _ in statement.walk()) > 500:
            return SQLValidationResult(False, 'SQL exceeds the complexity limit')
        if statement.find(exp.Lock) or any(cte.args.get('recursive') for cte in statement.find_all(exp.With)):
            return SQLValidationResult(False, 'locking and recursive queries are unavailable')
        for cast in statement.find_all(exp.Cast):
            target = cast.args.get('to')
            if target is None or getattr(target.this, 'name', None) not in {'TEXT', 'VARCHAR', 'CHAR', 'INT', 'BIGINT', 'SMALLINT', 'DECIMAL', 'DOUBLE', 'FLOAT', 'DATE', 'TIMESTAMP', 'TIMESTAMPTZ', 'BOOLEAN', 'INTERVAL'}:
                return SQLValidationResult(False, 'cast type is not allowed')
        for function in statement.find_all(exp.Func):
            if isinstance(function, exp.Anonymous) or function.sql_name() not in _PRODUCT_FUNCTIONS:
                return SQLValidationResult(False, 'function is not allowed on the fresh-data surface')
            if isinstance(function.parent, exp.Dot):
                return SQLValidationResult(False, 'qualified functions are unavailable')
        for scope in traverse_scope(statement):
            for source in scope.sources.values():
                if isinstance(source, exp.Table):
                    if source.catalog or source.db not in ('', 'bayan') or source.name not in PRODUCT_RELATIONS:
                        return SQLValidationResult(False, 'relation is outside the fresh-data surface')
        # Reject table-valued expressions even when represented as non-Table scopes.
        if statement.find(exp.Unnest, exp.Lateral):
            return SQLValidationResult(False, 'table-valued expressions are unavailable')
    except (ParseError, ValueError):
        return SQLValidationResult(False, 'could not validate fresh-data SQL')
    return SQLValidationResult(True)


def product_tables_used(sql: str) -> list[str]:
    from sqlglot.optimizer.scope import traverse_scope
    statement = sqlglot.parse_one(sql, read='postgres')
    return sorted({source.name for scope in traverse_scope(statement) for source in scope.sources.values() if isinstance(source, exp.Table)})

"""Small display metadata extracted from the SQL that actually ran."""

from __future__ import annotations

import sqlglot
from sqlglot import exp


DATE_COLUMNS = frozenset({
    "transaction_date", "period_end", "observed_from", "observed_through", "complete_through",
})
DATE_PREDICATES = (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between, exp.In)


def date_conditions(sql: str) -> list[str]:
    try:
        query = sqlglot.parse_one(sql, dialect="postgres")
    except sqlglot.ParseError:
        return []
    found = []
    for predicate in query.find_all(*DATE_PREDICATES):
        if not any(column.name.lower() in DATE_COLUMNS for column in predicate.find_all(exp.Column)):
            continue
        if not any(isinstance(value, (exp.Literal, exp.Date, exp.Cast)) for value in predicate.walk()):
            continue
        condition = predicate.sql(dialect="postgres")
        if condition not in found:
            found.append(condition)
    return found[:8]

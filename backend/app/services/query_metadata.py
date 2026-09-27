"""Small display metadata extracted from the SQL that actually ran."""

from __future__ import annotations

import sqlglot
from sqlglot import exp


DATE_COLUMNS = frozenset({
    "transaction_date", "period_end", "observed_from", "observed_through", "complete_through",
})
DATE_PREDICATES = (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between)


def date_conditions(sql: str) -> list[str]:
    try:
        query = sqlglot.parse_one(sql, dialect="postgres")
    except sqlglot.ParseError:
        return []
    found = []
    for where in query.find_all(exp.Where):
        for predicate in where.find_all(*DATE_PREDICATES):
            if any(column.name.lower() in DATE_COLUMNS for column in predicate.find_all(exp.Column)):
                condition = predicate.sql(dialect="postgres")
                if condition not in found:
                    found.append(condition)
    return found[:8]

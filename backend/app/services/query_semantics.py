"""Check explicit question filters that a plausible SQL query can omit."""

import re

import sqlglot
from sqlglot import exp


_READY_APARTMENT_RATE = re.compile(r"\bready residential apartments? sales\b", re.IGNORECASE)


def missing_question_filters(question: str, sql: str) -> list[str]:
    if not _READY_APARTMENT_RATE.search(question):
        return []
    query = sqlglot.parse_one(sql, dialect="postgres")
    where = query.args.get("where")
    terms: list[exp.Expression] = []

    def collect(node: exp.Expression) -> None:
        if isinstance(node, exp.And):
            collect(node.left)
            collect(node.right)
        else:
            terms.append(node)

    if where:
        collect(where.this)
    equalities: set[tuple[str, str]] = set()
    comparisons: set[tuple[str, str]] = set()
    for term in terms:
        if isinstance(term, exp.EQ):
            for column, value in ((term.left, term.right), (term.right, term.left)):
                if isinstance(column, exp.Column) and isinstance(value, exp.Literal) and value.is_string:
                    equalities.add((column.name.lower(), value.this.lower()))
        elif isinstance(term, exp.In) and isinstance(term.this, exp.Column):
            for value in term.expressions:
                if isinstance(value, exp.Literal) and value.is_string:
                    equalities.add((term.this.name.lower(), value.this.lower()))
        elif isinstance(term, exp.GT) and isinstance(term.left, exp.Column) and isinstance(term.right, exp.Literal):
            if term.right.is_number:
                comparisons.add((term.left.name.lower(), term.right.this))
    required = {("sale_type", "ready"), ("asset_class", "residential"),
                ("property_type", "apartment")}
    missing = [f"{column} = '{value}'" for column, value in sorted(required - equalities)]
    if re.search(r"sold area above 1 sqm", question, re.IGNORECASE) and ("sold_area_sqm", "1") not in comparisons:
        missing.append("sold_area_sqm > 1")
    return missing

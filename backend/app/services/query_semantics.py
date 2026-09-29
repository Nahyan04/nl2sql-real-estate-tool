"""Check explicit question filters that a plausible SQL query can omit."""

import re

import sqlglot
from sqlglot import exp


_READY_APARTMENT_RATE = re.compile(r"\bready residential apartments? sales\b", re.IGNORECASE)
_OFF_PLAN_COUNT = re.compile(r"\boff-plan sales observations\b", re.IGNORECASE)
_FRACTIONAL_SHARE_COUNT = re.compile(
    r"\bsold ownership share greater than zero and less than one\b", re.IGNORECASE,
)


def _literal_value(expression: exp.Expression) -> str | None:
    if isinstance(expression, exp.Cast):
        expression = expression.this
    return expression.this if isinstance(expression, exp.Literal) else None


def missing_question_filters(question: str, sql: str) -> list[str]:
    ready = bool(_READY_APARTMENT_RATE.search(question))
    off_plan = bool(_OFF_PLAN_COUNT.search(question))
    fractional = bool(_FRACTIONAL_SHARE_COUNT.search(question))
    if not (ready or off_plan or fractional):
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
    comparisons: set[tuple[str, str, str]] = set()
    for term in terms:
        if isinstance(term, exp.EQ):
            for column, value in ((term.left, term.right), (term.right, term.left)):
                if isinstance(column, exp.Column) and isinstance(value, exp.Literal) and value.is_string:
                    equalities.add((column.name.lower(), value.this.lower()))
        elif isinstance(term, exp.In) and isinstance(term.this, exp.Column):
            for value in term.expressions:
                if isinstance(value, exp.Literal) and value.is_string:
                    equalities.add((term.this.name.lower(), value.this.lower()))
        elif isinstance(term, (exp.GT, exp.GTE, exp.LT)) and isinstance(term.left, exp.Column):
            value = _literal_value(term.right)
            if value is not None:
                comparisons.add((term.left.name.lower(), type(term).__name__, value))
    required: set[tuple[str, str]] = set()
    if ready:
        required = {("sale_type", "ready"), ("asset_class", "residential"),
                    ("property_type", "apartment")}
    elif off_plan:
        required = {("sale_type", "off-plan")}
    missing = [f"{column} = '{value}'" for column, value in sorted(required - equalities)]
    if ready and re.search(r"sold area above 1 sqm", question, re.IGNORECASE) and ("sold_area_sqm", "GT", "1") not in comparisons:
        missing.append("sold_area_sqm > 1")
    if fractional:
        if ("sold_share", "GT", "0") not in comparisons:
            missing.append("sold_share > 0")
        if ("sold_share", "LT", "1") not in comparisons:
            missing.append("sold_share < 1")
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    if len(years) == 1:
        year = int(years[0])
        start = f"{year}-01-01"
        end = f"{year + 1}-01-01"
        if ("transaction_date", "GTE", start) not in comparisons:
            missing.append(f"transaction_date >= DATE '{start}'")
        if ("transaction_date", "LT", end) not in comparisons:
            missing.append(f"transaction_date < DATE '{end}'")
    return missing

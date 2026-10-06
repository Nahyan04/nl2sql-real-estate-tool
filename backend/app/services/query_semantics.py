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


def missing_resolved_filters(sql: str, context) -> list[str]:
    """Require confirmed source scopes in conjunctive predicates before execution."""
    from sqlglot.optimizer.scope import traverse_scope

    query = sqlglot.parse_one(sql, dialect='postgres')
    equalities = set()
    comparisons = set()
    for scope in traverse_scope(query):
        where = scope.expression.args.get('where')
        if not where:
            continue
        terms = []

        def collect(node):
            if isinstance(node, exp.Paren):
                collect(node.this)
            elif isinstance(node, exp.And):
                collect(node.left)
                collect(node.right)
            else:
                terms.append(node)

        collect(where.this)
        for term in terms:
            if isinstance(term, exp.In) and isinstance(term.this, exp.Column):
                values = [_literal_value(value) for value in term.expressions]
                if any(value is None for value in values):
                    continue
                for alias, source in scope.sources.items():
                    if not isinstance(source, exp.Table) or (term.this.table and term.this.table != alias):
                        continue
                    expected = {p.value for p in context.places
                                if p.relation == source.name and p.column == term.this.name}
                    if set(values) == expected:
                        equalities.update((source.name, term.this.name, value) for value in values)
                continue
            if not isinstance(term, (exp.EQ, exp.GTE, exp.LT)):
                continue
            column, literal = term.left, term.right
            if not isinstance(column, exp.Column):
                continue
            value = _literal_value(literal)
            if value is None:
                continue
            relations = [source.name for alias, source in scope.sources.items()
                         if isinstance(source, exp.Table) and (not column.table or alias == column.table)]
            for relation in relations:
                if isinstance(term, exp.EQ):
                    equalities.add((relation, column.name, value))
                comparisons.add((relation, column.name, type(term).__name__, value))
    missing = [f"{p.relation}.{p.column} = '{p.value}'" for p in context.places
               if (p.relation, p.column, p.value) not in equalities]
    if context.period:
        relation = context.places[0].relation if context.places else next(
            (table.name for table in query.find_all(exp.Table) if table.name in {'transactions', 'rental_observations', 'price_indices'}), 'transactions')
        column = 'transaction_date' if relation == 'transactions' else 'period_end'
        start, end = map(str, context.period)
        for operator, value, symbol in [('GTE', start, '>='), ('LT', end, '<')]:
            if (relation, column, operator, value) not in comparisons:
                missing.append(f"{relation}.{column} {symbol} DATE '{value}'")
    return missing

from __future__ import annotations

import datetime as dt

MAX_PROMPT_CHARS = 6000

_SYSTEM_PROMPT = '''You generate PostgreSQL analytical SQL over verified ADREC source observations.
Only SELECT or WITH queries, wrapped in <sql>...</sql>. Never write INSERT, UPDATE, DELETE or other mutations.
Only use the supplied bayan relations. All views select one active snapshot automatically.
English or Arabic questions use the same ASCII schema identifiers and ASCII output aliases.
Source place names are English; no verified Arabic name mapping exists. If a place cannot be matched confidently, return <unsupported>Clarify the source place name.</unsupported>.
District, community and project_name are separate fields. Never join a district to a community or infer municipality from a name. Sales municipality is unknown. Al Bateen is ambiguous: never assign it to one municipality without row evidence.
Keep source property types/layouts exactly: apartment, villa, and 5+ beds versus 6+ beds are distinct. ready, off-plan and court-mandated are separate sale types. sold_share is not a transaction count. COUNT(*) counts exported sales observations, not a guaranteed market census.
Use calculated_rate_aed_sqm for screened derived rates, not raw rates on invalid areas. Preserve exclusions/nulls in interpretations.
An index requires a single source_file, municipality, source_area_group, property_group and application_type series. Never average overlapping all-zone/subzone or all-rent/new-rent indices. Official base methodology is unknown.
Rental observations are separate files with different grains. active_value_aed is not annual rent. Do not annualize, derive yield, average averages, or sum repeated stock snapshots. Source rolling values may only be reported at their original grain with their source label, not reinterpreted as weighted annual rent.
There are no developer ownership, broker or lender records. Finance aggregates are not exposed pending unit definitions. For unsupported questions return <unsupported>Brief reason</unsupported> without SQL.
Today's date is {today}. Coverage differs by source. Use dataset_coverage for dates; a period-end label does not prove completeness. Ask for an explicit period using <unsupported> if a relative window is ambiguous; do not substitute a different period silently.
Example: sales observations by district in 2025:
<sql>SELECT district, SUM(price_aed) AS sales_value_aed FROM transactions WHERE transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01' GROUP BY district ORDER BY sales_value_aed DESC LIMIT 10</sql>
'''


def build_system_prompt(today: dt.date | None = None) -> str:
    return _SYSTEM_PROMPT.format(today=(today or dt.date.today()).isoformat())


def build_user_prompt(question: str, schema_context: str, feedback: str = "", *, system_prompt: str | None = None) -> str:
    tail = f"\n\nQuestion: {question}"
    if feedback:
        tail += f"\n\n{feedback}"

    # Trim the schema rather than the tail: the question and the retry feedback
    # are the two things the model cannot do without.
    available = MAX_PROMPT_CHARS - len(system_prompt if system_prompt is not None else build_system_prompt()) - len(tail) - len("Schema:\n")
    if available < 0:
        available = 0

    return f"Schema:\n{schema_context[:available]}{tail}"

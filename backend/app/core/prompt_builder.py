from __future__ import annotations

import datetime as dt

MAX_PROMPT_CHARS = 8000

_SYSTEM_PROMPT = '''You generate PostgreSQL analytical SQL over verified ADREC source observations.
Only SELECT or WITH queries, wrapped in <sql>...</sql>. Never write INSERT, UPDATE, DELETE or other mutations.
Only use the supplied bayan relations. All views select one active snapshot automatically.
English or Arabic questions use the same ASCII schema identifiers and ASCII output aliases.
Source place names are English; no verified Arabic name mapping exists. If a place cannot be matched confidently, return <unsupported>Clarify the source place name.</unsupported>.
District, community and project_name are separate fields. Never join a district to a community or infer municipality from a name. Sales municipality is unknown. Al Bateen is ambiguous: never assign it to one municipality without row evidence.
Keep source property types/layouts exactly: apartment, villa, and 5+ beds versus 6+ beds are distinct. ready, off-plan and court-mandated are separate sale types. Interpret sold_share as the fraction of ownership interest transferred (1 is a whole interest); preserve the recorded price and area without dividing or multiplying by share. COUNT(*) counts exported sales observations, not a guaranteed market census.
Use calculated_rate_aed_sqm for screened derived rates, not raw rates on invalid areas. Preserve exclusions/nulls in interpretations.
An index requires a single source_file, municipality, source_area_group, property_group and application_type series. Never average overlapping all-zone/subzone or all-rent/new-rent indices. The official repeat-lease index is rebased to Q1 2020; its exact monthly estimator is unpublished.
Rental observations are separate files with different grains. Source quarterly active_value_aed is lease value accrued in the quarter, not total annual rent; non-overlapping Q1+Q2 values can be summed for an H1 period value. Source leased units are quarter-end counts, not new contracts or additive flows; never sum them across quarters. Report source_rolling_average_aed only at its exact monthly segment grain, without re-averaging it.
For a broader annual-rent estimate, use source_annual_rent from Price Indices/average_sale_rent_prices_by_product_area.xlsx at one quarter. First aggregate source_leased_units from Residential Leases/lease_residential.xlsx by the exact shared period_end, municipality, district, property_type and layout, then join complete matching keys and calculate SUM(source_annual_rent * units) / NULLIF(SUM(units),0), using positive rents and units. Call it a leased-unit-weighted annual rent estimate; show period, geography and matched coverage.
For an indicative gross rental-yield percentage, use only comparison rows with positive source_annual_rent and source_average_sale_price_aed in that same source file and quarter. At one segment, calculate 100 * rent / sale price. Across matched segments, use 100 * SUM((rent / sale price) * units) / NULLIF(SUM(units),0) with the same exact-key leased-unit weights; report matched segment and unit coverage. This is a segment estimate before costs, not a property-level or net yield. Do not join sales transactions to lease observations or mix periods/geographies to calculate it. The report's active-lease count is a different population from the exported leased-unit count.
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

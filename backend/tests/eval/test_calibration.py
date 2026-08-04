from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_engine
from scripts.genlib import targets as T

CALIBRATION = json.loads((PROJECT_ROOT / "app" / "resources" / "calibration.json").read_text())
ANCHORS = CALIBRATION["anchors"]

WINDOWS = {
    "last_12mo": T.LAST_12MO,
    "fy_2025": T.FY_2025,
    "fy_2024": T.FY_2024,
    "h1_2025": T.H1_2025,
    "ytd_2026": T.YTD_2026,
}


def window_bounds(window: str) -> tuple:
    start_idx, end_idx = WINDOWS[window]
    return T.idx_to_month(start_idx), T.idx_to_month(end_idx + 1)


def run_scalar(sql: str, params: dict) -> float:
    engine = get_engine()
    with engine.connect() as connection:
        result = connection.execute(text(sql), params).scalar()
    return float(result or 0)


# (table[+join], date_column, value_expr, extra_where, window) for the anchors testable as a
# single windowed aggregate. rented_units_current, the price-index anchors, and the sales+mortgage
# composite anchors (see COMPOSITE_SPECS below -- they only reconcile against real data as sales
# plus mortgages combined, per their calibration.json notes) each need bespoke handling and get
# their own test below.
ANCHOR_SPECS = {
    "sales_value_ytd2026": ("transactions", "transaction_date", "SUM(price_aed)", None, "ytd_2026"),
    "mortgage_value_ytd2026": ("mortgages", "mortgage_date", "SUM(mortgage_value_aed)", None, "ytd_2026"),
    "residential_sales_value_fy2025": (
        "transactions t JOIN property_types pt ON t.property_type_id = pt.id",
        "t.transaction_date",
        "SUM(t.price_aed)",
        "pt.name IN ('Apartment', 'Villa')",
        "fy_2025",
    ),
    "txn_value_h1_2025": ("transactions", "transaction_date", "SUM(price_aed)", None, "h1_2025"),
}


def run_anchor_spec(spec: tuple) -> float:
    table, date_col, value_expr, extra_where, window = spec
    start, end = window_bounds(window)
    clauses = [f"{date_col} >= :start", f"{date_col} < :end"]
    if extra_where:
        clauses.append(extra_where)
    sql = f"SELECT {value_expr} FROM {table} WHERE {' AND '.join(clauses)}"
    return run_scalar(sql, {"start": start, "end": end})


@pytest.mark.parametrize("key", sorted(ANCHOR_SPECS))
def test_anchor_within_tolerance(key):
    anchor = ANCHORS[key]
    actual = run_anchor_spec(ANCHOR_SPECS[key])
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    off_pct = 100 * (actual - expected) / expected
    assert abs(actual - expected) <= tolerance * expected, f"{key}: actual={actual}, expected={expected}, off by {off_pct:.2f}%"


# (anchor_key, window, sales_agg_expr, mortgage_agg_expr) for anchors that only reconcile against
# real data as a sales+mortgages composite (see each anchor's calibration.json note). Three are
# value sums (price_aed / mortgage_value_aed); txn_volume_last12mo is a row count instead.
COMPOSITE_SPECS = {
    "txn_value_ytd2026": ("ytd_2026", "SUM(price_aed)", "SUM(mortgage_value_aed)"),
    "txn_value_fy2025": ("fy_2025", "SUM(price_aed)", "SUM(mortgage_value_aed)"),
    "txn_value_last12mo": ("last_12mo", "SUM(price_aed)", "SUM(mortgage_value_aed)"),
    "txn_volume_last12mo": ("last_12mo", "COUNT(*)", "COUNT(*)"),
}


def run_composite(window: str, sales_agg_expr: str, mortgage_agg_expr: str) -> float:
    start, end = window_bounds(window)
    sales = run_scalar(
        f"SELECT COALESCE({sales_agg_expr}, 0) FROM transactions WHERE transaction_date >= :start AND transaction_date < :end",
        {"start": start, "end": end},
    )
    mortgages = run_scalar(
        f"SELECT COALESCE({mortgage_agg_expr}, 0) FROM mortgages WHERE mortgage_date >= :start AND mortgage_date < :end",
        {"start": start, "end": end},
    )
    return sales + mortgages


@pytest.mark.parametrize("key", sorted(COMPOSITE_SPECS))
def test_composite_anchor_within_tolerance(key):
    anchor = ANCHORS[key]
    actual = run_composite(*COMPOSITE_SPECS[key])
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    off_pct = 100 * (actual - expected) / expected
    assert abs(actual - expected) <= tolerance * expected, f"{key}: actual={actual}, expected={expected}, off by {off_pct:.2f}%"


def test_rented_units_current():
    anchor = ANCHORS["rented_units_current"]
    # run_scalar casts its result to float, which blows up on the date MAX(period_end)
    # returns -- fetch that one directly instead of through run_scalar.
    engine = get_engine()
    with engine.connect() as connection:
        latest_period = connection.execute(text("SELECT MAX(period_end) FROM rental_market_stats")).scalar()
    actual = run_scalar(
        "SELECT SUM(leased_units) FROM rental_market_stats WHERE period_end = :period",
        {"period": latest_period},
    )
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    off_pct = 100 * (actual - expected) / expected
    assert abs(actual - expected) <= tolerance * expected, (
        f"rented_units_current: actual={actual}, expected={expected}, off by {off_pct:.2f}%"
    )


PRICE_INDEX_ANCHORS = ["apartment_sale_index", "villa_sale_index", "apartment_rent_index", "villa_rent_index"]


@pytest.mark.parametrize("key", PRICE_INDEX_ANCHORS)
def test_price_index_current_value(key):
    anchor = ANCHORS[key]
    sql = """
        SELECT pi.index_value FROM price_indices pi
        JOIN property_types pt ON pi.property_type_id = pt.id
        WHERE pi.index_type = :index_type AND pt.name = :property_type
        ORDER BY pi.month DESC LIMIT 1
    """
    actual = run_scalar(sql, {"index_type": anchor["index_type"], "property_type": anchor["property_type"]})
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    assert abs(actual - expected) <= tolerance * expected, f"{key}: actual={actual}, expected={expected}"

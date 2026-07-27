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
# single windowed aggregate. rented_units_current, the price-index anchors, foreign_growth_share_fy2025
# and the txn_value_ytd2026 composite each need bespoke handling and get their own test below.
ANCHOR_SPECS = {
    "txn_value_last12mo": ("transactions", "transaction_date", "SUM(price_aed)", None, "last_12mo"),
    "txn_volume_last12mo": ("transactions", "transaction_date", "COUNT(*)", None, "last_12mo"),
    "sales_value_ytd2026": ("transactions", "transaction_date", "SUM(price_aed)", None, "ytd_2026"),
    "mortgage_value_ytd2026": ("mortgages", "mortgage_date", "SUM(mortgage_value_aed)", None, "ytd_2026"),
    "fdi_value_ytd2026": ("transactions", "transaction_date", "SUM(price_aed)", "buyer_origin = 'Foreign'", "ytd_2026"),
    "txn_value_fy2025": ("transactions", "transaction_date", "SUM(price_aed)", None, "fy_2025"),
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


def test_txn_value_ytd2026_composite():
    anchor = ANCHORS["txn_value_ytd2026"]
    start, end = window_bounds("ytd_2026")
    sales = run_scalar(
        "SELECT COALESCE(SUM(price_aed), 0) FROM transactions WHERE transaction_date >= :start AND transaction_date < :end",
        {"start": start, "end": end},
    )
    mortgages = run_scalar(
        "SELECT COALESCE(SUM(mortgage_value_aed), 0) FROM mortgages WHERE mortgage_date >= :start AND mortgage_date < :end",
        {"start": start, "end": end},
    )
    actual = sales + mortgages
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    off_pct = 100 * (actual - expected) / expected
    assert abs(actual - expected) <= tolerance * expected, f"txn_value_ytd2026: actual={actual}, expected={expected}, off by {off_pct:.2f}%"


def test_rented_units_current():
    anchor = ANCHORS["rented_units_current"]
    turnover_rate = ANCHORS["rental_turnover_rate"]["value"]
    start, end = window_bounds("last_12mo")
    contract_count = run_scalar(
        "SELECT COUNT(*) FROM rental_contracts WHERE contract_date >= :start AND contract_date < :end",
        {"start": start, "end": end},
    )
    implied_stock = contract_count / turnover_rate
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    off_pct = 100 * (implied_stock - expected) / expected
    assert abs(implied_stock - expected) <= tolerance * expected, (
        f"rented_units_current: implied_stock={implied_stock}, expected={expected}, off by {off_pct:.2f}%"
    )


def test_foreign_growth_share_fy2025():
    anchor = ANCHORS["foreign_growth_share_fy2025"]
    fy2024_start, _ = window_bounds("fy_2024")
    _, fy2025_end = window_bounds("fy_2025")
    sql = """
        SELECT
            SUM(CASE WHEN transaction_date >= :fy2025_start AND buyer_origin = 'Foreign' THEN price_aed ELSE 0 END) AS foreign_2025,
            SUM(CASE WHEN transaction_date < :fy2025_start AND buyer_origin = 'Foreign' THEN price_aed ELSE 0 END) AS foreign_2024,
            SUM(CASE WHEN transaction_date >= :fy2025_start THEN price_aed ELSE 0 END) AS total_2025,
            SUM(CASE WHEN transaction_date < :fy2025_start THEN price_aed ELSE 0 END) AS total_2024
        FROM transactions
        WHERE transaction_date >= :fy2024_start AND transaction_date < :fy2025_end
    """
    fy2025_start, _ = window_bounds("fy_2025")
    engine = get_engine()
    with engine.connect() as connection:
        row = connection.execute(
            text(sql),
            {"fy2024_start": fy2024_start, "fy2025_start": fy2025_start, "fy2025_end": fy2025_end},
        ).one()
    foreign_growth = row.foreign_2025 - row.foreign_2024
    total_growth = row.total_2025 - row.total_2024
    actual = float(foreign_growth) / float(total_growth)
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    assert abs(actual - expected) <= tolerance, f"foreign_growth_share_fy2025: actual={actual}, expected={expected}"


PRICE_INDEX_ANCHORS = ["apartment_sale_index", "villa_sale_index", "apartment_rent_index", "villa_rent_index"]


@pytest.mark.parametrize("key", PRICE_INDEX_ANCHORS)
def test_price_index_current_value(key):
    anchor = ANCHORS[key]
    current_month = T.idx_to_month(T.N_MONTHS - 1)
    sql = """
        SELECT pi.index_value FROM price_indices pi
        JOIN property_types pt ON pi.property_type_id = pt.id
        WHERE pi.index_type = :index_type AND pt.name = :property_type AND pi.month = :month
    """
    actual = run_scalar(sql, {"index_type": anchor["index_type"], "property_type": anchor["property_type"], "month": current_month})
    expected = anchor["value"]
    tolerance = anchor["tolerance_pct"] / 100
    assert abs(actual - expected) <= tolerance * expected, f"{key}: actual={actual}, expected={expected}"


@pytest.mark.parametrize("key", PRICE_INDEX_ANCHORS)
def test_price_index_2019_base(key):
    anchor = ANCHORS[key]
    start = T.idx_to_month(0)
    end = T.idx_to_month(12)
    sql = """
        SELECT AVG(pi.index_value) FROM price_indices pi
        JOIN property_types pt ON pi.property_type_id = pt.id
        WHERE pi.index_type = :index_type AND pt.name = :property_type AND pi.month >= :start AND pi.month < :end
    """
    actual = run_scalar(sql, {"index_type": anchor["index_type"], "property_type": anchor["property_type"], "start": start, "end": end})
    assert abs(actual - 100) <= 1, f"{key}: 2019 mean={actual}, expected 100 +/- 1"

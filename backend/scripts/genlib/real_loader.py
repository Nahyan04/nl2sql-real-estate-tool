from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
ADREC_DATA = REPO_ROOT / "ADREC_DATA"

TRANSACTIONS_CSV = ADREC_DATA / "Transactions" / "recent_sales_2019-2026.csv"
YEARLY_SALES_XLSX = ADREC_DATA / "Transactions" / "resi_sales_by_period_yearly.xlsx"
LEASE_UNITS_XLSX = ADREC_DATA / "Residential Leases" / "lease_residential.xlsx"
LEASE_VALUE_XLSX = ADREC_DATA / "Residential Leases" / "lease_price_by_period.xlsx"
SALE_INDEX_XLSX = ADREC_DATA / "Price Indices" / "sale_price_index.xlsx"
RENT_INDEX_XLSX = ADREC_DATA / "Price Indices" / "rent_price_index.xlsx"
OFFICE_INDEX_XLSX = ADREC_DATA / "Price Indices" / "office_price_index.xlsx"
RETAIL_INDEX_XLSX = ADREC_DATA / "Price Indices" / "retail_price_index.xlsx"

# recent_sales_2019-2026.csv ships with no header row; this is the real column order.
TRANSACTION_COLUMNS = [
    "asset_class", "property_type", "date", "sold_area_sqm", "plot_area_sqm", "layout",
    "district", "community", "project", "price_aed", "count", "rate_aed_sqm", "sale_type", "market_type",
]

# Covers 99.9% of real transaction rows; everything else maps to 'Other'.
PROPERTY_TYPE_MAP = {
    "apartment": "Apartment",
    "villa": "Villa",
    "townhouse / attached villa": "Townhouse / Attached Villa",
    "plot for villa": "Plot for Villa",
    "residential complex": "Residential Complex",
    "duplex": "Duplex",
    "office": "Office",
    "plot for residential complex": "Plot for Residential Complex",
    "retail": "Retail",
    "plot for townhouse / attached villa": "Plot for Townhouse / Attached Villa",
    "mall / market / retail center": "Mall / Market / Retail Center",
    "plot for mall / market / retail center": "Plot for Mall / Market / Retail Center",
    "penthouse": "Penthouse",
    "office complex": "Office Complex",
}

LAYOUT_MAP = {
    "studio": "Studio",
    "1 bed": "1 Bedroom",
    "2 beds": "2 Bedroom",
    "3 beds": "3 Bedroom",
    "4 beds": "4 Bedroom",
    "5 beds": "5 Bedroom",
    "5+ beds": "6+ Bedroom",
    "6+ beds": "6+ Bedroom",
}

# Real ADREC district names that spell a curated community differently, or that
# should collapse into one curated community (Khalifa City has no real A/B split).
DISTRICT_OVERRIDES = {
    "al saadiyat island": "Saadiyat Island",
    "al rahah": "Al Raha Beach",
    "al shamkhah": "Al Shamkha",
    "al bahyah": "Al Bahia",
    "bani yas": "Baniyas",
    "khalifa city": "Khalifa City",
}


def map_property_type(raw: str) -> str:
    return PROPERTY_TYPE_MAP.get(raw.strip().lower(), "Other")


def map_layout(raw: str) -> str | None:
    return LAYOUT_MAP.get(raw.strip().lower())


def resolve_community_name(district: str) -> str:
    """The communities.name_en a real ADREC district should load under.

    An override wins first (a curated spelling variant, or the Khalifa City
    merge). Everything else is a brand-new community, named after the real
    district verbatim — the caller decides whether that name already exists.
    """
    return DISTRICT_OVERRIDES.get(district.strip().lower(), district)

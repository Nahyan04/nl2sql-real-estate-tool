from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

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


def load_district_municipality_lookup() -> dict[str, str]:
    """real district name -> real municipality name, built from the aggregate
    workbook (recent_sales_2019-2026.csv has no municipality column at all)."""
    df = pd.read_excel(YEARLY_SALES_XLSX)
    pairs = df[["District", "Municipality"]].drop_duplicates()
    return dict(zip(pairs["District"], pairs["Municipality"]))


def sync_geography(connection) -> dict[str, int]:
    """Ensure every real ADREC district has a communities row, and return a
    real-district-name -> communities.id map covering all of them — curated
    matches, spelling overrides, and newly-created rows alike."""
    raw = pd.read_csv(TRANSACTIONS_CSV, header=None, names=TRANSACTION_COLUMNS)
    real_districts = sorted(raw["district"].dropna().unique())
    district_to_municipality = load_district_municipality_lookup()

    existing = pd.read_sql("SELECT id, name_en FROM communities", connection)
    existing_ids = dict(zip(existing["name_en"], existing["id"]))

    municipality_ids = {
        row[0]: row[1] for row in connection.execute(text("SELECT name_en, id FROM municipalities")).fetchall()
    }
    default_municipality_id = municipality_ids["Abu Dhabi City"]

    result: dict[str, int] = {}
    for district in real_districts:
        community_name = resolve_community_name(district)
        if community_name in existing_ids:
            result[district] = existing_ids[community_name]
            continue

        municipality_name = district_to_municipality.get(district, "Abu Dhabi City")
        municipality_id = municipality_ids.get(municipality_name, default_municipality_id)

        district_id = connection.execute(
            text("INSERT INTO districts (municipality_id, name_en) VALUES (:mid, :name) RETURNING id"),
            {"mid": municipality_id, "name": community_name},
        ).scalar_one()
        community_id = connection.execute(
            text("INSERT INTO communities (district_id, name_en) VALUES (:did, :name) RETURNING id"),
            {"did": district_id, "name": community_name},
        ).scalar_one()

        existing_ids[community_name] = community_id
        result[district] = community_id

    return result


def load_real_transactions(community_id_by_district: dict[str, int]) -> pd.DataFrame:
    df = pd.read_csv(TRANSACTIONS_CSV, header=None, names=TRANSACTION_COLUMNS)
    df = df[df["asset_class"].isin(["residential", "commercial"])].copy()

    df["transaction_date"] = pd.to_datetime(df["date"]).dt.date
    df["community_id"] = df["district"].map(community_id_by_district)
    df["property_type"] = df["property_type"].map(map_property_type)
    df["layout"] = df["layout"].map(map_layout)
    df["is_offplan"] = df["sale_type"] == "off-plan"

    unmapped = df["community_id"].isna().sum()
    assert unmapped == 0, f"{unmapped} transaction rows have a district with no community mapping"

    return df[[
        "transaction_date", "community_id", "property_type", "layout",
        "market_type", "is_offplan", "sold_area_sqm", "plot_area_sqm", "price_aed", "rate_aed_sqm",
    ]]


def load_real_price_indices() -> pd.DataFrame:
    frames = []

    # rent_price_index.xlsx carries two overlapping series per month ('(all rents)'
    # and 'new rents'); keep the citywide one only, or every rent row doubles.
    sale_rent_property_map = {"apartments & duplexes": "Apartment", "villas & townhouses": "Villa"}
    for path, index_type, app_type in [
        (SALE_INDEX_XLSX, "sale", "(all sales)"),
        (RENT_INDEX_XLSX, "rent", "(all rents)"),
    ]:
        df = pd.read_excel(path)
        df = df[df["Property Type"].isin(sale_rent_property_map) & (df["App Type"] == app_type)].copy()
        df["property_type"] = df["Property Type"].map(sale_rent_property_map)
        df["index_type"] = index_type
        df["index_value"] = df["Average of sale_index_value"]
        df["month"] = pd.to_datetime(df["Date"]).dt.date
        frames.append(df[["month", "index_type", "property_type", "index_value"]])

    # office_price_index.xlsx and retail_price_index.xlsx carry rent-only series
    # (App Type is '(all rents)' or 'new rents') despite the value column being
    # named 'Sale Index Value' in the raw export. Each file also covers a single
    # municipality, not a mix: office is Abu Dhabi City only, retail is Al Ain
    # City only -- there is no Abu Dhabi retail rent series in this export.
    # Known geography inconsistency: the Retail/rent row below is therefore Al
    # Ain City data, loaded as the closest available real substitute since
    # price_indices has no geography column; every other row in this table is
    # Abu Dhabi City.
    for path, property_type, municipality in [
        (OFFICE_INDEX_XLSX, "Office", "Abu Dhabi City"),
        (RETAIL_INDEX_XLSX, "Retail", "Al Ain City"),
    ]:
        df = pd.read_excel(path)
        df = df[(df["Municipality"] == municipality) & (df["App Type"] == "(all rents)")].copy()
        assert len(df) > 0, f"{path} has no '(all rents)' rows for {municipality}"
        df["property_type"] = property_type
        df["index_type"] = "rent"
        df["index_value"] = df["Sale Index Value"]
        df["month"] = pd.to_datetime(df["Date"]).dt.date
        frames.append(df[["month", "index_type", "property_type", "index_value"]])

    return pd.concat(frames, ignore_index=True)

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_engine
from scripts.genlib import real_loader, sampler

CALIBRATION_PATH = PROJECT_ROOT / "app" / "resources" / "calibration.json"
GENERATED_DIR = PROJECT_ROOT / "db" / "generated"

FACT_TABLES = ["projects", "transactions", "mortgages", "rental_market_stats", "price_indices", "brokers"]


def load_dimensions(connection) -> dict:
    communities = pd.read_sql("SELECT id, name_en FROM communities", connection)
    property_types = pd.read_sql("SELECT id, name FROM property_types", connection)
    layouts = pd.read_sql("SELECT id, name FROM layouts", connection)
    developers = pd.read_sql("SELECT id, name FROM developers", connection)
    return {
        "communities": communities,
        "property_types": property_types,
        "layouts": layouts,
        "developers": developers,
    }


def map_ids(df: pd.DataFrame, column: str, id_column: str, lookup: pd.DataFrame, lookup_name_col: str) -> pd.DataFrame:
    name_to_id = dict(zip(lookup[lookup_name_col], lookup["id"]))
    df[id_column] = df[column].map(name_to_id)
    return df.drop(columns=[column])


def build_all(calibration: dict, dims: dict, community_id_by_district: dict[str, int]) -> dict[str, pd.DataFrame]:
    communities = dims["communities"]
    property_types = dims["property_types"]
    layouts = dims["layouts"]
    developers = dims["developers"]

    projects = sampler.generate_projects(communities, developers)

    transactions = real_loader.load_real_transactions(community_id_by_district)
    transactions = map_ids(transactions, "property_type", "property_type_id", property_types, "name")
    transactions = map_ids(transactions, "layout", "layout_id", layouts, "name")
    transactions["layout_id"] = transactions["layout_id"].astype("Int64")
    transactions["project_id"] = pd.Series([pd.NA] * len(transactions), dtype="Int64")

    # 6 raw ADREC rows (all "mall / market / retail center") carry a 0.01 sqm
    # sentinel for both sold_area_sqm and plot_area_sqm, which drives rate_aed_sqm
    # to 50M-120M AED/sqm -- clearly not a real per-sqm rate. Null the rate on all
    # rows sharing that sentinel (not just the 2 that overflow the numeric(10,2)
    # column) so the fix tracks the data defect rather than a storage ceiling; the
    # ceiling check stays as a backstop so a future overflow can't break the load.
    RATE_AED_SQM_MAX = 99_999_999.99
    sentinel_area = (transactions["sold_area_sqm"] == 0.01) & (transactions["plot_area_sqm"] == 0.01)
    overflow = transactions["rate_aed_sqm"].abs() > RATE_AED_SQM_MAX
    transactions.loc[sentinel_area | overflow, "rate_aed_sqm"] = pd.NA

    mortgages = sampler.generate_mortgages(calibration, communities)
    mortgages = map_ids(mortgages, "property_type", "property_type_id", property_types, "name")

    rentals = real_loader.load_real_rental_stats(community_id_by_district)
    rentals = map_ids(rentals, "property_type", "property_type_id", property_types, "name")
    rentals = map_ids(rentals, "layout", "layout_id", layouts, "name")
    rentals["layout_id"] = rentals["layout_id"].astype("Int64")

    price_indices = real_loader.load_real_price_indices()
    price_indices = map_ids(price_indices, "property_type", "property_type_id", property_types, "name")

    brokers = sampler.generate_brokers(communities)

    return {
        "transactions": transactions,
        "mortgages": mortgages,
        "rental_market_stats": rentals,
        "price_indices": price_indices,
        "brokers": brokers,
        "projects": projects,
    }


COLUMN_ORDER = {
    "transactions": [
        "transaction_date", "community_id", "project_id", "property_type_id", "layout_id",
        "market_type", "is_offplan", "sold_area_sqm", "plot_area_sqm", "price_aed", "rate_aed_sqm",
    ],
    "mortgages": ["mortgage_date", "community_id", "property_type_id", "mortgage_value_aed", "lender_type"],
    "rental_market_stats": ["period_end", "community_id", "property_type_id", "layout_id", "leased_units", "total_annual_rent_aed"],
    "price_indices": ["month", "index_type", "property_type_id", "index_value"],
    "brokers": ["name", "kind", "license_type", "community_focus_id"],
    "projects": ["id", "community_id", "developer_id", "name"],
}


def write_csvs(tables: dict[str, pd.DataFrame]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df[COLUMN_ORDER[name]].to_csv(GENERATED_DIR / f"{name}.csv", index=False)


def load_csvs(engine) -> None:
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(
            "TRUNCATE transactions, mortgages, rental_market_stats, price_indices, brokers, projects RESTART IDENTITY CASCADE"
        )
        for name in FACT_TABLES:
            path = GENERATED_DIR / f"{name}.csv"
            columns = ",".join(COLUMN_ORDER[name])
            with open(path) as f:
                cursor.copy_expert(f"COPY {name} ({columns}) FROM STDIN WITH CSV HEADER", f)
        cursor.close()
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def main() -> None:
    calibration = json.loads(CALIBRATION_PATH.read_text())
    engine = get_engine()
    try:
        with engine.begin() as connection:
            community_id_by_district = real_loader.sync_geography(connection)

        with engine.connect() as connection:
            dims = load_dimensions(connection)

        tables = build_all(calibration, dims, community_id_by_district)
        write_csvs(tables)
        load_csvs(engine)

        for name in FACT_TABLES:
            print(f"{name}: {len(tables[name])} rows")
    finally:
        engine.dispose()


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"done in {time.time() - t0:.1f}s")

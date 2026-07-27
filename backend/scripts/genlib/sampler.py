from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import targets as T

# Heavier weight on the islands narrative called out in plan.md; unlisted communities default to 2.
COMMUNITY_WEIGHTS = {
    "Yas Island": 10,
    "Saadiyat Island": 9,
    "Al Reem Island": 9,
    "Al Maryah Island": 6,
    "Khalifa City A": 6,
    "Khalifa City B": 5,
    "Al Raha Beach": 6,
    "Corniche Road": 5,
    "Al Khalidiyah": 5,
    "Al Bateen": 4,
    "Al Zahiyah": 4,
    "Masdar City": 4,
    "Zayed City": 3,
    "Al Shamkha": 3,
    "Al Bahia": 3,
    "Baniyas": 3,
    "Al Mushrif": 3,
    "Al Nahyan": 3,
    "Al Jimi": 2,
    "Al Muwaiji": 2,
    "Al Towayya": 2,
    "Al Yahar": 1,
    "Madinat Zayed": 2,
    "Ruwais": 1,
    "Liwa": 1,
}

PREMIUM_COMMUNITIES = {"Yas Island", "Saadiyat Island", "Al Reem Island", "Al Maryah Island", "Al Raha Beach"}
MIDTIER_COMMUNITIES = {"Khalifa City A", "Khalifa City B", "Corniche Road", "Al Khalidiyah", "Al Bateen", "Al Zahiyah", "Masdar City", "Zayed City"}

APARTMENT_LAYOUT_WEIGHTS = {
    "Studio": 0.15, "1 Bedroom": 0.30, "2 Bedroom": 0.30, "3 Bedroom": 0.15,
    "4 Bedroom": 0.06, "5 Bedroom": 0.02, "6+ Bedroom": 0.01, "Penthouse": 0.01,
}
VILLA_LAYOUT_WEIGHTS = {"3 Bedroom": 0.30, "4 Bedroom": 0.30, "5 Bedroom": 0.25, "6+ Bedroom": 0.15}

APARTMENT_PRICE_MEDIAN = {
    "Studio": 650_000, "1 Bedroom": 900_000, "2 Bedroom": 1_300_000, "3 Bedroom": 1_800_000,
    "4 Bedroom": 2_400_000, "5 Bedroom": 3_200_000, "6+ Bedroom": 4_000_000, "Penthouse": 6_500_000,
}
APARTMENT_AREA_MEDIAN = {
    "Studio": 45, "1 Bedroom": 75, "2 Bedroom": 110, "3 Bedroom": 160,
    "4 Bedroom": 220, "5 Bedroom": 300, "6+ Bedroom": 380, "Penthouse": 450,
}
VILLA_PRICE_MEDIAN = {"3 Bedroom": 2_800_000, "4 Bedroom": 3_800_000, "5 Bedroom": 5_200_000, "6+ Bedroom": 7_500_000}
VILLA_AREA_MEDIAN = {"3 Bedroom": 280, "4 Bedroom": 380, "5 Bedroom": 480, "6+ Bedroom": 650}

OTHER_PROPERTY_WEIGHTS = {"Land": 0.45, "Building": 0.30, "Commercial Unit": 0.25}
OTHER_PRICE_MEDIAN = {"Land": 1_500_000, "Building": 5_000_000, "Commercial Unit": 1_800_000}
OTHER_AREA_MEDIAN = {"Land": 800, "Building": 1200, "Commercial Unit": 350}  # Land's is plot_area, others sold_area

RENTAL_BASE_APARTMENT = {
    "Studio": 35_000, "1 Bedroom": 50_000, "2 Bedroom": 70_000, "3 Bedroom": 95_000,
    "4 Bedroom": 130_000, "5 Bedroom": 170_000, "6+ Bedroom": 220_000, "Penthouse": 320_000,
}
RENTAL_BASE_VILLA = {"3 Bedroom": 140_000, "4 Bedroom": 190_000, "5 Bedroom": 250_000, "6+ Bedroom": 350_000}

DEVELOPER_SUFFIXES = ["Residences", "Towers", "Gardens", "Heights", "Bay", "Views", "Court", "Terraces", "Plaza", "Square"]

FIRST_NAMES = [
    "Ahmed", "Mohammed", "Khalid", "Omar", "Youssef", "Sara", "Fatima", "Layla", "Noura", "Maryam",
    "James", "David", "Michael", "Emma", "Olivia", "Rajesh", "Priya", "Wei", "Chen", "Anastasia",
]
LAST_NAMES = [
    "Al Mansoori", "Al Suwaidi", "Al Kaabi", "Al Dhaheri", "Al Shamsi", "Hassan", "Khan", "Ahmed",
    "Smith", "Brown", "Sharma", "Patel", "Ivanova", "Petrov", "Wong", "Lee",
]


def community_weight_table(communities: pd.DataFrame) -> pd.DataFrame:
    communities = communities.copy()
    communities["weight"] = communities["name_en"].map(COMMUNITY_WEIGHTS).fillna(2)
    return communities


def rate_tier(name_en: str) -> float:
    if name_en in PREMIUM_COMMUNITIES:
        return 1.4
    if name_en in MIDTIER_COMMUNITIES:
        return 1.0
    return 0.6


def _weighted_choice(rng: np.random.Generator, options: list[str], weights: list[float], n: int) -> np.ndarray:
    probs = np.array(weights) / sum(weights)
    return rng.choice(options, size=n, p=probs)


def _lognormal_from_median(rng: np.random.Generator, median: float, sigma: float, n: int) -> np.ndarray:
    if n <= 0:
        return np.array([])
    return rng.lognormal(mean=np.log(median), sigma=sigma, size=n)


def _rescale_to_target(raw: np.ndarray, target_value: float) -> np.ndarray:
    if len(raw) == 0:
        return raw
    raw_sum = raw.sum()
    if raw_sum <= 0:
        return np.full(len(raw), target_value / len(raw))
    return raw * (target_value / raw_sum)


def _random_dates_in_month(rng: np.random.Generator, idx: int, n: int) -> np.ndarray:
    month_start = T.idx_to_month(idx)
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    days_in_month = (next_month - month_start).days
    offsets = rng.integers(0, days_in_month, size=n)
    return np.array([month_start + pd.Timedelta(days=int(d)) for d in offsets])


def _sample_residential_rows(rng: np.random.Generator, property_type: str, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (layouts, prices_raw, sold_area_sqm) for Apartment/Villa rows."""
    if property_type == "Apartment":
        layouts = _weighted_choice(rng, list(APARTMENT_LAYOUT_WEIGHTS), list(APARTMENT_LAYOUT_WEIGHTS.values()), n)
        prices = np.array([_lognormal_from_median(rng, APARTMENT_PRICE_MEDIAN[l], 0.35, 1)[0] for l in layouts])
        areas = np.array([_lognormal_from_median(rng, APARTMENT_AREA_MEDIAN[l], 0.15, 1)[0] for l in layouts])
    else:
        layouts = _weighted_choice(rng, list(VILLA_LAYOUT_WEIGHTS), list(VILLA_LAYOUT_WEIGHTS.values()), n)
        prices = np.array([_lognormal_from_median(rng, VILLA_PRICE_MEDIAN[l], 0.30, 1)[0] for l in layouts])
        areas = np.array([_lognormal_from_median(rng, VILLA_AREA_MEDIAN[l], 0.15, 1)[0] for l in layouts])
    return layouts, prices, areas


def generate_transactions(calibration: dict, communities: pd.DataFrame, projects: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    total_value = T.build_total_transaction_value(calibration)
    total_count = T.build_transaction_count(calibration)
    residential_share = T.build_residential_share(calibration, total_value)
    foreign_share = T.build_foreign_share(calibration, total_value)

    comm_weighted = community_weight_table(communities)
    comm_probs = comm_weighted["weight"] / comm_weighted["weight"].sum()

    rows = []
    for idx in range(T.N_MONTHS):
        n = int(round(total_count[idx]))
        if n <= 0:
            continue
        month_total_value = total_value[idx]
        month_residential_value = residential_share[idx] * month_total_value
        month_other_value = month_total_value - month_residential_value

        n_residential = int(round(n * 0.65))
        n_other = n - n_residential

        for pool_name, pool_n, pool_value in (("residential", n_residential, month_residential_value), ("other", n_other, month_other_value)):
            if pool_n <= 0:
                continue
            n_foreign = int(round(pool_n * foreign_share[idx]))
            n_domestic = pool_n - n_foreign

            for origin_bucket, bucket_n in (("Foreign", n_foreign), ("domestic", n_domestic)):
                if bucket_n <= 0:
                    continue

                if pool_name == "residential":
                    prop_types = _weighted_choice(rng, ["Apartment", "Villa"], [0.70, 0.30], bucket_n)
                else:
                    prop_types = _weighted_choice(rng, list(OTHER_PROPERTY_WEIGHTS), list(OTHER_PROPERTY_WEIGHTS.values()), bucket_n)

                layouts = np.full(bucket_n, "", dtype=object)
                prices_raw = np.zeros(bucket_n)
                sold_area = np.full(bucket_n, np.nan)
                plot_area = np.full(bucket_n, np.nan)

                for ptype in np.unique(prop_types):
                    mask = prop_types == ptype
                    m = int(mask.sum())
                    if ptype in ("Apartment", "Villa"):
                        lay, pr, area = _sample_residential_rows(rng, ptype, m)
                        layouts[mask] = lay
                        prices_raw[mask] = pr
                        sold_area[mask] = area
                        if ptype == "Villa":
                            plot_area[mask] = area * rng.uniform(1.2, 1.8, size=m)
                    else:
                        pr = _lognormal_from_median(rng, OTHER_PRICE_MEDIAN[ptype], 0.40, m)
                        prices_raw[mask] = pr
                        area = _lognormal_from_median(rng, OTHER_AREA_MEDIAN[ptype], 0.30, m)
                        if ptype == "Land":
                            plot_area[mask] = area
                        else:
                            sold_area[mask] = area

                bucket_target = foreign_share[idx] * pool_value if origin_bucket == "Foreign" else (1 - foreign_share[idx]) * pool_value
                prices = _rescale_to_target(prices_raw, bucket_target)

                comm_idx = rng.choice(len(comm_weighted), size=bucket_n, p=comm_probs.values)
                comm_ids = comm_weighted["id"].values[comm_idx]
                comm_names = comm_weighted["name_en"].values[comm_idx]

                is_offplan = np.where(
                    np.isin(prop_types, ["Apartment", "Villa"]),
                    rng.random(bucket_n) < 0.40,
                    rng.random(bucket_n) < 0.15,
                )
                sale_type = np.where(is_offplan, "sale", rng.choice(["sale", "resale"], size=bucket_n))

                if origin_bucket == "Foreign":
                    buyer_origin = np.full(bucket_n, "Foreign", dtype=object)
                else:
                    buyer_origin = rng.choice(["UAE", "GCC"], size=bucket_n, p=[0.70, 0.30])

                dates = _random_dates_in_month(rng, idx, bucket_n)

                project_ids = np.full(bucket_n, None, dtype=object)
                has_project = rng.random(bucket_n) < 0.55
                for i in range(bucket_n):
                    if has_project[i]:
                        candidates = projects.loc[projects["community_id"] == comm_ids[i], "id"]
                        if len(candidates) > 0:
                            project_ids[i] = int(rng.choice(candidates.values))

                rate = np.where(sold_area > 0, prices / sold_area, np.where(plot_area > 0, prices / plot_area, np.nan))

                rows.append(pd.DataFrame({
                    "transaction_date": dates,
                    "community_id": comm_ids,
                    "project_id": project_ids,
                    "property_type": prop_types,
                    "layout": layouts,
                    "sale_type": sale_type,
                    "is_offplan": is_offplan,
                    "sold_area_sqm": sold_area,
                    "plot_area_sqm": plot_area,
                    "price_aed": prices,
                    "rate_aed_sqm": rate,
                    "buyer_origin": buyer_origin,
                }))

    return pd.concat(rows, ignore_index=True)


def generate_mortgages(calibration: dict, communities: pd.DataFrame, seed: int = 43) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    total_value = T.build_total_transaction_value(calibration)
    total_count = T.build_transaction_count(calibration)
    mortgage_value = T.build_mortgage_value(calibration, total_value)
    mortgage_count = T.build_mortgage_count(total_count)

    comm_weighted = community_weight_table(communities)
    comm_probs = comm_weighted["weight"] / comm_weighted["weight"].sum()

    rows = []
    for idx in range(T.N_MONTHS):
        n = int(round(mortgage_count[idx]))
        if n <= 0:
            continue
        prop_types = _weighted_choice(rng, ["Apartment", "Villa", "Land", "Building", "Commercial Unit"], [0.45, 0.25, 0.10, 0.10, 0.10], n)
        raw = np.zeros(n)
        for ptype in np.unique(prop_types):
            mask = prop_types == ptype
            m = int(mask.sum())
            if ptype == "Apartment":
                raw[mask] = _lognormal_from_median(rng, 900_000, 0.4, m)
            elif ptype == "Villa":
                raw[mask] = _lognormal_from_median(rng, 3_200_000, 0.4, m)
            else:
                raw[mask] = _lognormal_from_median(rng, OTHER_PRICE_MEDIAN[ptype], 0.4, m)
        values = _rescale_to_target(raw, mortgage_value[idx])

        comm_idx = rng.choice(len(comm_weighted), size=n, p=comm_probs.values)
        dates = _random_dates_in_month(rng, idx, n)
        lender = rng.choice(["local_bank", "international_bank", "finance_company"], size=n, p=[0.55, 0.30, 0.15])

        rows.append(pd.DataFrame({
            "mortgage_date": dates,
            "community_id": comm_weighted["id"].values[comm_idx],
            "property_type": prop_types,
            "mortgage_value_aed": values,
            "lender_type": lender,
        }))

    return pd.concat(rows, ignore_index=True)


def generate_rental_contracts(calibration: dict, communities: pd.DataFrame, seed: int = 44) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rental_stock = T.build_rental_stock(calibration)
    contract_count = T.build_rental_contract_count(calibration, rental_stock)

    comm_weighted = community_weight_table(communities)
    comm_probs = comm_weighted["weight"] / comm_weighted["weight"].sum()

    rows = []
    for idx in range(T.N_MONTHS):
        n = int(round(contract_count[idx]))
        if n <= 0:
            continue
        prop_types = _weighted_choice(rng, ["Apartment", "Villa"], [0.75, 0.25], n)
        comm_idx = rng.choice(len(comm_weighted), size=n, p=comm_probs.values)
        comm_names = comm_weighted["name_en"].values[comm_idx]
        tiers = np.array([rate_tier(name) for name in comm_names])

        layouts = np.full(n, "", dtype=object)
        rents = np.zeros(n)
        for ptype in np.unique(prop_types):
            mask = prop_types == ptype
            m = int(mask.sum())
            weights = APARTMENT_LAYOUT_WEIGHTS if ptype == "Apartment" else VILLA_LAYOUT_WEIGHTS
            base_table = RENTAL_BASE_APARTMENT if ptype == "Apartment" else RENTAL_BASE_VILLA
            lay = _weighted_choice(rng, list(weights), list(weights.values()), m)
            layouts[mask] = lay
            base = np.array([base_table[l] for l in lay])
            noise = rng.lognormal(mean=0, sigma=0.20, size=m)
            rents[mask] = base * tiers[mask] * noise

        dates = _random_dates_in_month(rng, idx, n)
        contract_type = rng.choice(["new", "renewal"], size=n, p=[0.45, 0.55])

        rows.append(pd.DataFrame({
            "contract_date": dates,
            "community_id": comm_weighted["id"].values[comm_idx],
            "property_type": prop_types,
            "layout": layouts,
            "annual_rent_aed": rents,
            "contract_type": contract_type,
        }))

    return pd.concat(rows, ignore_index=True)


def generate_price_indices(calibration: dict, seed_base: int = 100) -> pd.DataFrame:
    series_specs = [
        ("apartment_sale_index", "sale", "Apartment"),
        ("villa_sale_index", "sale", "Villa"),
        ("apartment_rent_index", "rent", "Apartment"),
        ("villa_rent_index", "rent", "Villa"),
    ]
    rows = []
    for i, (key, index_type, property_type) in enumerate(series_specs):
        anchor = calibration["anchors"][key]
        curve = T.build_index_curve(anchor["value"], anchor["yoy_delta_pts"], seed=seed_base + i)
        months = [T.idx_to_month(idx) for idx in range(T.N_MONTHS)]
        rows.append(pd.DataFrame({
            "month": months,
            "index_type": index_type,
            "property_type": property_type,
            "index_value": curve,
        }))
    return pd.concat(rows, ignore_index=True)


def generate_projects(communities: pd.DataFrame, developers: pd.DataFrame, seed: int = 45) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    project_id = 1
    for _, community in communities.iterrows():
        n_projects = rng.integers(3, 10)
        for _ in range(n_projects):
            developer_id = int(rng.choice(developers["id"].values))
            suffix = rng.choice(DEVELOPER_SUFFIXES)
            name = f"{community['name_en']} {suffix}"
            rows.append({"id": project_id, "community_id": community["id"], "developer_id": developer_id, "name": name})
            project_id += 1
    return pd.DataFrame(rows)


def generate_brokers(communities: pd.DataFrame, seed: int = 46, n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    comm_weighted = community_weight_table(communities)
    comm_probs = comm_weighted["weight"] / comm_weighted["weight"].sum()

    kind = rng.choice(["individual", "company"], size=n, p=[0.70, 0.30])
    rows = []
    for i in range(n):
        if kind[i] == "individual":
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            license_type = "Individual Broker License"
        else:
            name = f"{rng.choice(LAST_NAMES)} {rng.choice(DEVELOPER_SUFFIXES)} Real Estate Brokerage"
            license_type = "Corporate Brokerage License"
        comm_idx = rng.choice(len(comm_weighted), p=comm_probs.values)
        rows.append({
            "name": name,
            "kind": kind[i],
            "license_type": license_type,
            "community_focus_id": int(comm_weighted["id"].values[comm_idx]),
        })
    return pd.DataFrame(rows)

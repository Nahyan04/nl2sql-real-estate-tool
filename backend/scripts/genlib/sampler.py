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


MORTGAGE_PROPERTY_WEIGHTS = {"Apartment": 0.45, "Villa": 0.25, "Office": 0.10, "Retail": 0.10, "Other": 0.10}
MORTGAGE_PRICE_MEDIAN = {"Apartment": 900_000, "Villa": 3_200_000, "Office": 2_200_000, "Retail": 1_800_000, "Other": 1_500_000}


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
        prop_types = _weighted_choice(rng, list(MORTGAGE_PROPERTY_WEIGHTS), list(MORTGAGE_PROPERTY_WEIGHTS.values()), n)
        raw = np.zeros(n)
        for ptype in np.unique(prop_types):
            mask = prop_types == ptype
            m = int(mask.sum())
            raw[mask] = _lognormal_from_median(rng, MORTGAGE_PRICE_MEDIAN[ptype], 0.4, m)
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

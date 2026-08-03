from __future__ import annotations

from datetime import date

import numpy as np

N_MONTHS = 91  # 2019-01 .. 2026-07 inclusive


def month_idx(year: int, month: int) -> int:
    return (year - 2019) * 12 + (month - 1)


def idx_to_month(idx: int) -> date:
    year = 2019 + idx // 12
    month = idx % 12 + 1
    return date(year, month, 1)


# (start_idx, end_idx) inclusive windows shared by targets.py and the calibration tests
LAST_12MO = (month_idx(2025, 8), month_idx(2026, 7))
PRIOR_12MO = (month_idx(2024, 8), month_idx(2025, 7))
FY_2025 = (month_idx(2025, 1), month_idx(2025, 12))
FY_2024 = (month_idx(2024, 1), month_idx(2024, 12))
H1_2025 = (month_idx(2025, 1), month_idx(2025, 6))
YTD_2026 = (month_idx(2026, 1), month_idx(2026, 7))


def rake(prior: np.ndarray, constraints: list[tuple[int, int, float]], iterations: int = 4000) -> np.ndarray:
    """Iterative proportional fitting: rescale each constrained window to its target sum,
    repeatedly, until overlapping windows converge to a mutual compromise."""
    values = prior.astype(float).copy()
    for _ in range(iterations):
        for start, end, target in constraints:
            current = values[start : end + 1].sum()
            if current > 0:
                values[start : end + 1] *= target / current
    return values


def build_prior(
    level_2024_monthly: float,
    n_months: int = N_MONTHS,
    backward_annual_growth: float = 1.19,
    seasonal_amp: float = 0.10,
) -> np.ndarray:
    """A smooth pre-rake shape: flat at `level_2024_monthly` from 2024 onward, decaying
    backward year-over-year before that (pure narrative filler — no anchors cover 2019-2023),
    with a seasonal multiplier (mean 1.0 over any full calendar year) layered on top."""
    prior = np.full(n_months, level_2024_monthly, dtype=float)
    level = level_2024_monthly
    for year in range(2023, 2018, -1):
        level = level / backward_annual_growth
        start = (year - 2019) * 12
        end = min(start + 11, n_months - 1)
        prior[start : end + 1] = level

    months = (np.arange(n_months) % 12) + 1
    seasonal = 1 + seasonal_amp * np.cos(2 * np.pi * (months - 1) / 12)
    return prior * seasonal


def build_total_transaction_value(calibration: dict) -> np.ndarray:
    anchors = calibration["anchors"]
    last12 = anchors["txn_value_last12mo"]
    fy2025 = anchors["txn_value_fy2025"]

    last12_value = last12["value"]
    prior12_value = last12_value / (1 + last12["yoy_delta_pct"] / 100)
    fy2025_value = fy2025["value"]
    fy2024_value = fy2025_value / (1 + fy2025["yoy_delta_pct"] / 100)
    ytd2026_value = anchors["sales_value_ytd2026"]["value"]

    # txn_value_h1_2025 is deliberately NOT raked here: algebraically, last_12mo minus
    # ytd_2026 pins Aug-Dec 2025 at ~110.9bn, while fy_2025 minus h1_2025 caps Jul-Dec 2025
    # at ~88bn total -- a direct contradiction between the live-dashboard-sourced anchors
    # (last_12mo, ytd_2026) and the biannual-report-sourced h1_2025 anchor. The other five
    # windows are mutually feasible; h1_2025 is tested informationally with a wider tolerance.
    prior = build_prior(fy2024_value / 12)
    constraints = [
        (*FY_2024, fy2024_value),
        (*FY_2025, fy2025_value),
        (*PRIOR_12MO, prior12_value),
        (*LAST_12MO, last12_value),
        (*YTD_2026, ytd2026_value),
    ]
    return rake(prior, constraints)


def build_transaction_count(calibration: dict) -> np.ndarray:
    anchors = calibration["anchors"]
    volume = anchors["txn_volume_last12mo"]
    last12_count = volume["value"]
    prior12_count = last12_count / (1 + volume["yoy_delta_pct"] / 100)

    prior = build_prior(last12_count / 12)
    constraints = [(*PRIOR_12MO, prior12_count), (*LAST_12MO, last12_count)]
    return rake(prior, constraints)


def build_mortgage_value(calibration: dict, total_value: np.ndarray) -> np.ndarray:
    ytd2026_value = calibration["anchors"]["mortgage_value_ytd2026"]["value"]
    prior = total_value * 0.37
    return rake(prior, [(*YTD_2026, ytd2026_value)])


def build_mortgage_count(transaction_count: np.ndarray, total_count: int = 40_000) -> np.ndarray:
    shape = transaction_count / transaction_count.sum()
    return shape * total_count


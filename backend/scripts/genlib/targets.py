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


def rake_share_curve(
    total_series: np.ndarray,
    baseline_share: float,
    constraints_as_shares: list[tuple[int, int, float]],
    iterations: int = 200,
) -> np.ndarray:
    """Derive a per-month share-of-`total_series` curve. `constraints_as_shares` are windowed
    share targets; internally converted to absolute-sum targets using the actual (already-raked)
    window totals, then raked as a sub-series, then divided back down to a share."""
    prior = total_series * baseline_share
    abs_constraints = [(start, end, share * total_series[start : end + 1].sum()) for start, end, share in constraints_as_shares]
    sub = rake(prior, abs_constraints, iterations=iterations)
    sub = np.clip(sub, 0, total_series)
    share = np.divide(sub, total_series, out=np.zeros_like(sub), where=total_series > 0)
    return np.clip(share, 0.0, 1.0)


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


def fy2024_total_value(calibration: dict) -> float:
    fy2025 = calibration["anchors"]["txn_value_fy2025"]
    return fy2025["value"] / (1 + fy2025["yoy_delta_pct"] / 100)


def build_residential_share(calibration: dict, total_value: np.ndarray) -> np.ndarray:
    anchors = calibration["anchors"]
    fy2025_value = anchors["txn_value_fy2025"]["value"]
    fy2024_value = fy2024_total_value(calibration)
    residential_fy2025 = anchors["residential_sales_value_fy2025"]
    residential_fy2025_value = residential_fy2025["value"]
    residential_fy2024_value = residential_fy2025_value / (1 + residential_fy2025["yoy_delta_pct"] / 100)

    fy2025_share = residential_fy2025_value / fy2025_value
    fy2024_share = residential_fy2024_value / fy2024_value

    return rake_share_curve(
        total_value,
        baseline_share=0.5,
        constraints_as_shares=[(*FY_2025, fy2025_share), (*FY_2024, fy2024_share)],
    )


def build_foreign_share(calibration: dict, total_value: np.ndarray) -> np.ndarray:
    anchors = calibration["anchors"]
    fy2025_value = anchors["txn_value_fy2025"]["value"]
    fy2024_value = fy2024_total_value(calibration)
    baseline = anchors["foreign_share_baseline_pre2025"]["value"]
    growth_share = anchors["foreign_growth_share_fy2025"]["value"]

    fy2024_foreign_value = fy2024_value * baseline
    fy2025_foreign_value = fy2024_foreign_value + growth_share * (fy2025_value - fy2024_value)
    fy2025_share = fy2025_foreign_value / fy2025_value

    ytd2026_share = anchors["fdi_value_ytd2026"]["value"] / anchors["sales_value_ytd2026"]["value"]

    return rake_share_curve(
        total_value,
        baseline_share=baseline,
        constraints_as_shares=[(*FY_2025, fy2025_share), (*YTD_2026, ytd2026_share)],
    )


def build_mortgage_value(calibration: dict, total_value: np.ndarray) -> np.ndarray:
    ytd2026_value = calibration["anchors"]["mortgage_value_ytd2026"]["value"]
    prior = total_value * 0.37
    return rake(prior, [(*YTD_2026, ytd2026_value)])


def build_mortgage_count(transaction_count: np.ndarray, total_count: int = 40_000) -> np.ndarray:
    shape = transaction_count / transaction_count.sum()
    return shape * total_count


def build_rental_stock(calibration: dict) -> np.ndarray:
    anchors = calibration["anchors"]
    stock = anchors["rented_units_current"]
    last12_avg = stock["value"]
    prior12_avg = last12_avg / (1 + stock["yoy_delta_pct"] / 100)

    prior = build_prior(last12_avg, backward_annual_growth=1.04, seasonal_amp=0.0)
    constraints = [(*PRIOR_12MO, prior12_avg * 12), (*LAST_12MO, last12_avg * 12)]
    return rake(prior, constraints)


def build_rental_contract_count(calibration: dict, rental_stock: np.ndarray) -> np.ndarray:
    turnover_rate = calibration["anchors"]["rental_turnover_rate"]["value"]
    return rental_stock * turnover_rate / 12


def build_index_curve(final_value: float, yoy_delta_pts: float, seed: int, n_months: int = N_MONTHS, last_idx: int = N_MONTHS - 1) -> np.ndarray:
    """Three segments: 2019 flat-noisy baseline averaging exactly 100, geometric growth to the
    value 12 months before `last_idx`, then geometric growth to `final_value` at `last_idx`."""
    rng = np.random.default_rng(seed)
    curve = np.zeros(n_months)

    year1 = 100 + rng.normal(0, 0.8, size=12)
    curve[0:12] = year1 - year1.mean() + 100

    mid_idx = last_idx - 12
    mid_value = final_value - yoy_delta_pts
    start_val = 100.0

    months_b = mid_idx - 11
    rate_b = (mid_value / start_val) ** (1 / months_b)
    for i in range(1, months_b + 1):
        curve[11 + i] = start_val * (rate_b**i)

    months_c = last_idx - mid_idx
    rate_c = (final_value / mid_value) ** (1 / months_c)
    for i in range(1, months_c + 1):
        curve[mid_idx + i] = mid_value * (rate_c**i)

    return curve

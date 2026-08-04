"""Golden-question evaluation.

The grading logic and the golden file itself are checked on every run. The live sweep —
30 questions through a real LLM — is opt-in, because it costs money and takes minutes:

    RUN_GOLDEN_EVAL=1 pytest tests/eval/test_golden.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.sql_validator import validate_read_only
from scripts.run_eval import (
    DEFAULT_MIN_ACCURACY,
    accuracy,
    grade,
    load_cases,
    reference_rows,
    run_all,
)

CASES = load_cases()
LIVE = pytest.mark.skipif(
    not os.getenv("RUN_GOLDEN_EVAL"),
    reason="set RUN_GOLDEN_EVAL=1 to run the live sweep against a real provider",
)


# --- the golden file ------------------------------------------------------


def test_golden_set_is_nineteen_english_and_ten_arabic() -> None:
    assert sum(c["lang"] == "en" for c in CASES) == 19
    assert sum(c["lang"] == "ar" for c in CASES) == 10


def test_case_ids_are_unique() -> None:
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_declares_a_known_match_mode(case) -> None:
    assert case["match"] in {"scalar", "set", "ordered"}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_query_is_read_only(case) -> None:
    assert validate_read_only(case["reference_sql"]).is_safe


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_query_returns_ground_truth(case) -> None:
    """A reference that returns nothing would pass any run that also returns nothing."""
    rows = reference_rows(case["reference_sql"])
    assert rows
    assert any(value is not None for row in rows for value in row)
    if case["match"] == "scalar":
        assert len(rows) == 1


# --- grading --------------------------------------------------------------


def test_scalar_within_tolerance_passes() -> None:
    assert grade([(100.0,)], [(100.9,)], "scalar")[0]


def test_scalar_outside_tolerance_fails() -> None:
    assert not grade([(100.0,)], [(102.0,)], "scalar")[0]


def test_scalar_ignores_a_label_column_the_reference_left_out() -> None:
    assert grade([(100.0,)], [("yas island", 100.0)], "scalar")[0]


def test_scalar_rejects_a_grouped_result() -> None:
    """"What was the total" answered with a breakdown is a different question."""
    assert not grade([(100.0,)], [(60.0,), (40.0,)], "scalar")[0]


def test_zero_is_compared_absolutely() -> None:
    assert grade([(0.0,)], [(0.0,)], "scalar")[0]
    assert not grade([(0.0,)], [(5.0,)], "scalar")[0]


def test_ordered_respects_the_ranking() -> None:
    ranking = [(3.0,), (2.0,), (1.0,)]
    assert grade(ranking, ranking, "ordered")[0]
    assert not grade(ranking, list(reversed(ranking)), "ordered")[0]


def test_set_ignores_row_order() -> None:
    assert grade([("a", 1.0), ("b", 2.0)], [("b", 2.0), ("a", 1.0)], "set")[0]


def test_set_requires_the_same_number_of_rows() -> None:
    assert not grade([("a", 1.0)], [("a", 1.0), ("b", 2.0)], "set")[0]


def test_row_match_ignores_column_order() -> None:
    assert grade([("yas island", 1.0)], [(1.0, "yas island")], "set")[0]


def test_a_value_cannot_satisfy_two_expected_columns() -> None:
    assert not grade([(1.0, 1.0)], [(1.0, 2.0)], "set")[0]


def test_unknown_match_mode_is_an_error() -> None:
    with pytest.raises(ValueError):
        grade([(1.0,)], [(1.0,)], "approximately")


# --- the live sweep -------------------------------------------------------


@pytest.fixture(scope="session")
def live_results():
    return {result.case_id: result for result in run_all(CASES)}


@LIVE
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_golden_case(live_results, case) -> None:
    result = live_results[case["id"]]
    assert result.passed, f"{result.reason}\nSQL: {result.sql}"


@LIVE
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_language_accuracy_meets_the_bar(live_results, lang) -> None:
    results = list(live_results.values())
    assert accuracy(results, lang) >= DEFAULT_MIN_ACCURACY[lang]

"""Golden-question evaluation.

The grading logic and the golden file itself are checked on every run. The live sweep —
Source-backed questions through a real LLM — is opt-in, because it costs money and takes minutes:

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

from app.services.sql_validator import validate_product_query
from scripts.run_eval import (
    DEFAULT_MIN_ACCURACY,
    accuracy,
    grade,
    load_cases,
    reference_rows,
    run_all,
)
from scripts import run_eval

CASES = load_cases()
LIVE = pytest.mark.skipif(
    not os.getenv("RUN_GOLDEN_EVAL"),
    reason="set RUN_GOLDEN_EVAL=1 to run the live sweep against a real provider",
)


# --- the golden file ------------------------------------------------------


def test_golden_set_covers_both_languages() -> None:
    assert {c["lang"] for c in CASES} == {"en", "ar"}


def test_case_ids_are_unique() -> None:
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_declares_a_known_match_mode(case) -> None:
    assert case.get("match") in {"scalar", "set", "ordered"} or case.get("expected_failure") in {"UNSUPPORTED", "CLARIFICATION"}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_query_is_read_only(case) -> None:
    if "reference_sql" in case:
        assert validate_product_query(case["reference_sql"]).is_safe


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_query_returns_ground_truth(case) -> None:
    """A reference that returns nothing would pass any run that also returns nothing."""
    if "reference_sql" not in case:
        return
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


def test_case_grades_language_and_proxy_label(monkeypatch) -> None:
    from app.services.executor import ExecResult

    monkeypatch.setattr(run_eval, 'reference_rows', lambda _: [(5.95,)])
    monkeypatch.setattr(run_eval, 'run_pipeline', lambda *_args, **_kwargs: {
        'sql': 'SELECT 5.95 AS gross_segment_yield_pct',
        'exec_result': ExecResult(columns=['gross_segment_yield_pct'], rows=[[5.95]], row_count=1),
        'answer': 'Indicative gross segment yield: 5.95%; net requires property costs.',
        'model_usage': {'calls': 2, 'input_tokens': 100, 'output_tokens': 20, 'model': 'test-model'},
        'snapshot_id': '2026-09-24',
    })
    case = {'id': 'proxy', 'lang': 'en', 'question': 'net yield', 'match': 'scalar',
            'reference_sql': 'SELECT 5.95', 'required_answer_terms': ['gross', 'net']}
    result = run_eval.run_case(case)
    assert result.passed
    assert (result.model_calls, result.input_tokens, result.output_tokens) == (2, 100, 20)
    assert result.snapshot_id == '2026-09-24'


def test_boundary_case_does_not_need_reference_query(monkeypatch) -> None:
    monkeypatch.setattr(run_eval, 'run_pipeline', lambda *_args, **_kwargs: {
        'failure': {'type': 'CLARIFICATION', 'detail': 'Specify the source place.'},
        'attempts': 0,
    })
    result = run_eval.run_case({'id': 'ambiguous', 'lang': 'ar', 'question': 'البطين',
                                'expected_failure': 'CLARIFICATION'})
    assert result.passed and result.expected == []


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

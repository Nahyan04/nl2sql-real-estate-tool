"""Golden-question evaluation: NL question -> pipeline -> rows, graded against a reference query.

    python scripts/run_eval.py --provider anthropic
    python scripts/run_eval.py --lang ar --json report.json

Grading is execution accuracy, not SQL similarity: two very different queries that return
the same values both count as correct. tests/eval/test_golden.py drives the same functions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from app.core.database import get_readonly_engine
from app.services.graph import run_pipeline

GOLDEN_PATH = PROJECT_ROOT / "tests" / "eval" / "golden_questions.json"
DEFAULT_TOLERANCE = 0.01
DEFAULT_MIN_ACCURACY = {"en": 0.90, "ar": 0.70}


def load_cases(lang: str | None = None, ids: list[str] | None = None) -> list[dict[str, Any]]:
    cases = json.loads(GOLDEN_PATH.read_text())["cases"]
    if lang:
        cases = [case for case in cases if case["lang"] == lang]
    if ids:
        wanted = set(ids)
        cases = [case for case in cases if case["id"] in wanted]
    return cases


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()[:10]
    return " ".join(str(value).split()).lower()


def _values_match(expected: Any, actual: Any, tolerance: float) -> bool:
    if isinstance(expected, float) and isinstance(actual, float):
        if expected == 0.0:
            return abs(actual) <= tolerance
        return abs(actual - expected) <= tolerance * abs(expected)
    return expected == actual


def _row_matches(expected_row: tuple, actual_row: tuple, tolerance: float) -> bool:
    """Each expected value claims its own cell in the row; extra columns are ignored.

    A run is free to return a label the reference left out, or to order its columns
    differently — only the values the reference asked for have to be there.
    """
    unclaimed = list(actual_row)
    for value in expected_row:
        for index, candidate in enumerate(unclaimed):
            if _values_match(value, candidate, tolerance):
                del unclaimed[index]
                break
        else:
            return False
    return True


def grade(
    expected: list[tuple],
    actual: list[tuple],
    match: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> tuple[bool, str]:
    if match == "scalar":
        if len(actual) != 1:
            return False, f"expected a single row, got {len(actual)}"
        return (
            (True, "")
            if _row_matches(expected[0], actual[0], tolerance)
            else (False, f"expected {expected[0]}, got {actual[0]}")
        )

    if len(expected) != len(actual):
        return False, f"expected {len(expected)} rows, got {len(actual)}"

    if match == "ordered":
        for position, (expected_row, actual_row) in enumerate(zip(expected, actual)):
            if not _row_matches(expected_row, actual_row, tolerance):
                return False, f"row {position}: expected {expected_row}, got {actual_row}"
        return True, ""

    if match == "set":
        unclaimed = list(actual)
        for expected_row in expected:
            for index, actual_row in enumerate(unclaimed):
                if _row_matches(expected_row, actual_row, tolerance):
                    del unclaimed[index]
                    break
            else:
                return False, f"no row matched {expected_row}"
        return True, ""

    raise ValueError(f"unknown match mode: {match}")


def reference_rows(sql: str) -> list[tuple]:
    with get_readonly_engine().connect() as connection:
        return [tuple(_normalize(v) for v in row) for row in connection.execute(text(sql))]


@dataclass
class CaseResult:
    case_id: str
    lang: str
    question: str
    passed: bool
    reason: str = ""
    sql: str | None = None
    attempts: int = 0
    latency_ms: int = 0
    expected: list[tuple] = field(default_factory=list)
    actual: list[tuple] = field(default_factory=list)


def run_case(case: dict[str, Any], provider: str | None = None) -> CaseResult:
    result = CaseResult(case["id"], case["lang"], case["question"], passed=False)
    result.expected = reference_rows(case["reference_sql"])

    try:
        state = run_pipeline(case["question"], provider)
    except Exception as exc:  # noqa: BLE001 - a crashed run is a failed case, not a crashed sweep
        result.reason = f"pipeline raised {type(exc).__name__}: {exc}"
        return result

    result.sql = state.get("sql")
    result.attempts = state.get("attempts", 0)
    result.latency_ms = state.get("latency_ms", 0)

    failure = state.get("failure")
    if failure:
        result.reason = f"{failure['type']}: {failure['detail'][:160]}"
        return result

    exec_result = state.get("exec_result")
    if exec_result is None:
        result.reason = "pipeline returned no result set"
        return result

    result.actual = [tuple(_normalize(v) for v in row) for row in exec_result.rows]
    result.passed, result.reason = grade(
        result.expected,
        result.actual,
        case["match"],
        case.get("tolerance", DEFAULT_TOLERANCE),
    )
    return result


def run_all(
    cases: list[dict[str, Any]],
    provider: str | None = None,
    workers: int = 4,
) -> list[CaseResult]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda case: run_case(case, provider), cases))


def accuracy(results: list[CaseResult], lang: str | None = None) -> float:
    scoped = [r for r in results if lang is None or r.lang == lang]
    if not scoped:
        return 0.0
    return sum(r.passed for r in scoped) / len(scoped)


def _scoreboard(results: list[CaseResult], provider: str) -> str:
    lines = ["", f"scoreboard — provider: {provider}", "-" * 58]
    for lang in ("en", "ar"):
        scoped = [r for r in results if r.lang == lang]
        if not scoped:
            continue
        passed = sum(r.passed for r in scoped)
        latencies = sorted(r.latency_ms for r in scoped)
        lines.append(
            f"  {lang}       {passed:>2}/{len(scoped):<2}  "
            f"{accuracy(results, lang):>6.1%}   median {latencies[len(latencies) // 2] / 1000:.1f}s"
        )
    passed = sum(r.passed for r in results)
    retried = sum(r.attempts > 1 for r in results)
    lines.append("-" * 58)
    lines.append(f"  overall  {passed:>2}/{len(results):<2}  {accuracy(results):>6.1%}")
    lines.append(f"  self-healed on retry: {retried}/{len(results)} runs needed a second attempt")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", help="anthropic or ollama; defaults to LLM_PROVIDER")
    parser.add_argument("--lang", choices=["en", "ar"], help="run one language only")
    parser.add_argument("--case", action="append", dest="cases", help="run one case id (repeatable)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json", dest="json_path", help="write the full report here")
    parser.add_argument(
        "--min-en", type=float, default=DEFAULT_MIN_ACCURACY["en"], help="exit non-zero below this"
    )
    parser.add_argument("--min-ar", type=float, default=DEFAULT_MIN_ACCURACY["ar"])
    args = parser.parse_args()

    cases = load_cases(args.lang, args.cases)
    if not cases:
        parser.error("no cases matched")

    provider = args.provider or "default"
    print(f"running {len(cases)} golden questions against {provider}...\n")
    results = run_all(cases, args.provider, args.workers)

    for result in results:
        mark = "PASS" if result.passed else "FAIL"
        print(f"  {mark}  {result.case_id:<32} {result.latency_ms / 1000:>5.1f}s  {result.reason}")

    print(_scoreboard(results, provider))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(
                {
                    "provider": provider,
                    "accuracy": {"overall": accuracy(results), "en": accuracy(results, "en"), "ar": accuracy(results, "ar")},
                    "cases": [
                        {
                            "id": r.case_id,
                            "lang": r.lang,
                            "question": r.question,
                            "passed": r.passed,
                            "reason": r.reason,
                            "sql": r.sql,
                            "attempts": r.attempts,
                            "latency_ms": r.latency_ms,
                        }
                        for r in results
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"\nreport written to {args.json_path}")

    below = [
        f"{lang} {accuracy(results, lang):.1%} < {minimum:.0%}"
        for lang, minimum in (("en", args.min_en), ("ar", args.min_ar))
        if any(r.lang == lang for r in results) and accuracy(results, lang) < minimum
    ]
    if below:
        print("\nbelow target: " + ", ".join(below))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

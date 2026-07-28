from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.services.chart_spec import build_chart_spec
from app.services.executor import ExecResult


def _result(columns: list[str], rows: list[list]) -> ExecResult:
    return ExecResult(columns=columns, rows=rows, row_count=len(rows), truncated=False)


def _months(n: int) -> list[list]:
    return [[dt.date(2025, m, 1), Decimal(100 + m)] for m in range(1, n + 1)]


def test_single_numeric_cell_is_a_stat() -> None:
    spec = build_chart_spec(_result(["total_aed"], [[Decimal("203000000000")]]))
    assert spec.type == "stat"


def test_stat_reports_the_value_column() -> None:
    spec = build_chart_spec(_result(["total_aed"], [[Decimal("42")]]))
    assert spec.y_keys == ["total_aed"]


def test_stat_has_no_x_axis() -> None:
    spec = build_chart_spec(_result(["total_aed"], [[Decimal("42")]]))
    assert spec.x_key is None


def test_single_non_numeric_cell_is_not_charted() -> None:
    assert build_chart_spec(_result(["name_en"], [["Yas Island"]])) is None


def test_date_column_with_a_measure_is_a_line() -> None:
    spec = build_chart_spec(_result(["month", "index_value"], _months(12)))
    assert spec.type == "line"


def test_line_uses_the_date_column_as_x() -> None:
    spec = build_chart_spec(_result(["month", "index_value"], _months(12)))
    assert spec.x_key == "month"


def test_line_uses_the_numeric_column_as_y() -> None:
    spec = build_chart_spec(_result(["month", "index_value"], _months(12)))
    assert spec.y_keys == ["index_value"]


def test_line_accepts_datetime_values() -> None:
    rows = [[dt.datetime(2025, 1, 1, 12), Decimal("1")], [dt.datetime(2025, 2, 1, 12), Decimal("2")]]
    assert build_chart_spec(_result(["ts", "n"], rows)).type == "line"


def test_line_is_used_even_beyond_the_bar_row_ceiling() -> None:
    spec = build_chart_spec(_result(["month", "index_value"], _months(12) * 8))
    assert spec.type == "line"


def test_line_carries_every_measure_column() -> None:
    rows = [[dt.date(2025, 1, 1), Decimal("1"), Decimal("2")]]
    spec = build_chart_spec(_result(["month", "sale_index", "rent_index"], rows))
    assert spec.y_keys == ["sale_index", "rent_index"]


def test_category_with_a_measure_is_a_bar() -> None:
    rows = [["Yas Island", Decimal("9")], ["Saadiyat Island", Decimal("8")]]
    assert build_chart_spec(_result(["name_en", "total_aed"], rows)).type == "bar"


def test_bar_uses_the_category_column_as_x() -> None:
    rows = [["Yas Island", Decimal("9")], ["Saadiyat Island", Decimal("8")]]
    assert build_chart_spec(_result(["name_en", "total_aed"], rows)).x_key == "name_en"


def test_too_many_categories_are_not_charted() -> None:
    rows = [[f"community {i}", Decimal(i)] for i in range(25)]
    assert build_chart_spec(_result(["name_en", "total_aed"], rows)) is None


def test_empty_result_is_not_charted() -> None:
    assert build_chart_spec(_result(["name_en", "total_aed"], [])) is None


def test_result_without_a_measure_is_not_charted() -> None:
    rows = [["Yas Island", "Abu Dhabi City"], ["Liwa", "Al Dhafra Region"]]
    assert build_chart_spec(_result(["community", "municipality"], rows)) is None


def test_result_without_a_dimension_is_not_charted() -> None:
    rows = [[Decimal("1"), Decimal("2")], [Decimal("3"), Decimal("4")]]
    assert build_chart_spec(_result(["a", "b"], rows)) is None


def test_null_only_column_does_not_become_a_measure() -> None:
    rows = [["Yas Island", None], ["Liwa", None]]
    assert build_chart_spec(_result(["name_en", "total_aed"], rows)) is None


def test_leading_nulls_do_not_hide_the_column_kind() -> None:
    rows = [["Yas Island", None], ["Liwa", Decimal("3")]]
    assert build_chart_spec(_result(["name_en", "total_aed"], rows)).type == "bar"


def test_booleans_are_not_treated_as_measures() -> None:
    rows = [["Yas Island", True], ["Liwa", False]]
    assert build_chart_spec(_result(["name_en", "is_offplan"], rows)) is None


def test_spec_carries_a_human_readable_title() -> None:
    rows = [["Yas Island", Decimal("9")]]
    spec = build_chart_spec(_result(["name_en", "total_sales_value_aed"], rows))
    assert spec.title == "Total sales value AED by name en"

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.executor import ExecResult

# A bar chart with more categories than this is unreadable; leave it as a table.
MAX_BAR_CATEGORIES = 20

_ACRONYMS = {"aed", "sqm", "yoy", "ytd", "fdi", "gcc", "uae", "id", "avg"}


@dataclass
class ChartSpec:
    type: str
    x_key: str | None
    y_keys: list[str]
    title: str
    category_keys: list[str] = field(default_factory=list)


def _first_value(rows: list[list[Any]], index: int) -> Any:
    return next((row[index] for row in rows if row[index] is not None), None)


def _is_numeric(value: Any) -> bool:
    # bool is an int subclass, but a flag column is a dimension, not a measure
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _is_temporal(value: Any) -> bool:
    return isinstance(value, (dt.date, dt.datetime))


def _humanize(column: str) -> str:
    words = [
        word.upper() if word.lower() in _ACRONYMS else word
        for word in column.split("_")
        if word
    ]
    return " ".join(words) if words else column


def _title(text: str) -> str:
    # capitalize the sentence, never the acronyms inside it
    return text[:1].upper() + text[1:]


def _category_keys(result: ExecResult, dimensions: list[str]) -> list[str]:
    indices = {col: result.columns.index(col) for col in dimensions}
    selected: list[str] = []
    remaining = list(dimensions)
    # Refine categories without an exponential search through column subsets.
    while remaining:
        def distinct_count(column: str) -> int:
            keys = selected + [column]
            return len({tuple(row[indices[key]] for key in keys) for row in result.rows})

        best = max(remaining, key=distinct_count)
        count = distinct_count(best)
        selected.append(best)
        remaining.remove(best)
        if count == len(result.rows):
            return [col for col in dimensions if col in selected]
    return []


def requested_chart_type(question: str) -> str | None:
    patterns = {
        'table': r'\b(?:table only|as a table|no chart)\b|جدول فقط|بدون رسم',
        'bar': r'\bbar (?:chart|graph)\b|رسم (?:بياني )?بالأعمدة|مخطط أعمدة',
        'line': r'\bline (?:chart|graph)\b|رسم (?:بياني )?خطي|مخطط خطي',
        'unsupported': r'\b(?:pie|scatter|donut|doughnut|area) (?:chart|plot|graph)\b|مخطط دائري',
    }
    return next((kind for kind, pattern in patterns.items() if re.search(pattern, question, re.I)), None)


def chart_request_note(preference: str | None, chart: ChartSpec | None, language: str) -> str | None:
    if preference is None or preference == 'table' or (chart and chart.type == preference):
        return None
    return ('نوع الرسم المطلوب غير متاح لهذه النتيجة؛ تظهر البيانات باستخدام العرض المناسب المتاح.'
            if language == 'ar' else 'The requested chart is unavailable for this result; the data uses the available suitable display.')


def build_chart_spec(result: ExecResult, preference: str | None = None) -> ChartSpec | None:
    """Pick a chart for a result set, or None when a table says it better."""
    if preference == 'table' or not result.rows or not result.columns:
        return None

    samples = [_first_value(result.rows, i) for i in range(len(result.columns))]
    years = [col for col in result.columns if re.fullmatch(r'(?:[a-z]+_)*year', col.lower())]
    measures = [col for col, value in zip(result.columns, samples) if _is_numeric(value) and col not in years]
    temporal = [col for col, value in zip(result.columns, samples) if _is_temporal(value) or col in years]

    if not measures:
        return None

    if len(result.columns) == 1 and result.row_count == 1:
        column = result.columns[0]
        return ChartSpec(type="stat", x_key=None, y_keys=[column], title=_title(_humanize(column)))

    if temporal:
        x_key = temporal[0]
        index = result.columns.index(x_key)
        if len({row[index] for row in result.rows}) != len(result.rows):
            return None
        # One populated value is a comparison detail, not a time series.
        measures = [
            col for col in measures
            if sum(_is_numeric(row[result.columns.index(col)]) for row in result.rows) >= 2
        ]
        if not measures:
            return None
        return ChartSpec(
            type="bar" if preference == 'bar' and result.row_count <= MAX_BAR_CATEGORIES else "line",
            x_key=x_key,
            y_keys=measures,
            title=_title(f"{_humanize(measures[0])} over {_humanize(x_key)}"),
        )

    dimensions = [
        col
        for col, value in zip(result.columns, samples)
        if col not in measures and col not in temporal and value is not None
    ]
    if dimensions and result.row_count <= MAX_BAR_CATEGORIES:
        # A category must identify the row: constant municipality labels hide
        # district/layout segments, and duplicate categories imply aggregation.
        category_keys = _category_keys(result, dimensions)
        if not category_keys:
            return None
        x_key = category_keys[0]
        return ChartSpec(
            type="bar",
            x_key=x_key,
            y_keys=measures,
            title=_title(f"{_humanize(measures[0])} by {' / '.join(_humanize(key) for key in category_keys)}"),
            category_keys=category_keys,
        )

    return None

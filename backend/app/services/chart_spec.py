from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
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


def build_chart_spec(result: ExecResult) -> ChartSpec | None:
    """Pick a chart for a result set, or None when a table says it better."""
    if not result.rows or not result.columns:
        return None

    samples = [_first_value(result.rows, i) for i in range(len(result.columns))]
    measures = [col for col, value in zip(result.columns, samples) if _is_numeric(value)]
    temporal = [col for col, value in zip(result.columns, samples) if _is_temporal(value)]

    if not measures:
        return None

    if len(result.columns) == 1 and result.row_count == 1:
        column = result.columns[0]
        return ChartSpec(type="stat", x_key=None, y_keys=[column], title=_title(_humanize(column)))

    if temporal:
        x_key = temporal[0]
        return ChartSpec(
            type="line",
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
        x_key = dimensions[0]
        return ChartSpec(
            type="bar",
            x_key=x_key,
            y_keys=measures,
            title=_title(f"{_humanize(measures[0])} by {_humanize(x_key)}"),
        )

    return None

"""Surfacing CHECK-constraint values in the schema context.

Without these the model has to guess categorical literals, and it guesses
wrong — 'Sales' instead of 'sale' returns an empty result with no error.
"""

from __future__ import annotations

from app.services.retrieval.lexical import build_table_descriptor
from app.services.schema_introspector import parse_allowed_values


def _check(sqltext: str) -> list[dict]:
    return [{"name": "c", "sqltext": sqltext, "comment": None}]


def test_parses_the_postgres_any_array_form() -> None:
    constraints = _check("index_type = ANY (ARRAY['sale'::text, 'rent'::text])")
    assert parse_allowed_values(constraints) == {"index_type": ["sale", "rent"]}


def test_parses_the_plain_in_form() -> None:
    constraints = _check("sale_type IN ('sale', 'resale')")
    assert parse_allowed_values(constraints) == {"sale_type": ["sale", "resale"]}


def test_parses_a_parenthesised_constraint() -> None:
    constraints = _check("(buyer_origin = ANY (ARRAY['UAE'::text, 'GCC'::text]))")
    assert parse_allowed_values(constraints) == {"buyer_origin": ["UAE", "GCC"]}


def test_collects_several_constraints() -> None:
    constraints = _check("a = ANY (ARRAY['x'::text])") + _check("b IN ('y')")
    assert parse_allowed_values(constraints) == {"a": ["x"], "b": ["y"]}


def test_ignores_range_checks_that_carry_no_literals() -> None:
    assert parse_allowed_values(_check("price_aed > 0")) == {}


def test_ignores_unparseable_constraints() -> None:
    assert parse_allowed_values(_check("something entirely unexpected")) == {}


def test_handles_no_constraints() -> None:
    assert parse_allowed_values([]) == {}


def test_descriptor_lists_the_allowed_values() -> None:
    table = {
        "name": "price_indices",
        "columns": [
            {"name": "month", "type": "DATE", "nullable": False},
            {
                "name": "index_type",
                "type": "TEXT",
                "nullable": False,
                "allowed_values": ["sale", "rent"],
            },
        ],
        "foreign_keys": [],
    }
    assert build_table_descriptor(table) == "price_indices(month, index_type IN ('sale','rent'))"


def test_descriptor_is_unchanged_for_columns_without_allowed_values() -> None:
    table = {
        "name": "communities",
        "columns": [{"name": "id", "type": "INTEGER", "nullable": False}],
        "foreign_keys": [],
    }
    assert build_table_descriptor(table) == "communities(id)"

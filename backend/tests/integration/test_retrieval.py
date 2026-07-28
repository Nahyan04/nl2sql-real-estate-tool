"""Alias-driven retrieval against the real seeded schema.

These live in integration rather than unit because the alias map is only
meaningful against the actual real-estate tables it names.

Assertions target `score_tables` rather than `retrieve`: this schema is small
and densely joined through `communities`, so FK expansion pulls back nearly
every table whatever the question. Ranking, not membership, is what the alias
map actually controls — and ranking is what survives the serializer's budget.
"""

from __future__ import annotations

import pytest

from app.core.aliases import load_default_aliases
from app.core.database import get_engine
from app.services.retrieval.lexical import retrieve, score_tables
from app.services.schema_introspector import introspect_schema


@pytest.fixture(scope="module")
def schema() -> dict:
    engine = get_engine()
    try:
        return introspect_schema(engine)
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def aliases() -> dict[str, list[str]]:
    return load_default_aliases()


def _ranked(question: str, schema: dict, aliases: dict, top: int = 3) -> list[str]:
    """Tables that actually matched, best first — zero-score tables are noise."""
    return [name for name, score in score_tables(question, schema, aliases)[:top] if score > 0]


def test_alias_map_only_names_tables_that_exist(schema, aliases) -> None:
    known = {t["name"] for t in schema["tables"]}
    referenced = {table for tables in aliases.values() for table in tables}
    assert referenced <= known, f"alias map references unknown tables: {referenced - known}"


def test_alias_map_covers_every_fact_table(schema, aliases) -> None:
    referenced = {table for tables in aliases.values() for table in tables}
    assert {"transactions", "rental_contracts", "mortgages", "price_indices"} <= referenced


def test_english_rent_question_ranks_rental_contracts(schema, aliases) -> None:
    assert "rental_contracts" in _ranked("average rent in Al Reem", schema, aliases, top=2)


def test_english_rent_question_ranks_the_named_community(schema, aliases) -> None:
    assert "communities" in _ranked("average rent in Al Reem", schema, aliases, top=2)


def test_arabic_rent_question_ranks_rental_contracts(schema, aliases) -> None:
    question = "ما هو متوسط الإيجار السنوي للشقق في جزيرة الريم؟"
    assert "rental_contracts" in _ranked(question, schema, aliases)


def test_english_sales_question_ranks_transactions(schema, aliases) -> None:
    question = "total sales value by community this year"
    assert "transactions" in _ranked(question, schema, aliases, top=2)


def test_arabic_sales_question_ranks_transactions(schema, aliases) -> None:
    assert "transactions" in _ranked("إجمالي قيمة المبيعات في جزيرة ياس", schema, aliases, top=2)


def test_english_mortgage_question_ranks_mortgages_first(schema, aliases) -> None:
    assert _ranked("total mortgage value last year", schema, aliases, top=1) == ["mortgages"]


def test_arabic_mortgage_question_ranks_mortgages_first(schema, aliases) -> None:
    assert _ranked("ما هو إجمالي قيمة الرهن العقاري؟", schema, aliases, top=1) == ["mortgages"]


def test_english_broker_question_ranks_brokers_first(schema, aliases) -> None:
    question = "how many licensed brokers are there"
    assert _ranked(question, schema, aliases, top=1) == ["brokers"]


def test_arabic_broker_question_ranks_brokers_first(schema, aliases) -> None:
    assert _ranked("كم عدد الوسطاء العقاريين؟", schema, aliases, top=1) == ["brokers"]


def test_english_price_index_question_ranks_price_indices(schema, aliases) -> None:
    question = "how has the apartment sale price index moved"
    assert "price_indices" in _ranked(question, schema, aliases, top=2)


def test_arabic_price_index_question_ranks_price_indices(schema, aliases) -> None:
    assert "price_indices" in _ranked("مؤشر أسعار بيع الشقق", schema, aliases, top=2)


def test_developer_question_ranks_developers_and_projects(schema, aliases) -> None:
    question = "which developer sold the most projects"
    assert {"developers", "projects"} <= set(_ranked(question, schema, aliases))


@pytest.mark.parametrize(
    "question",
    [
        "ما هو متوسط الإيجار السنوي للشقق في جزيرة الريم؟",
        "كم عدد الوسطاء العقاريين؟",
        "مؤشر أسعار بيع الشقق",
    ],
)
def test_arabic_questions_score_nothing_without_the_alias_map(schema, question) -> None:
    """The tokenizer is ASCII-only, so Arabic retrieval rests entirely on aliases."""
    assert _ranked(question, schema, {}) == []


@pytest.mark.parametrize(
    "table,column,expected",
    [
        ("price_indices", "index_type", ["sale", "rent"]),
        ("transactions", "sale_type", ["sale", "resale"]),
        ("transactions", "buyer_origin", ["UAE", "GCC", "Foreign"]),
        ("rental_contracts", "contract_type", ["new", "renewal"]),
        (
            "mortgages",
            "lender_type",
            ["local_bank", "international_bank", "finance_company"],
        ),
    ],
)
def test_categorical_columns_expose_their_allowed_values(
    schema, table: str, column: str, expected: list[str]
) -> None:
    columns = next(t for t in schema["tables"] if t["name"] == table)["columns"]
    assert next(c for c in columns if c["name"] == column)["allowed_values"] == expected


def test_serialized_schema_carries_the_categorical_values(schema, aliases) -> None:
    from app.services.schema_serializer import serialize_schema

    question = "how has the villa sale price index moved"
    selected = retrieve(question, schema, aliases=aliases, top_n=5)
    assert "index_type IN ('sale','rent')" in serialize_schema(selected)


def test_retrieve_fk_expands_rental_contracts_to_its_dimensions(schema, aliases) -> None:
    question = "average rent in Al Reem"
    selected = {t["name"] for t in retrieve(question, schema, aliases=aliases, top_n=2)}
    assert {"rental_contracts", "communities", "property_types", "layouts"} <= selected

from __future__ import annotations

import datetime as dt

from app.core.prompt_builder import MAX_PROMPT_CHARS, build_system_prompt, build_user_prompt


def test_system_prompt_names_the_postgres_dialect() -> None:
    assert "PostgreSQL" in build_system_prompt()


def test_system_prompt_restricts_to_read_only_statements() -> None:
    prompt = build_system_prompt()
    assert "SELECT" in prompt and "WITH" in prompt
    assert "Never write INSERT, UPDATE, DELETE" in prompt


def test_system_prompt_asks_for_sql_tags() -> None:
    assert "<sql>" in build_system_prompt()


def test_system_prompt_states_todays_date() -> None:
    assert "2026-03-04" in build_system_prompt(today=dt.date(2026, 3, 4))


def test_system_prompt_defaults_to_the_current_date() -> None:
    assert dt.date.today().isoformat() in build_system_prompt()


def test_system_prompt_mentions_arabic_questions() -> None:
    assert "Arabic" in build_system_prompt()


def test_system_prompt_keeps_identifiers_ascii_for_arabic_questions() -> None:
    assert "ASCII" in build_system_prompt()


def test_system_prompt_matches_place_names_with_ilike() -> None:
    """`name_ar = 'مدينة خليفة'` returns zero rows against 'مدينة خليفة أ' and nothing
    in the pipeline flags an empty result, so the prompt has to rule out equality."""
    prompt = build_system_prompt()
    assert "ILIKE" in prompt
    assert "never with =" in prompt


def test_system_prompt_resolves_place_names_at_the_community_level() -> None:
    assert "is a community unless" in build_system_prompt()


def test_system_prompt_lists_the_property_type_values() -> None:
    prompt = build_system_prompt()
    for value in ("'Apartment'", "'Villa'", "'Office'", "'Retail'", "'Duplex'"):
        assert value in prompt


def test_system_prompt_points_bedroom_counts_at_the_layouts_column() -> None:
    assert "layouts.bedrooms" in build_system_prompt()


def test_user_prompt_includes_the_schema_context() -> None:
    prompt = build_user_prompt("how many communities", "communities(id, name_en)")
    assert "communities(id, name_en)" in prompt


def test_user_prompt_includes_the_question() -> None:
    prompt = build_user_prompt("how many communities", "communities(id, name_en)")
    assert "how many communities" in prompt


def test_user_prompt_includes_retry_feedback_when_given() -> None:
    prompt = build_user_prompt("q", "schema", feedback="Previous attempt was rejected.")
    assert "Previous attempt was rejected." in prompt


def test_user_prompt_omits_the_feedback_section_when_absent() -> None:
    assert "Previous attempt" not in build_user_prompt("q", "schema")


def test_user_prompt_stays_within_the_char_budget() -> None:
    prompt = build_user_prompt("how many communities", "x" * 50_000)
    assert len(prompt) + len(build_system_prompt()) <= MAX_PROMPT_CHARS


def test_oversized_schema_is_trimmed_but_the_question_survives() -> None:
    """The question sits after the schema — a naive tail-trim would eat it."""
    prompt = build_user_prompt("how many communities", "x" * 50_000)
    assert "how many communities" in prompt


def test_oversized_schema_is_trimmed_but_feedback_survives() -> None:
    prompt = build_user_prompt("q", "x" * 50_000, feedback="Previous attempt was rejected.")
    assert "Previous attempt was rejected." in prompt

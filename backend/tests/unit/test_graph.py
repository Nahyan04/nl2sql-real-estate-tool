from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.services.graph import (
    EMPTY_RESPONSE,
    EXECUTION_ERROR,
    MAX_ATTEMPTS,
    PARSE_ERROR,
    UNSAFE_SQL,
    VALIDATION_ERROR,
    run_pipeline,
)

GOOD_SQL = "<sql>SELECT name_en FROM communities ORDER BY id</sql>"


class FakeChatModel:
    """Replays canned responses in order so each retry path can be forced.

    The same model serves both graph LLM nodes, so prompts are split by shape:
    a SQL-generation prompt leads with the schema, a synthesis prompt does not.
    """

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def invoke(self, messages, **kwargs) -> AIMessage:
        self.prompts.append(messages[-1].content)
        return AIMessage(content=self._responses.pop(0) if self._responses else "")

    @property
    def generation_prompts(self) -> list[str]:
        return [p for p in self.prompts if p.startswith("Schema:")]

    @property
    def synthesis_prompts(self) -> list[str]:
        return [p for p in self.prompts if not p.startswith("Schema:")]


def _run(engine, *responses: str):
    model = FakeChatModel(*responses)
    state = run_pipeline("how many communities are there", chat_model=model, engine=engine, engine_ro=engine)
    return state, model


def _exhaust(engine, response: str):
    state, _ = _run(engine, *([response] * MAX_ATTEMPTS))
    return state


def test_happy_path_returns_the_generated_sql(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["sql"] == "SELECT name_en FROM communities ORDER BY id"


def test_happy_path_returns_executed_rows(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["exec_result"].rows == [["Yas Island"], ["Al Reem Island"]]


def test_happy_path_returns_column_names(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["exec_result"].columns == ["name_en"]


def test_happy_path_takes_a_single_attempt(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["attempts"] == 1


def test_happy_path_reports_no_failure(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["failure"] is None


def test_schema_context_is_retrieved(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert "communities" in state["schema_context"]


def test_tables_used_is_populated(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert "communities" in state["tables_used"]


def test_latency_is_recorded(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL)
    assert state["latency_ms"] >= 0


def test_unsafe_sql_is_classified(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "<sql>SELECT * INTO copies FROM communities</sql>")
    assert state["failure"]["type"] == UNSAFE_SQL


def test_unparseable_response_is_classified(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "I am afraid I cannot help with that question.")
    assert state["failure"]["type"] == PARSE_ERROR


def test_empty_response_is_classified(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "")
    assert state["failure"]["type"] == EMPTY_RESPONSE


def test_sql_shaped_but_mutating_response_is_classified_as_validation_error(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "<sql>DELETE FROM communities</sql>")
    assert state["failure"]["type"] == VALIDATION_ERROR


def test_execution_error_is_classified(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "<sql>SELECT no_such_column FROM communities</sql>")
    assert state["failure"]["type"] == EXECUTION_ERROR


@pytest.mark.parametrize(
    "bad",
    [
        "<sql>SELECT * INTO copies FROM communities</sql>",
        "I am afraid I cannot help with that question.",
        "",
        "<sql>DELETE FROM communities</sql>",
        "<sql>SELECT no_such_column FROM communities</sql>",
    ],
)
def test_pipeline_recovers_on_the_retry_after_any_failure(sqlite_engine, bad: str) -> None:
    state, _ = _run(sqlite_engine, bad, GOOD_SQL)
    assert state["sql"] == "SELECT name_en FROM communities ORDER BY id"
    assert state["failure"] is None
    assert state["attempts"] == 2


def test_retry_sends_feedback_back_to_the_model(sqlite_engine) -> None:
    _, model = _run(sqlite_engine, "<sql>DELETE FROM communities</sql>", GOOD_SQL)
    assert len(model.generation_prompts) == 2
    assert "Previous attempt" in model.generation_prompts[1]


def test_first_attempt_carries_no_feedback(sqlite_engine) -> None:
    _, model = _run(sqlite_engine, GOOD_SQL)
    assert "Previous attempt" not in model.generation_prompts[0]


def test_execution_failure_feedback_quotes_the_database_error(sqlite_engine) -> None:
    _, model = _run(sqlite_engine, "<sql>SELECT no_such_column FROM communities</sql>", GOOD_SQL)
    assert "no_such_column" in model.generation_prompts[1]


def test_pipeline_gives_up_after_max_attempts(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "")
    assert state["attempts"] == MAX_ATTEMPTS


def test_pipeline_stops_calling_the_model_once_exhausted(sqlite_engine) -> None:
    model = FakeChatModel(*([""] * 10))
    run_pipeline("q", chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert len(model.generation_prompts) == MAX_ATTEMPTS


def test_exhausted_pipeline_returns_no_exec_result(sqlite_engine) -> None:
    assert _exhaust(sqlite_engine, "")["exec_result"] is None


def test_exhausted_pipeline_returns_no_sql(sqlite_engine) -> None:
    assert _exhaust(sqlite_engine, "I cannot help.")["sql"] is None


def test_failure_carries_a_detail_message(sqlite_engine) -> None:
    state = _exhaust(sqlite_engine, "<sql>SELECT no_such_column FROM communities</sql>")
    assert state["failure"]["detail"]


CHARTABLE_SQL = "<sql>SELECT name_en, id FROM communities ORDER BY id</sql>"
NARRATIVE = "Yas Island and Al Reem Island are the two communities."


def test_successful_run_returns_a_synthesized_answer(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL, NARRATIVE)
    assert state["answer"] == NARRATIVE


def test_synthesis_is_given_the_executed_rows(sqlite_engine) -> None:
    _, model = _run(sqlite_engine, GOOD_SQL, NARRATIVE)
    assert "Yas Island" in model.synthesis_prompts[0]


def test_synthesis_runs_once_per_successful_request(sqlite_engine) -> None:
    _, model = _run(sqlite_engine, GOOD_SQL, NARRATIVE)
    assert len(model.synthesis_prompts) == 1


def test_successful_run_returns_a_chart_spec(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, CHARTABLE_SQL, NARRATIVE)
    assert state["chart"].type == "bar"
    assert state["chart"].x_key == "name_en"


def test_chart_is_absent_when_the_result_shape_does_not_suit_one(sqlite_engine) -> None:
    state, _ = _run(sqlite_engine, GOOD_SQL, NARRATIVE)
    assert state["chart"] is None


def test_exhausted_pipeline_never_reaches_synthesis(sqlite_engine) -> None:
    model = FakeChatModel(*([""] * MAX_ATTEMPTS))
    state = run_pipeline("q", chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert model.synthesis_prompts == []
    assert state["answer"] == ""
    assert state["chart"] is None


def test_dry_run_returns_validated_sql_without_executing(sqlite_engine) -> None:
    model = FakeChatModel(GOOD_SQL)
    state = run_pipeline(
        "q", dry_run=True, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine
    )
    assert state["sql"] == "SELECT name_en FROM communities ORDER BY id"
    assert state["exec_result"] is None
    assert state["failure"] is None


def test_dry_run_skips_synthesis_and_charting(sqlite_engine) -> None:
    model = FakeChatModel(GOOD_SQL)
    state = run_pipeline(
        "q", dry_run=True, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine
    )
    assert model.synthesis_prompts == []
    assert state["answer"] == ""
    assert state["chart"] is None


def test_dry_run_still_retries_unsafe_sql(sqlite_engine) -> None:
    model = FakeChatModel("<sql>DROP TABLE communities</sql>", GOOD_SQL)
    state = run_pipeline(
        "q", dry_run=True, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine
    )
    assert state["attempts"] == 2
    assert state["sql"] == "SELECT name_en FROM communities ORDER BY id"


class ExplodingSynthesis(FakeChatModel):
    def invoke(self, messages, **kwargs):
        if not messages[-1].content.startswith("Schema:"):
            raise RuntimeError("provider unavailable")
        return super().invoke(messages, **kwargs)


def test_synthesis_failure_still_returns_sql_and_rows(sqlite_engine) -> None:
    model = ExplodingSynthesis(CHARTABLE_SQL)
    state = run_pipeline("q", chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state["sql"] == "SELECT name_en, id FROM communities ORDER BY id"
    assert state["exec_result"].row_count == 2
    assert state["answer"] == ""


def test_synthesis_failure_does_not_retry_sql_generation(sqlite_engine) -> None:
    model = ExplodingSynthesis(CHARTABLE_SQL)
    run_pipeline("q", chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert len(model.generation_prompts) == 1


def test_synthesis_failure_still_produces_a_chart(sqlite_engine) -> None:
    model = ExplodingSynthesis(CHARTABLE_SQL)
    state = run_pipeline("q", chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state["chart"].type == "bar"

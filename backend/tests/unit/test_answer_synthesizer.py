from __future__ import annotations

from decimal import Decimal

from langchain_core.messages import AIMessage

from app.services.answer_synthesizer import MAX_ANSWER_ROWS, synthesize_answer
from app.services.executor import ExecResult

QUESTION = "top communities by total sales value"
SQL = "SELECT name_en, SUM(price_aed) FROM transactions GROUP BY name_en"


class FakeChatModel:
    def __init__(self, reply: str | list = "Yas Island led with AED 9.35 billion.") -> None:
        self._reply = reply
        self.prompts: list[str] = []

    def invoke(self, messages, **kwargs) -> AIMessage:
        self.prompts.append("\n".join(str(m.content) for m in messages))
        return AIMessage(content=self._reply)


def _result(rows: list[list], truncated: bool = False) -> ExecResult:
    return ExecResult(
        columns=["name_en", "total_aed"],
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


ROWS = [["Yas Island", Decimal("9348147541.07")], ["Saadiyat Island", Decimal("8190614235.85")]]


def test_returns_the_models_answer() -> None:
    answer = synthesize_answer(QUESTION, SQL, _result(ROWS), FakeChatModel())
    assert answer == "Yas Island led with AED 9.35 billion."


def test_flattens_content_blocks_from_hosted_providers() -> None:
    model = FakeChatModel([{"type": "text", "text": "Yas Island led."}])
    assert synthesize_answer(QUESTION, SQL, _result(ROWS), model) == "Yas Island led."


def test_prompt_includes_the_question() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert QUESTION in model.prompts[0]


def test_prompt_includes_the_sql() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert SQL in model.prompts[0]


def test_prompt_includes_the_result_values() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert "Yas Island" in model.prompts[0]
    assert "9348147541.07" in model.prompts[0]


def test_prompt_includes_the_column_names() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert "total_aed" in model.prompts[0]


def test_prompt_caps_the_rows_fed_to_the_model() -> None:
    rows = [[f"community {i}", Decimal(i)] for i in range(200)]
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(rows), model)
    assert "community 199" not in model.prompts[0]
    assert f"community {MAX_ANSWER_ROWS - 1}" in model.prompts[0]


def test_prompt_says_how_many_rows_were_withheld() -> None:
    rows = [[f"community {i}", Decimal(i)] for i in range(200)]
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(rows), model)
    assert str(200 - MAX_ANSWER_ROWS) in model.prompts[0]


def test_prompt_flags_a_truncated_result_set() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS, truncated=True), model)
    assert "truncated" in model.prompts[0].lower()


def test_prompt_does_not_flag_truncation_when_complete() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert "truncated" not in model.prompts[0].lower()


def test_prompt_asks_for_the_questions_language() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result(ROWS), model)
    assert "same language" in model.prompts[0].lower()


def test_empty_result_still_produces_an_answer() -> None:
    model = FakeChatModel("No transactions matched that filter.")
    answer = synthesize_answer(QUESTION, SQL, _result([]), model)
    assert answer == "No transactions matched that filter."


def test_empty_result_tells_the_model_there_were_no_rows() -> None:
    model = FakeChatModel()
    synthesize_answer(QUESTION, SQL, _result([]), model)
    assert "no rows" in model.prompts[0].lower()

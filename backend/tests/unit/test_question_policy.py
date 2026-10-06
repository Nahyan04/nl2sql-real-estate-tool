from __future__ import annotations

import pytest

from app.services.question_policy import classify_question


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Which broker sold most homes in 2025?", "UNSUPPORTED"),
        ("Which developers had the highest sales value in 2025?", "UNSUPPORTED"),
    ],
)
def test_declines_unsupported_topics(question, code):
    assert classify_question(question).code == code


def test_explicit_source_backed_period_can_continue():
    assert classify_question("What were the latest sales?") is None
    assert classify_question("Show sales in Al Bateen in 2025") is None
    assert classify_question("What was the sales value in 2025?") is None
    assert classify_question("ما قيمة المبيعات لعام 2025؟") is None
    assert classify_question("كم قيمة المبيعات في منطقه البطين عام 2025؟") is None
    assert classify_question("What is the sales value in Al Bateen district in 2025?") is None
    assert classify_question("What was the exported sales value in the Al Bateen source district in 2025, across all municipalities?") is None
    assert classify_question("What is the indicative gross segment yield in Q2 2026?") is None
    assert classify_question("What is the net rental yield for an individual Al Reem Island apartment in Q2 2026?") is None
    assert classify_question("ما صافي العائد الإيجاري لشقة في Al Reem Island في الربع الثاني 2026؟") is None

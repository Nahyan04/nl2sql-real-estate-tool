from __future__ import annotations

import pytest

from app.services.question_policy import classify_question


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Which broker sold most homes in 2025?", "UNSUPPORTED"),
        ("Show sales in Al Bateen in 2025", "CLARIFICATION"),
        ("كم بلغت مبيعات البطين في 2025؟", "CLARIFICATION"),
        ("What were the latest sales?", "CLARIFICATION"),
        ("ما قيمة المبيعات هذا العام؟", "CLARIFICATION"),
    ],
)
def test_declines_unsupported_or_ambiguous_questions(question, code):
    assert classify_question(question).code == code


def test_explicit_source_backed_period_can_continue():
    assert classify_question("What was the sales value in 2025?") is None
    assert classify_question("ما قيمة المبيعات لعام 2025؟") is None
    assert classify_question("What is the indicative gross segment yield in Q2 2026?") is None
    assert classify_question("What is the net rental yield for an individual Al Reem Island apartment in Q2 2026?") is None
    assert classify_question("ما صافي العائد الإيجاري لشقة في Al Reem Island في الربع الثاني 2026؟") is None

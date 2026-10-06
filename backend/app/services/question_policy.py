"""Deterministic boundaries for questions the source contract cannot resolve."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDecision:
    code: str
    detail: str


_UNAVAILABLE_TOPIC = re.compile(
    r"\b(?:mortgages?|lenders?|brokers?|developers?|financ(?:e|ing|ed) sales)\b|"
    r"(?:رهن|رهون|تمويل|ممول|وسيط|وسطاء|بنك|مصرف|المطور|المطوّر)",
    re.IGNORECASE,
)


def classify_question(question: str) -> QuestionDecision | None:
    if _UNAVAILABLE_TOPIC.search(question):
        return QuestionDecision(
            "UNSUPPORTED",
            "Lender, broker, developer-ownership and financing records are outside the verified query surface.",
        )
    return None

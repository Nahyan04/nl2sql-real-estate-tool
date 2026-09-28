"""Deterministic boundaries for questions the source contract cannot resolve."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDecision:
    code: str
    detail: str


_UNAVAILABLE_TOPIC = re.compile(
    r"\b(?:mortgages?|lenders?|brokers?|developer ownership|financ(?:e|ing|ed) sales)\b|"
    r"(?:رهن|رهون|تمويل|ممول|وسيط|وسطاء|بنك|مصرف|المطور|المطوّر)",
    re.IGNORECASE,
)
_AMBIGUOUS_PLACE = re.compile(r"\bAl[ -]?Bateen\b|البطين", re.IGNORECASE)
_RELATIVE_PERIOD = re.compile(
    r"\b(?:latest|current|recent|this year|last year|year to date|ytd|past\s+\d+\s+(?:days?|months?|years?))\b|"
    r"(?:الأحدث|أحدث|الحالي|الحالية|هذا العام|السنة الماضية|آخر\s+\d+\s+(?:أيام|أشهر|سنوات))",
    re.IGNORECASE,
)


def classify_question(question: str) -> QuestionDecision | None:
    if _UNAVAILABLE_TOPIC.search(question):
        return QuestionDecision(
            "UNSUPPORTED",
            "Lender, broker, developer-ownership and financing records are outside the verified query surface.",
        )
    if _AMBIGUOUS_PLACE.search(question):
        return QuestionDecision(
            "CLARIFICATION",
            "Al Bateen is ambiguous in the source. Specify the source district or community and a verifiable geography.",
        )
    if _RELATIVE_PERIOD.search(question):
        return QuestionDecision(
            "CLARIFICATION",
            "Specify exact dates or a named reporting period. Source coverage differs, and a period-end label does not establish completeness.",
        )
    return None

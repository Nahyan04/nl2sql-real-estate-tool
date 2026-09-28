"""Resolve the language of one request before model and UI work begins."""

import re
from typing import Literal

Language = Literal["en", "ar"]
LanguageChoice = Literal["auto", "en", "ar"]

_ARABIC = re.compile(r"[\u0600-\u06FF]")


def resolve_language(question: str, choice: LanguageChoice = "auto") -> Language:
    if choice != "auto":
        return choice
    return "ar" if _ARABIC.search(question) else "en"


def answer_matches_language(answer: str, language: Language, source_names: tuple[str, ...] = ()) -> bool:
    # Source names and SQL acronyms can be Latin in an Arabic answer.
    prose = answer
    for name in source_names:
        prose = prose.replace(name, "")
    arabic_letters = len(re.findall(r"[\u0621-\u064A]", prose))
    if language == "en":
        return arabic_letters == 0
    if arabic_letters < 8:
        return False
    return not re.search(r"\b(?:the|is|are|was|were|from|with|and|for|totaled|amounted)\b", prose, re.IGNORECASE)

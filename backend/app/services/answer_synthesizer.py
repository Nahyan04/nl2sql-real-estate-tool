from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import message_text
from app.services.executor import ExecResult
from app.core.language import Language, answer_matches_language, resolve_language

# Caps the tokens spent on synthesis; the full result set still reaches the UI.
MAX_ANSWER_ROWS = 50

_SYSTEM_PROMPT = """\
You are a real-estate market analyst writing the answer to an analyst's question \
about Abu Dhabi property data. You are given the question, the SQL that was run, \
and the rows it returned.

Rules:
- Reply entirely in the requested answer language. Keep English source names and SQL acronyms as source data, but do not write explanatory English in Arabic answers or Arabic in English answers.
- Answer in 1-3 sentences. No preamble, no restating the question, no bullet lists.
- Cite the concrete numbers from the result. Never invent a figure that is not in the rows.
- Describe observed differences without assigning causes such as unit size, development premiums, demand or policy unless the SQL result directly measures those causes.
- Sales counts and values cover exported observations. Do not call them a complete Abu Dhabi market census.
- Format large amounts readably (for example AED 9.35 billion rather than 9348147541.07).
- Arabic answers use Western digits and Arabic scale words, the way UAE market reports are \
written: 92.1 مليار درهم, 1.4 مليون درهم, 102,888 درهم. Never use Eastern Arabic numerals.
- Names of places and projects stay exactly as the rows spell them, \
even in an Arabic answer. Never transliterate them.
- If SQL calculates yield from segment average annual rent and sale price, call it \
an indicative gross segment yield, not an individual property's realized or net return. \
If SQL weights rent by leased units, call it a leased-unit-weighted annual rent estimate.
- If the question asks for net or an individual property yield, give the computed gross \
segment estimate first, then briefly say net/property-specific yield needs property costs \
and the individual property's rent and sale price. Never call the proxy a net yield.
- If the result contains no rows, say plainly that no records matched.
- Describe percentage change, percentage-point change and index-level change with their correct units and denominator. A null ratio is unavailable, not zero.
- If only a sample of rows is supplied, describe conclusions as applying only to those rows. Do not claim a full-population result from a sample or a truncated query.
- Do not describe the SQL or mention that you were given a table.
"""


def _format_rows(result: ExecResult) -> str:
    if not result.rows:
        return "(no rows)"

    shown = result.rows[:MAX_ANSWER_ROWS]
    lines = [" | ".join(result.columns)]
    lines += [" | ".join("" if value is None else str(value) for value in row) for row in shown]

    withheld = result.row_count - len(shown)
    if withheld > 0:
        lines.append(f"(+{withheld} further rows not shown)")

    return "\n".join(lines)


def _numbers(text: str) -> list[str]:
    return sorted(re.findall(r"(?<!\w)\d[\d,]*(?:\.\d+)?%?", text))


def _sales_count_answer(question: str, result: ExecResult, language: Language) -> str | None:
    if result.columns != ["sales_observation_count"] or len(result.rows) != 1:
        return None
    count = result.rows[0][0]
    if not isinstance(count, int) or isinstance(count, bool):
        return None
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    arabic = language == "ar"
    if arabic:
        suffix = f" في عام {years[0]}" if len(years) == 1 else " للفترة المحددة"
        return f"تتضمن البيانات {count:,} سجل مبيعات مُصدّر{suffix}."
    suffix = f" in {years[0]}" if len(years) == 1 else " for the requested period"
    return f"The export contains {count:,} sales observations{suffix}."


def _format_aed(value: int | float | Decimal, arabic: bool) -> str:
    amount = float(value)
    if abs(amount) >= 1_000_000_000:
        number, scale = amount / 1_000_000_000, "مليار" if arabic else "billion"
    elif abs(amount) >= 1_000_000:
        number, scale = amount / 1_000_000, "مليون" if arabic else "million"
    else:
        number, scale = amount, ""
    formatted = f"{number:,.2f}" + (f" {scale}" if scale else "")
    return f"{formatted} درهم" if arabic else f"AED {formatted}"


def _source_result_answer(question: str, result: ExecResult, language: Language) -> str | None:
    count_answer = _sales_count_answer(question, result, language)
    if count_answer is not None:
        return count_answer
    arabic = language == "ar"
    ranking_question = re.search(r"\b(?:top|highest)\b|الأعلى", question, re.IGNORECASE)
    if (ranking_question and result.columns == ["district", "sales_value_aed"]
            and result.rows and not result.truncated):
        if not all(isinstance(row[0], str) and isinstance(row[1], (int, float, Decimal)) for row in result.rows):
            return None
        entries = [
            f"{row[0]} ({_format_aed(row[1], arabic)})"
            for row in result.rows
        ]
        if arabic:
            return "المناطق المصدرية الأعلى بقيمة المبيعات المصدّرة: " + "، ".join(entries) + "."
        return "The source districts with the highest exported sales value were " + ", ".join(entries) + "."
    residential_question = re.search(r"residential|السكنية|السكني", question, re.IGNORECASE)
    if (residential_question and result.columns in (["total_lease_value_aed"], ["residential_lease_value_aed"])
            and len(result.rows) == 1):
        value = result.rows[0][0]
        if not isinstance(value, (int, float, Decimal)):
            return None
        from app.services.rental_query_plans import lease_period_scope
        scope = lease_period_scope(question, arabic)
        if arabic:
            return f"بلغت قيمة الإيجارات السكنية الواردة في المصدر للفترة {scope} {_format_aed(value, True)}."
        return f"The source-labelled residential lease value for {scope} was {_format_aed(value, False)}."
    return None


def synthesize_answer(
    question: str,
    sql: str,
    result: ExecResult,
    invoke: Callable[[list[Any]], Any] | Any,
    *,
    language: Language | None = None,
) -> str:
    language = language or resolve_language(question)
    source_answer = _source_result_answer(question, result, language)
    if source_answer is not None:
        return source_answer
    notes = ""
    if result.truncated:
        notes = (
            "\nNote: the result was truncated at a row or response-size limit, so these are "
            "the first rows only — say so if it affects the answer.\n"
        )
    elif result.row_count > MAX_ANSWER_ROWS:
        notes = f"\nNote: only the first {MAX_ANSWER_ROWS} returned rows are provided for this explanation; do not claim a full-result conclusion.\n"

    human = (
        f"Question: {question}\n\n"
        f"SQL:\n{sql}\n\n"
        f"Result ({result.row_count} rows):\n{_format_rows(result)}\n{notes}"
    )

    language_name = "Arabic" if language == "ar" else "English"
    messages = [SystemMessage(content=f"{_SYSTEM_PROMPT}\nRequired answer language: {language_name}."), HumanMessage(content=human)]
    caller = invoke if callable(invoke) else invoke.invoke
    source_names = tuple(str(value) for row in result.rows for value in row if isinstance(value, str))
    answer = message_text(caller(messages)).strip()
    if not answer_matches_language(answer, language, source_names):
        original_numbers = _numbers(answer)
        repair = [
            SystemMessage(content=f"Rewrite the supplied answer entirely in {language_name}. Preserve all figures, qualifiers and source place names exactly. Return only the rewritten answer."),
            HumanMessage(content=answer),
        ]
        answer = message_text(caller(repair)).strip()
        if _numbers(answer) != original_numbers:
            raise ValueError("Answer figures changed during language repair")
    if not answer_matches_language(answer, language, source_names):
        raise ValueError("Answer language did not match request")
    return answer

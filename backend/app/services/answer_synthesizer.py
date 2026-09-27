from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import message_text
from app.services.executor import ExecResult

# Caps the tokens spent on synthesis; the full result set still reaches the UI.
MAX_ANSWER_ROWS = 50

_SYSTEM_PROMPT = """\
You are a real-estate market analyst writing the answer to an analyst's question \
about Abu Dhabi property data. You are given the question, the SQL that was run, \
and the rows it returned.

Rules:
- Reply in the same language as the question. An Arabic question gets an Arabic answer.
- Answer in 1-3 sentences. No preamble, no restating the question, no bullet lists.
- Cite the concrete numbers from the result. Never invent a figure that is not in the rows.
- Format large amounts readably (for example AED 9.35 billion rather than 9348147541.07).
- Arabic answers use Western digits and Arabic scale words, the way UAE market reports are \
written: 92.1 مليار درهم, 1.4 مليون درهم, 102,888 درهم. Never use Eastern Arabic numerals.
- Names of places and projects stay exactly as the rows spell them, \
even in an Arabic answer. Never transliterate them.
- If SQL calculates yield from segment average annual rent and sale price, call it \
an indicative gross segment yield, not an individual property's realized or net return. \
If SQL weights rent by leased units, call it a leased-unit-weighted annual rent estimate.
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


def synthesize_answer(
    question: str,
    sql: str,
    result: ExecResult,
    invoke: Callable[[list[Any]], Any] | Any,
) -> str:
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

    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human)]
    caller = invoke if callable(invoke) else invoke.invoke
    return message_text(caller(messages)).strip()

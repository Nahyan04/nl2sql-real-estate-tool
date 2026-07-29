from __future__ import annotations

from langchain_core.language_models import BaseChatModel
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
- Names of places, projects, developers and brokers stay exactly as the rows spell them, \
even in an Arabic answer. Never transliterate them.
- If the result contains no rows, say plainly that no records matched.
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
    chat_model: BaseChatModel,
) -> str:
    notes = ""
    if result.truncated:
        notes = (
            "\nNote: the result was truncated at the row limit, so these are "
            "the first rows only — say so if it affects the answer.\n"
        )

    human = (
        f"Question: {question}\n\n"
        f"SQL:\n{sql}\n\n"
        f"Result ({result.row_count} rows):\n{_format_rows(result)}\n{notes}"
    )

    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human)]
    return message_text(chat_model.invoke(messages)).strip()

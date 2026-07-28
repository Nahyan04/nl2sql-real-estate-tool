from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# read-only check skips leading whitespace, line comments, and block comments
_READ_ONLY_PREFIX = re.compile(
    r"\A(?:\s+|--[^\n]*\n|/\*.*?\*/)*(select|with)\b",
    re.IGNORECASE | re.DOTALL,
)


class SQLQueryResult(BaseModel):
    query: str
    is_valid: bool = True

    @field_validator("query")
    @classmethod
    def must_be_read_only(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        if not _READ_ONLY_PREFIX.match(stripped):
            raise ValueError("only SELECT or WITH queries are allowed")
        return stripped

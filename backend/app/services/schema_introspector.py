from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

# Postgres normalises `x IN ('a','b')` to `x = ANY (ARRAY['a'::text, 'b'::text])`;
# accept both so the parsing is not tied to one dialect's rendering.
_CHECKED_COLUMN = re.compile(r"^\s*\(?\s*([A-Za-z_]\w*)\s*(?:=\s*ANY\b|IN\b)", re.IGNORECASE)
_STRING_LITERAL = re.compile(r"'((?:[^']|'')*)'")


def parse_allowed_values(check_constraints: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Map column -> permitted literals, read off CHECK constraints.

    The model otherwise has to guess categorical values, and a wrong guess
    ('Sales' for 'sale') returns zero rows without raising anything.
    """
    allowed: dict[str, list[str]] = {}

    for constraint in check_constraints:
        sqltext = constraint.get("sqltext") or ""
        column = _CHECKED_COLUMN.match(sqltext)
        if not column:
            continue
        values = [literal.replace("''", "'") for literal in _STRING_LITERAL.findall(sqltext)]
        if values:
            allowed[column.group(1)] = values

    return allowed


def introspect_schema(bind: Engine | Connection, schema: str | None = None) -> dict[str, Any]:
    inspector = inspect(bind)
    schema_name = schema or inspector.default_schema_name
    table_names = sorted(inspector.get_table_names(schema=schema))

    tables = [build_table_metadata(inspector, table_name, schema) for table_name in table_names]

    return {
        "schema": schema_name,
        "tables": tables,
    }


def build_table_metadata(inspector: Any, table_name: str, schema: str | None) -> dict[str, Any]:
    primary_key = inspector.get_pk_constraint(table_name, schema=schema) or {}
    primary_key_columns = list(primary_key.get("constrained_columns") or [])

    try:
        check_constraints = inspector.get_check_constraints(table_name, schema=schema)
    except NotImplementedError:
        check_constraints = []
    allowed_values = parse_allowed_values(check_constraints)

    columns = []
    for column in inspector.get_columns(table_name, schema=schema):
        metadata = {
            "name": column["name"],
            "type": str(column["type"]),
            "nullable": bool(column.get("nullable", True)),
        }
        if column["name"] in allowed_values:
            metadata["allowed_values"] = allowed_values[column["name"]]
        columns.append(metadata)

    foreign_keys = []
    for foreign_key in inspector.get_foreign_keys(table_name, schema=schema):
        foreign_keys.append(
            {
                "name": foreign_key.get("name"),
                "columns": list(foreign_key.get("constrained_columns") or []),
                "referred_schema": foreign_key.get("referred_schema"),
                "referred_table": foreign_key.get("referred_table"),
                "referred_columns": list(foreign_key.get("referred_columns") or []),
            }
        )

    return {
        "name": table_name,
        "columns": columns,
        "primary_key": primary_key_columns,
        "foreign_keys": foreign_keys,
    }

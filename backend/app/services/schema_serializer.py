from __future__ import annotations

from typing import Any


def serialize_schema(tables: list[dict[str, Any]], char_budget: int = 4000) -> str:
    lines: list[str] = []
    used = 0

    # Column signatures for every relation precede optional, longer descriptions.
    descriptors = [table.get("descriptor") or table.get("name", "") for table in tables]
    signatures = [descriptor.partition(" | ")[0] for descriptor in descriptors]
    descriptions = [f"{table['name']}: {descriptor.partition(' | ')[2]}"
                    for table, descriptor in zip(tables, descriptors) if " | " in descriptor]
    for line in signatures + descriptions:
        separator = "\n" if lines else ""
        cost = len(separator) + len(line)
        if used + cost > char_budget:
            continue
        lines.append(line)
        used += cost

    return "\n".join(lines)

from __future__ import annotations

import json
from pathlib import Path

SCHEMA_ALIASES_PATH = Path(__file__).resolve().parents[1] / "resources" / "schema_aliases.json"


def load_aliases(path: str | None) -> dict[str, list[str]]:
    if not path or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text())
    return data.get("aliases", {})


def load_default_aliases() -> dict[str, list[str]]:
    return load_aliases(str(SCHEMA_ALIASES_PATH))

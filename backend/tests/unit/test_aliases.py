import json
import re
from pathlib import Path

from app.core.aliases import load_aliases, load_default_aliases

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def _schema_tables() -> set[str]:
    ddl = (DB_DIR / "schema.sql").read_text()
    return set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)", ddl))


def _seeded_arabic_names(table: str) -> list[str]:
    """Pull the name_ar column out of the reference seed's INSERT block for one table."""
    seed = (DB_DIR / "reference_seed.sql").read_text()
    block = re.search(rf"INSERT INTO {table} \([^)]*\) VALUES(.*?);", seed, re.DOTALL)
    assert block, f"no seed block for {table}"
    return re.findall(r"'([^']*[؀-ۿ][^']*)'", block.group(1))


def test_load_aliases_returns_empty_dict_when_path_is_none() -> None:
    assert load_aliases(None) == {}


def test_load_aliases_returns_empty_dict_when_file_missing(tmp_path) -> None:
    missing = tmp_path / "does_not_exist.json"

    assert load_aliases(str(missing)) == {}


def test_load_aliases_reads_alias_map_from_file(tmp_path) -> None:
    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({"aliases": {"purchases": ["orders", "order_items"]}}))

    assert load_aliases(str(alias_file)) == {"purchases": ["orders", "order_items"]}


def test_default_aliases_only_point_at_tables_that_exist() -> None:
    tables = _schema_tables()
    unknown = {
        (phrase, table)
        for phrase, targets in load_default_aliases().items()
        for table in targets
        if table not in tables
    }

    assert not unknown


def test_default_alias_phrases_are_lowercased() -> None:
    """Matching lowercases the question, so an upper-cased phrase can never fire."""
    assert [p for p in load_default_aliases() if p != p.lower()] == []


def test_every_seeded_community_is_reachable_from_its_arabic_name() -> None:
    """Arabic questions score nothing from table/column names — the alias map is the
    only signal, so a community with no Arabic phrase is invisible to retrieval."""
    aliases = load_default_aliases()
    unreachable = [
        name
        for name in _seeded_arabic_names("communities")
        if not any(phrase in name for phrase in aliases if "communities" in aliases[phrase])
    ]

    assert unreachable == []

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.genlib.real_loader import map_layout, map_property_type, resolve_community_name


def test_maps_known_property_types():
    assert map_property_type("apartment") == "Apartment"
    assert map_property_type("townhouse / attached villa") == "Townhouse / Attached Villa"
    assert map_property_type("mall / market / retail center") == "Mall / Market / Retail Center"


def test_property_type_is_case_and_whitespace_insensitive():
    assert map_property_type("  Apartment  ") == "Apartment"
    assert map_property_type("VILLA") == "Villa"


def test_unknown_property_type_falls_back_to_other():
    assert map_property_type("factory") == "Other"
    assert map_property_type("palace") == "Other"


def test_maps_known_layouts():
    assert map_layout("studio") == "Studio"
    assert map_layout("1 bed") == "1 Bedroom"
    assert map_layout("2 beds") == "2 Bedroom"
    assert map_layout("6+ beds") == "6+ Bedroom"


def test_five_plus_beds_folds_into_six_plus():
    assert map_layout("5+ beds") == "6+ Bedroom"


def test_unclassified_and_unknown_layouts_are_none():
    assert map_layout("unclassified") is None
    assert map_layout("medium (50 to 500 sqm)") is None
    assert map_layout("line store") is None


def test_resolve_community_name_applies_known_overrides():
    assert resolve_community_name("Al Saadiyat Island") == "Saadiyat Island"
    assert resolve_community_name("Al Rahah") == "Al Raha Beach"
    assert resolve_community_name("Al Shamkhah") == "Al Shamkha"
    assert resolve_community_name("Al Bahyah") == "Al Bahia"
    assert resolve_community_name("Bani Yas") == "Baniyas"
    assert resolve_community_name("Khalifa City") == "Khalifa City"


def test_resolve_community_name_passes_through_unmapped_districts():
    assert resolve_community_name("Al Mirfa") == "Al Mirfa"

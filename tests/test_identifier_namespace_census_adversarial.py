from __future__ import annotations

from pathlib import Path

from scripts.identifier_namespace_census import extract_text, namespace_matches


def _signals(text: str) -> tuple[set[str], list[dict]]:
    return extract_text(Path("fixture.py"), text)


def test_unknown_prefix_is_surfaced() -> None:
    signals, unresolved = _signals('ASSET_ID_PREFIX = "TOTALLY_NEW_"\n')
    assert signals == {"TOTALLY_NEW_"}
    assert unresolved == []


def test_unresolved_dynamic_fstring_blocks_silent_success() -> None:
    signals, unresolved = _signals('asset_id = f"{prefix}_{value}"\n')
    assert signals == set()
    assert unresolved and unresolved[0]["kind"] == "UNRESOLVED_ID_EXPRESSION"


def test_unresolved_dynamic_concatenation_is_retained() -> None:
    signals, unresolved = _signals('asset_id = prefix + "_" + value\n')
    assert signals == set()
    assert unresolved and unresolved[0]["field"] == "asset_id"


def test_tuple_driven_prefix_family_is_detected_and_resolved() -> None:
    text = '''
LAYERS = {
    "water_treatment": ("water", "treatment", "WTR", "Water Treatment"),
    "pump": ("water", "pump", "PMP", "Pump"),
}
for _stem, (_kind, _subtype, prefix, _label) in LAYERS.items():
    asset_id = f"{prefix}_{123}"
'''
    signals, unresolved = _signals(text)
    assert {"WTR_", "PMP_"}.issubset(signals)
    assert unresolved == []


def test_bare_taxonomy_id_is_not_identity() -> None:
    signals, unresolved = _signals('ROW = {"id": "administrative", "label": "Administrative"}\n')
    assert signals == set()
    assert unresolved == []


def test_literal_fstring_prefix_is_detected() -> None:
    signals, unresolved = _signals('asset_id = f"EIA_PLANT_{plant_code}"\n')
    assert "EIA_PLANT_" in signals
    assert unresolved == []


def test_deterministic_shared_stream_helper_is_detected() -> None:
    text = '''
def _fid(prefix, key):
    return prefix + "_" + key
entity_id = _fid("ent", "abc")
source_id = _fid("src", "abc")
'''
    signals, _ = _signals(text)
    assert {"ent_", "src_"}.issubset(signals)


def test_stable_id_plain_prefix_is_detected() -> None:
    text = '''
def stable_id(prefix, value):
    return f"{prefix}_{value}"
edge_id = stable_id("pfe", "x")
'''
    signals, unresolved = _signals(text)
    assert "pfe_" in signals
    assert unresolved == []


def test_colon_stable_id_prefix_is_detected() -> None:
    text = '''
def stable_id(prefix, value):
    return f"{prefix}:{value}"
track_id = stable_id("track", "x")
'''
    signals, unresolved = _signals(text)
    assert "track:" in signals
    assert unresolved == []


def test_namespace_match_accepts_prefix_signal_but_not_neighbor_namespace() -> None:
    namespace = {"pattern": r"^EIA_PLANT_.*$", "repository": "jotaele44/aguayluz-pr"}
    assert namespace_matches(namespace, "EIA_PLANT_")
    assert namespace_matches(namespace, "EIA_PLANT_61014")
    assert not namespace_matches(namespace, "EIA_UTIL_")


def test_overlapping_patterns_can_be_exposed_by_registry_validation_inputs() -> None:
    broad = {"pattern": r"^EIA_.*$"}
    narrow = {"pattern": r"^EIA_PLANT_.*$"}
    assert namespace_matches(broad, "EIA_PLANT_61014")
    assert namespace_matches(narrow, "EIA_PLANT_61014")


def test_hyphen_underscore_are_not_silently_equivalent() -> None:
    namespace = {"pattern": r"^CENT-SIG-.+$"}
    assert namespace_matches(namespace, "CENT-SIG-123")
    assert not namespace_matches(namespace, "CENT_SIG_123")


def test_empty_census_guard_has_positive_controls() -> None:
    corpus = '''
SW_RECORD_ID_PREFIX = "SW-PRINTAKE-"
visual_id_prefix = "SATIM-VIS"
asset_id = f"OSMS_{123}"
case_id = "CAND-0001"
'''
    signals, unresolved = _signals(corpus)
    assert {"SW-PRINTAKE-", "SATIM-VIS", "OSMS_", "CAND-0001"}.issubset(signals)
    assert unresolved == []

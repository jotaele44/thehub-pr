from __future__ import annotations

import pytest

from hub.htr_v2 import (
    HTRV2InvariantError,
    adjudicate_candidates,
    assert_safe,
    discover_candidates,
    normalize_name,
)


def hydro(raw_name: str, *, hydro_entity_id: str = "hydro:test", **extra):
    return {
        "hydro_entity_id": hydro_entity_id,
        "raw_name": raw_name,
        "feature_type": "HYDRO_FEATURE",
        "source_id": extra.pop("source_id", "thehub:frozen-prepa-preb-registry-v1"),
        **extra,
    }


def road(raw_name: str, *, observation_id: str = "road:test", **extra):
    return {
        "observation_id": observation_id,
        "raw_name": raw_name,
        "feature_type": "ROAD",
        "source_id": extra.pop("source_id", "census:tigerline:2025:roads:72001"),
        **extra,
    }


def test_tiger_source_normalization_expands_cll_and_preserves_raw():
    name = normalize_name("Cll Luchetti", "TIGER2025_ROAD")
    assert name["raw"] == "Cll Luchetti"
    assert name["normalized"] == "cll luchetti"
    assert name["source_normalized"] == "calle luchetti"
    assert name["core"] == "luchetti"
    assert name["canonical"] is None


def test_luchetti_lucchetti_is_candidate_not_identity_with_contradiction():
    candidates = discover_candidates([hydro("Lucchetti")], [road("Cll Luchetti")])
    rows = adjudicate_candidates(candidates)
    assert len(rows) == 1
    row = rows[0]
    assert row["discovery_method"] == "ORTHOGRAPHIC_NEAR_MATCH"
    assert row["similarity"] == pytest.approx(0.941176)
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"
    assert row["identity_state"] == "UNRESOLVED"
    assert row["pair_binding_state"] == "UNBOUND"
    assert row["contradictions"] == ["ORTHOGRAPHIC_VARIANT_UNBOUND_LUCHETTI_LUCCHETTI"]
    assert row["identity_claim"] is False
    assert row["connectivity_claim"] is False


def test_single_character_other_name_is_unsupported_not_rejected():
    candidates = discover_candidates(
        [
            hydro(
                "A",
                hydro_entity_id="hydro:a",
                name_manifestation_role="OTHER",
                source_id="sige:mipr-infraestructura:represas:1",
            )
        ],
        [road("Cll A")],
    )
    row = adjudicate_candidates(candidates)[0]
    assert row["state"] == "UNSUPPORTED"
    assert row["identity_state"] == "UNRESOLVED"
    assert row["pair_binding_state"] == "UNBOUND"
    assert "AMBIGUOUS_SINGLE_CHARACTER_OTHER_NAME" in row["unsupported_reasons"]
    assert "LOW_INFORMATION_HYDRO_DISCOVERY_KEY" in row["unsupported_reasons"]


def test_antillas_patillas_weak_single_token_fuzzy_is_unsupported():
    row = adjudicate_candidates(
        discover_candidates([hydro("Patillas Dam")], [road("Cll Antillas")])
    )[0]
    assert row["state"] == "UNSUPPORTED"
    assert "WEAK_SINGLE_TOKEN_FUZZY_PREFIX_MISMATCH" in row["unsupported_reasons"]
    assert row["identity_state"] == "UNRESOLVED"


def test_rio_blanco_descriptor_collapse_requires_explicit_road_class_token():
    collapsed = adjudicate_candidates(
        discover_candidates([hydro("Río Blanco")], [road("Cll Blanco")])
    )[0]
    assert collapsed["state"] == "UNSUPPORTED"
    assert "RIVER_CLASS_TOKEN_COLLAPSE" in collapsed["unsupported_reasons"]

    explicit = adjudicate_candidates(
        discover_candidates(
            [hydro("Río Blanco")],
            [road("Río Blanco", observation_id="road:explicit")],
        )
    )[0]
    assert explicit["state"] == "CANDIDATE_NOT_IDENTITY"


def test_normalization_never_supplies_canonical_identity():
    road_name = normalize_name("Cll Guajataca", "TIGER2025_ROAD")
    hydro_name = normalize_name("Guajataca Reservoir", "HYDRO_FROZEN_V1")
    assert road_name["canonical"] is None
    assert hydro_name["canonical"] is None


def test_safety_gate_rejects_connectivity_promotion():
    row = adjudicate_candidates(discover_candidates([hydro("Carite")], [road("Cll Carite")]))[0]
    row["connectivity_claim"] = True
    with pytest.raises(HTRV2InvariantError):
        assert_safe([row])

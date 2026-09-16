import copy
import json
from pathlib import Path

import pytest

from hub.htr import (
    HTRInvariantError,
    adjudicate_candidate,
    cluster_candidates,
    discover_candidates,
    downstream_context,
    make_graph,
    normalize_name,
    write_bundle,
)

REGISTRY = [
    {"hydro_entity_id": "hydro:lucchetti", "raw_name": "Lucchetti", "feature_type": "HYDRO_PROJECT_NAME_FAMILY"},
    {"hydro_entity_id": "hydro:toa_vaca", "raw_name": "Toa Vaca", "feature_type": "RESERVOIR"},
]
OBS = [{
    "observation_id": "toponym:calle_luchetti_villalba",
    "raw_name": "CALLE LUCHETTI",
    "feature_type": "ROAD",
    "municipality": "Villalba",
    "cluster_id": "villalba-hydro-context",
}]


def seed():
    rows = discover_candidates(REGISTRY, OBS)
    assert len(rows) == 1
    return rows[0]


def toro_negro_context():
    return {
        "evidence_type": "AUTHORITATIVE_ADDRESS",
        "relation_type": "ADDRESS_OF",
        "source_id": "pr-energy-bureau:toro-negro-i-calle-luchetti",
        "authoritative": True,
        "contextual": True,
        "binds_candidate_pair": False,
        "related_entity_id": "hydro:toro_negro_i",
        "related_entity_type": "HYDRO_PLANT",
        "related_entity_raw_name": "Toro Negro I Hydroelectric Power Plant",
    }


def test_luchetti_seed_is_candidate_not_identity_and_raw_spelling_survives():
    row = seed()
    assert row["source_name"] == {"raw": "CALLE LUCHETTI", "normalized": "calle luchetti", "core": "luchetti"}
    assert row["hydro_name"]["raw"] == "Lucchetti"
    assert row["hydro_name"]["core"] == "lucchetti"
    assert row["discovery_method"] == "ORTHOGRAPHIC_NEAR_MATCH"
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"
    assert row["identity_state"] == "UNRESOLVED"
    assert row["pair_binding_state"] == "UNBOUND"


def test_name_or_fuzzy_evidence_cannot_promote_identity():
    row = adjudicate_candidate(seed(), [{
        "evidence_type": "FUZZY_MATCH",
        "relation_type": "ORTHOGRAPHIC_VARIANT",
        "source_id": "derived:fuzzy",
    }])
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"
    assert row["identity_state"] == "UNRESOLVED"


def test_toro_negro_address_supports_context_without_binding_lucchetti_pair():
    row = adjudicate_candidate(seed(), [toro_negro_context()])
    assert row["state"] == "CONTEXT_SUPPORTED"
    assert row["identity_state"] == "DISTINCT_ENTITIES"
    assert row["pair_binding_state"] == "UNBOUND"
    assert row["relation_type"] == "ORTHOGRAPHIC_VARIANT"


@pytest.mark.parametrize(
    "override",
    [
        {"authoritative": False},
        {"relation_type": "UNSUPPORTED_CONTEXT_RELATION"},
        {"source_id": ""},
    ],
)
def test_context_requires_authority_supported_relation_and_stable_source(override):
    evidence = {**toro_negro_context(), **override}
    row = adjudicate_candidate(seed(), [evidence])
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"
    assert row["identity_state"] == "UNRESOLVED"
    assert row["pair_binding_state"] == "UNBOUND"
    assert make_graph([row])["invariants"]["edge_count"] == 1


def test_authoritative_pair_naming_can_bind_relation_but_not_identity():
    row = adjudicate_candidate(seed(), [{
        "evidence_type": "AUTHORITATIVE_NAMING",
        "relation_type": "NAMED_AFTER",
        "source_id": "archive:naming-record",
        "authoritative": True,
        "binds_candidate_pair": True,
    }])
    assert row["state"] == "ADJUDICATED"
    assert row["relation_type"] == "NAMED_AFTER"
    assert row["pair_binding_state"] == "BOUND_RELATION_NOT_IDENTITY"
    assert row["identity_state"] == "DISTINCT_ENTITIES"


def test_non_authoritative_pair_naming_does_not_promote():
    row = adjudicate_candidate(seed(), [{
        "evidence_type": "SECONDARY_HISTORY",
        "relation_type": "NAMED_AFTER",
        "source_id": "secondary:history",
        "authoritative": False,
        "binds_candidate_pair": True,
    }])
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"


def test_same_as_is_forbidden():
    with pytest.raises(HTRInvariantError):
        adjudicate_candidate(seed(), [{
            "evidence_type": "BAD",
            "relation_type": "SAME_AS",
            "source_id": "bad",
            "authoritative": True,
            "binds_candidate_pair": True,
        }])


def test_contradiction_fails_closed_and_rejection_is_retained():
    unresolved = adjudicate_candidate(
        seed(), [toro_negro_context()],
        contradictions=[{"class": "TIME", "source_id": "archive:b", "detail": "conflicting chronology"}],
    )
    assert unresolved["state"] == "UNRESOLVED"
    rejected = adjudicate_candidate(seed(), [], rejection_reasons=["independent unrelated namesake"])
    assert rejected["state"] == "REJECTED"
    assert rejected["rejected_reasons"] == ["independent unrelated namesake"]


def test_downstream_excludes_discovery_and_includes_context_only():
    raw, contextual = seed(), adjudicate_candidate(seed(), [toro_negro_context()])
    assert downstream_context([raw]) == []
    rows = downstream_context([raw, contextual])
    assert len(rows) == 1
    assert rows[0]["downstream_semantics"] == "CONTEXT_ONLY_NOT_IDENTITY"


def test_graph_keeps_candidate_pair_unbound_and_preserves_third_party_address():
    row = adjudicate_candidate(seed(), [toro_negro_context()])
    graph = make_graph([row])
    assert graph["invariants"]["identity_edges"] == 0
    assert graph["invariants"]["node_count"] == 3
    assert {e["relationship_type"] for e in graph["edges"]} == {"POSSIBLE_EPONYM_OF", "ADDRESS_OF"}
    assert all(e["identity_claim"] is False for e in graph["edges"])
    assert graph == make_graph([copy.deepcopy(row)])


def test_multiplicity_preserved_and_duplicate_ids_fail_closed():
    obs = OBS + [{"observation_id": "toponym:luchetti_other", "raw_name": "Calle Luchetti", "feature_type": "ROAD"}]
    rows = discover_candidates(REGISTRY, obs)
    assert len(rows) == 2
    with pytest.raises(HTRInvariantError):
        discover_candidates(REGISTRY, OBS + [copy.deepcopy(OBS[0])])


def test_cluster_members_and_arithmetic_close(tmp_path: Path):
    contextual = adjudicate_candidate(seed(), [toro_negro_context()])
    clusters = cluster_candidates([contextual])
    assert clusters[0]["candidate_count"] == 1
    assert clusters[0]["unique_hydro_name_families"] == 1
    manifest = write_bundle(str(tmp_path), [contextual], source_manifest={"snapshot": "seed"})
    assert manifest == {
        "schema_version": "htr-1.0",
        "candidate_count": 1,
        "context_supported_count": 1,
        "rejected_count": 0,
        "unresolved_count": 0,
        "identity_edge_count": 0,
        "source_manifest": {"snapshot": "seed"},
    }
    assert json.loads((tmp_path / "graph.json").read_text())["invariants"]["edge_count"] == 2


def test_normalization_preserves_raw_and_is_not_canonical_identity():
    form = normalize_name("  Calle Río-Cañón  ")
    assert form["raw"] == "  Calle Río-Cañón  "
    assert form["normalized"] == "calle rio canon"
    assert form["core"] == "canon"

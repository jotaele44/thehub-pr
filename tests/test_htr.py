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
    {
        "hydro_entity_id": "hydro:lucchetti",
        "raw_name": "Lucchetti",
        "feature_type": "HYDRO_PROJECT_NAME_FAMILY",
        "municipality": "Yauco",
    },
    {
        "hydro_entity_id": "hydro:toa_vaca",
        "raw_name": "Toa Vaca",
        "feature_type": "RESERVOIR",
        "municipality": "Villalba",
    },
]

OBSERVATIONS = [
    {
        "observation_id": "toponym:calle_luchetti_villalba",
        "raw_name": "CALLE LUCHETTI",
        "feature_type": "ROAD",
        "municipality": "Villalba",
        "cluster_id": "villalba-hydro-context",
    },
]


def _seed():
    rows = discover_candidates(REGISTRY, OBSERVATIONS)
    assert len(rows) == 1
    return rows[0]


def test_luchetti_villalba_detected_but_not_identity():
    row = _seed()
    assert row["source_name"]["raw"] == "CALLE LUCHETTI"
    assert row["hydro_name"]["raw"] == "Lucchetti"
    assert row["discovery_method"] == "ORTHOGRAPHIC_NEAR_MATCH"
    assert row["relation_type"] == "ORTHOGRAPHIC_VARIANT"
    assert row["state"] == "CANDIDATE_NOT_IDENTITY"
    assert row["identity_state"] == "UNRESOLVED"


def test_lucchetti_spelling_preserved():
    row = _seed()
    assert row["source_name"]["normalized"] == "calle luchetti"
    assert row["source_name"]["core"] == "luchetti"
    assert row["hydro_name"]["normalized"] == "lucchetti"
    assert row["source_name"]["raw"] != row["hydro_name"]["raw"]


def test_no_identity_from_fuzzy_only():
    row = _seed()
    adjudicated = adjudicate_candidate(row, [{
        "evidence_type": "FUZZY_MATCH",
        "relation_type": "ORTHOGRAPHIC_VARIANT",
        "source_id": "derived:fuzzy",
    }])
    assert adjudicated["state"] == "CANDIDATE_NOT_IDENTITY"
    assert adjudicated["identity_state"] == "UNRESOLVED"


def test_toro_negro_address_edge_promoted_but_identity_stays_distinct():
    row = _seed()
    adjudicated = adjudicate_candidate(row, [{
        "evidence_type": "AUTHORITATIVE_ADDRESS",
        "relation_type": "ADDRESS_OF",
        "source_id": "pr-energy-bureau:filing:seed",
        "authoritative": True,
    }])
    assert adjudicated["state"] == "CONTEXT_SUPPORTED"
    assert adjudicated["relation_type"] == "ADDRESS_OF"
    assert adjudicated["identity_state"] == "DISTINCT_ENTITIES"


def test_non_authoritative_naming_claim_does_not_promote():
    row = _seed()
    result = adjudicate_candidate(row, [{
        "evidence_type": "SECONDARY_HISTORY",
        "relation_type": "NAMED_AFTER",
        "source_id": "secondary:history",
        "authoritative": False,
    }])
    assert result["state"] == "CANDIDATE_NOT_IDENTITY"


def test_authoritative_naming_binding_promotes_relation_not_identity():
    row = _seed()
    result = adjudicate_candidate(row, [{
        "evidence_type": "AUTHORITATIVE_NAMING",
        "relation_type": "NAMED_AFTER",
        "source_id": "archive:naming-record",
        "authoritative": True,
    }])
    assert result["state"] == "CONTEXT_SUPPORTED"
    assert result["relation_type"] == "NAMED_AFTER"
    assert result["identity_state"] == "DISTINCT_ENTITIES"


def test_forbidden_same_as_rejected():
    row = _seed()
    with pytest.raises(HTRInvariantError):
        adjudicate_candidate(row, [{
            "evidence_type": "AUTHORITATIVE_NAMING",
            "relation_type": "SAME_AS",
            "source_id": "bad",
            "authoritative": True,
        }])


def test_rejected_candidate_retained():
    row = _seed()
    rejected = adjudicate_candidate(row, [], rejection_reasons=["independent unrelated namesake"])
    assert rejected["state"] == "REJECTED"
    assert rejected["rejected_reasons"] == ["independent unrelated namesake"]


def test_temporal_or_source_contradiction_blocks_context_promotion():
    row = _seed()
    result = adjudicate_candidate(
        row,
        [{
            "evidence_type": "AUTHORITATIVE_NAMING",
            "relation_type": "NAMED_AFTER",
            "source_id": "archive:a",
            "authoritative": True,
        }],
        contradictions=[{"class": "TIME", "source_id": "archive:b", "detail": "road predates candidate eponym"}],
    )
    assert result["state"] == "UNRESOLVED"
    assert result["identity_state"] == "DISTINCT_ENTITIES"


def test_downstream_requires_adjudicated_context():
    row = _seed()
    assert downstream_context([row]) == []
    supported = adjudicate_candidate(row, [{
        "evidence_type": "AUTHORITATIVE_ADDRESS",
        "relation_type": "ADDRESS_OF",
        "source_id": "pr-energy-bureau:seed",
        "authoritative": True,
    }])
    emitted = downstream_context([row, supported])
    assert len(emitted) == 1
    assert emitted[0]["downstream_semantics"] == "CONTEXT_ONLY_NOT_IDENTITY"


def test_same_name_multiplicity_preserved():
    observations = OBSERVATIONS + [{
        "observation_id": "toponym:luchetti_second",
        "raw_name": "Calle Luchetti",
        "feature_type": "ROAD",
        "municipality": "Other",
    }]
    rows = discover_candidates(REGISTRY, observations)
    assert len(rows) == 2
    assert {r["source_observation_id"] for r in rows} == {
        "toponym:calle_luchetti_villalba", "toponym:luchetti_second"
    }


def test_duplicate_ids_fail_closed():
    with pytest.raises(HTRInvariantError):
        discover_candidates(REGISTRY, OBSERVATIONS + [copy.deepcopy(OBSERVATIONS[0])])


def test_cluster_preserves_candidate_members():
    rows = discover_candidates(REGISTRY, OBSERVATIONS)
    clusters = cluster_candidates(rows)
    assert clusters == [{
        "cluster_id": "villalba-hydro-context",
        "candidate_count": 1,
        "unique_hydro_name_families": 1,
        "source_observation_count": 1,
        "candidate_ids": [rows[0]["candidate_id"]],
        "state": "DISCOVERY_CLUSTER_NOT_IDENTITY",
    }]


def test_graph_contains_no_identity_edges_and_is_deterministic():
    row = _seed()
    supported = adjudicate_candidate(row, [{
        "evidence_type": "AUTHORITATIVE_ADDRESS",
        "relation_type": "ADDRESS_OF",
        "source_id": "pr-energy-bureau:seed",
        "authoritative": True,
    }])
    a = make_graph([supported])
    b = make_graph([copy.deepcopy(supported)])
    assert a == b
    assert a["invariants"]["identity_edges"] == 0
    assert all(edge["identity_claim"] is False for edge in a["edges"])


def test_raw_normalized_canonical_separation_survives_accents():
    form = normalize_name("  Calle Río-Cañón  ")
    assert form.raw == "  Calle Río-Cañón  "
    assert form.normalized == "calle rio canon"
    assert form.core == "canon"


def test_write_bundle_arithmetic_closes(tmp_path: Path):
    row = _seed()
    supported = adjudicate_candidate(row, [{
        "evidence_type": "AUTHORITATIVE_ADDRESS",
        "relation_type": "ADDRESS_OF",
        "source_id": "pr-energy-bureau:seed",
        "authoritative": True,
    }])
    manifest = write_bundle(str(tmp_path), [supported], source_manifest={"snapshot": "seed"})
    assert manifest["candidate_count"] == 1
    assert manifest["context_supported_count"] == 1
    assert manifest["rejected_count"] == 0
    assert manifest["unresolved_count"] == 0
    assert manifest["identity_edge_count"] == 0
    graph = json.loads((tmp_path / "graph.json").read_text())
    assert graph["invariants"]["node_count"] == 2

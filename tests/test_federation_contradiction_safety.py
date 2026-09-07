"""Regression gates for contradiction-safe federation runtime semantics."""
from __future__ import annotations

import json

import pytest

from hub.aggregate import aggregate
from hub.bridge import write_manifest
from hub.identity_adjudication import (
    adjudicate_identity,
    annotate_candidate_relationship,
    reject_identity,
)

_TS = "2026-01-01T00:00:00Z"
_SRC = "src_0123456789abcdef0123456789abcdef"
_ENT = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_LINEAGE = {
    "producer_script": "tests/test_federation_contradiction_safety.py",
    "producer_phase": "TEST",
    "source_inputs": ["fixture"],
}


def _entity(name: str) -> dict:
    return {
        "entity_id": _ENT,
        "source_id": _SRC,
        "name": name,
        "normalized_name": name.upper(),
        "entity_type": "recipient",
        "jurisdiction": "PR",
        "confidence": 0.9,
        "lineage": _LINEAGE,
        "synthetic": True,
        "created_at": _TS,
        "extracted_at": _TS,
    }


def _package(tmp_path, producer: str, row: dict):
    pkg = tmp_path / producer
    pkg.mkdir()
    (pkg / "entities.jsonl").write_text(json.dumps(row, sort_keys=True) + "\n")
    write_manifest(pkg, producer)
    return pkg


def _candidate(match_basis: str) -> dict:
    return {
        "relationship_id": "rel_0123456789abcdef0123456789abcdef",
        "source_entity_id": _ENT,
        "target_entity_id": "ent_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "relationship_type": "entity_correlation",
        "match_basis": match_basis,
        "confidence": 0.8,
    }


def test_identical_same_id_rows_coalesce_provenance(tmp_path):
    row = _entity("ACME")
    a = _package(tmp_path, "a-producer", row)
    b = _package(tmp_path, "b-producer", row)
    out = tmp_path / "out"

    summary = aggregate({"b-producer": b, "a-producer": a}, out)

    rows = [json.loads(line) for line in (out / "entities.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["_producers"] == ["a-producer", "b-producer"]
    assert summary["collisions"]["count"] == 0
    assert json.loads((out / "aggregation_collisions.json").read_text()) == []


def test_different_same_id_rows_fail_closed_and_preserve_variants(tmp_path):
    a = _package(tmp_path, "a-producer", _entity("ACME"))
    b = _package(tmp_path, "b-producer", _entity("OTHER"))
    out = tmp_path / "out"

    summary = aggregate({"a-producer": a, "b-producer": b}, out)

    assert (out / "entities.jsonl").read_text() == ""
    collisions = json.loads((out / "aggregation_collisions.json").read_text())
    assert summary["collisions"] == {"count": 1, "by_stream": {"entities": 1}}
    assert len(collisions) == 1
    assert collisions[0]["record_id"] == _ENT
    assert collisions[0]["status"] == "UNRESOLVED"
    assert collisions[0]["reason"] == "same_deterministic_id_different_payload"
    assert [v["producer"] for v in collisions[0]["variants"]] == [
        "a-producer",
        "b-producer",
    ]


def test_collision_output_is_order_independent(tmp_path):
    a = _package(tmp_path, "a-producer", _entity("ACME"))
    b = _package(tmp_path, "b-producer", _entity("OTHER"))
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    aggregate({"a-producer": a, "b-producer": b}, out1)
    aggregate({"b-producer": b, "a-producer": a}, out2)

    for filename in ("entities.jsonl", "aggregation_collisions.json", "graph_summary.json"):
        assert (out1 / filename).read_bytes() == (out2 / filename).read_bytes()


def test_name_and_location_correlations_are_candidates_not_identity():
    for basis in ("normalized_name", "location", "award_transaction_date"):
        annotated = annotate_candidate_relationship(_candidate(basis))
        assert annotated["identity_assertion"] is False
        assert annotated["identity_adjudication_state"] == "CANDIDATE"
        assert annotated["identity_cardinality"] == "UNRESOLVED"
        assert annotated["identity_evidence_class"] == "WEAK_CORRELATION"


def test_external_identifier_remains_candidate_until_explicit_adjudication():
    annotated = annotate_candidate_relationship(_candidate("external_id:uei"))
    assert annotated["identity_assertion"] is False
    assert annotated["identity_evidence_class"] == "HARD_IDENTIFIER_CANDIDATE"


def test_identity_resolution_requires_cardinality_evidence_and_basis():
    row = _candidate("external_id:uei")
    with pytest.raises(ValueError):
        adjudicate_identity(
            row,
            cardinality="UNRESOLVED",
            evidence_refs=["src:uei-registry"],
            decision_basis="authoritative UEI binding",
        )
    with pytest.raises(ValueError):
        adjudicate_identity(
            row,
            cardinality="1:1",
            evidence_refs=[],
            decision_basis="authoritative UEI binding",
        )
    with pytest.raises(ValueError):
        adjudicate_identity(
            row,
            cardinality="1:1",
            evidence_refs=["src:uei-registry"],
            decision_basis="",
        )

    resolved = adjudicate_identity(
        row,
        cardinality="1:1",
        evidence_refs=["src:uei-registry"],
        decision_basis="authoritative UEI binding",
    )
    assert resolved["identity_assertion"] is True
    assert resolved["identity_adjudication_state"] == "RESOLVED"
    assert resolved["identity_cardinality"] == "1:1"


def test_rejected_identity_is_preserved_as_negative_adjudication():
    rejected = reject_identity(
        _candidate("normalized_name"),
        evidence_refs=["src:corporate-registry"],
        decision_basis="distinct registration identifiers",
    )
    assert rejected["identity_assertion"] is False
    assert rejected["identity_adjudication_state"] == "REJECTED"
    assert rejected["identity_cardinality"] == "UNRESOLVED"

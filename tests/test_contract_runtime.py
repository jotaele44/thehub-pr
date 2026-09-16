"""Regression gates for binding frozen Phase-1 contracts to runtime."""

import jsonschema
import pytest

from hub.contract_runtime import (
    adjudication_record,
    correlation_candidate_record,
    provenance_record,
    validate_contract,
)
from hub.identity_adjudication import adjudicate_identity, annotate_candidate_relationship, reject_identity


REL = {
    "relationship_id": "rel_0123456789abcdef0123456789abcdef",
    "source_id": "src_0123456789abcdef0123456789abcdef",
    "source_entity_id": "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "target_entity_id": "ent_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "relationship_type": "entity_correlation",
    "evidence_source_id": "src_0123456789abcdef0123456789abcdef",
    "confidence": 0.8,
    "match_basis": "normalized_name",
    "explanation": "same normalized label",
    "created_at": "1970-01-01T00:00:00Z",
    "extracted_at": "1970-01-01T00:00:00Z",
}


def test_candidate_projects_to_frozen_entity_resolution_contract():
    candidate = annotate_candidate_relationship(REL)
    row = correlation_candidate_record(candidate)
    assert row["decision_type"] == "entity_match_candidate"
    assert row["reason_code"] == "cross_producer_correlation_candidate"
    assert row["candidate_entity_ids"] == sorted(
        [REL["source_entity_id"], REL["target_entity_id"]]
    )
    validate_contract("entity_resolution.v1", row)


def test_weak_signal_cannot_directly_become_identity_decision():
    candidate = annotate_candidate_relationship(REL)
    with pytest.raises(ValueError, match="identity_evidence_refs"):
        adjudication_record(candidate, decided_by="test")


def test_resolved_runtime_adjudication_maps_to_frozen_merge_decision():
    resolved = adjudicate_identity(
        REL,
        cardinality="1:1",
        evidence_refs=["prov_authoritative_registry_record"],
        decision_basis="authoritative registry identifiers agree",
    )
    row = adjudication_record(resolved, decided_by="operator:test")
    assert row["decision_type"] == "entity_identity_decision"
    assert row["outcome"] == "MERGE"
    validate_contract("entity_resolution.v1", row)


def test_rejected_runtime_adjudication_is_retained_in_frozen_ledger():
    rejected = reject_identity(
        REL,
        evidence_refs=["prov_conflicting_legal_entities"],
        decision_basis="distinct legal identifiers",
    )
    row = adjudication_record(rejected, decided_by="operator:test")
    assert row["decision_type"] == "rejected_match"
    validate_contract("entity_resolution.v1", row)


def test_provenance_builder_validates_exact_frozen_contract():
    row = provenance_record(
        producer_id="moneysweep-pr",
        canonical_stream="entities",
        artifact_sha256="a" * 64,
        snapshot_id="snap_" + "b" * 32,
        schema_version="1.0.0",
        evidence_tier="T1",
        tier_source="producer-certified",
        tier_review_status="CONFIRMED",
        synthetic_status="REAL",
        access_level="PUBLIC",
        canonical_record_id=REL["source_entity_id"],
    )
    assert row["tier_authority"]["tier_review_status"] == "CONFIRMED"
    validate_contract("provenance.v1", row)


def test_machine_suggested_provenance_cannot_claim_confirmed_status():
    with pytest.raises(jsonschema.ValidationError):
        provenance_record(
            producer_id="spiderweb-pr",
            canonical_stream="observations",
            artifact_sha256="c" * 64,
            snapshot_id="snap_" + "d" * 32,
            schema_version="1.0.0",
            evidence_tier="T3",
            tier_source="provisional machine suggestion",
            tier_review_status="CONFIRMED",
            synthetic_status="REAL",
            access_level="PUBLIC",
        )

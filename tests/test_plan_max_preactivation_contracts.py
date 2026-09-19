from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_receipt_contract_is_v4_and_fail_closed() -> None:
    schema = load("registry/federation/authority_boundary_receipt.schema.json")
    assert schema["properties"]["schema_version"]["const"] == "authority_boundary_validation_v4"
    assert "blocker_count" in schema["required"]
    assert "certification" in schema["required"]
    assert "next_phase" in schema["required"]


def test_authority_matrix_has_unique_objects_and_single_shared_writer() -> None:
    matrix = load("registry/federation/authority_matrix.json")
    rows = matrix["objects"]
    ids = [row["authority_object_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert matrix["invariants"]["unclassified_authority_objects"] == 0
    for row in rows:
        assert isinstance(row["write_authority"], list)
        if row["shared_or_domain"] == "SHARED":
            assert row["write_authority"] == ["prii-federation-spatial-identity"]
        if len(row["write_authority"]) > 1:
            assert row["shared_or_domain"] == "CROSS_DOMAIN"


def test_source_ownership_closes_without_ambiguous_family() -> None:
    source = load("registry/federation/source_ownership.json")
    allowed = set(source["allowed_classifications"])
    assert source["closure"]["unclassified_families"] == 0
    assert source["closure"]["ambiguous_authority_families"] == 0
    assert all(row["classification"] in allowed for row in source["families"])


def test_dormant_certificate_cannot_unlock_A() -> None:
    cert = load("registry/federation/certifications/authority_boundary_certification.json")
    assert cert["state"] == "READY_FOR_ZERO_BLOCKER_RECEIPT"
    assert cert["issued_at"] is None
    assert cert["receipt_sha256"] is None
    assert cert["manual_override_permitted"] is False
    assert cert["successor_phase"]["state"] == "LOCKED"


def test_A_contract_is_draft_only() -> None:
    contract = load("registry/federation/draft/federation_spatial_entity_contract_1_0.json")
    assert contract["status"] == "DRAFT_NONAUTHORITATIVE"
    assert contract["activation_requires"] == "AUTHORITY_BOUNDARY_CERTIFIED"
    assert contract["activation_state"] == "LOCKED_PENDING_B_CERTIFICATION"
    assert len(contract["A9_invariants"]) >= 30


def test_D_fixture_corpus_closes_ten_families() -> None:
    corpus = load("tests/fixtures/federation_identity_adversarial/corpus.json")
    assert corpus["status"] == "FROZEN_DRAFT_FIXTURES"
    assert len(corpus["fixtures"]) == 10
    assert corpus["closure"]["difference"] == 0
    assert corpus["closure"]["material_unclassified_fixtures"] == 0


def test_arithmetic_contract_requires_zero_material_residue() -> None:
    arithmetic = load("registry/federation/arithmetic_closure.json")
    req = arithmetic["certification_requirements"]
    assert req["blocked"] == 0
    assert req["unclassified"] == 0
    assert req["repository_difference"] == 0
    assert req["producer_difference"] == 0

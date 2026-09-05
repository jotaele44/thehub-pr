from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hub.review_quarantine import (
    ReviewQuarantineError,
    validate_review_quarantine_package,
)

PRODUCER_COMMIT = "1" * 40
PRODUCER_TREE = "2" * 40


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _scope():
    return {
        "schema_version": "prii_federation_spatial_certification_scope_v1",
        "claim": "FEDERATION_SPATIAL_ARCHITECTURE",
        "claim_version": "1.0.0",
        "producer": "jotaele44/aguayluz-pr",
        "consumer_authority": "jotaele44/thehub-pr",
        "zero_residue_rule": "ZERO_MATERIAL_UNRESOLVED_WITHIN_CLAIM",
        "blocking_residue_classes": ["CONTRACT", "UNCLASSIFIED"],
        "nonblocking_disclosed_residue_classes": ["DOMAIN_RECORD_ADJUDICATION"],
        "promotion_rule": (
            "Only zero blocking residue permits certification. "
            "Nonblocking domain residue must remain present and must never be rewritten as resolved."
        ),
    }


def _receipt():
    return {
        "schema_version": "aguayluz_federation_review_quarantine_v1",
        "policy_version": "federation-review-quarantine/1.0",
        "producer": "aguayluz-pr",
        "state": "PASS",
        "canonical_admission_rule": "ACCEPTED_ONLY",
        "legacy_aliases": {"approved": "accepted"},
        "raw_counts": {"assets": 2, "events": 2, "alerts": 2},
        "accepted_input_counts": {"assets": 1, "events": 1, "alerts": 1},
        "quarantined_input_counts": {
            "assets": 1,
            "events": 1,
            "alerts": 1,
            "by_state": {"blocked": 1, "needs_review": 2},
            "total": 3,
        },
        "legacy_alias_count": 0,
        "quarantined": [
            {
                "kind": "asset",
                "record_id": "A2",
                "review_status_raw": "blocked",
                "review_status": "blocked",
                "reason": "review_status=blocked",
            },
            {
                "kind": "event",
                "record_id": "E2",
                "review_status_raw": "needs_review",
                "review_status": "needs_review",
                "reason": "review_status=needs_review",
            },
            {
                "kind": "alert",
                "record_id": "AL2",
                "review_status_raw": "needs_review",
                "review_status": "needs_review",
                "reason": "review_status=needs_review",
            },
        ],
        "invariants": {
            "input_arithmetic_closed": True,
            "quarantined_primary_entities_absent": True,
            "canonical_alerts_accepted_only": True,
            "relationship_endpoints_retained": True,
        },
        "problems": [],
    }


def _package(tmp_path: Path) -> Path:
    root = tmp_path / "pkg"
    scope_path = root / "governance" / "federation_spatial_certification_scope_v1.json"
    _write_json(scope_path, _scope())
    scope_bytes = scope_path.read_bytes()
    _write_json(
        root / "outputs" / "federation_spatial_certification_scope_receipt.json",
        {
            "schema_version": "prii_federation_spatial_certification_scope_receipt_v1",
            "state": "PASS",
            "claim": "FEDERATION_SPATIAL_ARCHITECTURE",
            "claim_version": "1.0.0",
            "producer_repository": "jotaele44/aguayluz-pr",
            "producer_commit": PRODUCER_COMMIT,
            "producer_tree": PRODUCER_TREE,
            "scope_path": "governance/federation_spatial_certification_scope_v1.json",
            "scope_bytes": len(scope_bytes),
            "scope_sha256": hashlib.sha256(scope_bytes).hexdigest(),
            "scope_git_blob_sha": "3" * 40,
            "scope_status": "PROVISIONAL_UNTIL_REFERENCE_EXECUTION_PASSES",
            "problems": [],
        },
    )
    _write_json(root / "outputs" / "review_quarantine_receipt.json", _receipt())
    _write_json(
        root / "outputs" / "federation" / "manifest.json",
        {"review_quarantine_policy": "federation-review-quarantine/1.0"},
    )

    asset = {
        "entity_id": "ent_" + "a" * 32,
        "entity_type": "utility_asset",
        "attributes": {
            "review_status_raw": "accepted",
            "review_status": "accepted",
            "promotion_eligible": True,
        },
    }
    event = {
        "entity_id": "ent_" + "b" * 32,
        "entity_type": "service_event",
        "attributes": {
            "review_status_raw": "approved",
            "review_status": "accepted",
            "promotion_eligible": True,
        },
    }
    municipality = {"entity_id": "ent_" + "c" * 32, "entity_type": "municipality"}
    _write_jsonl(root / "outputs" / "federation" / "entities.jsonl", [asset, event, municipality])
    _write_jsonl(
        root / "outputs" / "federation" / "relationships.jsonl",
        [
            {
                "relationship_id": "rel_" + "d" * 32,
                "source_entity_id": asset["entity_id"],
                "target_entity_id": municipality["entity_id"],
            },
            {
                "relationship_id": "rel_" + "e" * 32,
                "source_entity_id": asset["entity_id"],
                "target_entity_id": event["entity_id"],
            },
        ],
    )
    _write_jsonl(
        root / "outputs" / "federation" / "alerts.jsonl",
        [
            {
                "alert_id": "alrt_" + "f" * 32,
                "is_critical": True,
                "attributes": {
                    "review_status_raw": "accepted",
                    "review_status": "accepted",
                    "promotion_eligible": True,
                },
            }
        ],
    )
    return root


def _validate_certification(root: Path):
    return validate_review_quarantine_package(
        root,
        certification=True,
        producer_commit=PRODUCER_COMMIT,
        producer_tree=PRODUCER_TREE,
    )


def test_valid_quarantine_package_passes_audit_without_promotion(tmp_path):
    root = _package(tmp_path)
    result = validate_review_quarantine_package(
        root,
        certification=False,
        producer_commit=PRODUCER_COMMIT,
        producer_tree=PRODUCER_TREE,
    )
    assert result.state == "PASS"
    assert result.promotable is False
    assert result.quarantined_total == 3
    assert result.canonical_primary_counts == {"assets": 1, "events": 1, "alerts": 1}


def test_valid_quarantine_package_can_support_certification(tmp_path):
    root = _package(tmp_path)
    result = _validate_certification(root)
    assert result.state == "PASS"
    assert result.promotable is True


def test_certification_requires_quarantine_receipt(tmp_path):
    root = _package(tmp_path)
    (root / "outputs" / "review_quarantine_receipt.json").unlink()
    with pytest.raises(ReviewQuarantineError, match="missing outputs/review_quarantine_receipt"):
        _validate_certification(root)


def test_audit_can_inspect_legacy_package_but_never_promotes(tmp_path):
    root = _package(tmp_path)
    (root / "outputs" / "review_quarantine_receipt.json").unlink()
    result = validate_review_quarantine_package(root, certification=False)
    assert result.state == "UNVERIFIED_LEGACY_AUDIT"
    assert result.promotable is False


def test_nonaccepted_primary_in_canonical_stream_fails_closed(tmp_path):
    root = _package(tmp_path)
    entities_path = root / "outputs" / "federation" / "entities.jsonl"
    rows = [json.loads(line) for line in entities_path.read_text().splitlines()]
    rows[0]["attributes"]["review_status"] = "blocked"
    rows[0]["attributes"]["promotion_eligible"] = False
    _write_jsonl(entities_path, rows)
    with pytest.raises(ReviewQuarantineError, match="is not accepted"):
        _validate_certification(root)


def test_nonaccepted_critical_alert_fails_closed(tmp_path):
    root = _package(tmp_path)
    alert_path = root / "outputs" / "federation" / "alerts.jsonl"
    rows = [json.loads(line) for line in alert_path.read_text().splitlines()]
    rows[0]["attributes"]["review_status"] = "blocked"
    rows[0]["attributes"]["promotion_eligible"] = False
    _write_jsonl(alert_path, rows)
    with pytest.raises(ReviewQuarantineError, match="is not accepted"):
        _validate_certification(root)


def test_relationship_to_quarantined_or_missing_entity_fails_closed(tmp_path):
    root = _package(tmp_path)
    rel_path = root / "outputs" / "federation" / "relationships.jsonl"
    rows = [json.loads(line) for line in rel_path.read_text().splitlines()]
    rows[0]["target_entity_id"] = "ent_" + "0" * 32
    _write_jsonl(rel_path, rows)
    with pytest.raises(ReviewQuarantineError, match="outside retained canonical entity set"):
        _validate_certification(root)


def test_scope_drift_fails_closed(tmp_path):
    root = _package(tmp_path)
    scope_path = root / "governance" / "federation_spatial_certification_scope_v1.json"
    scope = json.loads(scope_path.read_text())
    scope["nonblocking_disclosed_residue_classes"] = []
    _write_json(scope_path, scope)
    with pytest.raises(ReviewQuarantineError, match="domain record adjudication"):
        _validate_certification(root)


def test_scope_receipt_must_bind_runtime_producer_identity(tmp_path):
    root = _package(tmp_path)
    receipt_path = root / "outputs" / "federation_spatial_certification_scope_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["producer_commit"] = "9" * 40
    _write_json(receipt_path, receipt)
    with pytest.raises(ReviewQuarantineError, match="producer_commit does not match runtime producer"):
        _validate_certification(root)


def test_scope_receipt_hash_detects_mutated_policy_bytes(tmp_path):
    root = _package(tmp_path)
    scope_path = root / "governance" / "federation_spatial_certification_scope_v1.json"
    scope = json.loads(scope_path.read_text())
    scope["claim_version"] = "9.9.9"
    _write_json(scope_path, scope)
    with pytest.raises(ReviewQuarantineError, match="SHA256 mismatch"):
        _validate_certification(root)

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evidence_engine.artifact_intake import (
    ArtifactIntakeError,
    IntakeValidationError,
    intake_local_artifacts,
    validate_acquisition_receipt,
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact(data: bytes) -> tuple[str, str]:
    digest = _digest(data)
    return "artifact-sha256-" + digest, digest


def _schema_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / "contracts" / "skywatcher_ai"


def _receipt(artifact_ids: list[str], receipt_id: str = "receipt-1") -> dict:
    return {
        "schema_version": "acquisition_receipt.v1",
        "receipt_id": receipt_id,
        "operation_id": "offline-fixture-intake",
        "provider": "offline-fixture",
        "requested_at": "2026-07-30T18:00:00Z",
        "completed_at": "2026-07-30T18:00:01Z",
        "outcome": "SUCCEEDED",
        "request_digest": "a" * 64,
        "artifact_ids": artifact_ids,
        "classification": "INTERNAL",
        "egress_decision_id": None,
        "failure": None,
        "audit_event_id": "audit-1",
    }


def test_receipt_validation_uses_frozen_schema(tmp_path: Path) -> None:
    artifact_id, _ = _artifact(b"fixture")
    validate_acquisition_receipt(_receipt([artifact_id]), schema_dir=_schema_dir())
    invalid = _receipt([artifact_id])
    invalid["request_digest"] = "not-a-digest"
    with pytest.raises(IntakeValidationError, match="invalid acquisition receipt"):
        validate_acquisition_receipt(invalid, schema_dir=_schema_dir())
    assert list(tmp_path.iterdir()) == []


def test_quarantine_first_sha_identity_and_classification_inheritance(tmp_path: Path) -> None:
    data = b"%PDF-1.7\nfixture\n"
    artifact_id, digest = _artifact(data)
    source = tmp_path / "source.pdf"
    source.write_bytes(data)
    storage = tmp_path / "store"

    report = intake_local_artifacts(
        storage,
        _receipt([artifact_id]),
        [
            {
                "artifact_id": artifact_id,
                "sha256": digest,
                "path": str(source),
                "declared_mime_type": "application/pdf",
                "classification": "PUBLIC",
                "inherited_classifications": [
                    {
                        "level": "RESTRICTED",
                        "object_id": "case-1",
                        "reason": "case restriction",
                    }
                ],
            }
        ],
        max_size_bytes=1024,
        schema_dir=_schema_dir(),
    )

    assert report["accounting"] == {
        "inputs": 1,
        "registered": 1,
        "existing": 0,
        "rejected": 0,
        "quarantine_written": 1,
        "quarantine_existing": 0,
        "not_stored": 0,
    }
    item = report["dispositions"][0]
    assert item["actual_artifact_id"] == artifact_id
    assert item["intended_classification"]["level"] == "RESTRICTED"
    assert item["effective_classification"]["level"] == "QUARANTINED"
    assert item["active_snapshot_eligible"] is False
    quarantine = storage / item["quarantine_locator"]
    assert quarantine.read_bytes() == data
    content = json.loads((storage / item["content_record_locator"]).read_text())
    assert content["sha256"] == digest
    assert content["active_snapshot_eligible"] is False


def test_same_receipt_replay_and_cross_receipt_content_registration_are_idempotent(
    tmp_path: Path,
) -> None:
    data = b'{"registration":"N999ZY"}\n'
    artifact_id, digest = _artifact(data)
    source = tmp_path / "vision.json"
    source.write_bytes(data)
    storage = tmp_path / "store"
    item = {
        "artifact_id": artifact_id,
        "sha256": digest,
        "path": str(source),
        "declared_mime_type": "application/json",
        "classification": "INTERNAL",
    }

    first = intake_local_artifacts(
        storage,
        _receipt([artifact_id], "receipt-1"),
        [item],
        max_size_bytes=4096,
        schema_dir=_schema_dir(),
    )
    replay = intake_local_artifacts(
        storage,
        _receipt([artifact_id], "receipt-1"),
        [item],
        max_size_bytes=4096,
        schema_dir=_schema_dir(),
    )
    assert replay == first

    second_receipt = _receipt([artifact_id], "receipt-2")
    second_receipt["audit_event_id"] = "audit-2"
    second = intake_local_artifacts(
        storage,
        second_receipt,
        [item],
        max_size_bytes=4096,
        schema_dir=_schema_dir(),
    )
    assert second["accounting"]["existing"] == 1
    assert second["accounting"]["registered"] == 0
    assert second["accounting"]["quarantine_existing"] == 1


def test_mime_and_size_fail_closed_with_complete_accounting(tmp_path: Path) -> None:
    unknown = b"\x00\x01\x02\x03"
    unknown_id, unknown_sha = _artifact(unknown)
    unknown_path = tmp_path / "unknown.bin"
    unknown_path.write_bytes(unknown)

    large = b"x" * 33
    large_id, large_sha = _artifact(large)
    large_path = tmp_path / "large.txt"
    large_path.write_bytes(large)

    missing_id, missing_sha = _artifact(b"missing")
    report = intake_local_artifacts(
        tmp_path / "store",
        _receipt([unknown_id, large_id, missing_id]),
        [
            {
                "artifact_id": unknown_id,
                "sha256": unknown_sha,
                "path": str(unknown_path),
            },
            {
                "artifact_id": large_id,
                "sha256": large_sha,
                "path": str(large_path),
                "declared_mime_type": "text/plain",
            },
            {
                "artifact_id": missing_id,
                "sha256": missing_sha,
                "path": str(tmp_path / "missing.txt"),
            },
        ],
        max_size_bytes=32,
        schema_dir=_schema_dir(),
    )
    accounting = report["accounting"]
    assert accounting["inputs"] == 3
    assert accounting["rejected"] == 3
    assert accounting["quarantine_written"] == 1
    assert accounting["not_stored"] == 2
    assert accounting["inputs"] == (
        accounting["registered"] + accounting["existing"] + accounting["rejected"]
    )
    assert accounting["inputs"] == (
        accounting["quarantine_written"]
        + accounting["quarantine_existing"]
        + accounting["not_stored"]
    )
    assert {item["reason"] for item in report["dispositions"]} == {
        "mime_type_not_allowed",
        "size_limit_exceeded",
        "source_not_regular_file",
    }


def test_sha_mismatch_remains_quarantined_but_unregistered(tmp_path: Path) -> None:
    actual = b"plain fixture"
    actual_id, actual_sha = _artifact(actual)
    expected_id, expected_sha = _artifact(b"different")
    source = tmp_path / "source.txt"
    source.write_bytes(actual)
    report = intake_local_artifacts(
        tmp_path / "store",
        _receipt([expected_id]),
        [
            {
                "artifact_id": expected_id,
                "sha256": expected_sha,
                "path": str(source),
                "declared_mime_type": "text/plain",
            }
        ],
        max_size_bytes=1024,
        schema_dir=_schema_dir(),
    )
    item = report["dispositions"][0]
    assert item["reason"] == "sha256_identity_mismatch"
    assert item["actual_artifact_id"] == actual_id
    assert item["actual_sha256"] == actual_sha
    assert (tmp_path / "store" / item["quarantine_locator"]).exists()
    assert report["accounting"]["registered"] == 0


def test_receipt_id_cannot_be_reused_for_different_manifest(tmp_path: Path) -> None:
    first_data = b"first"
    first_id, first_sha = _artifact(first_data)
    first_path = tmp_path / "first.txt"
    first_path.write_bytes(first_data)
    storage = tmp_path / "store"
    receipt = _receipt([first_id])
    intake_local_artifacts(
        storage,
        receipt,
        [{"artifact_id": first_id, "sha256": first_sha, "path": str(first_path)}],
        max_size_bytes=1024,
        schema_dir=_schema_dir(),
    )
    changed = {
        "artifact_id": first_id,
        "sha256": first_sha,
        "path": str(first_path),
        "classification": "LEGAL_HOLD",
    }
    with pytest.raises(ArtifactIntakeError, match="different artifact manifest"):
        intake_local_artifacts(
            storage,
            receipt,
            [changed],
            max_size_bytes=1024,
            schema_dir=_schema_dir(),
        )


def test_intake_source_contains_no_network_model_rpc_or_query_runtime() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "evidence_engine"
        / "artifact_intake.py"
    ).read_text(encoding="utf-8").lower()
    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "anthropic",
        "openai",
        "boto3",
        "subprocess",
        "import skywatcher",
        "from skywatcher",
        "database_url",
        "active_snapshot_promoted\": true",
    ):
        assert forbidden not in source

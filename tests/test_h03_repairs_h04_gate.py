from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from control_plane.snapshot_gate import (
    certify_validation_report,
    compute_snapshot_gate,
    snapshot_operation_decision,
)
from evidence_engine.artifact_intake import intake_local_artifacts
from evidence_engine.artifact_validation import (
    validate_and_normalize_quarantined_artifacts,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact(data: bytes) -> tuple[str, str]:
    digest = _sha(data)
    return "artifact-sha256-" + digest, digest


def _schema_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "contracts"
        / "skywatcher_ai"
    )


def _receipt(
    artifact_ids: list[str],
    receipt_id: str,
    classification: str = "INTERNAL",
) -> dict:
    return {
        "schema_version": "acquisition_receipt.v1",
        "receipt_id": receipt_id,
        "operation_id": "offline-fixture-intake",
        "provider": "offline-fixture",
        "requested_at": "2026-07-30T20:00:00Z",
        "completed_at": "2026-07-30T20:00:01Z",
        "outcome": "SUCCEEDED",
        "request_digest": "a" * 64,
        "artifact_ids": artifact_ids,
        "classification": classification,
        "egress_decision_id": None,
        "failure": None,
        "audit_event_id": "audit-" + receipt_id,
    }


def _intake_one(
    root: Path,
    data: bytes,
    *,
    receipt_id: str,
    classification: str = "INTERNAL",
    inherited: Optional[List[Dict]] = None,
) -> tuple[str, str, dict]:
    artifact_id, digest = _artifact(data)
    source = root / (receipt_id + ".input")
    source.write_bytes(data)
    report = intake_local_artifacts(
        root,
        _receipt([artifact_id], receipt_id, classification),
        [
            {
                "artifact_id": artifact_id,
                "sha256": digest,
                "path": str(source),
                "classification": "PUBLIC",
                "inherited_classifications": inherited or [],
            }
        ],
        max_size_bytes=1024 * 1024,
        schema_dir=_schema_dir(),
    )
    return artifact_id, digest, report


def test_malformed_schema_and_external_ref_are_accounted(
    tmp_path: Path,
) -> None:
    artifact_id, digest, _ = _intake_one(
        tmp_path, b'{"value":1}', receipt_id="schema"
    )
    malformed = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "malformed-schema",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
                "json_schema": {"type": 7},
            }
        ],
        completed_at="2026-07-30T20:01:00Z",
    )
    assert malformed["accounting"]["failed"] == 1
    assert (
        malformed["dispositions"][0]["failure_code"]
        == "SCHEMA_DEFINITION_INVALID"
    )

    external = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "external-schema",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
                "json_schema": {
                    "$ref": "https://example.invalid/schema.json"
                },
            }
        ],
        completed_at="2026-07-30T20:02:00Z",
    )
    assert external["accounting"]["failed"] == 1
    assert (
        external["dispositions"][0]["failure_code"]
        == "SCHEMA_EXTERNAL_REF_DENIED"
    )


def test_distinct_sources_share_derivative_but_not_provenance(
    tmp_path: Path,
) -> None:
    first = b'{"b":2,"a":1}\n'
    second = b'{\n  "a": 1,\n  "b": 2\n}\n'
    first_id, first_sha = _artifact(first)
    second_id, second_sha = _artifact(second)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_bytes(first)
    second_path.write_bytes(second)
    intake_local_artifacts(
        tmp_path,
        _receipt([first_id, second_id], "two-sources"),
        [
            {
                "artifact_id": first_id,
                "sha256": first_sha,
                "path": str(first_path),
                "classification": "INTERNAL",
            },
            {
                "artifact_id": second_id,
                "sha256": second_sha,
                "path": str(second_path),
                "classification": "INTERNAL",
            },
        ],
        max_size_bytes=4096,
        schema_dir=_schema_dir(),
    )
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "two-source-normalization",
        [
            {
                "source_artifact_id": first_id,
                "source_sha256": first_sha,
            },
            {
                "source_artifact_id": second_id,
                "source_sha256": second_sha,
            },
        ],
        completed_at="2026-07-30T20:03:00Z",
    )
    first_row, second_row = report["dispositions"]
    assert first_row["derivative_sha256"] == second_row["derivative_sha256"]
    assert first_row["provenance_locator"] != second_row["provenance_locator"]
    assert report["accounting"]["derivative_written"] == 1
    assert report["accounting"]["derivative_existing"] == 1


def test_real_h02_lineage_flows_to_h03_and_h04(
    tmp_path: Path,
) -> None:
    data = b'{"status":"verified"}\n'
    artifact_id, digest, intake_report = _intake_one(
        tmp_path,
        data,
        receipt_id="lineage",
        inherited=[
            {
                "level": "RESTRICTED",
                "object_id": "case-1",
                "reason": "case restriction",
            }
        ],
    )
    intake_ledger = next((tmp_path / "registry" / "intakes").glob("*.json"))
    source_path = tmp_path / "quarantine" / "sha256" / digest[:2] / digest
    before_source = source_path.read_bytes()
    before_ledger = intake_ledger.read_bytes()

    content_locator = intake_report["dispositions"][0][
        "content_record_locator"
    ]
    content = json.loads(
        (tmp_path / content_locator).read_text(encoding="utf-8")
    )
    assert content["intended_classification"]["restriction_floor"] == (
        "RESTRICTED"
    )
    assert content["classification_lineage_complete"] is True

    validation = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "lineage-validation",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
            }
        ],
        completed_at="2026-07-30T20:04:00Z",
    )
    classification = validation["dispositions"][0]["classification"]
    assert classification["restriction_floor"] == "RESTRICTED"
    assert classification["lineage_complete"] is True

    candidate = certify_validation_report(
        tmp_path,
        "lineage-certification",
        validation,
        completed_at="2026-07-30T20:05:00Z",
    )
    assert candidate["state"] == "CERTIFIED"
    assert candidate["certification_decision"] == compute_snapshot_gate(
        candidate
    )
    assert candidate["active_snapshot_promoted"] is False
    assert candidate["query_serving_eligible"] is False
    assert snapshot_operation_decision(candidate, "ANSWER")["allowed"] is False
    assert (
        snapshot_operation_decision(candidate, "CITATION")["allowed"]
        is False
    )
    assert (
        snapshot_operation_decision(candidate, "OPERATIONAL_STATUS")[
            "allowed"
        ]
        is True
    )
    assert (
        snapshot_operation_decision(candidate, "PROVISIONAL_METADATA")[
            "allowed"
        ]
        is True
    )
    assert source_path.read_bytes() == before_source
    assert intake_ledger.read_bytes() == before_ledger
    assert not (tmp_path / "active_snapshot.json").exists()
    assert not (tmp_path / "registry" / "active").exists()


def test_legacy_lineage_blocks_certification(tmp_path: Path) -> None:
    data = b'{"legacy":true}'
    artifact_id, digest = _artifact(data)
    quarantine = tmp_path / "quarantine" / "sha256" / digest[:2] / digest
    quarantine.parent.mkdir(parents=True)
    quarantine.write_bytes(data)
    record = {
        "schema_version": "content_addressed_artifact.v1",
        "artifact_id": artifact_id,
        "sha256": digest,
        "size_bytes": len(data),
        "mime_type": "application/json",
        "quarantine_locator": quarantine.relative_to(tmp_path).as_posix(),
        "lifecycle_state": "QUARANTINED",
        "effective_classification": {
            "level": "QUARANTINED",
            "inherited_from": artifact_id,
            "reason": "legacy",
        },
        "active_snapshot_eligible": False,
    }
    record_path = (
        tmp_path
        / "registry"
        / "content"
        / digest[:2]
        / (digest + ".json")
    )
    record_path.parent.mkdir(parents=True)
    record_path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    validation = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "legacy-validation",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
            }
        ],
        completed_at="2026-07-30T20:06:00Z",
    )
    assert (
        validation["dispositions"][0]["classification"]["lineage_complete"]
        is False
    )
    candidate = certify_validation_report(
        tmp_path,
        "legacy-certification",
        validation,
        completed_at="2026-07-30T20:07:00Z",
    )
    assert candidate["state"] == "QUARANTINED"
    assert "CLASSIFICATION_LINEAGE_INCOMPLETE" in (
        candidate["certification_decision"]["blockers"]
    )
    accounting = candidate["accounting"]
    assert accounting["inputs"] == (
        accounting["included"]
        + accounting["excluded_validation_failure"]
        + accounting["excluded_certification_failure"]
    )


def test_text_normalization_has_exactly_one_trailing_lf(
    tmp_path: Path,
) -> None:
    artifact_id, digest, _ = _intake_one(
        tmp_path, b"\r\n\n", receipt_id="newlines"
    )
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "newlines-validation",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
                "expected_mime_type": "text/plain",
            }
        ],
        completed_at="2026-07-30T20:08:00Z",
    )
    derivative = tmp_path / report["dispositions"][0]["derivative_locator"]
    assert derivative.read_bytes() == b"\n"


def test_certification_replay_is_idempotent(tmp_path: Path) -> None:
    artifact_id, digest, _ = _intake_one(
        tmp_path, b'{"idempotent":true}', receipt_id="replay"
    )
    validation = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "replay-validation",
        [
            {
                "source_artifact_id": artifact_id,
                "source_sha256": digest,
            }
        ],
        completed_at="2026-07-30T20:09:00Z",
    )
    first = certify_validation_report(
        tmp_path,
        "replay-certification",
        validation,
        completed_at="2026-07-30T20:10:00Z",
    )
    second = certify_validation_report(
        tmp_path,
        "replay-certification",
        validation,
        completed_at="2026-07-30T20:11:00Z",
    )
    assert first == second


def test_static_runtime_boundaries() -> None:
    root = Path(__file__).resolve().parents[1] / "src"
    source = (
        (root / "evidence_engine" / "artifact_intake.py").read_text()
        + (root / "evidence_engine" / "artifact_validation.py").read_text()
        + (root / "control_plane" / "snapshot_gate.py").read_text()
    ).lower()
    forbidden = (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "urllib.request",
        "import anthropic",
        "import openai",
        "import skywatcher",
        "from skywatcher",
        "import socket",
        "import subprocess",
        "import sqlalchemy",
        "import psycopg",
        "database_url",
    )
    assert all(token not in source for token in forbidden)

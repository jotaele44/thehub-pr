from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evidence_engine.artifact_intake import _safe_write_once
from evidence_engine.artifact_validation import (
    ArtifactNormalizationError,
    validate_and_normalize_quarantined_artifacts,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed(root: Path, data: bytes, classification: str = "QUARANTINED") -> tuple[str, str]:
    digest = _sha(data)
    artifact_id = "artifact-sha256-" + digest
    quarantine = root / "quarantine" / "sha256" / digest[:2] / digest
    _safe_write_once(quarantine, data)
    record = {
        "schema_version": "content_addressed_artifact.v1",
        "artifact_id": artifact_id,
        "sha256": digest,
        "size_bytes": len(data),
        "mime_type": "application/json",
        "quarantine_locator": quarantine.relative_to(root).as_posix(),
        "lifecycle_state": "QUARANTINED",
        "effective_classification": {
            "level": classification,
            "inherited_from": artifact_id,
            "reason": "test",
        },
        "active_snapshot_eligible": False,
    }
    record_path = root / "registry" / "content" / digest[:2] / (digest + ".json")
    _safe_write_once(
        record_path,
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n",
    )
    return artifact_id, digest


def test_json_derivative_is_reproducible_and_source_is_unchanged(tmp_path: Path) -> None:
    source = b'{"b":2, "a":1}\n'
    artifact_id, digest = _seed(tmp_path, source)
    request = [{"source_artifact_id": artifact_id, "source_sha256": digest}]
    first = validate_and_normalize_quarantined_artifacts(
        tmp_path, "run-1", request, completed_at="2026-07-30T19:30:00Z"
    )
    second = validate_and_normalize_quarantined_artifacts(
        tmp_path, "run-1", request, completed_at="2026-07-30T19:30:00Z"
    )
    assert first == second
    row = first["dispositions"][0]
    derivative = tmp_path / row["derivative_locator"]
    assert derivative.read_bytes() == b'{"a":1,"b":2}\n'
    quarantine = tmp_path / "quarantine" / "sha256" / digest[:2] / digest
    assert quarantine.read_bytes() == source
    assert row["derivative_sha256"] == _sha(derivative.read_bytes())


def test_text_newlines_are_normalized(tmp_path: Path) -> None:
    artifact_id, digest = _seed(tmp_path, b"alpha\r\nbeta\r")
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "run-text",
        [{
            "source_artifact_id": artifact_id,
            "source_sha256": digest,
            "expected_mime_type": "text/plain",
        }],
        completed_at="2026-07-30T19:30:00Z",
    )
    assert (tmp_path / report["dispositions"][0]["derivative_locator"]).read_bytes() == b"alpha\nbeta\n"


def test_schema_failure_is_fully_accounted(tmp_path: Path) -> None:
    artifact_id, digest = _seed(tmp_path, b'{"value":"bad"}')
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "run-schema",
        [{
            "source_artifact_id": artifact_id,
            "source_sha256": digest,
            "json_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        }],
        completed_at="2026-07-30T19:30:00Z",
    )
    assert report["accounting"] == {
        "inputs": 1,
        "validated": 0,
        "failed": 1,
        "derivative_written": 0,
        "derivative_existing": 0,
    }
    assert report["dispositions"][0]["failure_code"] == "SCHEMA_INVALID"


def test_source_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    artifact_id, digest = _seed(tmp_path, b'{"ok":true}')
    quarantine = tmp_path / "quarantine" / "sha256" / digest[:2] / digest
    quarantine.write_bytes(b"tampered")
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "run-digest",
        [{"source_artifact_id": artifact_id, "source_sha256": digest}],
        completed_at="2026-07-30T19:30:00Z",
    )
    assert report["dispositions"][0]["failure_code"] == "SOURCE_DIGEST_MISMATCH"


def test_classification_inherits_and_promotion_stays_blocked(tmp_path: Path) -> None:
    artifact_id, digest = _seed(tmp_path, b'{"ok":true}', "LEGAL_HOLD")
    report = validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "run-classification",
        [{"source_artifact_id": artifact_id, "source_sha256": digest}],
        completed_at="2026-07-30T19:30:00Z",
    )
    row = report["dispositions"][0]
    assert row["classification"]["level"] == "LEGAL_HOLD"
    assert row["active_snapshot_eligible"] is False
    assert report["active_snapshot_promoted"] is False


def test_later_run_reuses_identical_derivative(tmp_path: Path) -> None:
    artifact_id, digest = _seed(tmp_path, b'{"b":2,"a":1}')
    request = [{"source_artifact_id": artifact_id, "source_sha256": digest}]
    first = validate_and_normalize_quarantined_artifacts(
        tmp_path, "run-a", request, completed_at="2026-07-30T19:30:00Z"
    )
    second = validate_and_normalize_quarantined_artifacts(
        tmp_path, "run-b", request, completed_at="2026-07-30T19:31:00Z"
    )
    assert first["dispositions"][0]["derivative_sha256"] == second["dispositions"][0]["derivative_sha256"]
    assert second["accounting"]["derivative_existing"] == 1


def test_run_id_conflict_is_rejected(tmp_path: Path) -> None:
    first_id, first_sha = _seed(tmp_path, b'{"a":1}')
    second_id, second_sha = _seed(tmp_path, b'{"a":2}')
    validate_and_normalize_quarantined_artifacts(
        tmp_path,
        "same-run",
        [{"source_artifact_id": first_id, "source_sha256": first_sha}],
        completed_at="2026-07-30T19:30:00Z",
    )
    with pytest.raises(ArtifactNormalizationError, match="different requests"):
        validate_and_normalize_quarantined_artifacts(
            tmp_path,
            "same-run",
            [{"source_artifact_id": second_id, "source_sha256": second_sha}],
            completed_at="2026-07-30T19:31:00Z",
        )


def test_static_runtime_boundary() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "evidence_engine"
        / "artifact_validation.py"
    ).read_text(encoding="utf-8").lower()
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
    )
    assert all(token not in source for token in forbidden)

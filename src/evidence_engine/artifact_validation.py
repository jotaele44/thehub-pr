"""Offline validation and deterministic normalization of quarantined artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .artifact_intake import ArtifactIntakeError, IntakeValidationError

_ALLOWED_MIME = {"application/json", "text/plain"}
_CLASS_ORDER = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "RESTRICTED": 2,
    "SENSITIVE_LOCATION": 3,
    "LEGAL_HOLD": 4,
    "QUARANTINED": 5,
}


class ArtifactNormalizationError(ArtifactIntakeError):
    """Raised when validation or normalization cannot complete safely."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_id(digest: str) -> str:
    return "artifact-sha256-" + digest


def _safe_write_once(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ArtifactNormalizationError(
                "immutable path content conflict: " + str(path)
            )
        return False
    fd, temporary_name = tempfile.mkstemp(prefix=".normalize-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
            return True
        except FileExistsError:
            if path.read_bytes() != data:
                raise ArtifactNormalizationError(
                    "immutable path content conflict: " + str(path)
                )
            return False
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(path: Path, value: Mapping[str, Any]) -> bool:
    return _safe_write_once(path, _canonical_bytes(dict(value)) + b"\n")


def _load_json(path: Path, label: str) -> Dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise IntakeValidationError(label + " must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntakeValidationError(label + " is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise IntakeValidationError(label + " must contain a JSON object")
    return value


def _detected_mime(data: bytes) -> Optional[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\x00" in text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return "text/plain"
    return "application/json" if isinstance(parsed, (dict, list)) else "text/plain"


def _normalize(data: bytes, mime_type: str) -> bytes:
    text = data.decode("utf-8")
    if mime_type == "application/json":
        value = json.loads(text)
        return _canonical_bytes(value) + b"\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized.encode("utf-8")


def _classification(content_record: Mapping[str, Any]) -> Dict[str, Any]:
    effective = content_record.get("effective_classification")
    if not isinstance(effective, Mapping):
        raise IntakeValidationError("content record lacks effective_classification")
    level = str(effective.get("level") or "")
    if level not in set(_CLASS_ORDER) | {"TEST_ONLY"}:
        raise IntakeValidationError("unsupported source classification: " + level)
    floor = "PUBLIC" if level == "TEST_ONLY" else level
    return {
        "level": level,
        "restriction_floor": floor,
        "inherited_from": str(content_record.get("artifact_id") or ""),
        "reason": "immutable derivative inherits source access classification",
    }


def _validate_json_schema(value: Any, schema: Mapping[str, Any]) -> List[str]:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(dict(schema))
    return sorted(error.message for error in validator.iter_errors(value))


def _request_fingerprint(requests: Sequence[Mapping[str, Any]]) -> str:
    normalized = []
    for request in requests:
        normalized.append(
            {
                "source_artifact_id": request.get("source_artifact_id"),
                "source_sha256": request.get("source_sha256"),
                "expected_mime_type": request.get("expected_mime_type"),
                "json_schema": request.get("json_schema"),
            }
        )
    normalized.sort(key=lambda item: str(item["source_artifact_id"]))
    return _sha256(_canonical_bytes(normalized))


def validate_and_normalize_quarantined_artifacts(
    storage_root: Path,
    validation_run_id: str,
    requests: Iterable[Mapping[str, Any]],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Validate H02 quarantine content and create immutable normalized derivatives."""
    run_id = validation_run_id.strip()
    if not run_id:
        raise IntakeValidationError("validation_run_id is required")
    items = [dict(item) for item in requests]
    source_ids = [str(item.get("source_artifact_id") or "") for item in items]
    if any(not source_id for source_id in source_ids):
        raise IntakeValidationError("every request requires source_artifact_id")
    if len(source_ids) != len(set(source_ids)):
        raise IntakeValidationError("duplicate source_artifact_id in validation request")

    root = Path(storage_root)
    request_digest = _request_fingerprint(items)
    run_key = _sha256(run_id.encode("utf-8"))
    ledger_path = root / "registry" / "validation_runs" / (run_key + ".json")
    if ledger_path.exists():
        existing = _load_json(ledger_path, "validation ledger")
        if existing.get("request_digest") != request_digest:
            raise ArtifactNormalizationError(
                "validation_run_id already exists with different requests"
            )
        return existing

    dispositions: List[Dict[str, Any]] = []
    accounting = {
        "inputs": len(items),
        "validated": 0,
        "failed": 0,
        "derivative_written": 0,
        "derivative_existing": 0,
    }

    for index, item in enumerate(items):
        source_id = str(item["source_artifact_id"])
        source_sha = str(item.get("source_sha256") or "")
        disposition: Dict[str, Any] = {
            "input_index": index,
            "source_artifact_id": source_id,
            "source_sha256": source_sha,
        }
        if (
            len(source_sha) != 64
            or any(ch not in "0123456789abcdef" for ch in source_sha)
            or source_id != _artifact_id(source_sha)
        ):
            disposition.update(
                {"outcome": "FAILED", "failure_code": "SOURCE_IDENTITY_INVALID"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue

        content_record_path = (
            root / "registry" / "content" / source_sha[:2] / (source_sha + ".json")
        )
        quarantine_path = root / "quarantine" / "sha256" / source_sha[:2] / source_sha
        try:
            content_record = _load_json(content_record_path, "content record")
        except IntakeValidationError:
            disposition.update(
                {"outcome": "FAILED", "failure_code": "CONTENT_RECORD_UNAVAILABLE"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue
        if (
            content_record.get("artifact_id") != source_id
            or content_record.get("sha256") != source_sha
            or content_record.get("lifecycle_state") != "QUARANTINED"
            or content_record.get("active_snapshot_eligible") is not False
        ):
            disposition.update(
                {"outcome": "FAILED", "failure_code": "CONTENT_RECORD_INVALID"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue
        if not quarantine_path.is_file() or quarantine_path.is_symlink():
            disposition.update(
                {"outcome": "FAILED", "failure_code": "QUARANTINE_BYTES_UNAVAILABLE"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue

        source_bytes = quarantine_path.read_bytes()
        actual_sha = _sha256(source_bytes)
        if actual_sha != source_sha:
            disposition.update(
                {"outcome": "FAILED", "failure_code": "SOURCE_DIGEST_MISMATCH"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue

        detected_mime = _detected_mime(source_bytes)
        expected_mime = item.get("expected_mime_type")
        if detected_mime not in _ALLOWED_MIME:
            disposition.update(
                {"outcome": "FAILED", "failure_code": "MIME_UNSUPPORTED"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue
        if expected_mime is not None and str(expected_mime) != detected_mime:
            disposition.update(
                {"outcome": "FAILED", "failure_code": "MIME_MISMATCH"}
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue

        schema_errors: List[str] = []
        if item.get("json_schema") is not None:
            if detected_mime != "application/json":
                schema_errors = ["JSON schema supplied for non-JSON artifact"]
            else:
                schema = item["json_schema"]
                if not isinstance(schema, Mapping):
                    schema_errors = ["json_schema must be an object"]
                else:
                    schema_errors = _validate_json_schema(
                        json.loads(source_bytes.decode("utf-8")), schema
                    )
        if schema_errors:
            disposition.update(
                {
                    "outcome": "FAILED",
                    "failure_code": "SCHEMA_INVALID",
                    "schema_errors": schema_errors,
                }
            )
            accounting["failed"] += 1
            dispositions.append(disposition)
            continue

        derivative_bytes = _normalize(source_bytes, detected_mime)
        derivative_sha = _sha256(derivative_bytes)
        derivative_id = _artifact_id(derivative_sha)
        derivative_path = (
            root / "normalized" / "sha256" / derivative_sha[:2] / derivative_sha
        )
        created = _safe_write_once(derivative_path, derivative_bytes)
        if created:
            accounting["derivative_written"] += 1
        else:
            accounting["derivative_existing"] += 1
        inherited = _classification(content_record)
        provenance = {
            "schema_version": "normalized_derivative_provenance.v1",
            "derivative_artifact_id": derivative_id,
            "derivative_sha256": derivative_sha,
            "source_artifact_id": source_id,
            "source_sha256": source_sha,
            "normalization": {
                "algorithm": (
                    "canonical-json-v1"
                    if detected_mime == "application/json"
                    else "utf8-newline-v1"
                ),
                "mime_type": detected_mime,
            },
            "classification": inherited,
            "lifecycle_state": "QUARANTINED",
            "active_snapshot_eligible": False,
        }
        provenance_path = (
            root
            / "registry"
            / "derivatives"
            / derivative_sha[:2]
            / (derivative_sha + ".json")
        )
        _write_json_once(provenance_path, provenance)
        disposition.update(
            {
                "outcome": "VALIDATED",
                "detected_mime_type": detected_mime,
                "schema_valid": True,
                "derivative_artifact_id": derivative_id,
                "derivative_sha256": derivative_sha,
                "derivative_locator": derivative_path.relative_to(root).as_posix(),
                "provenance_locator": provenance_path.relative_to(root).as_posix(),
                "classification": inherited,
                "active_snapshot_eligible": False,
            }
        )
        accounting["validated"] += 1
        dispositions.append(disposition)

    if accounting["inputs"] != accounting["validated"] + accounting["failed"]:
        raise ArtifactNormalizationError("validation accounting partition is incomplete")
    if accounting["validated"] != (
        accounting["derivative_written"] + accounting["derivative_existing"]
    ):
        raise ArtifactNormalizationError("derivative accounting partition is incomplete")

    report = {
        "schema_version": "artifact_validation_report.v1",
        "validation_run_id": run_id,
        "request_digest": request_digest,
        "completed_at": completed_at,
        "accounting": accounting,
        "dispositions": dispositions,
        "active_snapshot_promoted": False,
    }
    _write_json_once(ledger_path, report)
    return report

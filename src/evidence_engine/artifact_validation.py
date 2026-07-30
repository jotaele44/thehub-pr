"""Offline validation and deterministic normalization of quarantined artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from jsonschema import Draft202012Validator

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
    fd, temporary_name = tempfile.mkstemp(
        prefix=".normalize-", dir=str(path.parent)
    )
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
        raise IntakeValidationError(
            label + " is not valid UTF-8 JSON"
        ) from exc
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
    return (
        "application/json"
        if isinstance(parsed, (dict, list))
        else "text/plain"
    )


def _normalize(data: bytes, mime_type: str) -> bytes:
    """Return canonical bytes.

    JSON is serialized with sorted keys and exactly one trailing LF.
    Text converts CRLF/CR to LF, removes all trailing LFs, and appends exactly
    one LF. Empty text therefore normalizes to a single LF byte.
    """
    text = data.decode("utf-8")
    if mime_type == "application/json":
        value = json.loads(text)
        return _canonical_bytes(value) + b"\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.rstrip("\n") + "\n"
    return normalized.encode("utf-8")


def _classification(content_record: Mapping[str, Any]) -> Dict[str, Any]:
    effective = content_record.get("effective_classification")
    if not isinstance(effective, Mapping):
        raise IntakeValidationError(
            "content record lacks effective_classification"
        )
    effective_level = str(effective.get("level") or "")
    if effective_level not in set(_CLASS_ORDER) | {"TEST_ONLY"}:
        raise IntakeValidationError(
            "unsupported source classification: " + effective_level
        )

    intended = content_record.get("intended_classification")
    complete = bool(
        content_record.get("classification_lineage_complete")
        and isinstance(intended, Mapping)
        and intended.get("lineage_complete") is True
    )
    if complete and isinstance(intended, Mapping):
        intended_level = str(intended.get("level") or "")
        restriction_floor = str(
            intended.get("restriction_floor") or ""
        )
        test_only = bool(intended.get("test_only"))
        source_levels = intended.get("source_levels", [])
        if (
            intended_level not in set(_CLASS_ORDER) | {"TEST_ONLY"}
            or restriction_floor not in _CLASS_ORDER
            or not isinstance(source_levels, list)
        ):
            raise IntakeValidationError(
                "content record has invalid intended classification lineage"
            )
        return {
            "level": intended_level,
            "effective_level": effective_level,
            "restriction_floor": restriction_floor,
            "test_only": test_only,
            "source_levels": sorted(str(value) for value in source_levels),
            "lineage_complete": True,
            "inherited_from": str(
                content_record.get("artifact_id") or ""
            ),
            "reason": (
                "derivative inherits H02 intended classification lineage "
                "while remaining effectively quarantined"
            ),
        }

    legacy_floor = (
        "PUBLIC" if effective_level == "TEST_ONLY" else effective_level
    )
    return {
        "level": effective_level,
        "effective_level": effective_level,
        "restriction_floor": legacy_floor,
        "test_only": effective_level == "TEST_ONLY",
        "source_levels": [effective_level],
        "lineage_complete": False,
        "inherited_from": str(content_record.get("artifact_id") or ""),
        "reason": (
            "legacy H02 content record lacks persisted intended "
            "classification lineage"
        ),
    }


def _external_schema_refs(value: Any) -> List[str]:
    refs: List[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                if not child.startswith("#"):
                    refs.append(child)
            refs.extend(_external_schema_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_external_schema_refs(child))
    return refs


def _validate_json_schema(
    value: Any, schema: Mapping[str, Any]
) -> Tuple[List[str], Optional[str]]:
    """Validate locally and return messages plus a stable failure code."""
    if _external_schema_refs(schema):
        return [], "SCHEMA_EXTERNAL_REF_DENIED"
    try:
        Draft202012Validator.check_schema(dict(schema))
    except Exception:
        return [], "SCHEMA_DEFINITION_INVALID"
    try:
        validator = Draft202012Validator(dict(schema))
        messages = sorted(
            error.message for error in validator.iter_errors(value)
        )
    except Exception:
        return [], "SCHEMA_EVALUATION_ERROR"
    if messages:
        return messages, "SCHEMA_INVALID"
    return [], None


def _request_fingerprint(
    requests: Sequence[Mapping[str, Any]]
) -> str:
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
    normalized.sort(
        key=lambda item: str(item["source_artifact_id"])
    )
    return _sha256(_canonical_bytes(normalized))


def _failed_disposition(
    disposition: Dict[str, Any],
    failure_code: str,
    *,
    details: Optional[List[str]] = None,
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    disposition["outcome"] = "FAILED"
    disposition["failure_code"] = failure_code
    if details:
        disposition["schema_errors"] = details
    if error_type:
        disposition["error_type"] = error_type
    return disposition


def _provenance_edge_key(
    source_sha: str,
    derivative_sha: str,
    algorithm: str,
) -> str:
    return _sha256(
        _canonical_bytes(
            {
                "source_sha256": source_sha,
                "derivative_sha256": derivative_sha,
                "normalization_algorithm": algorithm,
            }
        )
    )


def validate_and_normalize_quarantined_artifacts(
    storage_root: Path,
    validation_run_id: str,
    requests: Iterable[Mapping[str, Any]],
    *,
    completed_at: str,
) -> Dict[str, Any]:
    """Validate H02 quarantine content and create immutable derivatives."""
    run_id = validation_run_id.strip()
    if not run_id:
        raise IntakeValidationError("validation_run_id is required")
    items = [dict(item) for item in requests]
    source_ids = [
        str(item.get("source_artifact_id") or "")
        for item in items
    ]
    if any(not source_id for source_id in source_ids):
        raise IntakeValidationError(
            "every request requires source_artifact_id"
        )
    if len(source_ids) != len(set(source_ids)):
        raise IntakeValidationError(
            "duplicate source_artifact_id in validation request"
        )

    root = Path(storage_root)
    request_digest = _request_fingerprint(items)
    run_key = _sha256(run_id.encode("utf-8"))
    ledger_path = (
        root
        / "registry"
        / "validation_runs"
        / (run_key + ".json")
    )
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
        try:
            if (
                len(source_sha) != 64
                or any(
                    ch not in "0123456789abcdef"
                    for ch in source_sha
                )
                or source_id != _artifact_id(source_sha)
            ):
                _failed_disposition(
                    disposition, "SOURCE_IDENTITY_INVALID"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue

            content_record_path = (
                root
                / "registry"
                / "content"
                / source_sha[:2]
                / (source_sha + ".json")
            )
            quarantine_path = (
                root
                / "quarantine"
                / "sha256"
                / source_sha[:2]
                / source_sha
            )
            try:
                content_record = _load_json(
                    content_record_path, "content record"
                )
            except IntakeValidationError:
                _failed_disposition(
                    disposition, "CONTENT_RECORD_UNAVAILABLE"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue
            if (
                content_record.get("artifact_id") != source_id
                or content_record.get("sha256") != source_sha
                or content_record.get("lifecycle_state")
                != "QUARANTINED"
                or content_record.get("active_snapshot_eligible")
                is not False
            ):
                _failed_disposition(
                    disposition, "CONTENT_RECORD_INVALID"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue
            if (
                not quarantine_path.is_file()
                or quarantine_path.is_symlink()
            ):
                _failed_disposition(
                    disposition, "QUARANTINE_BYTES_UNAVAILABLE"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue

            source_bytes = quarantine_path.read_bytes()
            actual_sha = _sha256(source_bytes)
            if actual_sha != source_sha:
                _failed_disposition(
                    disposition, "SOURCE_DIGEST_MISMATCH"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue

            detected_mime = _detected_mime(source_bytes)
            expected_mime = item.get("expected_mime_type")
            if detected_mime not in _ALLOWED_MIME:
                _failed_disposition(
                    disposition, "MIME_UNSUPPORTED"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue
            if (
                expected_mime is not None
                and str(expected_mime) != detected_mime
            ):
                _failed_disposition(
                    disposition, "MIME_MISMATCH"
                )
                accounting["failed"] += 1
                dispositions.append(disposition)
                continue

            assert detected_mime is not None
            if item.get("json_schema") is not None:
                if detected_mime != "application/json":
                    _failed_disposition(
                        disposition,
                        "SCHEMA_INVALID",
                        details=[
                            "JSON schema supplied for non-JSON artifact"
                        ],
                    )
                    accounting["failed"] += 1
                    dispositions.append(disposition)
                    continue
                schema = item["json_schema"]
                if not isinstance(schema, Mapping):
                    _failed_disposition(
                        disposition,
                        "SCHEMA_DEFINITION_INVALID",
                    )
                    accounting["failed"] += 1
                    dispositions.append(disposition)
                    continue
                schema_errors, schema_failure = (
                    _validate_json_schema(
                        json.loads(
                            source_bytes.decode("utf-8")
                        ),
                        schema,
                    )
                )
                if schema_failure is not None:
                    _failed_disposition(
                        disposition,
                        schema_failure,
                        details=schema_errors,
                    )
                    accounting["failed"] += 1
                    dispositions.append(disposition)
                    continue

            derivative_bytes = _normalize(
                source_bytes, detected_mime
            )
            derivative_sha = _sha256(derivative_bytes)
            derivative_id = _artifact_id(derivative_sha)
            algorithm = (
                "canonical-json-v1"
                if detected_mime == "application/json"
                else "utf8-newline-v1"
            )
            derivative_path = (
                root
                / "normalized"
                / "sha256"
                / derivative_sha[:2]
                / derivative_sha
            )
            derivative_created = _safe_write_once(
                derivative_path, derivative_bytes
            )

            derivative_record = {
                "schema_version": (
                    "normalized_derivative_content.v1"
                ),
                "derivative_artifact_id": derivative_id,
                "derivative_sha256": derivative_sha,
                "size_bytes": len(derivative_bytes),
                "mime_type": detected_mime,
                "normalization_algorithm": algorithm,
                "derivative_locator": (
                    derivative_path.relative_to(root).as_posix()
                ),
                "lifecycle_state": "QUARANTINED",
                "effective_classification": {
                    "level": "QUARANTINED",
                    "reason": (
                        "normalized derivative is not certified "
                        "or active"
                    ),
                },
                "active_snapshot_eligible": False,
            }
            derivative_record_path = (
                root
                / "registry"
                / "derivative_content"
                / derivative_sha[:2]
                / (derivative_sha + ".json")
            )
            _write_json_once(
                derivative_record_path, derivative_record
            )

            inherited = _classification(content_record)
            edge_key = _provenance_edge_key(
                source_sha, derivative_sha, algorithm
            )
            provenance = {
                "schema_version": (
                    "source_derivative_provenance_edge.v1"
                ),
                "provenance_edge_id": (
                    "provenance-sha256-" + edge_key
                ),
                "source_artifact_id": source_id,
                "source_sha256": source_sha,
                "derivative_artifact_id": derivative_id,
                "derivative_sha256": derivative_sha,
                "normalization": {
                    "algorithm": algorithm,
                    "mime_type": detected_mime,
                },
                "classification": inherited,
                "lifecycle_state": "QUARANTINED",
                "active_snapshot_eligible": False,
            }
            provenance_path = (
                root
                / "registry"
                / "provenance_edges"
                / edge_key[:2]
                / (edge_key + ".json")
            )
            _write_json_once(provenance_path, provenance)
            disposition.update(
                {
                    "outcome": "VALIDATED",
                    "detected_mime_type": detected_mime,
                    "schema_valid": True,
                    "derivative_artifact_id": derivative_id,
                    "derivative_sha256": derivative_sha,
                    "derivative_locator": (
                        derivative_path.relative_to(root).as_posix()
                    ),
                    "derivative_content_record_locator": (
                        derivative_record_path.relative_to(
                            root
                        ).as_posix()
                    ),
                    "provenance_locator": (
                        provenance_path.relative_to(root).as_posix()
                    ),
                    "provenance_edge_id": (
                        provenance["provenance_edge_id"]
                    ),
                    "classification": inherited,
                    "active_snapshot_eligible": False,
                }
            )
            if derivative_created:
                accounting["derivative_written"] += 1
            else:
                accounting["derivative_existing"] += 1
            accounting["validated"] += 1
            dispositions.append(disposition)
        except Exception as exc:
            _failed_disposition(
                disposition,
                "VALIDATION_PROCESSING_ERROR",
                error_type=type(exc).__name__,
            )
            accounting["failed"] += 1
            dispositions.append(disposition)

    if accounting["inputs"] != (
        accounting["validated"] + accounting["failed"]
    ):
        raise ArtifactNormalizationError(
            "validation accounting partition is incomplete"
        )
    if accounting["validated"] != (
        accounting["derivative_written"]
        + accounting["derivative_existing"]
    ):
        raise ArtifactNormalizationError(
            "derivative accounting partition is incomplete"
        )

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

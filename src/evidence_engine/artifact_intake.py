"""Offline, quarantine-first, content-addressed artifact intake.

The module accepts only caller-supplied local files and an already-created
``acquisition_receipt.v1`` record. It performs no acquisition, model execution,
producer RPC, snapshot promotion, query answering, or remote database access.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

CLASSIFICATION_LEVELS = {
    "PUBLIC",
    "INTERNAL",
    "RESTRICTED",
    "SENSITIVE_LOCATION",
    "LEGAL_HOLD",
    "QUARANTINED",
    "TEST_ONLY",
}
_RESTRICTION_ORDER = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "RESTRICTED": 2,
    "SENSITIVE_LOCATION": 3,
    "LEGAL_HOLD": 4,
    "QUARANTINED": 5,
}
_DEFAULT_ALLOWED_MIME_TYPES = {
    "application/json",
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "text/plain",
}


class ArtifactIntakeError(RuntimeError):
    """Raised when an intake cannot be completed safely or idempotently."""


class IntakeValidationError(ArtifactIntakeError, ValueError):
    """Raised when a receipt or local artifact manifest violates the contract."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_id(digest: str) -> str:
    return "artifact-sha256-" + digest


def _default_schema_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "contracts"
        / "skywatcher_ai"
    )


def validate_acquisition_receipt(
    receipt: Mapping[str, Any], *, schema_dir: Optional[Path] = None
) -> None:
    """Validate an acquisition receipt against the frozen ADR 0006 schema."""
    root = Path(schema_dir) if schema_dir is not None else _default_schema_dir()
    acquisition_path = root / "acquisition_receipt.v1.schema.json"
    common_path = root / "skywatcher_ai_common.v1.schema.json"
    if not acquisition_path.is_file() or not common_path.is_file():
        raise IntakeValidationError("acquisition receipt schemas are unavailable")

    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    common = json.loads(common_path.read_text(encoding="utf-8"))
    registry = Registry()
    for name, schema in (
        (acquisition_path.name, acquisition),
        (common_path.name, common),
    ):
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(name, resource)
        registry = registry.with_resource(schema["$id"], resource)

    validator = Draft202012Validator(
        acquisition,
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(dict(receipt)), key=lambda item: list(item.path))
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise IntakeValidationError("invalid acquisition receipt: " + messages)


def _detect_mime_type(data: bytes) -> Optional[str]:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"

    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\x00" in decoded:
        return None
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return "text/plain"
    if isinstance(parsed, (dict, list)):
        return "application/json"
    return "text/plain"


def _classification_source(
    level: str, object_id: Optional[str], reason: Optional[str]
) -> Dict[str, Optional[str]]:
    if level not in CLASSIFICATION_LEVELS:
        raise IntakeValidationError("unsupported classification level: " + level)
    return {"level": level, "object_id": object_id, "reason": reason}


def _resolve_intended_classification(
    receipt: Mapping[str, Any], item: Mapping[str, Any]
) -> Dict[str, Any]:
    sources: List[Dict[str, Optional[str]]] = []
    receipt_level = str(receipt.get("classification") or "PUBLIC")
    sources.append(
        _classification_source(
            receipt_level,
            str(receipt["receipt_id"]),
            "acquisition receipt",
        )
    )

    item_level = str(item.get("classification") or "PUBLIC")
    sources.append(
        _classification_source(
            item_level,
            str(item.get("artifact_id") or ""),
            "artifact manifest",
        )
    )
    inherited = item.get("inherited_classifications", [])
    if not isinstance(inherited, list):
        raise IntakeValidationError("inherited_classifications must be an array")
    for entry in inherited:
        if not isinstance(entry, Mapping):
            raise IntakeValidationError("classification inheritance entries must be objects")
        sources.append(
            _classification_source(
                str(entry.get("level") or ""),
                str(entry.get("object_id")) if entry.get("object_id") is not None else None,
                str(entry.get("reason")) if entry.get("reason") is not None else None,
            )
        )

    test_only = any(source["level"] == "TEST_ONLY" for source in sources)
    non_test_levels = [
        str(source["level"])
        for source in sources
        if source["level"] != "TEST_ONLY"
    ]
    restriction_floor = max(
        non_test_levels or ["PUBLIC"], key=lambda level: _RESTRICTION_ORDER[level]
    )
    intended_level = "TEST_ONLY" if test_only else restriction_floor
    return {
        "level": intended_level,
        "restriction_floor": restriction_floor,
        "test_only": test_only,
        "sources": sources,
    }


def _safe_write_once(path: Path, data: bytes) -> bool:
    """Write bytes without replacing an existing path; return True if created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing != data:
            raise ArtifactIntakeError("immutable path content conflict: " + str(path))
        return False

    fd, temporary_name = tempfile.mkstemp(prefix=".intake-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
            created = True
        except FileExistsError:
            if path.read_bytes() != data:
                raise ArtifactIntakeError("immutable path content conflict: " + str(path))
            created = False
        return created
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(path: Path, value: Mapping[str, Any]) -> bool:
    return _safe_write_once(path, _canonical_bytes(dict(value)) + b"\n")


def _receipt_ledger_path(root: Path, receipt_id: str) -> Path:
    key = _sha256_bytes(receipt_id.encode("utf-8"))
    return root / "registry" / "intakes" / (key + ".json")


def _manifest_fingerprint(items: Sequence[Mapping[str, Any]]) -> str:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        normalized.append(
            {
                "artifact_id": item.get("artifact_id"),
                "sha256": item.get("sha256"),
                "declared_mime_type": item.get("declared_mime_type"),
                "classification": item.get("classification"),
                "inherited_classifications": item.get("inherited_classifications", []),
            }
        )
    normalized.sort(key=lambda value: str(value.get("artifact_id") or ""))
    return _sha256_bytes(_canonical_bytes(normalized))


def _replay_existing_ledger(
    ledger_path: Path,
    receipt_digest: str,
    manifest_digest: str,
) -> Optional[Dict[str, Any]]:
    if not ledger_path.exists():
        return None
    existing = json.loads(ledger_path.read_text(encoding="utf-8"))
    if existing.get("receipt_digest") != receipt_digest:
        raise ArtifactIntakeError("receipt_id already exists with different receipt content")
    if existing.get("input_manifest_digest") != manifest_digest:
        raise ArtifactIntakeError("receipt_id already exists with different artifact manifest")
    return existing


def intake_local_artifacts(
    storage_root: Path,
    receipt: Mapping[str, Any],
    artifacts: Iterable[Mapping[str, Any]],
    *,
    max_size_bytes: int,
    allowed_mime_types: Optional[Iterable[str]] = None,
    schema_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Quarantine and register local artifacts with complete accounting.

    Every input receives exactly one terminal disposition. Inputs that pass the
    pre-read regular-file and size gates are copied to a content-addressed
    quarantine path before digest, MIME, classification, or registry acceptance
    is finalized. Nothing is promoted to an active snapshot.
    """
    if max_size_bytes <= 0:
        raise IntakeValidationError("max_size_bytes must be positive")
    validate_acquisition_receipt(receipt, schema_dir=schema_dir)

    items = [dict(item) for item in artifacts]
    declared_ids: List[str] = []
    for item in items:
        artifact_id = str(item.get("artifact_id") or "").strip()
        expected_sha = str(item.get("sha256") or "").strip()
        if not artifact_id or not expected_sha:
            raise IntakeValidationError("every artifact requires artifact_id and sha256")
        if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
            raise IntakeValidationError("artifact sha256 must be lowercase hexadecimal")
        declared_ids.append(artifact_id)
    if len(set(declared_ids)) != len(declared_ids):
        raise IntakeValidationError("artifact manifest contains duplicate artifact_id values")
    receipt_ids = list(receipt.get("artifact_ids", []))
    if sorted(receipt_ids) != sorted(declared_ids):
        raise IntakeValidationError("receipt artifact_ids must exactly match the intake manifest")

    root = Path(storage_root)
    allowed = set(
        _DEFAULT_ALLOWED_MIME_TYPES
        if allowed_mime_types is None
        else allowed_mime_types
    )
    if not allowed or not allowed <= _DEFAULT_ALLOWED_MIME_TYPES:
        raise IntakeValidationError("allowed_mime_types contains an unsupported or empty set")

    receipt_digest = _sha256_bytes(_canonical_bytes(dict(receipt)))
    manifest_digest = _manifest_fingerprint(items)
    ledger_path = _receipt_ledger_path(root, str(receipt["receipt_id"]))
    replay = _replay_existing_ledger(ledger_path, receipt_digest, manifest_digest)
    if replay is not None:
        return replay

    dispositions: List[Dict[str, Any]] = []
    counters = {
        "inputs": len(items),
        "registered": 0,
        "existing": 0,
        "rejected": 0,
        "quarantine_written": 0,
        "quarantine_existing": 0,
        "not_stored": 0,
    }

    for index, item in enumerate(items):
        declared_id = str(item["artifact_id"])
        expected_sha = str(item["sha256"])
        source_path = Path(str(item.get("path") or ""))
        disposition: Dict[str, Any] = {
            "input_index": index,
            "declared_artifact_id": declared_id,
            "expected_sha256": expected_sha,
        }

        if not source_path.is_file() or source_path.is_symlink():
            disposition.update(
                {
                    "disposition": "REJECTED_NOT_STORED",
                    "reason": "source_not_regular_file",
                }
            )
            counters["rejected"] += 1
            counters["not_stored"] += 1
            dispositions.append(disposition)
            continue

        size_bytes = source_path.stat().st_size
        disposition["size_bytes"] = size_bytes
        if size_bytes > max_size_bytes:
            disposition.update(
                {
                    "disposition": "REJECTED_NOT_STORED",
                    "reason": "size_limit_exceeded",
                }
            )
            counters["rejected"] += 1
            counters["not_stored"] += 1
            dispositions.append(disposition)
            continue

        data = source_path.read_bytes()
        if len(data) > max_size_bytes:
            disposition.update(
                {
                    "disposition": "REJECTED_NOT_STORED",
                    "reason": "size_limit_exceeded_during_read",
                }
            )
            counters["rejected"] += 1
            counters["not_stored"] += 1
            dispositions.append(disposition)
            continue
        actual_sha = _sha256_bytes(data)
        actual_id = _artifact_id(actual_sha)
        quarantine_path = root / "quarantine" / "sha256" / actual_sha[:2] / actual_sha
        quarantine_created = _safe_write_once(quarantine_path, data)
        if quarantine_created:
            counters["quarantine_written"] += 1
        else:
            counters["quarantine_existing"] += 1
        disposition.update(
            {
                "actual_artifact_id": actual_id,
                "actual_sha256": actual_sha,
                "quarantine_locator": quarantine_path.relative_to(root).as_posix(),
            }
        )

        if actual_sha != expected_sha or actual_id != declared_id:
            disposition.update(
                {
                    "disposition": "REJECTED_QUARANTINED",
                    "reason": "sha256_identity_mismatch",
                }
            )
            counters["rejected"] += 1
            dispositions.append(disposition)
            continue

        detected_mime = _detect_mime_type(data)
        declared_mime = item.get("declared_mime_type")
        disposition["detected_mime_type"] = detected_mime
        if detected_mime is None or detected_mime not in allowed:
            disposition.update(
                {
                    "disposition": "REJECTED_QUARANTINED",
                    "reason": "mime_type_not_allowed",
                }
            )
            counters["rejected"] += 1
            dispositions.append(disposition)
            continue
        if declared_mime is not None and str(declared_mime) != detected_mime:
            disposition.update(
                {
                    "disposition": "REJECTED_QUARANTINED",
                    "reason": "declared_mime_mismatch",
                }
            )
            counters["rejected"] += 1
            dispositions.append(disposition)
            continue

        intended = _resolve_intended_classification(receipt, item)
        content_record = {
            "schema_version": "content_addressed_artifact.v1",
            "artifact_id": actual_id,
            "sha256": actual_sha,
            "size_bytes": size_bytes,
            "mime_type": detected_mime,
            "quarantine_locator": quarantine_path.relative_to(root).as_posix(),
            "lifecycle_state": "QUARANTINED",
            "effective_classification": {
                "level": "QUARANTINED",
                "inherited_from": actual_id,
                "reason": "quarantine-first intake; no operational snapshot eligibility",
            },
            "active_snapshot_eligible": False,
        }
        record_path = root / "registry" / "content" / actual_sha[:2] / (actual_sha + ".json")
        created = _write_json_once(record_path, content_record)
        disposition.update(
            {
                "disposition": (
                    "REGISTERED_QUARANTINED" if created else "EXISTING_QUARANTINED"
                ),
                "reason": "accepted_into_quarantine_registry",
                "intended_classification": intended,
                "effective_classification": content_record["effective_classification"],
                "content_record_locator": record_path.relative_to(root).as_posix(),
                "active_snapshot_eligible": False,
            }
        )
        if created:
            counters["registered"] += 1
        else:
            counters["existing"] += 1
        dispositions.append(disposition)

    if counters["inputs"] != counters["registered"] + counters["existing"] + counters["rejected"]:
        raise ArtifactIntakeError("intake accounting partition is incomplete")
    if counters["inputs"] != counters["quarantine_written"] + counters["quarantine_existing"] + counters["not_stored"]:
        raise ArtifactIntakeError("storage accounting partition is incomplete")

    report = {
        "schema_version": "artifact_intake_report.v1",
        "receipt_id": str(receipt["receipt_id"]),
        "receipt_digest": receipt_digest,
        "input_manifest_digest": manifest_digest,
        "completed_at": receipt["completed_at"],
        "receipt": dict(receipt),
        "accounting": counters,
        "dispositions": dispositions,
        "active_snapshot_promoted": False,
    }
    _write_json_once(ledger_path, report)
    return report

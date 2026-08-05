"""Shared offline H07 schema, identity, path, and immutable-write helpers."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

class ProducerPackageAdmissionError(RuntimeError):
    """Raised when H07 cannot safely validate or persist an admission."""


_RESTRICTION_ORDER = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "RESTRICTED": 2,
    "SENSITIVE_LOCATION": 3,
    "LEGAL_HOLD": 4,
    "QUARANTINED": 5,
}
_SECRET_KEYS = {
    "api_key",
    "authorization",
    "authorization_header",
    "credential",
    "credential_value",
    "password",
    "secret",
    "secret_value",
    "token",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _contains_secret_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).strip().lower()
            if key in _SECRET_KEYS:
                return True
            if _contains_secret_material(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_material(item) for item in value)
    return False


def _safe_relative_path(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    if value.startswith("/") or value.endswith("/"):
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if ":" in parts[0]:
        return None
    normalized = PurePosixPath(value).as_posix()
    return normalized if normalized == value else None


def _path_within(root: Path, relative_path: str) -> Optional[Path]:
    safe = _safe_relative_path(relative_path)
    if safe is None:
        return None
    root_resolved = root.resolve()
    current = root
    for part in PurePosixPath(safe).parts:
        current = current / part
        if current.is_symlink():
            return None
    candidate = root / safe
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (FileNotFoundError, OSError, ValueError):
        return None
    if not resolved.is_file() or resolved.is_symlink():
        return None
    return resolved


def _safe_write_once(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ProducerPackageAdmissionError(
                "immutable path content conflict: " + str(path)
            )
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".producer-admission-",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
            return True
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise ProducerPackageAdmissionError(
                    "immutable path content conflict: " + str(path)
                )
            return False
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(path: Path, value: Mapping[str, Any]) -> bool:
    return _safe_write_once(path, _canonical_bytes(dict(value)) + b"\n")


def _load_json(path: Path, label: str) -> Dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ProducerPackageAdmissionError(label + " is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProducerPackageAdmissionError(
            label + " is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ProducerPackageAdmissionError(label + " must be a JSON object")
    return value


def _default_schema_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "contracts"
        / "skywatcher_ai"
    )


def validate_producer_package_records(
    job_record: Mapping[str, Any],
    run_receipt: Mapping[str, Any],
    package_manifest: Mapping[str, Any],
    lineage_manifest: Mapping[str, Any],
    *,
    schema_dir: Optional[Path] = None,
) -> None:
    """Validate H06/H07 records against the frozen Draft 2020-12 contracts."""
    root = Path(schema_dir) if schema_dir is not None else _default_schema_dir()
    schemas: Dict[str, Dict[str, Any]] = {}
    for path in sorted(root.glob("*.schema.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProducerPackageAdmissionError(
                "schema is not valid UTF-8 JSON: " + str(path)
            ) from exc
        if not isinstance(schema, dict):
            raise ProducerPackageAdmissionError(
                "schema must contain an object: " + str(path)
            )
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
    required = {
        "bounded_producer_job_record.v1.schema.json": job_record,
        "producer_run_receipt.v1.schema.json": run_receipt,
        "producer_package_manifest.v1.schema.json": package_manifest,
        "producer_output_lineage.v1.schema.json": lineage_manifest,
    }
    if not required.keys() <= schemas.keys():
        raise ProducerPackageAdmissionError(
            "required producer admission schemas are unavailable"
        )
    registry = Registry()
    for name, schema in schemas.items():
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(name, resource)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            registry = registry.with_resource(schema_id, resource)
    labels = {
        "bounded_producer_job_record.v1.schema.json": "job record",
        "producer_run_receipt.v1.schema.json": "run receipt",
        "producer_package_manifest.v1.schema.json": "package manifest",
        "producer_output_lineage.v1.schema.json": "lineage manifest",
    }
    for name, record in required.items():
        validator = Draft202012Validator(
            schemas[name],
            registry=registry,
            format_checker=FormatChecker(),
        )
        errors = sorted(
            validator.iter_errors(dict(record)),
            key=lambda item: list(item.path),
        )
        if errors:
            detail = "; ".join(error.message for error in errors)
            raise ProducerPackageAdmissionError(
                labels[name] + " violates its frozen schema: " + detail
            )


def _job_identity(job_spec: Mapping[str, Any]) -> Dict[str, str]:
    identity_body = dict(job_spec)
    identity_body.pop("signature", None)
    identity_body.pop("job_id", None)
    signed_body = dict(job_spec)
    signed_body.pop("signature", None)
    identity_digest = _sha256(_canonical_bytes(identity_body))
    return {
        "job_spec_id": "producer-job-sha256-" + identity_digest,
        "job_identity_sha256": identity_digest,
        "signed_payload_sha256": _sha256(_canonical_bytes(signed_body)),
    }


def _package_identity(package_manifest: Mapping[str, Any]) -> Dict[str, str]:
    manifest = _mapping(package_manifest)
    body = {
        "job_spec_id": manifest.get("job_spec_id"),
        "job_spec_sha256": manifest.get("job_spec_sha256"),
        "producer": manifest.get("producer"),
        "producer_revision": manifest.get("producer_revision"),
        "worker_profile": manifest.get("worker_profile"),
        "schema_revisions": manifest.get("schema_revisions"),
        "entries": manifest.get("entries"),
    }
    digest = _sha256(_canonical_bytes(body))
    return {
        "producer_package_id": "producer-package-sha256-" + digest,
        "package_sha256": digest,
    }


def _lineage_identity(lineage_manifest: Mapping[str, Any]) -> Dict[str, str]:
    body = dict(lineage_manifest)
    body.pop("lineage_manifest_id", None)
    digest = _sha256(_canonical_bytes(body))
    return {
        "lineage_manifest_id": "producer-lineage-sha256-" + digest,
        "lineage_manifest_sha256": _sha256(
            _canonical_bytes(dict(lineage_manifest))
        ),
    }


def _record_digests(
    job_record: Mapping[str, Any],
    run_receipt: Mapping[str, Any],
    package_manifest: Mapping[str, Any],
    lineage_manifest: Mapping[str, Any],
) -> Dict[str, str]:
    return {
        "job_record_sha256": _sha256(_canonical_bytes(dict(job_record))),
        "run_receipt_sha256": _sha256(_canonical_bytes(dict(run_receipt))),
        "package_manifest_sha256": _sha256(
            _canonical_bytes(dict(package_manifest))
        ),
        "lineage_manifest_sha256": _sha256(
            _canonical_bytes(dict(lineage_manifest))
        ),
    }


def _inspect_package_files(
    package_root: Path,
    package_manifest: Mapping[str, Any],
    expected_write_root: str,
) -> Tuple[Dict[str, Any], Dict[str, Path]]:
    root = Path(package_root)
    entries = [
        dict(item)
        for item in package_manifest.get("entries", [])
        if isinstance(item, Mapping)
    ]
    declared_paths = {
        str(item.get("relative_path") or "") for item in entries
    }
    failures: List[str] = []
    observations: List[Dict[str, Any]] = []
    verified_paths: Dict[str, Path] = {}
    root_valid = (
        root.is_dir()
        and not root.is_symlink()
        and root.name == expected_write_root
    )
    if not root_valid:
        failures.append("DESIGNATED_PACKAGE_ROOT_MISMATCH")
    observed_files: Set[str] = set()
    if root_valid:
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                failures.append("PACKAGE_SYMLINK_DENIED")
                continue
            if candidate.is_file():
                relative = candidate.relative_to(root).as_posix()
                observed_files.add(relative)
                if relative not in declared_paths:
                    failures.append("UNDECLARED_PACKAGE_FILE")
    for entry in entries:
        output_id = str(entry.get("output_id") or "")
        relative_path = str(entry.get("relative_path") or "")
        entry_failures: List[str] = []
        path = _path_within(root, relative_path) if root_valid else None
        if path is None:
            entry_failures.append("OUTPUT_PATH_ESCAPE_OR_MISSING")
            actual_sha = None
            actual_size = None
        else:
            try:
                data = path.read_bytes()
            except OSError:
                entry_failures.append("OUTPUT_READ_FAILED")
                actual_sha = None
                actual_size = None
            else:
                actual_sha = _sha256(data)
                actual_size = len(data)
                if (
                    entry.get("sha256") != actual_sha
                    or entry.get("size_bytes") != actual_size
                ):
                    entry_failures.append("OUTPUT_DIGEST_OR_SIZE_MISMATCH")
                else:
                    verified_paths[output_id] = path
        observations.append(
            {
                "output_id": output_id,
                "relative_path": relative_path,
                "declared_sha256": entry.get("sha256"),
                "declared_size_bytes": entry.get("size_bytes"),
                "actual_sha256": actual_sha,
                "actual_size_bytes": actual_size,
                "verified": not entry_failures,
                "failure_codes": sorted(set(entry_failures)),
            }
        )
    if observed_files != declared_paths and root_valid:
        failures.append("PACKAGE_FILE_SET_MISMATCH")
    return (
        {
            "root_valid": root_valid,
            "package_failures": sorted(set(failures)),
            "observed_files": sorted(observed_files),
            "entries": observations,
        },
        verified_paths,
    )

def _detect_mime_type(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return "text/plain"
    return (
        "application/json"
        if isinstance(parsed, (dict, list))
        else "text/plain"
    )


def _admission_receipt_path(storage_root: Path, admission_id: str) -> Path:
    key = _sha256(admission_id.encode("utf-8"))
    return (
        Path(storage_root)
        / "registry"
        / "producer_admissions"
        / (key + ".json")
    )


def _replay_existing_receipt(
    receipt_path: Path,
    digests: Mapping[str, str],
) -> Optional[Dict[str, Any]]:
    if not receipt_path.exists():
        return None
    existing = _load_json(receipt_path, "producer admission receipt")
    for key in (
        "job_record_sha256",
        "run_receipt_sha256",
        "package_manifest_sha256",
        "lineage_manifest_sha256",
    ):
        if existing.get(key) != digests.get(key):
            raise ProducerPackageAdmissionError(
                "admission_id already exists with changed "
                "job, run, package, or lineage"
            )
    return existing

__all__ = [
    "ProducerPackageAdmissionError",
    "_RESTRICTION_ORDER",
    "_admission_receipt_path",
    "_canonical_bytes",
    "_contains_secret_material",
    "_detect_mime_type",
    "_inspect_package_files",
    "_is_sha256",
    "_job_identity",
    "_lineage_identity",
    "_load_json",
    "_mapping",
    "_package_identity",
    "_record_digests",
    "_replay_existing_receipt",
    "_safe_write_once",
    "_sha256",
    "_write_json_once",
    "validate_producer_package_records",
]

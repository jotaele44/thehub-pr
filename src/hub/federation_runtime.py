"""Exact-byte validation for frozen federation producer runtime packages.

A producer runtime receipt is not an identity or certification claim by itself.
Audit loading may inspect coherent unresolved evidence, but is non-promotable.
Certified loading additionally requires a PASS producer state and validates the
actual control-plane documents shipped with the same artifact.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional, Union

from .spatial import SpatialContractError, validate_spatial_manifest

RUNTIME_SCHEMA_VERSION = "aguayluz_federation_runtime_freeze_v1"
AGUAYLUZ_REPOSITORY = "jotaele44/aguayluz-pr"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RUNTIME_PATHS = {
    "outputs/utility_assets.json",
    "outputs/service_events.json",
    "outputs/monitoring_readings.json",
    "outputs/source_manifest.json",
    "outputs/review_queue.json",
    "outputs/bridge_summary.json",
    "outputs/hub_export.json",
    "outputs/integration_report.json",
    "outputs/federation/manifest.json",
}
REQUIRED_CONTROL_PATHS = {
    "federation.spatial.json",
    ".federation/haf_contract.json",
    "governance/federation_compatibility.json",
    "governance/federation_gis_retention_v1.json",
}
REQUIRED_STREAMS = {"sources", "entities", "relationships", "alerts"}


class FederationRuntimeError(ValueError):
    """Raised when frozen producer runtime evidence violates the Hub contract."""


@dataclass(frozen=True)
class FederationRuntimePackage:
    repository: str
    producer_commit: str
    producer_tree: str
    state: str
    ingestion_mode: str
    promotable: bool
    manifest: Mapping[str, object]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return None
    return path.as_posix()


def _validate_file_receipts(
    entries: object,
    *,
    expected_count: object,
    required_paths: set[str],
    package_root: Optional[Path],
    require_git_blob: bool,
    label: str,
) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    if not isinstance(entries, list):
        return [f"{label} must be an array"], set()
    if not isinstance(expected_count, int) or isinstance(expected_count, bool):
        errors.append(f"{label} count must be an integer")
    elif expected_count != len(entries):
        errors.append(f"{label} count={expected_count} does not equal receipt count={len(entries)}")

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            errors.append(f"{label}[{index}] must be an object")
            continue
        rel = _safe_relative_path(entry.get("path"))
        if rel is None:
            errors.append(f"{label}[{index}] has unsafe or invalid path")
            continue
        if rel in seen:
            errors.append(f"duplicate {label} path: {rel}")
            continue
        seen.add(rel)
        size = entry.get("bytes")
        digest = entry.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"{label} {rel} has invalid byte size")
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            errors.append(f"{label} {rel} has invalid sha256")
        if require_git_blob:
            blob = entry.get("git_blob_sha")
            if not isinstance(blob, str) or not _HEX40.fullmatch(blob):
                errors.append(f"{label} {rel} has invalid git_blob_sha")

        if package_root is not None:
            candidate = package_root / rel
            if candidate.is_symlink():
                errors.append(f"{label} {rel} is a symlink")
            elif not candidate.is_file():
                errors.append(f"{label} {rel} is missing from package")
            else:
                actual_size = candidate.stat().st_size
                actual_hash = _sha256(candidate)
                if isinstance(size, int) and actual_size != size:
                    errors.append(f"{label} {rel} byte-size mismatch")
                if isinstance(digest, str) and actual_hash != digest:
                    errors.append(f"{label} {rel} sha256 mismatch")

    missing = sorted(required_paths - seen)
    if missing:
        errors.append(f"{label} missing required paths: {missing}")
    return errors, seen


def _validate_counts(counts: object) -> list[str]:
    if not isinstance(counts, Mapping):
        return ["counts object is required"]
    errors: list[str] = []
    integer_keys = (
        "utility_assets",
        "service_events",
        "records_total",
        "source_manifest_entries",
        "review_queue_items",
    )
    for key in integer_keys:
        value = counts.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"counts.{key} must be a non-negative integer")
    if all(isinstance(counts.get(key), int) and not isinstance(counts.get(key), bool) for key in ("utility_assets", "service_events", "records_total")):
        if counts["records_total"] != counts["utility_assets"] + counts["service_events"]:
            errors.append("counts.records_total does not equal utility_assets + service_events")
    streams = counts.get("canonical_streams")
    if not isinstance(streams, Mapping):
        errors.append("counts.canonical_streams is required")
    else:
        if set(streams) != REQUIRED_STREAMS:
            errors.append(f"canonical stream count keys mismatch: {sorted(streams)}")
        for stream, value in streams.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"canonical stream {stream} count must be a non-negative integer")
    return errors


def _load_json_object(path: Path, label: str, errors: list[str]) -> Optional[Mapping[str, object]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {label}: {exc}")
        return None
    if not isinstance(value, Mapping):
        errors.append(f"{label} root must be an object")
        return None
    return value


def _validate_control_documents(package_root: Path, *, certification: bool) -> list[str]:
    errors: list[str] = []

    spatial = _load_json_object(package_root / "federation.spatial.json", "federation.spatial.json", errors)
    if spatial is not None:
        errors.extend(validate_spatial_manifest(spatial, certification=certification))

    haf = _load_json_object(package_root / ".federation/haf_contract.json", "HAF contract", errors)
    if haf is not None:
        if haf.get("repository_full_name") != AGUAYLUZ_REPOSITORY:
            errors.append("HAF repository_full_name mismatch")
        if haf.get("certification_required") is not True:
            errors.append("HAF certification_required must be true")
        if haf.get("identity_policy") != "EVIDENCE_PRIORITY_FAIL_CLOSED":
            errors.append("HAF identity policy drift")
        if haf.get("unresolved_policy") != "FAIL_CLOSED":
            errors.append("HAF unresolved policy drift")
        if haf.get("adapter_release_version") != "0.5.0":
            errors.append("HAF adapter release version drift")
        if haf.get("haf_contract_version") != "2.0.0":
            errors.append("HAF contract version drift")

    compatibility = _load_json_object(
        package_root / "governance/federation_compatibility.json",
        "federation compatibility receipt",
        errors,
    )
    if compatibility is not None:
        if compatibility.get("repo") != "aguayluz-pr":
            errors.append("federation compatibility repo mismatch")
        disposition = compatibility.get("disposition")
        if disposition not in {"UNAFFECTED", "COMPATIBLE", "UPDATED", "BLOCKED"}:
            errors.append("invalid federation compatibility disposition")
        elif certification and disposition == "BLOCKED":
            errors.append("federation compatibility is BLOCKED")

    retention = _load_json_object(
        package_root / "governance/federation_gis_retention_v1.json",
        "GIS retention ledger",
        errors,
    )
    if retention is not None:
        if retention.get("repository") != AGUAYLUZ_REPOSITORY:
            errors.append("GIS retention repository mismatch")
        if retention.get("source_pr") != 209:
            errors.append("GIS retention source PR mismatch")
        if retention.get("expected_path_count") != 20:
            errors.append("GIS retention expected path count must be 20")

    return errors


def validate_federation_runtime_manifest(
    manifest: Mapping[str, object],
    *,
    package_root: Optional[Union[str, Path]] = None,
    certification: bool = False,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != RUNTIME_SCHEMA_VERSION:
        errors.append("unsupported runtime freeze schema")
    if manifest.get("repository") != AGUAYLUZ_REPOSITORY:
        errors.append("runtime repository mismatch")
    for key in ("producer_commit", "producer_tree"):
        value = manifest.get(key)
        if not isinstance(value, str) or not _HEX40.fullmatch(value):
            errors.append(f"{key} must be a lowercase 40-character Git SHA")

    mode = manifest.get("mode")
    state = manifest.get("state")
    if mode not in {"EVIDENCE_ONLY", "CERTIFICATION"}:
        errors.append("invalid runtime mode")
    if state not in {"PASS", "AUDIT_ONLY", "BLOCKED"}:
        errors.append("invalid runtime state")
    eligible = manifest.get("certification_eligible")
    if not isinstance(eligible, bool):
        errors.append("certification_eligible must be boolean")
    problems = manifest.get("problems")
    if not isinstance(problems, list) or not all(isinstance(item, str) for item in problems):
        errors.append("problems must be an array of strings")
        problems = []

    receipt = manifest.get("test_receipt")
    if not isinstance(receipt, Mapping) or receipt.get("status") != "PASS":
        errors.append("FULL executed-test receipt must be PASS")

    root = Path(package_root) if package_root is not None else None
    file_errors, _ = _validate_file_receipts(
        manifest.get("files"),
        expected_count=manifest.get("file_count"),
        required_paths=REQUIRED_RUNTIME_PATHS,
        package_root=root,
        require_git_blob=False,
        label="runtime files",
    )
    errors.extend(file_errors)
    control_errors, control_seen = _validate_file_receipts(
        manifest.get("control_plane_files"),
        expected_count=manifest.get("control_plane_file_count"),
        required_paths=REQUIRED_CONTROL_PATHS,
        package_root=root,
        require_git_blob=True,
        label="control-plane files",
    )
    errors.extend(control_errors)
    if control_seen and control_seen != REQUIRED_CONTROL_PATHS:
        errors.append(f"control-plane path set mismatch: {sorted(control_seen)}")
    errors.extend(_validate_counts(manifest.get("counts")))

    spatial_summary = manifest.get("spatial_certification")
    if not isinstance(spatial_summary, Mapping):
        errors.append("spatial_certification object is required")

    if root is not None and not errors:
        errors.extend(_validate_control_documents(root, certification=certification))

    if certification:
        if mode != "CERTIFICATION":
            errors.append("certified ingestion requires runtime mode CERTIFICATION")
        if state != "PASS":
            errors.append(f"certified ingestion requires runtime state PASS, got {state!r}")
        if eligible is not True:
            errors.append("certified ingestion requires certification_eligible=true")
        if problems:
            errors.append("certified ingestion requires zero producer problems")
        if isinstance(spatial_summary, Mapping):
            if spatial_summary.get("certification_ready") is not True:
                errors.append("producer spatial certification is not ready")
            if spatial_summary.get("certification_state") != "PASS":
                errors.append("producer spatial certification state is not PASS")
    return errors


def load_federation_runtime_manifest(
    path: Union[str, Path],
    *,
    package_root: Optional[Union[str, Path]] = None,
    certification: bool = False,
) -> FederationRuntimePackage:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise FederationRuntimeError("runtime manifest root must be an object")
    errors = validate_federation_runtime_manifest(
        data,
        package_root=package_root,
        certification=certification,
    )
    if errors:
        raise FederationRuntimeError("; ".join(errors))
    return FederationRuntimePackage(
        repository=str(data["repository"]),
        producer_commit=str(data["producer_commit"]),
        producer_tree=str(data["producer_tree"]),
        state=str(data["state"]),
        ingestion_mode="CERTIFIED" if certification else "AUDIT_ONLY",
        promotable=bool(certification),
        manifest=data,
    )


def load_certified_federation_runtime_manifest(
    path: Union[str, Path], *, package_root: Union[str, Path]
) -> FederationRuntimePackage:
    """Validate exact producer bytes and return a promotable package only on PASS."""
    try:
        return load_federation_runtime_manifest(
            path,
            package_root=package_root,
            certification=True,
        )
    except SpatialContractError as exc:
        raise FederationRuntimeError(str(exc)) from exc

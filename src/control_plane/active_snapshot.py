"""Atomic ACTIVE snapshot pointer promotion and rollback.

Snapshot content is immutable. Promotion and rollback only replace the small
query-serving pointer after validating the target frozen snapshot manifest.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from hub.contract_runtime import validate_contract


class ActiveSnapshotError(RuntimeError):
    """Raised when the ACTIVE snapshot pointer cannot be changed safely."""


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _atomic_replace(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".active-snapshot-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ActiveSnapshotError(f"snapshot manifest must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ActiveSnapshotError("snapshot manifest is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ActiveSnapshotError("snapshot manifest must contain an object")
    validate_contract("snapshot_manifest.v1", payload)
    return payload


def promote_snapshot(storage_root, manifest_path, *, actor: str, promoted_at: str) -> dict[str, Any]:
    """Atomically make a frozen snapshot the sole ACTIVE query target.

    Only manifests carrying a PROMOTE decision and zero failed/synthetic/test-only
    accounting are eligible. The manifest itself is never modified.
    """
    root = Path(storage_root)
    manifest = _load_snapshot(Path(manifest_path))
    decision = manifest["promotion_decision"]
    if decision.get("decision") != "PROMOTE":
        raise ActiveSnapshotError("snapshot promotion_decision is not PROMOTE")
    if manifest.get("failed_record_count") != 0:
        raise ActiveSnapshotError("snapshot contains failed records")
    synthetic = manifest.get("synthetic_accounting") or {}
    if synthetic.get("synthetic_count") != 0 or synthetic.get("test_only_count") != 0:
        raise ActiveSnapshotError("snapshot contains synthetic or TEST_ONLY records")

    snapshot_id = str(manifest["snapshot_id"])
    immutable_path = root / "registry" / "snapshots" / f"{snapshot_id}.json"
    immutable_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = _canonical_bytes(manifest)
    if immutable_path.exists():
        if immutable_path.is_symlink() or not immutable_path.is_file():
            raise ActiveSnapshotError(
                f"existing immutable snapshot must be a regular file: {immutable_path}"
            )
        if immutable_path.read_bytes() != manifest_bytes:
            raise ActiveSnapshotError("snapshot id already exists with different content")
    else:
        fd, temporary_name = tempfile.mkstemp(prefix=".snapshot-", dir=str(immutable_path.parent))
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(manifest_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, immutable_path)
            except FileExistsError:
                if immutable_path.read_bytes() != manifest_bytes:
                    raise ActiveSnapshotError("snapshot id content conflict")
        finally:
            temporary.unlink(missing_ok=True)

    pointer_path = root / "registry" / "active_snapshot.json"
    previous = None
    if pointer_path.exists():
        try:
            previous_payload = json.loads(pointer_path.read_text(encoding="utf-8"))
            previous = previous_payload.get("snapshot_id")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            raise ActiveSnapshotError("existing ACTIVE snapshot pointer is invalid")

    pointer = {
        "schema_version": "active_snapshot_pointer.v1",
        "snapshot_id": snapshot_id,
        "previous_snapshot_id": previous,
        "actor": actor,
        "activated_at": promoted_at,
        "manifest_locator": str(immutable_path.relative_to(root)),
    }
    _atomic_replace(pointer_path, pointer)
    return pointer


def rollback_snapshot(storage_root, target_snapshot_id: str, *, actor: str, rolled_back_at: str) -> dict[str, Any]:
    """Atomically repoint ACTIVE to an immutable previously registered snapshot."""
    root = Path(storage_root)
    target = root / "registry" / "snapshots" / f"{target_snapshot_id}.json"
    manifest = _load_snapshot(target)
    if manifest.get("snapshot_id") != target_snapshot_id:
        raise ActiveSnapshotError("rollback target snapshot identity mismatch")

    pointer_path = root / "registry" / "active_snapshot.json"
    previous = None
    if pointer_path.exists():
        try:
            previous = json.loads(pointer_path.read_text(encoding="utf-8")).get("snapshot_id")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            raise ActiveSnapshotError("existing ACTIVE snapshot pointer is invalid")
    pointer = {
        "schema_version": "active_snapshot_pointer.v1",
        "snapshot_id": target_snapshot_id,
        "previous_snapshot_id": previous,
        "actor": actor,
        "activated_at": rolled_back_at,
        "manifest_locator": str(target.relative_to(root)),
        "transition": "ROLLBACK",
    }
    _atomic_replace(pointer_path, pointer)
    return pointer


__all__ = ["ActiveSnapshotError", "promote_snapshot", "rollback_snapshot"]

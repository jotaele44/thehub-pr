"""Validated artifact registration and atomic activation for manager runs.

Execution success and dataset activation are separate states.  A producer may
exit zero and still fail validation; such a run must never replace the last
known-good application dataset.  This store therefore accepts only artifacts
whose validators all passed, copies them into an immutable run-addressed store,
hashes the copied bytes, and changes the active pointer only through an explicit
activation call.

The store is deliberately agnostic about producer semantics.  The runner or a
producer-specific validator decides *what* is valid; this module guarantees the
promotion mechanics and provenance identity once that decision is supplied.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from server.backend.federation_manager_transactions import write_atomic


class ArtifactRegistrationError(RuntimeError):
    """Artifact registration or activation was refused."""


@dataclass(frozen=True)
class ArtifactManifest:
    app_id: str
    artifact_id: str
    run_id: str
    kind: str
    sha256: str
    bytes: int
    payload_path: Path
    manifest_path: Path

    def as_receipt_output(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "path": str(self.payload_path),
            "manifest": str(self.manifest_path),
        }


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _tree_members(root: Path) -> list[tuple[str, int, str]]:
    members: list[tuple[str, int, str]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        digest, size = _sha256_file(path)
        members.append((relative, size, digest))
    return members


def _sha256_tree(root: Path) -> tuple[str, int, list[tuple[str, int, str]]]:
    members = _tree_members(root)
    digest = hashlib.sha256()
    total = 0
    for relative, size, member_hash in members:
        total += size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(member_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), total, members


def _all_validators_passed(validators: Sequence[Mapping[str, Any]]) -> bool:
    return bool(validators) and all(record.get("status") == "passed" for record in validators)


class ArtifactStore:
    """Immutable artifact manifests plus an atomic per-application active pointer."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.objects = self.root / "objects"
        self.active = self.root / "active"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.active.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _require_within(source: Path, allowed_root: Path) -> Path:
        source = Path(source).expanduser().resolve()
        allowed_root = Path(allowed_root).expanduser().resolve()
        try:
            source.relative_to(allowed_root)
        except ValueError as exc:
            raise ArtifactRegistrationError(
                f"artifact path escapes its allowed root: {source} outside {allowed_root}"
            ) from exc
        return source

    def register_validated(
        self,
        *,
        app_id: str,
        run_id: str,
        source: Path,
        allowed_root: Path,
        validators: Sequence[Mapping[str, Any]],
    ) -> ArtifactManifest:
        """Freeze one validated file/tree. Registration never changes active state."""
        if not _all_validators_passed(validators):
            raise ArtifactRegistrationError(
                "artifact registration requires a non-empty all-passed validator set"
            )
        source = self._require_within(source, allowed_root)
        if not source.exists():
            raise ArtifactRegistrationError(f"declared artifact does not exist: {source}")
        if not source.is_file() and not source.is_dir():
            raise ArtifactRegistrationError(f"artifact must be a file or directory: {source}")

        if source.is_file():
            kind = "file"
            digest, size = _sha256_file(source)
            members: list[tuple[str, int, str]] = []
        else:
            kind = "directory"
            digest, size, members = _sha256_tree(source)

        artifact_id = f"art_{digest[:32]}"
        destination = self.objects / app_id / artifact_id
        manifest_path = destination / "manifest.json"
        payload_path = destination / ("payload" if kind == "directory" else source.name)

        if destination.exists():
            existing = self._read_manifest(manifest_path)
            if existing.get("sha256") != digest or existing.get("kind") != kind:
                raise ArtifactRegistrationError(
                    f"artifact id collision at {destination}: existing manifestation differs"
                )
            return self._manifest_from_document(existing, manifest_path)

        staging = destination.with_name(f".{destination.name}.{run_id}.tmp")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=False)
        try:
            staged_payload = staging / payload_path.name
            if kind == "file":
                shutil.copy2(source, staged_payload)
                staged_hash, staged_size = _sha256_file(staged_payload)
            else:
                shutil.copytree(source, staged_payload)
                staged_hash, staged_size, staged_members = _sha256_tree(staged_payload)
                if staged_members != members:
                    raise ArtifactRegistrationError("directory changed while being registered")
            if staged_hash != digest or staged_size != size:
                raise ArtifactRegistrationError("artifact changed while being registered")

            document: Dict[str, Any] = {
                "schema_version": "prii.artifact-manifest/v1",
                "app_id": app_id,
                "artifact_id": artifact_id,
                "run_id": run_id,
                "kind": kind,
                "sha256": digest,
                "bytes": size,
                "payload_name": staged_payload.name,
                "members": [
                    {"path": path, "uncompressed_size": member_size, "sha256": member_hash}
                    for path, member_size, member_hash in members
                ],
            }
            write_atomic(staging / "manifest.json", json.dumps(document, sort_keys=True) + "\n")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, destination)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return self._manifest_from_document(document, manifest_path)

    def activate(self, app_id: str, artifact_id: str) -> Dict[str, Optional[str]]:
        """Atomically point an app at a registered immutable manifestation."""
        manifest_path = self.objects / app_id / artifact_id / "manifest.json"
        document = self._read_manifest(manifest_path)
        if document.get("app_id") != app_id or document.get("artifact_id") != artifact_id:
            raise ArtifactRegistrationError("artifact manifest identity does not match activation request")

        pointer = self.active / f"{app_id}.json"
        previous = self.current(app_id)
        payload = {
            "schema_version": "prii.active-artifact/v1",
            "app_id": app_id,
            "artifact_id": artifact_id,
            "sha256": document["sha256"],
        }
        write_atomic(pointer, json.dumps(payload, sort_keys=True) + "\n")
        return {
            "app_id": app_id,
            "previous_artifact_id": previous.get("artifact_id") if previous else None,
            "active_artifact_id": artifact_id,
        }

    def rollback(self, app_id: str, artifact_id: str) -> Dict[str, Optional[str]]:
        """Rollback is the same checked pointer swap to an already registered object."""
        return self.activate(app_id, artifact_id)

    def current(self, app_id: str) -> Optional[Dict[str, Any]]:
        pointer = self.active / f"{app_id}.json"
        if not pointer.exists():
            return None
        try:
            document = json.loads(pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactRegistrationError(f"active pointer is unreadable for {app_id}: {exc}") from exc
        artifact_id = document.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ArtifactRegistrationError(f"active pointer lacks artifact_id for {app_id}")
        manifest = self._read_manifest(self.objects / app_id / artifact_id / "manifest.json")
        if manifest.get("sha256") != document.get("sha256"):
            raise ArtifactRegistrationError(f"active pointer hash disagrees with artifact for {app_id}")
        return document

    @staticmethod
    def _read_manifest(path: Path) -> Dict[str, Any]:
        if not path.is_file():
            raise ArtifactRegistrationError(f"artifact manifest does not exist: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactRegistrationError(f"artifact manifest is unreadable: {path}: {exc}") from exc
        return document

    @staticmethod
    def _manifest_from_document(document: Mapping[str, Any], manifest_path: Path) -> ArtifactManifest:
        payload_path = manifest_path.parent / str(document["payload_name"])
        return ArtifactManifest(
            app_id=str(document["app_id"]),
            artifact_id=str(document["artifact_id"]),
            run_id=str(document["run_id"]),
            kind=str(document["kind"]),
            sha256=str(document["sha256"]),
            bytes=int(document["bytes"]),
            payload_path=payload_path,
            manifest_path=manifest_path,
        )

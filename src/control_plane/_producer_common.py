"""Shared H06 validation helpers with no worker, network, or credential runtime."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Dict, Mapping, Optional

from ._egress_common import (
    _canonical_bytes,
    _contains_secret_material,
    _is_sha256,
    _load_json,
    _nonempty,
    _safe_write_once,
    _sha256,
    _string_list,
    _write_json_once,
)


class ProducerBoundaryError(RuntimeError):
    """Raised when an H06 job, package, or immutable receipt fails closed."""


def _is_hex40(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _artifact_id(digest: str) -> str:
    return "artifact-sha256-" + digest


def _job_identity_body(job_spec: Mapping[str, Any]) -> Dict[str, Any]:
    value = dict(job_spec)
    value.pop("signature", None)
    value.pop("job_id", None)
    return value


def _signed_job_body(job_spec: Mapping[str, Any]) -> Dict[str, Any]:
    value = dict(job_spec)
    value.pop("signature", None)
    return value


def _job_identity(job_spec: Mapping[str, Any]) -> Dict[str, str]:
    identity_digest = _sha256(_canonical_bytes(_job_identity_body(job_spec)))
    payload = _canonical_bytes(_signed_job_body(job_spec))
    return {
        "job_spec_id": "producer-job-sha256-" + identity_digest,
        "job_identity_sha256": identity_digest,
        "signed_payload_sha256": _sha256(payload),
    }


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


def _content_locator_matches(locator: Any, digest: str) -> bool:
    return locator == "content://sha256/" + digest


def _path_within(root: Path, relative_path: str) -> Optional[Path]:
    safe = _safe_relative_path(relative_path)
    if safe is None:
        return None
    root_resolved = root.resolve()
    candidate = root / safe
    current = root
    for part in PurePosixPath(safe).parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (FileNotFoundError, ValueError, OSError):
        return None
    if not resolved.is_file() or resolved.is_symlink():
        return None
    return resolved


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = [
    "ProducerBoundaryError",
    "_artifact_id",
    "_canonical_bytes",
    "_contains_secret_material",
    "_content_locator_matches",
    "_is_hex40",
    "_is_sha256",
    "_job_identity",
    "_load_json",
    "_mapping",
    "_nonempty",
    "_path_within",
    "_safe_relative_path",
    "_safe_write_once",
    "_sha256",
    "_string_list",
    "_write_json_once",
]

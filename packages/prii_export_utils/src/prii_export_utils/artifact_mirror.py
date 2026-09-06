"""Exact-byte wrapper for optional hosted artifact mirrors.

Local outbox files remain authoritative. A hosted bridge may carry this wrapper,
which embeds the complete canonical envelope bytes plus independent size and
SHA-256 bindings. Receivers must reconstruct and verify those bytes before any
application-level processing; the hosted delivery identifier is never canonical.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .artifact_transport import (
    ArtifactTransportError,
    canonical_json_bytes,
    sha256_bytes,
    verify_envelope,
)

MIRROR_SCHEMA_VERSION = "prii.artifact-mirror.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MIRROR_FIELDS = frozenset(
    {
        "schema_version",
        "message_id",
        "source",
        "target",
        "kind",
        "envelope_size",
        "envelope_sha256",
        "envelope_base64",
    }
)


class InvalidMirrorError(ArtifactTransportError):
    """Raised when a mirror wrapper or its embedded envelope is invalid."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _require_fields(value: Mapping[str, Any]) -> None:
    missing = sorted(_MIRROR_FIELDS - set(value))
    extra = sorted(set(value) - _MIRROR_FIELDS)
    if missing or extra:
        raise InvalidMirrorError(
            f"mirror fields mismatch missing={missing} extra={extra}"
        )


def _canonical_envelope(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidMirrorError("embedded envelope is not UTF-8") from exc
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidMirrorError(f"embedded envelope is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidMirrorError("embedded envelope is not a JSON object")
    try:
        verify_envelope(value)
    except ArtifactTransportError as exc:
        raise InvalidMirrorError(str(exc)) from exc
    canonical = canonical_json_bytes(value) + b"\n"
    if data != canonical:
        raise InvalidMirrorError("embedded envelope bytes are not canonical")
    return value


def read_canonical_envelope(path: str | Path) -> tuple[dict[str, Any], bytes]:
    """Read one regular canonical outbox file without normalizing its bytes."""

    source_path = Path(path)
    if source_path.is_symlink() or not source_path.is_file():
        raise InvalidMirrorError(f"envelope path is not a regular file: {source_path}")
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise InvalidMirrorError(f"cannot read envelope {source_path}: {exc}") from exc
    return _canonical_envelope(data), data


def build_mirror_payload(path: str | Path) -> dict[str, Any]:
    """Wrap the exact canonical bytes from a local outbox file for mirroring."""

    envelope, data = read_canonical_envelope(path)
    return {
        "schema_version": MIRROR_SCHEMA_VERSION,
        "message_id": envelope["message_id"],
        "source": envelope["source"],
        "target": envelope["target"],
        "kind": envelope["kind"],
        "envelope_size": len(data),
        "envelope_sha256": sha256_bytes(data),
        "envelope_base64": base64.b64encode(data).decode("ascii"),
    }


def verify_mirror_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    """Verify wrapper metadata, exact bytes, and embedded envelope identity."""

    if not isinstance(payload, Mapping):
        raise InvalidMirrorError("mirror payload must be an object")
    _require_fields(payload)
    if payload["schema_version"] != MIRROR_SCHEMA_VERSION:
        raise InvalidMirrorError(
            f"unsupported mirror schema_version {payload['schema_version']!r}"
        )
    for field in ("message_id", "source", "target", "kind", "envelope_sha256"):
        if not isinstance(payload[field], str):
            raise InvalidMirrorError(f"{field} must be a string")
    if not _SHA256.fullmatch(payload["message_id"]):
        raise InvalidMirrorError("message_id must be a lowercase SHA-256 digest")
    if not _SHA256.fullmatch(payload["envelope_sha256"]):
        raise InvalidMirrorError(
            "envelope_sha256 must be a lowercase SHA-256 digest"
        )
    size = payload["envelope_size"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise InvalidMirrorError("envelope_size must be a positive integer")
    encoded = payload["envelope_base64"]
    if not isinstance(encoded, str):
        raise InvalidMirrorError("envelope_base64 must be a string")
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise InvalidMirrorError("envelope_base64 is not canonical base64") from exc
    if len(data) != size:
        raise InvalidMirrorError("envelope_size does not match embedded bytes")
    if sha256_bytes(data) != payload["envelope_sha256"]:
        raise InvalidMirrorError("envelope_sha256 does not match embedded bytes")

    envelope = _canonical_envelope(data)
    for field in ("message_id", "source", "target", "kind"):
        if payload[field] != envelope[field]:
            raise InvalidMirrorError(
                f"mirror {field} does not bind to embedded envelope"
            )
    return envelope, data

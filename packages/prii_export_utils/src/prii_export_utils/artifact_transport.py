"""Local-first, idempotent artifact transport for Federation repositories.

The transport deliberately has no network, database, queue, or third-party runtime
requirements. Producers emit immutable JSON envelopes into an outbox. A local
operator or optional bridge copies those exact bytes into a target inbox. Message
identity is derived from canonical content rather than filenames or timestamps, so
retries are deterministic and duplicates are bounded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = "prii.artifact-message.v1"
RECEIPT_SCHEMA_VERSION = "prii.artifact-receipt.v1"
_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ArtifactTransportError(RuntimeError):
    """Base exception for local artifact-transport failures."""


class InvalidEnvelopeError(ArtifactTransportError):
    """Raised when an envelope is malformed or fails its content hashes."""


class MessageCollisionError(ArtifactTransportError):
    """Raised when an existing message ID is bound to different bytes/content."""


@dataclass(frozen=True)
class TransportResult:
    """Deterministic result returned by emit/deliver/acknowledge operations."""

    status: str
    message_id: str
    path: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _component(value: str, field: str) -> str:
    if not isinstance(value, str) or not _COMPONENT.fullmatch(value):
        raise ValueError(f"{field} must match {_COMPONENT.pattern!r}; got {value!r}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for hashing and byte comparisons."""

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity_document(
    *,
    source: str,
    target: str,
    kind: str,
    idempotency_key: str,
    payload_sha256: str,
) -> dict[str, str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "target": target,
        "kind": kind,
        "idempotency_key": idempotency_key,
        "payload_sha256": payload_sha256,
    }


def build_envelope(
    *,
    source: str,
    target: str,
    kind: str,
    payload: Any,
    idempotency_key: str | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build and validate an immutable message envelope.

    ``idempotency_key`` defaults to the payload SHA-256. Callers that need to
    distinguish two logically separate emissions with byte-identical payloads must
    supply a stable domain key, such as a source event ID.
    """

    source = _component(source, "source")
    target = _component(target, "target")
    kind = _component(kind, "kind")
    payload_sha256 = sha256_bytes(canonical_json_bytes(payload))
    key = _component(idempotency_key or payload_sha256, "idempotency_key")
    identity = _identity_document(
        source=source,
        target=target,
        kind=kind,
        idempotency_key=key,
        payload_sha256=payload_sha256,
    )
    message_id = sha256_bytes(canonical_json_bytes(identity))
    envelope: dict[str, Any] = {
        **identity,
        "message_id": message_id,
        "created_at_utc": created_at_utc or _utc_now(),
        "payload": payload,
    }
    verify_envelope(envelope)
    return envelope


def verify_envelope(envelope: Mapping[str, Any]) -> None:
    """Fail closed when required fields, hashes, or identifiers disagree."""

    required = {
        "schema_version",
        "message_id",
        "source",
        "target",
        "kind",
        "idempotency_key",
        "created_at_utc",
        "payload_sha256",
        "payload",
    }
    missing = sorted(required - set(envelope))
    extra = sorted(set(envelope) - required)
    if missing or extra:
        raise InvalidEnvelopeError(f"envelope fields mismatch missing={missing} extra={extra}")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise InvalidEnvelopeError(f"unsupported schema_version {envelope['schema_version']!r}")
    try:
        source = _component(str(envelope["source"]), "source")
        target = _component(str(envelope["target"]), "target")
        kind = _component(str(envelope["kind"]), "kind")
        key = _component(str(envelope["idempotency_key"]), "idempotency_key")
    except ValueError as exc:
        raise InvalidEnvelopeError(str(exc)) from exc
    payload_sha256 = sha256_bytes(canonical_json_bytes(envelope["payload"]))
    if payload_sha256 != envelope["payload_sha256"]:
        raise InvalidEnvelopeError("payload_sha256 does not match canonical payload")
    identity = _identity_document(
        source=source,
        target=target,
        kind=kind,
        idempotency_key=key,
        payload_sha256=payload_sha256,
    )
    expected_id = sha256_bytes(canonical_json_bytes(identity))
    if expected_id != envelope["message_id"]:
        raise InvalidEnvelopeError("message_id does not match canonical identity")
    created = envelope["created_at_utc"]
    if not isinstance(created, str) or not created.endswith("Z"):
        raise InvalidEnvelopeError("created_at_utc must be an RFC3339 UTC string ending in Z")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _load_envelope(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidEnvelopeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidEnvelopeError(f"{path} is not a JSON object")
    verify_envelope(value)
    return value


def _same_identity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    keys = (
        "schema_version",
        "message_id",
        "source",
        "target",
        "kind",
        "idempotency_key",
        "payload_sha256",
        "payload",
    )
    return all(left[key] == right[key] for key in keys)


def emit_message(
    exchange_root: str | Path,
    *,
    source: str,
    target: str,
    kind: str,
    payload: Any,
    idempotency_key: str | None = None,
) -> TransportResult:
    """Atomically emit one immutable message to ``outbox/<target>``."""

    candidate = build_envelope(
        source=source,
        target=target,
        kind=kind,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    root = Path(exchange_root)
    path = root / "outbox" / candidate["target"] / f"{candidate['message_id']}.json"
    if path.exists():
        existing = _load_envelope(path)
        if not _same_identity(existing, candidate):
            raise MessageCollisionError(f"message collision at {path}")
        return TransportResult("DUPLICATE", candidate["message_id"], path)
    _atomic_write(path, canonical_json_bytes(candidate) + b"\n")
    return TransportResult("EMITTED", candidate["message_id"], path)


def deliver_message(
    exchange_root: str | Path,
    outbox_message: str | Path,
) -> TransportResult:
    """Copy exact canonical envelope bytes into ``inbox/<target>`` idempotently."""

    source_path = Path(outbox_message)
    envelope = _load_envelope(source_path)
    canonical = canonical_json_bytes(envelope) + b"\n"
    target = Path(exchange_root) / "inbox" / envelope["target"] / f"{envelope['message_id']}.json"
    if target.exists():
        existing = _load_envelope(target)
        if canonical_json_bytes(existing) != canonical_json_bytes(envelope):
            raise MessageCollisionError(f"inbox collision at {target}")
        return TransportResult("DUPLICATE", envelope["message_id"], target)
    _atomic_write(target, canonical)
    return TransportResult("DELIVERED", envelope["message_id"], target)


def iter_inbox(
    exchange_root: str | Path,
    target: str,
    *,
    include_acknowledged: bool = False,
) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield validated whole envelopes in deterministic filename order."""

    target = _component(target, "target")
    root = Path(exchange_root)
    inbox = root / "inbox" / target
    receipts = root / "receipts" / target
    if not inbox.is_dir():
        return
    for path in sorted(inbox.glob("*.json")):
        if not include_acknowledged and (receipts / path.name).is_file():
            continue
        yield path, _load_envelope(path)


def acknowledge_message(
    exchange_root: str | Path,
    *,
    target: str,
    message_id: str,
    consumer: str,
) -> TransportResult:
    """Write an immutable local receipt after the consumer commits its result."""

    target = _component(target, "target")
    consumer = _component(consumer, "consumer")
    if not re.fullmatch(r"[0-9a-f]{64}", message_id):
        raise ValueError("message_id must be a lowercase SHA-256 hex digest")
    root = Path(exchange_root)
    inbox_path = root / "inbox" / target / f"{message_id}.json"
    envelope = _load_envelope(inbox_path)
    if envelope["target"] != target or envelope["message_id"] != message_id:
        raise InvalidEnvelopeError("inbox path does not match envelope identity")
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "message_id": message_id,
        "target": target,
        "consumer": consumer,
        "payload_sha256": envelope["payload_sha256"],
        "acknowledged_at_utc": _utc_now(),
    }
    path = root / "receipts" / target / f"{message_id}.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactTransportError(f"cannot read receipt {path}: {exc}") from exc
        stable_keys = (
            "schema_version",
            "message_id",
            "target",
            "consumer",
            "payload_sha256",
        )
        if not isinstance(existing, dict) or any(existing.get(key) != receipt[key] for key in stable_keys):
            raise MessageCollisionError(f"receipt collision at {path}")
        return TransportResult("DUPLICATE", message_id, path)
    _atomic_write(path, canonical_json_bytes(receipt) + b"\n")
    return TransportResult("ACKNOWLEDGED", message_id, path)

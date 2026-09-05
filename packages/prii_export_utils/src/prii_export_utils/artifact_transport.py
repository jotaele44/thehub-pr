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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = "prii.artifact-message.v1"
RECEIPT_SCHEMA_VERSION = "prii.artifact-receipt.v1"
_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_FIELDS = frozenset(
    {
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
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "message_id",
        "target",
        "consumer",
        "payload_sha256",
        "acknowledged_at_utc",
    }
)


class ArtifactTransportError(RuntimeError):
    """Base exception for local artifact-transport failures."""


class InvalidEnvelopeError(ArtifactTransportError):
    """Raised when an envelope is malformed or fails its content hashes."""


class InvalidReceiptError(ArtifactTransportError):
    """Raised when a receipt is malformed or does not bind to its message."""


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


def _component(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _COMPONENT.fullmatch(value):
        raise ValueError(f"{field} must match {_COMPONENT.pattern!r}; got {value!r}")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC3339 UTC string ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 UTC timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
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


def _require_fields(
    value: Mapping[str, Any], required: frozenset[str], label: str
) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing or extra:
        raise ValueError(f"{label} fields mismatch missing={missing} extra={extra}")


def verify_envelope(envelope: Mapping[str, Any]) -> None:
    """Fail closed when required fields, types, hashes, or identifiers disagree."""

    try:
        _require_fields(envelope, _ENVELOPE_FIELDS, "envelope")
        if envelope["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {envelope['schema_version']!r}")
        message_id = _sha256(envelope["message_id"], "message_id")
        source = _component(envelope["source"], "source")
        target = _component(envelope["target"], "target")
        kind = _component(envelope["kind"], "kind")
        key = _component(envelope["idempotency_key"], "idempotency_key")
        _utc(envelope["created_at_utc"], "created_at_utc")
        declared_payload_sha256 = _sha256(
            envelope["payload_sha256"], "payload_sha256"
        )
        payload_sha256 = sha256_bytes(canonical_json_bytes(envelope["payload"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidEnvelopeError(str(exc)) from exc
    if payload_sha256 != declared_payload_sha256:
        raise InvalidEnvelopeError("payload_sha256 does not match canonical payload")
    identity = _identity_document(
        source=source,
        target=target,
        kind=kind,
        idempotency_key=key,
        payload_sha256=payload_sha256,
    )
    expected_id = sha256_bytes(canonical_json_bytes(identity))
    if expected_id != message_id:
        raise InvalidEnvelopeError("message_id does not match canonical identity")


def verify_receipt(
    receipt: Mapping[str, Any], envelope: Mapping[str, Any] | None = None
) -> None:
    """Validate exact receipt schema and, when supplied, its envelope binding."""

    try:
        _require_fields(receipt, _RECEIPT_FIELDS, "receipt")
        if receipt["schema_version"] != RECEIPT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported receipt schema_version {receipt['schema_version']!r}"
            )
        message_id = _sha256(receipt["message_id"], "message_id")
        target = _component(receipt["target"], "target")
        _component(receipt["consumer"], "consumer")
        payload_sha256 = _sha256(receipt["payload_sha256"], "payload_sha256")
        _utc(receipt["acknowledged_at_utc"], "acknowledged_at_utc")
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidReceiptError(str(exc)) from exc
    if envelope is not None:
        verify_envelope(envelope)
        if (
            message_id != envelope["message_id"]
            or target != envelope["target"]
            or payload_sha256 != envelope["payload_sha256"]
        ):
            raise InvalidReceiptError("receipt does not bind to the inbox envelope")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        error = InvalidEnvelopeError if label == "envelope" else InvalidReceiptError
        raise error(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        error = InvalidEnvelopeError if label == "envelope" else InvalidReceiptError
        raise error(f"{path} is not a JSON object")
    return value


def _load_envelope(path: Path) -> dict[str, Any]:
    value = _load_json_object(path, "envelope")
    verify_envelope(value)
    return value


def _load_receipt(path: Path, envelope: Mapping[str, Any] | None = None) -> dict[str, Any]:
    value = _load_json_object(path, "receipt")
    verify_receipt(value, envelope)
    return value


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
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
            finally:
                os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


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
        envelope = _load_envelope(path)
        if path.name != f"{envelope['message_id']}.json" or envelope["target"] != target:
            raise InvalidEnvelopeError(f"inbox path does not match envelope identity: {path}")
        receipt_path = receipts / path.name
        if receipt_path.is_file():
            _load_receipt(receipt_path, envelope)
            if not include_acknowledged:
                continue
        yield path, envelope


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
    message_id = _sha256(message_id, "message_id")
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
    verify_receipt(receipt, envelope)
    path = root / "receipts" / target / f"{message_id}.json"
    if path.exists():
        existing = _load_receipt(path, envelope)
        stable_keys = (
            "schema_version",
            "message_id",
            "target",
            "consumer",
            "payload_sha256",
        )
        if any(existing[key] != receipt[key] for key in stable_keys):
            raise MessageCollisionError(f"receipt collision at {path}")
        return TransportResult("DUPLICATE", message_id, path)
    _atomic_write(path, canonical_json_bytes(receipt) + b"\n")
    return TransportResult("ACKNOWLEDGED", message_id, path)

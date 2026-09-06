"""Fail-closed local-envelope ingestion for TheHub.

This module consumes complete ``prii.artifact-message.v1`` files only. It does
not accept a payload extracted from a hosted event, infer a target, or rewrite a
producer record. The shared ``prii_export_utils`` package remains the authority
for envelope validation, local delivery, and transport acknowledgements.

The module itself remains importable on the Hub's Python 3.9 compatibility
floor. Actual local-envelope ingestion requires Python 3.10+, matching the
shared transport package's declared runtime floor.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

TARGET_REPOSITORY = "thehub-pr"
DEFAULT_SOURCE_REPOSITORY = "centinelas-pr"
DEFAULT_KIND = "centinelas-signal"
PROCESSOR_ID = "thehub-local-inbox-v1"
INTAKE_SCHEMA_VERSION = "thehub.local-inbox-record.v1"
REJECTION_SCHEMA_VERSION = "thehub.local-inbox-rejection.v1"
FAILURE_SCHEMA_VERSION = "thehub.local-inbox-failure.v1"
PROCESSING_RECEIPT_SCHEMA_VERSION = "thehub.local-inbox-processing-receipt.v1"


class LocalInboxError(RuntimeError):
    """Base class for bounded local-inbox failures."""


class UnsupportedRuntimeError(LocalInboxError):
    """Raised when the shared transport cannot run on this interpreter."""


class PolicyBindingError(LocalInboxError):
    """Raised when source, target, kind, or path identity is not authorized."""


class IntakeCollisionError(LocalInboxError):
    """Raised when an immutable Hub intake artifact already has other bytes."""


@dataclass(frozen=True)
class IntakeResult:
    """One disjoint terminal classification for a discovered source entry."""

    status: str
    source_path: str
    message_id: Optional[str] = None
    record_path: Optional[str] = None
    receipt_path: Optional[str] = None
    processing_receipt_path: Optional[str] = None
    reason: Optional[str] = None


def _shared_transport() -> ModuleType:
    if sys.version_info < (3, 10):
        raise UnsupportedRuntimeError(
            "local-envelope ingestion requires Python 3.10+; "
            "other Hub commands retain the repository's Python 3.9 floor"
        )
    try:
        import prii_export_utils
    except ImportError:
        # Source checkouts carry the exact shared package in this repository.
        # Keep it independently packaged so the Hub's Python 3.9 root wheel is
        # not silently widened to include a Python 3.10+ distribution.
        candidate = (
            Path(__file__).resolve().parents[2]
            / "packages"
            / "prii_export_utils"
            / "src"
        )
        if candidate.is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
        try:
            import prii_export_utils
        except ImportError as exc:  # pragma: no cover - packaging regression gate
            raise UnsupportedRuntimeError(
                "prii_export_utils is unavailable; install the exact shared "
                "package wheel or run from a complete TheHub source checkout"
            ) from exc
    return prii_export_utils


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonical JSON: {exc}") from exc


def _atomic_write_new(path: Path, data: bytes) -> bool:
    """Write immutable bytes once; return False for an exact existing artifact."""

    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise IntakeCollisionError(f"immutable artifact path is not a regular file: {path}")
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise IntakeCollisionError(f"cannot read existing artifact {path}: {exc}") from exc
        if existing != data:
            raise IntakeCollisionError(f"immutable artifact collision at {path}")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # Refuse a race instead of replacing an independently-created artifact.
        if path.exists():
            if path.read_bytes() != data:
                raise IntakeCollisionError(f"immutable artifact collision at {path}")
            return False
        os.link(temporary_path, path)
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
        return True
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise IntakeCollisionError(f"immutable artifact collision at {path}")
        return False
    finally:
        temporary_path.unlink(missing_ok=True)


def _policy_bind(
    source_path: Path,
    envelope: Mapping[str, Any],
    *,
    expected_source: str,
    expected_kind: str,
) -> None:
    expected_name = f"{envelope['message_id']}.json"
    if source_path.name != expected_name:
        raise PolicyBindingError(
            f"source filename {source_path.name!r} does not bind to {expected_name!r}"
        )
    if envelope["source"] != expected_source:
        raise PolicyBindingError(
            f"source {envelope['source']!r} is not authorized; expected {expected_source!r}"
        )
    if envelope["target"] != TARGET_REPOSITORY:
        raise PolicyBindingError(
            f"target {envelope['target']!r} is not {TARGET_REPOSITORY!r}"
        )
    if envelope["kind"] != expected_kind:
        raise PolicyBindingError(
            f"kind {envelope['kind']!r} is not authorized; expected {expected_kind!r}"
        )


def _intake_record(envelope: Mapping[str, Any], envelope_bytes: bytes) -> Dict[str, Any]:
    return {
        "schema_version": INTAKE_SCHEMA_VERSION,
        "processor": PROCESSOR_ID,
        "state": "ACCEPTED",
        "message_id": envelope["message_id"],
        "source": envelope["source"],
        "target": envelope["target"],
        "kind": envelope["kind"],
        "idempotency_key": envelope["idempotency_key"],
        "payload_sha256": envelope["payload_sha256"],
        "envelope_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
        "envelope_size": len(envelope_bytes),
        # Preserve the validated whole envelope rather than synthesizing a
        # partial record from selected payload fields.
        "envelope": dict(envelope),
    }


def _processing_receipt(
    envelope: Mapping[str, Any],
    record_bytes: bytes,
) -> Dict[str, Any]:
    """Bind completed Hub processing to the immutable acceptance record."""

    return {
        "schema_version": PROCESSING_RECEIPT_SCHEMA_VERSION,
        "processor": PROCESSOR_ID,
        "state": "PROCESSED",
        "message_id": envelope["message_id"],
        "source": envelope["source"],
        "target": envelope["target"],
        "kind": envelope["kind"],
        "payload_sha256": envelope["payload_sha256"],
        "acceptance_record_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "transport_acknowledgement_required": True,
    }


def consume_envelope(
    source_path: Union[str, Path],
    *,
    exchange_root: Union[str, Path],
    state_root: Union[str, Path],
    expected_source: str = DEFAULT_SOURCE_REPOSITORY,
    expected_kind: str = DEFAULT_KIND,
    dry_run: bool = False,
) -> IntakeResult:
    """Validate, locally deliver, persist, and acknowledge one exact envelope.

    Durable ordering is deliberate and restartable:

    1. validate exact canonical bytes and policy bindings;
    2. deliver the complete envelope to ``inbox/thehub-pr``;
    3. commit the immutable Hub ``ACCEPTED`` record;
    4. commit the immutable Hub ``PROCESSED`` receipt;
    5. create the shared transport acknowledgement.

    A failure after an earlier durable step is safe to retry. Exact retries are
    duplicates; different bytes under an existing identity fail closed.
    """

    shared = _shared_transport()
    path = Path(source_path)
    envelope, envelope_bytes = shared.read_canonical_envelope(path)
    _policy_bind(
        path,
        envelope,
        expected_source=expected_source,
        expected_kind=expected_kind,
    )

    record = _intake_record(envelope, envelope_bytes)
    record_path = (
        Path(state_root)
        / "records"
        / envelope["source"]
        / f"{envelope['message_id']}.json"
    )
    receipt_path = (
        Path(exchange_root)
        / "receipts"
        / TARGET_REPOSITORY
        / f"{envelope['message_id']}.json"
    )
    processing_receipt_path = (
        Path(state_root)
        / "receipts"
        / envelope["source"]
        / f"{envelope['message_id']}.json"
    )

    if dry_run:
        return IntakeResult(
            status="VALIDATED",
            source_path=str(path),
            message_id=envelope["message_id"],
            record_path=str(record_path),
            receipt_path=str(receipt_path),
            processing_receipt_path=str(processing_receipt_path),
        )

    delivery = shared.deliver_message(exchange_root, path)
    record_bytes = _canonical_json_bytes(record) + b"\n"
    record_created = _atomic_write_new(record_path, record_bytes)
    processing_receipt = _processing_receipt(envelope, record_bytes)
    processing_created = _atomic_write_new(
        processing_receipt_path,
        _canonical_json_bytes(processing_receipt) + b"\n",
    )
    # Acknowledge only after both Hub-owned durable artifacts exist. This keeps
    # partially processed messages visible to iter_inbox on restart.
    acknowledgement = shared.acknowledge_message(
        exchange_root,
        target=TARGET_REPOSITORY,
        message_id=envelope["message_id"],
        consumer=PROCESSOR_ID,
    )

    duplicate = (
        delivery.status == "DUPLICATE"
        and not record_created
        and not processing_created
        and acknowledgement.status == "DUPLICATE"
    )
    return IntakeResult(
        status="DUPLICATE" if duplicate else "PROCESSED",
        source_path=str(path),
        message_id=envelope["message_id"],
        record_path=str(record_path),
        receipt_path=str(receipt_path),
        processing_receipt_path=str(processing_receipt_path),
    )


def _disposition_identity(
    path: Path,
    exc: BaseException,
    state: str,
) -> Tuple[str, Optional[str], Optional[int]]:
    raw_sha256: Optional[str] = None
    size: Optional[int] = None
    if path.is_file() and not path.is_symlink():
        try:
            data = path.read_bytes()
        except OSError:
            data = None
        if data is not None:
            raw_sha256 = hashlib.sha256(data).hexdigest()
            size = len(data)
    identity = {
        "entry_name": path.name,
        "raw_sha256": raw_sha256,
        "size": size,
        "state": state,
        "error_class": type(exc).__name__,
        "reason": str(exc),
    }
    return (
        hashlib.sha256(_canonical_json_bytes(identity)).hexdigest(),
        raw_sha256,
        size,
    )


def _write_disposition(
    state_root: Path,
    path: Path,
    exc: BaseException,
    *,
    state: str,
) -> Path:
    if state not in {"REJECTED", "FAILED"}:  # pragma: no cover - internal gate
        raise ValueError(f"unsupported disposition state: {state}")
    disposition_id, raw_sha256, size = _disposition_identity(path, exc, state)
    schema = (
        REJECTION_SCHEMA_VERSION if state == "REJECTED" else FAILURE_SCHEMA_VERSION
    )
    record = {
        "schema_version": schema,
        "processor": PROCESSOR_ID,
        "state": state,
        "disposition_id": disposition_id,
        "entry_name": path.name,
        "raw_sha256": raw_sha256,
        "size": size,
        "error_class": type(exc).__name__,
        "reason": str(exc),
    }
    directory = "rejections" if state == "REJECTED" else "failures"
    disposition_path = state_root / directory / f"{disposition_id}.json"
    _atomic_write_new(
        disposition_path, _canonical_json_bytes(record) + b"\n"
    )
    return disposition_path


def _discover(source_dir: Path) -> List[Path]:
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise PolicyBindingError(
            f"source directory is not a regular directory: {source_dir}"
        )
    return sorted(source_dir.iterdir(), key=lambda path: path.name)


def consume_directory(
    source_dir: Union[str, Path],
    *,
    exchange_root: Union[str, Path],
    state_root: Union[str, Path],
    expected_source: str = DEFAULT_SOURCE_REPOSITORY,
    expected_kind: str = DEFAULT_KIND,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Consume every direct source entry with closed, disjoint arithmetic."""

    shared = _shared_transport()
    source = Path(source_dir)
    state = Path(state_root)
    entries = _discover(source)
    results: List[IntakeResult] = []
    rejection_errors = (
        PolicyBindingError,
        UnicodeError,
        ValueError,
        shared.InvalidEnvelopeError,
        shared.InvalidMirrorError,
    )
    failure_errors = (
        IntakeCollisionError,
        LocalInboxError,
        OSError,
        shared.InvalidReceiptError,
        shared.MessageCollisionError,
        shared.ArtifactTransportError,
    )

    for path in entries:
        try:
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise PolicyBindingError(
                    f"unexpected source residue; expected a regular .json file: {path.name}"
                )
            result = consume_envelope(
                path,
                exchange_root=exchange_root,
                state_root=state,
                expected_source=expected_source,
                expected_kind=expected_kind,
                dry_run=dry_run,
            )
        except rejection_errors as exc:
            disposition_path = (
                None
                if dry_run
                else _write_disposition(state, path, exc, state="REJECTED")
            )
            result = IntakeResult(
                status="REJECTED",
                source_path=str(path),
                record_path=(
                    str(disposition_path) if disposition_path is not None else None
                ),
                reason=str(exc),
            )
        except failure_errors as exc:
            disposition_path = (
                None
                if dry_run
                else _write_disposition(state, path, exc, state="FAILED")
            )
            result = IntakeResult(
                status="FAILED",
                source_path=str(path),
                record_path=(
                    str(disposition_path) if disposition_path is not None else None
                ),
                reason=str(exc),
            )
        results.append(result)

    statuses = ("PROCESSED", "DUPLICATE", "VALIDATED", "REJECTED", "FAILED")
    counts = {status: sum(result.status == status for result in results) for status in statuses}
    discovered = len(entries)
    classified = sum(counts.values())
    if classified != discovered:  # pragma: no cover - invariant tripwire
        raise AssertionError(
            f"local-inbox arithmetic does not close: discovered={discovered} classified={classified}"
        )

    return {
        "schema_version": "thehub.local-inbox-summary.v1",
        "processor": PROCESSOR_ID,
        "source_dir": str(source),
        "exchange_root": str(Path(exchange_root)),
        "state_root": str(state),
        "expected_source": expected_source,
        "expected_target": TARGET_REPOSITORY,
        "expected_kind": expected_kind,
        "dry_run": dry_run,
        "discovered": discovered,
        "classified": classified,
        "counts": counts,
        "accepted": counts["PROCESSED"] + counts["DUPLICATE"] + counts["VALIDATED"],
        "results": [asdict(result) for result in results],
        "certification_state": "PROVISIONAL",
        "dynamic_gates_closed": 0,
        "policy_gates_closed": 0,
        "service_independence_proven": False,
        "disconnected_rebuild_proven": False,
    }

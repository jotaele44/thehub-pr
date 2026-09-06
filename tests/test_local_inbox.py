from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from hub.local_inbox import (
    INTAKE_SCHEMA_VERSION,
    PROCESSOR_ID,
    TARGET_REPOSITORY,
    IntakeCollisionError,
    consume_directory,
    consume_envelope,
)

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="prii_export_utils declares Python 3.10+",
)


def _shared():
    import hub.local_inbox as module

    return module._shared_transport()


def _emit(
    root: Path,
    *,
    source: str = "centinelas-pr",
    target: str = TARGET_REPOSITORY,
    kind: str = "centinelas-signal",
    item_id: str = "signal-001",
):
    return _shared().emit_message(
        root,
        source=source,
        target=target,
        kind=kind,
        idempotency_key=f"centinelas-{item_id}",
        payload={"item_id": item_id, "title": "Local-first signal"},
    )


def _write_envelope(drop: Path, envelope: dict, *, canonical: bool = True) -> Path:
    drop.mkdir(parents=True, exist_ok=True)
    path = drop / f"{envelope['message_id']}.json"
    if canonical:
        data = _shared().canonical_json_bytes(envelope) + b"\n"
    else:
        data = json.dumps(envelope, indent=2).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return path


def test_processes_whole_envelope_then_acknowledges(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)

    result = consume_envelope(
        emitted.path,
        exchange_root=exchange,
        state_root=state,
    )

    assert result.status == "PROCESSED"
    record_path = Path(result.record_path or "")
    receipt_path = Path(result.receipt_path or "")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["schema_version"] == INTAKE_SCHEMA_VERSION
    assert record["processor"] == PROCESSOR_ID
    assert record["state"] == "ACCEPTED"
    assert record["envelope"]["message_id"] == emitted.message_id
    assert record["envelope"]["payload"]["item_id"] == "signal-001"
    assert receipt_path.is_file()
    processing_path = Path(result.processing_receipt_path or "")
    processing = json.loads(processing_path.read_text(encoding="utf-8"))
    assert processing["state"] == "PROCESSED"
    assert processing["message_id"] == emitted.message_id
    inbox = exchange / "inbox" / TARGET_REPOSITORY / f"{emitted.message_id}.json"
    assert inbox.read_bytes() == emitted.path.read_bytes()


def test_exact_replay_is_one_duplicate_without_multiplication(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    source_dir = emitted.path.parent

    first = consume_directory(source_dir, exchange_root=exchange, state_root=state)
    second = consume_directory(source_dir, exchange_root=exchange, state_root=state)

    assert first["counts"]["PROCESSED"] == 1
    assert second["counts"]["DUPLICATE"] == 1
    assert second["discovered"] == second["classified"] == 1
    assert len(list((state / "records" / "centinelas-pr").glob("*.json"))) == 1
    assert len(list((exchange / "inbox" / TARGET_REPOSITORY).glob("*.json"))) == 1
    assert len(list((exchange / "receipts" / TARGET_REPOSITORY).glob("*.json"))) == 1
    assert len(list((state / "receipts" / "centinelas-pr").glob("*.json"))) == 1


@pytest.mark.parametrize(
    ("source", "target", "kind", "reason"),
    [
        ("other-producer", TARGET_REPOSITORY, "centinelas-signal", "not authorized"),
        ("centinelas-pr", "moneysweep-pr", "centinelas-signal", "not 'thehub-pr'"),
        ("centinelas-pr", TARGET_REPOSITORY, "other-kind", "not authorized"),
    ],
)
def test_policy_binding_rejects_without_inbox_or_acceptance_record(
    tmp_path: Path,
    source: str,
    target: str,
    kind: str,
    reason: str,
) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    envelope = _shared().build_envelope(
        source=source,
        target=target,
        kind=kind,
        idempotency_key="policy-negative",
        payload={"item_id": "negative"},
    )
    _write_envelope(drop, envelope)

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["counts"]["REJECTED"] == 1
    assert reason in summary["results"][0]["reason"]
    assert not (exchange / "inbox").exists()
    assert not (state / "records").exists()
    assert len(list((state / "rejections").glob("*.json"))) == 1


def test_filename_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    envelope = _shared().build_envelope(
        source="centinelas-pr",
        target=TARGET_REPOSITORY,
        kind="centinelas-signal",
        idempotency_key="wrong-name",
        payload={"item_id": "wrong-name"},
    )
    drop.mkdir()
    (drop / "not-the-message-id.json").write_bytes(
        _shared().canonical_json_bytes(envelope) + b"\n"
    )

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["counts"]["REJECTED"] == 1
    assert "does not bind" in summary["results"][0]["reason"]


def test_noncanonical_and_duplicate_key_json_are_rejected(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    emitted = _emit(tmp_path / "producer")
    envelope = json.loads(emitted.path.read_text(encoding="utf-8"))
    _write_envelope(drop, envelope, canonical=False)
    duplicate = drop / "duplicate.json"
    duplicate.write_text('{"schema_version":"x","schema_version":"y"}\n', encoding="utf-8")

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["discovered"] == summary["classified"] == 2
    assert summary["counts"]["REJECTED"] == 2
    assert not (exchange / "inbox").exists()


def test_tampered_payload_hash_is_rejected(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    emitted = _emit(tmp_path / "producer")
    envelope = json.loads(emitted.path.read_text(encoding="utf-8"))
    envelope["payload"]["title"] = "tampered"
    _write_envelope(drop, envelope)

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["counts"]["REJECTED"] == 1
    assert "payload_sha256" in summary["results"][0]["reason"]


def test_unexpected_residue_is_classified_and_arithmetic_closes(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    drop.mkdir()
    (drop / "notes.txt").write_text("not an envelope", encoding="utf-8")
    (drop / "nested").mkdir()
    emitted = _emit(tmp_path / "producer")
    valid = drop / emitted.path.name
    valid.write_bytes(emitted.path.read_bytes())

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["discovered"] == summary["classified"] == 3
    assert summary["counts"]["PROCESSED"] == 1
    assert summary["counts"]["REJECTED"] == 2
    assert summary["counts"]["FAILED"] == 0
    assert sum(summary["counts"].values()) == 3


def test_dry_run_validates_without_writing_authority(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)

    summary = consume_directory(
        emitted.path.parent,
        exchange_root=exchange,
        state_root=state,
        dry_run=True,
    )

    assert summary["counts"]["VALIDATED"] == 1
    assert not (exchange / "inbox").exists()
    assert not state.exists()


def test_changed_existing_record_fails_closed_and_is_not_overwritten(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    first = consume_envelope(emitted.path, exchange_root=exchange, state_root=state)
    record_path = Path(first.record_path or "")
    tampered = b'{"tampered":true}\n'
    record_path.write_bytes(tampered)

    with pytest.raises(IntakeCollisionError, match="collision"):
        consume_envelope(emitted.path, exchange_root=exchange, state_root=state)

    assert record_path.read_bytes() == tampered


def test_symlink_source_is_rejected(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink unsupported")
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    drop.mkdir()
    emitted = _emit(tmp_path / "producer")
    link = drop / emitted.path.name
    try:
        link.symlink_to(emitted.path)
    except OSError:
        pytest.skip("symlink creation unavailable")

    summary = consume_directory(drop, exchange_root=exchange, state_root=state)

    assert summary["counts"]["REJECTED"] == 1
    assert "regular .json" in summary["results"][0]["reason"]
    assert not (exchange / "inbox").exists()


def test_dry_run_rejection_is_non_mutating(tmp_path: Path) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    drop = tmp_path / "drop"
    drop.mkdir()
    (drop / "unexpected.txt").write_text("residue", encoding="utf-8")

    summary = consume_directory(
        drop, exchange_root=exchange, state_root=state, dry_run=True
    )

    assert summary["counts"]["REJECTED"] == 1
    assert summary["results"][0]["record_path"] is None
    assert not exchange.exists()
    assert not state.exists()


def test_governance_manifest_keeps_all_eight_composite_gates_open() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "federation"
        / "centinelas-local-inbox-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["certification_state"] == "PROVISIONAL"
    assert manifest["certified"] is False
    assert manifest["governance"]["implementation_pr"] == "Jotaele44/thehub-pr#260"
    assert manifest["governance"]["completion_contract_relationship"] == (
        "INDEPENDENT_AUDIT_NOT_STACK_PARENT"
    )
    assert len(manifest["dynamic_composite_gates"]) == 8
    assert set(manifest["dynamic_composite_gates"].values()) == {"OPEN"}
    policy_numbers = sorted(
        number
        for numbers in manifest["policy_gate_crosswalk"].values()
        for number in numbers
    )
    assert policy_numbers == list(range(1, 11))
    assert manifest["claims"]["dynamic_gates_closed"] == 0
    assert manifest["claims"]["service_independence_proven"] is False
    assert manifest["claims"]["offline_reproducible_build_proven"] is False


def test_cli_json_summary_and_rejection_exit_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hub.local_inbox_cli import main

    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    ok = main(
        [
            "--exchange-root",
            str(exchange),
            "--source-dir",
            str(emitted.path.parent),
            "--state-root",
            str(state),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert ok == 0
    assert payload["counts"]["PROCESSED"] == 1
    assert payload["dynamic_gates_closed"] == 0

    rejected_drop = tmp_path / "rejected"
    rejected_drop.mkdir()
    (rejected_drop / "notes.txt").write_text("not an envelope", encoding="utf-8")
    rejected = main(
        [
            "--exchange-root",
            str(exchange),
            "--source-dir",
            str(rejected_drop),
            "--state-root",
            str(state),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rejected == 1
    assert payload["counts"]["REJECTED"] == 1
    assert payload["counts"]["FAILED"] == 0


def test_batch_classifies_immutable_record_collision_as_failed(
    tmp_path: Path,
) -> None:
    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    first = consume_envelope(emitted.path, exchange_root=exchange, state_root=state)
    Path(first.record_path or "").write_bytes(b'{"tampered":true}\n')

    summary = consume_directory(
        emitted.path.parent, exchange_root=exchange, state_root=state
    )

    assert summary["counts"]["FAILED"] == 1
    assert summary["counts"]["REJECTED"] == 0
    assert len(list((state / "failures").glob("*.json"))) == 1


def test_failure_after_processing_before_ack_is_restartable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hub.local_inbox as module

    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    real = _shared()

    class FailOnceProxy:
        ArtifactTransportError = real.ArtifactTransportError
        InvalidEnvelopeError = real.InvalidEnvelopeError
        InvalidMirrorError = real.InvalidMirrorError
        InvalidReceiptError = real.InvalidReceiptError
        MessageCollisionError = real.MessageCollisionError
        read_canonical_envelope = staticmethod(real.read_canonical_envelope)
        deliver_message = staticmethod(real.deliver_message)

        @staticmethod
        def acknowledge_message(*args, **kwargs):
            raise real.ArtifactTransportError("injected acknowledgement failure")

    monkeypatch.setattr(module, "_shared_transport", lambda: FailOnceProxy)
    with pytest.raises(real.ArtifactTransportError, match="injected"):
        consume_envelope(emitted.path, exchange_root=exchange, state_root=state)

    assert len(list((state / "records" / "centinelas-pr").glob("*.json"))) == 1
    assert len(list((state / "receipts" / "centinelas-pr").glob("*.json"))) == 1
    assert not (exchange / "receipts" / TARGET_REPOSITORY).exists()

    monkeypatch.setattr(module, "_shared_transport", lambda: real)
    result = consume_envelope(emitted.path, exchange_root=exchange, state_root=state)
    assert result.status == "PROCESSED"
    assert Path(result.receipt_path or "").is_file()
    assert Path(result.processing_receipt_path or "").is_file()


def test_failure_before_processing_receipt_leaves_message_unacknowledged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hub.local_inbox as module

    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    original = module._atomic_write_new
    failed = False

    def fail_processing_receipt(path: Path, data: bytes) -> bool:
        nonlocal failed
        candidate = Path(path)
        if not failed and state / "receipts" in candidate.parents:
            failed = True
            raise OSError("injected processing-receipt failure")
        return original(candidate, data)

    monkeypatch.setattr(module, "_atomic_write_new", fail_processing_receipt)
    with pytest.raises(OSError, match="injected"):
        consume_envelope(emitted.path, exchange_root=exchange, state_root=state)

    assert not (exchange / "receipts" / TARGET_REPOSITORY).exists()
    assert not (state / "receipts" / "centinelas-pr").exists()

    monkeypatch.setattr(module, "_atomic_write_new", original)
    result = consume_envelope(emitted.path, exchange_root=exchange, state_root=state)
    assert result.status == "PROCESSED"
    assert Path(result.processing_receipt_path or "").is_file()


def test_unsupported_runtime_fails_before_transport_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hub.local_inbox as module

    monkeypatch.setattr(module.sys, "version_info", (3, 9, 99))
    with pytest.raises(module.UnsupportedRuntimeError, match="Python 3.10"):
        module._shared_transport()


def test_canonical_json_rejects_nonfinite_numbers() -> None:
    import hub.local_inbox as module

    with pytest.raises(ValueError, match="canonical JSON"):
        module._canonical_json_bytes({"bad": float("nan")})


def test_atomic_write_rejects_nonregular_existing_artifact(tmp_path: Path) -> None:
    import hub.local_inbox as module

    destination = tmp_path / "artifact.json"
    destination.mkdir()
    with pytest.raises(IntakeCollisionError, match="not a regular file"):
        module._atomic_write_new(destination, b"{}\n")


def test_cli_human_summary_and_missing_source_fail_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hub.local_inbox_cli import main

    exchange = tmp_path / "exchange"
    state = tmp_path / "state"
    emitted = _emit(exchange)
    status = main(
        [
            "--exchange-root",
            str(exchange),
            "--source-dir",
            str(emitted.path.parent),
            "--state-root",
            str(state),
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "validated=1" in captured.out
    assert "dynamic_gates=0/8" in captured.out

    missing = main(
        [
            "--exchange-root",
            str(exchange),
            "--source-dir",
            str(tmp_path / "missing"),
            "--state-root",
            str(state),
        ]
    )
    captured = capsys.readouterr()
    assert missing == 1
    assert "failed closed" in captured.err

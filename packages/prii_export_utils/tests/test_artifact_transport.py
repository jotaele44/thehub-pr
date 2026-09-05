from __future__ import annotations

import json
from pathlib import Path

import pytest

from prii_export_utils.artifact_transport import (
    InvalidEnvelopeError,
    MessageCollisionError,
    acknowledge_message,
    build_envelope,
    deliver_message,
    emit_message,
    iter_inbox,
    verify_envelope,
)


def test_emit_deliver_acknowledge_is_idempotent(tmp_path: Path) -> None:
    first = emit_message(
        tmp_path,
        source="centinelas-pr",
        target="moneysweep-pr",
        kind="signal",
        idempotency_key="source-event-17",
        payload={"records": [{"id": "17", "amount": 20}], "count": 1},
    )
    second = emit_message(
        tmp_path,
        source="centinelas-pr",
        target="moneysweep-pr",
        kind="signal",
        idempotency_key="source-event-17",
        payload={"count": 1, "records": [{"amount": 20, "id": "17"}]},
    )
    assert first.status == "EMITTED"
    assert second.status == "DUPLICATE"
    assert first.message_id == second.message_id

    delivered = deliver_message(tmp_path, first.path)
    duplicate_delivery = deliver_message(tmp_path, first.path)
    assert delivered.status == "DELIVERED"
    assert duplicate_delivery.status == "DUPLICATE"

    pending = list(iter_inbox(tmp_path, "moneysweep-pr"))
    assert [item[1]["message_id"] for item in pending] == [first.message_id]

    ack = acknowledge_message(
        tmp_path,
        target="moneysweep-pr",
        message_id=first.message_id,
        consumer="moneysweep-pr",
    )
    duplicate_ack = acknowledge_message(
        tmp_path,
        target="moneysweep-pr",
        message_id=first.message_id,
        consumer="moneysweep-pr",
    )
    assert ack.status == "ACKNOWLEDGED"
    assert duplicate_ack.status == "DUPLICATE"
    assert list(iter_inbox(tmp_path, "moneysweep-pr")) == []
    assert len(list(iter_inbox(tmp_path, "moneysweep-pr", include_acknowledged=True))) == 1


def test_payload_tampering_fails_closed(tmp_path: Path) -> None:
    result = emit_message(
        tmp_path,
        source="producer",
        target="consumer",
        kind="export",
        payload={"value": 1},
    )
    envelope = json.loads(result.path.read_text(encoding="utf-8"))
    envelope["payload"]["value"] = 2
    result.path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(InvalidEnvelopeError, match="payload_sha256"):
        deliver_message(tmp_path, result.path)


def test_same_id_with_different_existing_content_is_collision(tmp_path: Path) -> None:
    result = emit_message(
        tmp_path,
        source="producer",
        target="consumer",
        kind="export",
        idempotency_key="event-1",
        payload={"value": 1},
    )
    envelope = json.loads(result.path.read_text(encoding="utf-8"))
    envelope["created_at_utc"] = "2026-01-01T00:00:00Z"
    result.path.write_text(json.dumps(envelope), encoding="utf-8")

    duplicate = emit_message(
        tmp_path,
        source="producer",
        target="consumer",
        kind="export",
        idempotency_key="event-1",
        payload={"value": 1},
    )
    assert duplicate.status == "DUPLICATE"

    inbox = tmp_path / "inbox" / "consumer"
    inbox.mkdir(parents=True)
    target = inbox / result.path.name
    conflicting = dict(envelope)
    conflicting["created_at_utc"] = "2026-01-02T00:00:00Z"
    target.write_text(json.dumps(conflicting), encoding="utf-8")
    with pytest.raises(MessageCollisionError, match="inbox collision"):
        deliver_message(tmp_path, result.path)


def test_invalid_components_and_non_json_payloads_are_rejected() -> None:
    with pytest.raises(ValueError, match="source"):
        build_envelope(source="../escape", target="b", kind="c", payload={})
    with pytest.raises(ValueError, match="canonical JSON"):
        build_envelope(source="a", target="b", kind="c", payload={"n": float("nan")})


def test_unknown_fields_fail_closed() -> None:
    envelope = build_envelope(source="a", target="b", kind="c", payload={})
    envelope["unexpected"] = True
    with pytest.raises(InvalidEnvelopeError, match="fields mismatch"):
        verify_envelope(envelope)

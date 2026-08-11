from __future__ import annotations

import sqlite3

import pytest

from hub.identity_registry import IdentityRegistry, payload_hash, stable_id


def test_member_identity_is_stable_and_replay_safe(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    fed = reg.create_entity(entity_type="organization", canonical_name="Example Corp")
    payload = {"entity_id": "ent_" + "a" * 32, "name": "Example Corp"}

    kwargs = dict(
        federation_entity_id=fed,
        source_producer="moneysweep-pr",
        local_record_id=payload["entity_id"],
        source_revision="r1",
        payload=payload,
        match_class="EXACT_IDENTIFIER",
        reason_code="authoritative_uei",
        evidence_ids=["src_" + "b" * 32],
    )
    reg.attach_member(**kwargs)
    reg.attach_member(**kwargs)

    assert reg.resolve_member("moneysweep-pr", payload["entity_id"]) == fed
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT COUNT(*) FROM federation_entity_members").fetchone()[0] == 1


def test_normalized_name_cannot_create_membership(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    fed = reg.create_entity(entity_type="organization", canonical_name="Acme")
    with pytest.raises(ValueError, match="non-adjudicative"):
        reg.attach_member(
            federation_entity_id=fed,
            source_producer="spiderweb-pr",
            local_record_id="ent_" + "c" * 32,
            source_revision=None,
            payload={"name": "Acme"},
            match_class="NORMALIZED_NAME",
            reason_code="normalized_name",
            evidence_ids=["candidate-1"],
        )


def test_producer_member_cannot_be_silently_reassigned(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    payload = {"entity_id": "ent_" + "d" * 32}
    common = dict(
        source_producer="skywatcher-pr",
        local_record_id=payload["entity_id"],
        source_revision="1",
        payload=payload,
        match_class="REVIEWED_MATCH",
        reason_code="reviewed_identity_evidence",
        evidence_ids=["review-1"],
    )
    reg.attach_member(federation_entity_id=a, **common)
    with pytest.raises(ValueError, match="different federation entity"):
        reg.attach_member(federation_entity_id=b, **common)


def test_event_replay_is_idempotent(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    payload = {"federation_entity_id": stable_id("fed", "x")}
    first = reg.record_event(
        event_type="UPSERT",
        source_producer="thehub-pr",
        local_record_id="control:x",
        source_revision="1",
        payload=payload,
    )
    second = reg.record_event(
        event_type="UPSERT",
        source_producer="thehub-pr",
        local_record_id="control:x",
        source_revision="1",
        payload=payload,
    )
    assert first == second
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT COUNT(*) FROM federation_events").fetchone()[0] == 1


def test_payload_hash_is_canonical_order_independent():
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})

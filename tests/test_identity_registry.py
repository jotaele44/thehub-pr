from __future__ import annotations

import sqlite3
import pytest

from hub.identity_registry import IdentityRegistry, payload_hash, stable_id


def _decision(reg: IdentityRegistry, decision_id: str, outcome: str = "MERGE") -> None:
    reg.record_resolution_decision(
        decision_id=decision_id,
        decision_type="entity_identity_decision",
        outcome=outcome,
        reason_code="authoritative_identifier",
        evidence_ids=["evidence-1"],
        candidate_ref="candidate-1",
        decided_by="reviewer",
    )


def test_member_identity_is_stable_and_bound_to_resolution_decision(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    fed = reg.create_entity(entity_type="organization", canonical_name="Example Corp")
    _decision(reg, "decision-1")
    payload = {"entity_id": "ent_" + "a" * 32, "name": "Example Corp"}
    kwargs = dict(
        federation_entity_id=fed, source_producer="moneysweep-pr",
        local_record_id=payload["entity_id"], source_revision="1", payload=payload,
        match_class="EXACT_IDENTIFIER", decision_id="decision-1",
    )
    reg.attach_member(**kwargs)
    reg.attach_member(**kwargs)
    assert reg.resolve_member("moneysweep-pr", payload["entity_id"]) == fed
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT decision_id,COUNT(*) FROM federation_entity_members").fetchone() == ("decision-1", 1)


def test_non_merge_decision_cannot_create_membership(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    fed = reg.create_entity(entity_type="organization", canonical_name="Acme")
    _decision(reg, "decision-distinct", "DISTINCT")
    with pytest.raises(ValueError, match="MERGE"):
        reg.attach_member(
            federation_entity_id=fed, source_producer="spiderweb-pr", local_record_id="ent_c",
            source_revision=None, payload={"name": "Acme"}, match_class="REVIEWED_MATCH",
            decision_id="decision-distinct",
        )


def test_normalized_name_cannot_create_membership(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    fed = reg.create_entity(entity_type="organization", canonical_name="Acme")
    _decision(reg, "decision-2")
    with pytest.raises(ValueError, match="non-adjudicative"):
        reg.attach_member(
            federation_entity_id=fed, source_producer="spiderweb-pr", local_record_id="ent_c",
            source_revision=None, payload={"name": "Acme"}, match_class="NORMALIZED_NAME",
            decision_id="decision-2",
        )


def test_alias_collision_does_not_automerge(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    _decision(reg, "decision-a")
    prov = reg.add_provenance(source_producer="moneysweep-pr", local_record_id="x", evidence_id="e1")
    reg.add_alias(federation_entity_id=a, alias_text="Same Name", provenance_id=prov, decision_id="decision-a")
    reg.add_alias(federation_entity_id=b, alias_text="Same Name", provenance_id=prov, decision_id="decision-a")
    assert a != b


def test_global_identifier_collision_is_rejected_without_automerge(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    _decision(reg, "decision-id")
    prov = reg.add_provenance(source_producer="moneysweep-pr", local_record_id="x", evidence_id="e1")
    reg.add_identifier(federation_entity_id=a, namespace="UEI", identifier_value="ABC", provenance_id=prov, decision_id="decision-id")
    with pytest.raises(ValueError, match="cannot auto-merge"):
        reg.add_identifier(federation_entity_id=b, namespace="UEI", identifier_value="ABC", provenance_id=prov, decision_id="decision-id")


def test_transactional_merge_moves_members_and_redirects_edges(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    c = reg.create_entity(entity_type="organization", canonical_name="C")
    _decision(reg, "decision-merge")
    reg.attach_member(federation_entity_id=a, source_producer="moneysweep-pr", local_record_id="ent_a", source_revision="1", payload={"id": "a"}, match_class="EXACT_IDENTIFIER", decision_id="decision-merge")
    rel = reg.add_relationship(source_federation_entity_id=a, target_federation_entity_id=c, relationship_type="operates", provenance_ids=["p1"])
    merge_id = reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=b, decision_id="decision-merge")
    assert reg.resolve_member("moneysweep-pr", "ent_a") == b
    with sqlite3.connect(tmp_path / "hub.db") as db:
        db.row_factory = sqlite3.Row
        entity = db.execute("SELECT status,superseded_by FROM federation_entities WHERE federation_entity_id=?", (a,)).fetchone()
        edge = db.execute("SELECT source_federation_entity_id,status FROM federation_relationships WHERE federation_relationship_id=?", (rel,)).fetchone()
        history = db.execute("SELECT before_hash,after_hash FROM federation_merge_history WHERE merge_id=?", (merge_id,)).fetchone()
        assert tuple(entity) == ("SUPERSEDED", b)
        assert tuple(edge) == (b, "ACTIVE")
        assert history["before_hash"] != history["after_hash"]


def test_identical_merge_replay_noop_and_incompatible_second_merge_rejected(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    c = reg.create_entity(entity_type="organization", canonical_name="C")
    _decision(reg, "decision-merge")
    _decision(reg, "decision-other")
    first = reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=b, decision_id="decision-merge")
    second = reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=b, decision_id="decision-merge")
    assert first == second
    with pytest.raises(ValueError, match="incompatible second merge"):
        reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=c, decision_id="decision-other")
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT COUNT(*) FROM federation_merge_history").fetchone()[0] == 1


def test_relationship_redirect_dedupes_without_delete(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    c = reg.create_entity(entity_type="organization", canonical_name="C")
    _decision(reg, "decision-merge")
    r1 = reg.add_relationship(source_federation_entity_id=a, target_federation_entity_id=c, relationship_type="owns", provenance_ids=["p1"])
    r2 = reg.add_relationship(source_federation_entity_id=b, target_federation_entity_id=c, relationship_type="owns", provenance_ids=["p2"])
    reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=b, decision_id="decision-merge")
    with sqlite3.connect(tmp_path / "hub.db") as db:
        rows = db.execute("SELECT federation_relationship_id,status,superseded_by FROM federation_relationships ORDER BY federation_relationship_id").fetchall()
        active = [row for row in rows if row[1] == "ACTIVE"]
        superseded = [row for row in rows if row[1] == "SUPERSEDED"]
        assert len(rows) == 2 and len(active) == 1 and len(superseded) == 1
        assert superseded[0][2] == active[0][0]
        assert {row[0] for row in rows} == {r1, r2}


def test_supersede_and_tombstone_preserve_history(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    reg.record_resolution_decision(decision_id="sup-1", decision_type="superseded_decision", reason_code="corrected_identity", evidence_ids=["e1"], decided_by="reviewer")
    reg.supersede_entity(federation_entity_id=a, superseded_by=b, decision_id="sup-1")
    reg.tombstone_entity(b)
    with sqlite3.connect(tmp_path / "hub.db") as db:
        rows = dict(db.execute("SELECT federation_entity_id,status FROM federation_entities").fetchall())
        assert rows[a] == "SUPERSEDED" and rows[b] == "TOMBSTONED"
        assert db.execute("SELECT COUNT(*) FROM federation_entities").fetchone()[0] == 2


def test_event_dispositions_fail_closed_and_preserve_rejections(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    reg.register_revision_contract("moneysweep-pr", "INTEGER_REVISION")
    payload = {"x": 1}
    _, applied = reg.record_event(event_type="UPSERT", source_producer="moneysweep-pr", local_record_id="x", source_revision="2", payload=payload)
    _, stale = reg.record_event(event_type="UPSERT", source_producer="moneysweep-pr", local_record_id="x", source_revision="1", payload={"x": 2})
    _, bad_schema = reg.record_event(event_type="UPSERT", source_producer="moneysweep-pr", local_record_id="y", source_revision="1", payload=payload, schema_version="9.9.9")
    _, bad_hash = reg.record_event(event_type="UPSERT", source_producer="moneysweep-pr", local_record_id="z", source_revision="1", payload=payload, payload_hash_value="0" * 64)
    assert (applied, stale, bad_schema, bad_hash) == ("APPLIED", "REJECTED_STALE", "REJECTED_SCHEMA", "REJECTED_HASH")
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT COUNT(*) FROM federation_events").fetchone()[0] == 4
        assert db.execute("SELECT COUNT(*) FROM federation_events WHERE disposition LIKE 'REJECTED_%'").fetchone()[0] == 3


def test_event_identical_replay_is_noop(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    reg.register_revision_contract("thehub-pr", "MONOTONIC_SEQUENCE")
    payload = {"federation_entity_id": stable_id("fed", "x")}
    first = reg.record_event(event_type="UPSERT", source_producer="thehub-pr", local_record_id="control:x", source_revision=None, source_sequence=1, payload=payload)
    second = reg.record_event(event_type="UPSERT", source_producer="thehub-pr", local_record_id="control:x", source_revision=None, source_sequence=1, payload=payload)
    assert first[0] == second[0] and first[1] == "APPLIED" and second[1] == "IDEMPOTENT_REPLAY"
    with sqlite3.connect(tmp_path / "hub.db") as db:
        assert db.execute("SELECT COUNT(*) FROM federation_events").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM federation_event_attempts").fetchone()[0] == 2


def test_non_orderable_revision_requires_monotonic_sequence(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    reg.register_revision_contract("spiderweb-pr", "MONOTONIC_SEQUENCE")
    _, disposition = reg.record_event(event_type="UPSERT", source_producer="spiderweb-pr", local_record_id="x", source_revision="rev-a", source_sequence=None, payload={"x": 1})
    assert disposition == "REJECTED_OUT_OF_ORDER"


def test_integrity_report_is_zero_after_merge(tmp_path):
    reg = IdentityRegistry(tmp_path / "hub.db")
    a = reg.create_entity(entity_type="organization", canonical_name="A")
    b = reg.create_entity(entity_type="organization", canonical_name="B")
    _decision(reg, "decision-merge")
    reg.merge_entities(from_federation_entity_id=a, to_federation_entity_id=b, decision_id="decision-merge")
    assert all(value == 0 for value in reg.integrity_report().values())


def test_payload_hash_is_canonical_order_independent():
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})

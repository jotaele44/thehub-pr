"""Persistent, producer-preserving federation identity registry.

Aggregate rows retain producer-native ent_* ids. This registry assigns stable
Hub federation ids to adjudicated equivalence classes without mutating producer
identifiers.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

SCHEMA_VERSION = "1.0.0"
FEDERATION_AUTHORITY = "thehub-pr"
ALLOWED_MATCH_CLASSES = {"EXACT_IDENTIFIER", "EXPLICIT_CROSSWALK", "PROVEN_RELATIONSHIP", "REVIEWED_MATCH"}
ALLOWED_EVENTS = {"UPSERT", "MERGE", "SUPERSEDE", "TOMBSTONE"}
ALLOWED_DECISION_TYPES = {"entity_match_candidate", "entity_identity_decision", "relationship_assertion", "canonical_entity", "alias", "rejected_match", "superseded_decision"}
ALLOWED_OUTCOMES = {"MERGE", "DISTINCT", "DEFER"}
REVISION_MODES = {"INTEGER_REVISION", "MONOTONIC_SEQUENCE"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS federation_entities (
 federation_entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, canonical_name TEXT NOT NULL,
 domain_owner TEXT, federation_authority TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUPERSEDED','TOMBSTONED')),
 valid_from TEXT, valid_to TEXT, superseded_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (superseded_by) REFERENCES federation_entities(federation_entity_id));
CREATE TABLE IF NOT EXISTS federation_resolution_decisions (
 decision_id TEXT PRIMARY KEY, decision_type TEXT NOT NULL, outcome TEXT, reason_code TEXT NOT NULL,
 evidence_json TEXT NOT NULL, candidate_ref TEXT, supersedes_decision_id TEXT, superseded_by TEXT,
 decided_by TEXT, created_at TEXT NOT NULL,
 CHECK(decision_type IN ('entity_match_candidate','entity_identity_decision','relationship_assertion','canonical_entity','alias','rejected_match','superseded_decision')),
 CHECK(outcome IS NULL OR outcome IN ('MERGE','DISTINCT','DEFER')),
 FOREIGN KEY (supersedes_decision_id) REFERENCES federation_resolution_decisions(decision_id),
 FOREIGN KEY (superseded_by) REFERENCES federation_resolution_decisions(decision_id));
CREATE TABLE IF NOT EXISTS federation_provenance (
 provenance_id TEXT PRIMARY KEY, source_producer TEXT NOT NULL, local_record_id TEXT NOT NULL,
 evidence_id TEXT NOT NULL, payload_hash TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_entity_members (
 source_producer TEXT NOT NULL, local_record_id TEXT NOT NULL, federation_entity_id TEXT NOT NULL,
 source_revision TEXT, source_sequence INTEGER, payload_hash TEXT NOT NULL, match_class TEXT NOT NULL,
 decision_id TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUPERSEDED','TOMBSTONED')),
 created_at TEXT NOT NULL, PRIMARY KEY (source_producer, local_record_id),
 FOREIGN KEY (federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (decision_id) REFERENCES federation_resolution_decisions(decision_id));
CREATE TABLE IF NOT EXISTS federation_aliases (
 alias_id TEXT PRIMARY KEY, federation_entity_id TEXT NOT NULL, alias_text TEXT NOT NULL,
 normalized_alias TEXT NOT NULL, provenance_id TEXT NOT NULL, decision_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUPERSEDED','TOMBSTONED')),
 superseded_by_alias_id TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY (federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (provenance_id) REFERENCES federation_provenance(provenance_id),
 FOREIGN KEY (decision_id) REFERENCES federation_resolution_decisions(decision_id),
 FOREIGN KEY (superseded_by_alias_id) REFERENCES federation_aliases(alias_id));
CREATE UNIQUE INDEX IF NOT EXISTS uq_federation_alias_per_entity
 ON federation_aliases(federation_entity_id, normalized_alias) WHERE status='ACTIVE';
CREATE TABLE IF NOT EXISTS federation_identifiers (
 identifier_id TEXT PRIMARY KEY, federation_entity_id TEXT NOT NULL, namespace TEXT NOT NULL,
 identifier_value TEXT NOT NULL, provenance_id TEXT NOT NULL, decision_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUPERSEDED','TOMBSTONED')),
 created_at TEXT NOT NULL,
 FOREIGN KEY (federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (provenance_id) REFERENCES federation_provenance(provenance_id),
 FOREIGN KEY (decision_id) REFERENCES federation_resolution_decisions(decision_id));
CREATE UNIQUE INDEX IF NOT EXISTS uq_federation_identifier_global
 ON federation_identifiers(namespace, identifier_value) WHERE status='ACTIVE';
CREATE TABLE IF NOT EXISTS federation_relationships (
 federation_relationship_id TEXT PRIMARY KEY, source_federation_entity_id TEXT NOT NULL,
 target_federation_entity_id TEXT NOT NULL, relationship_type TEXT NOT NULL, domain_owner TEXT,
 federation_authority TEXT NOT NULL, confidence REAL, provenance_json TEXT NOT NULL, decision_id TEXT,
 valid_from TEXT, valid_to TEXT, superseded_by TEXT,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUPERSEDED','TOMBSTONED')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (source_federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (target_federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (decision_id) REFERENCES federation_resolution_decisions(decision_id),
 FOREIGN KEY (superseded_by) REFERENCES federation_relationships(federation_relationship_id));
CREATE TABLE IF NOT EXISTS federation_merge_history (
 merge_id TEXT PRIMARY KEY, from_federation_entity_id TEXT NOT NULL, to_federation_entity_id TEXT NOT NULL,
 decision_id TEXT NOT NULL, reason_code TEXT NOT NULL, evidence_json TEXT NOT NULL,
 before_hash TEXT NOT NULL, after_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(from_federation_entity_id),
 FOREIGN KEY (from_federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (to_federation_entity_id) REFERENCES federation_entities(federation_entity_id),
 FOREIGN KEY (decision_id) REFERENCES federation_resolution_decisions(decision_id));
CREATE TABLE IF NOT EXISTS federation_producer_revision_contracts (
 source_producer TEXT PRIMARY KEY,
 revision_mode TEXT NOT NULL CHECK(revision_mode IN ('INTEGER_REVISION','MONOTONIC_SEQUENCE')),
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_events (
 event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, schema_version TEXT NOT NULL,
 source_producer TEXT NOT NULL, local_record_id TEXT NOT NULL, source_revision TEXT, source_sequence INTEGER,
 payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, effective_at TEXT, disposition TEXT NOT NULL,
 rejection_reason TEXT, state_mutated INTEGER NOT NULL DEFAULT 0 CHECK(state_mutated IN (0,1)),
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_event_attempts (
 attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL, disposition TEXT NOT NULL,
 rejection_reason TEXT, attempted_at TEXT NOT NULL,
 FOREIGN KEY (event_id) REFERENCES federation_events(event_id));
CREATE INDEX IF NOT EXISTS idx_fed_members_entity ON federation_entity_members(federation_entity_id);
CREATE INDEX IF NOT EXISTS idx_fed_relationship_source ON federation_relationships(source_federation_entity_id);
CREATE INDEX IF NOT EXISTS idx_fed_relationship_target ON federation_relationships(target_federation_entity_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


class IdentityRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def resolve_member(self, source_producer: str, local_record_id: str) -> Optional[str]:
        with self._connect() as db:
            row = db.execute("SELECT federation_entity_id FROM federation_entity_members WHERE source_producer=? AND local_record_id=? AND status='ACTIVE'", (source_producer, local_record_id)).fetchone()
        return str(row[0]) if row else None

    def create_entity(self, *, entity_type: str, canonical_name: str, domain_owner: str | None = None, federation_entity_id: str | None = None) -> str:
        fed_id = federation_entity_id or stable_id("fed", entity_type, canonical_name, FEDERATION_AUTHORITY)
        now = _utcnow()
        with self._connect() as db:
            row = db.execute("SELECT entity_type,canonical_name,federation_authority FROM federation_entities WHERE federation_entity_id=?", (fed_id,)).fetchone()
            if row:
                if tuple(row) != (entity_type, canonical_name, FEDERATION_AUTHORITY):
                    raise ValueError("federation_entity_id collision")
                return fed_id
            db.execute("INSERT INTO federation_entities (federation_entity_id,entity_type,canonical_name,domain_owner,federation_authority,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (fed_id, entity_type, canonical_name, domain_owner, FEDERATION_AUTHORITY, now, now))
        return fed_id

    def record_resolution_decision(self, *, decision_id: str, decision_type: str, reason_code: str, evidence_ids: Sequence[str], outcome: str | None = None, candidate_ref: str | None = None, supersedes_decision_id: str | None = None, superseded_by: str | None = None, decided_by: str | None = None) -> None:
        if decision_type not in ALLOWED_DECISION_TYPES:
            raise ValueError("unsupported entity_resolution.v1 decision_type")
        if outcome is not None and outcome not in ALLOWED_OUTCOMES:
            raise ValueError("unsupported entity_resolution.v1 outcome")
        if not reason_code or not evidence_ids:
            raise ValueError("decision requires reason_code and evidence_ids")
        if reason_code in {"normalized_name", "similar_name", "shared_address", "shared_coordinates", "co_occurrence", "embedding_similarity"}:
            raise ValueError("non-adjudicative reason_code is prohibited")
        evidence_json = json.dumps(list(evidence_ids), sort_keys=True)
        expected = (decision_type, outcome, reason_code, evidence_json, candidate_ref, supersedes_decision_id, superseded_by, decided_by)
        with self._connect() as db:
            row = db.execute("SELECT decision_type,outcome,reason_code,evidence_json,candidate_ref,supersedes_decision_id,superseded_by,decided_by FROM federation_resolution_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if row:
                if tuple(row) != expected:
                    raise ValueError("immutable decision_id already recorded with different semantics")
                return
            db.execute("INSERT INTO federation_resolution_decisions (decision_id,decision_type,outcome,reason_code,evidence_json,candidate_ref,supersedes_decision_id,superseded_by,decided_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (decision_id, *expected, _utcnow()))

    def add_provenance(self, *, source_producer: str, local_record_id: str, evidence_id: str, payload_hash_value: str | None = None) -> str:
        provenance_id = stable_id("fprov", source_producer, local_record_id, evidence_id)
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO federation_provenance (provenance_id,source_producer,local_record_id,evidence_id,payload_hash,created_at) VALUES (?,?,?,?,?,?)", (provenance_id, source_producer, local_record_id, evidence_id, payload_hash_value, _utcnow()))
        return provenance_id

    def attach_member(self, *, federation_entity_id: str, source_producer: str, local_record_id: str, source_revision: str | None, payload: Mapping[str, Any], match_class: str, decision_id: str, source_sequence: int | None = None) -> None:
        if match_class not in ALLOWED_MATCH_CLASSES:
            raise ValueError(f"non-adjudicative match class cannot merge: {match_class}")
        digest = payload_hash(payload)
        with self._connect() as db:
            decision = db.execute("SELECT decision_type,outcome FROM federation_resolution_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if not decision or decision["decision_type"] != "entity_identity_decision":
                raise ValueError("membership requires entity_resolution.v1 identity decision")
            if decision["outcome"] != "MERGE":
                raise ValueError("membership requires MERGE outcome")
            entity = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (federation_entity_id,)).fetchone()
            if not entity or entity["status"] != "ACTIVE":
                raise ValueError("membership target must be active")
            row = db.execute("SELECT federation_entity_id,source_revision,source_sequence,payload_hash,decision_id FROM federation_entity_members WHERE source_producer=? AND local_record_id=?", (source_producer, local_record_id)).fetchone()
            expected = (federation_entity_id, source_revision, source_sequence, digest, decision_id)
            if row:
                if tuple(row) == expected:
                    return
                if row["federation_entity_id"] != federation_entity_id:
                    raise ValueError("producer member already belongs to a different federation entity")
                raise ValueError("member mutation requires an explicit supersession event")
            db.execute("INSERT INTO federation_entity_members (source_producer,local_record_id,federation_entity_id,source_revision,source_sequence,payload_hash,match_class,decision_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (source_producer, local_record_id, federation_entity_id, source_revision, source_sequence, digest, match_class, decision_id, _utcnow()))

    def add_alias(self, *, federation_entity_id: str, alias_text: str, provenance_id: str, decision_id: str) -> str:
        normalized = _normalize_alias(alias_text)
        alias_id = stable_id("falias", federation_entity_id, normalized)
        with self._connect() as db:
            row = db.execute("SELECT alias_id FROM federation_aliases WHERE federation_entity_id=? AND normalized_alias=? AND status='ACTIVE'", (federation_entity_id, normalized)).fetchone()
            if row:
                return str(row[0])
            db.execute("INSERT INTO federation_aliases (alias_id,federation_entity_id,alias_text,normalized_alias,provenance_id,decision_id,created_at) VALUES (?,?,?,?,?,?,?)", (alias_id, federation_entity_id, alias_text, normalized, provenance_id, decision_id, _utcnow()))
        return alias_id

    def add_identifier(self, *, federation_entity_id: str, namespace: str, identifier_value: str, provenance_id: str, decision_id: str) -> str:
        identifier_id = stable_id("fid", namespace, identifier_value)
        with self._connect() as db:
            row = db.execute("SELECT identifier_id,federation_entity_id FROM federation_identifiers WHERE namespace=? AND identifier_value=? AND status='ACTIVE'", (namespace, identifier_value)).fetchone()
            if row:
                if row["federation_entity_id"] != federation_entity_id:
                    raise ValueError("global identifier collision cannot auto-merge entities")
                return str(row["identifier_id"])
            db.execute("INSERT INTO federation_identifiers (identifier_id,federation_entity_id,namespace,identifier_value,provenance_id,decision_id,created_at) VALUES (?,?,?,?,?,?,?)", (identifier_id, federation_entity_id, namespace, identifier_value, provenance_id, decision_id, _utcnow()))
        return identifier_id

    def add_relationship(self, *, source_federation_entity_id: str, target_federation_entity_id: str, relationship_type: str, provenance_ids: Sequence[str], domain_owner: str | None = None, confidence: float | None = None, decision_id: str | None = None) -> str:
        relationship_id = stable_id("frel", source_federation_entity_id, relationship_type, target_federation_entity_id, domain_owner or "")
        now = _utcnow()
        with self._connect() as db:
            for endpoint in (source_federation_entity_id, target_federation_entity_id):
                row = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (endpoint,)).fetchone()
                if not row or row["status"] != "ACTIVE":
                    raise ValueError("relationship endpoints must be active")
            db.execute("INSERT OR IGNORE INTO federation_relationships (federation_relationship_id,source_federation_entity_id,target_federation_entity_id,relationship_type,domain_owner,federation_authority,confidence,provenance_json,decision_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (relationship_id, source_federation_entity_id, target_federation_entity_id, relationship_type, domain_owner, FEDERATION_AUTHORITY, confidence, json.dumps(sorted(set(provenance_ids))), decision_id, now, now))
        return relationship_id

    def register_revision_contract(self, source_producer: str, revision_mode: str) -> None:
        if revision_mode not in REVISION_MODES:
            raise ValueError("unsupported revision ordering mode")
        with self._connect() as db:
            row = db.execute("SELECT revision_mode FROM federation_producer_revision_contracts WHERE source_producer=?", (source_producer,)).fetchone()
            if row and row["revision_mode"] != revision_mode:
                raise ValueError("revision contract is immutable once recorded")
            db.execute("INSERT OR IGNORE INTO federation_producer_revision_contracts (source_producer,revision_mode,created_at) VALUES (?,?,?)", (source_producer, revision_mode, _utcnow()))

    def _event_order_disposition(self, db: sqlite3.Connection, source_producer: str, local_record_id: str, source_revision: str | None, source_sequence: int | None) -> tuple[str | None, str | None]:
        contract = db.execute("SELECT revision_mode FROM federation_producer_revision_contracts WHERE source_producer=?", (source_producer,)).fetchone()
        if not contract:
            return "REJECTED_INVARIANT", "missing producer revision contract"
        prior = db.execute("SELECT source_revision,source_sequence FROM federation_events WHERE source_producer=? AND local_record_id=? AND disposition='APPLIED' ORDER BY created_at DESC LIMIT 1", (source_producer, local_record_id)).fetchone()
        if contract["revision_mode"] == "MONOTONIC_SEQUENCE":
            if source_sequence is None:
                return "REJECTED_OUT_OF_ORDER", "monotonic source_sequence required"
            if prior is not None and prior["source_sequence"] is not None:
                previous = int(prior["source_sequence"])
                if source_sequence < previous:
                    return "REJECTED_STALE", "source_sequence is stale"
                if source_sequence == previous:
                    return "REJECTED_OUT_OF_ORDER", "source_sequence reused by non-identical event"
            return None, None
        if source_revision is None:
            return "REJECTED_OUT_OF_ORDER", "integer source_revision required"
        try:
            current = int(source_revision)
        except ValueError:
            return "REJECTED_OUT_OF_ORDER", "revision is not provably integer-orderable"
        if prior is not None and prior["source_revision"] is not None:
            previous = int(prior["source_revision"])
            if current < previous:
                return "REJECTED_STALE", "source_revision is stale"
            if current == previous:
                return "REJECTED_OUT_OF_ORDER", "source_revision reused by non-identical event"
        return None, None

    def record_event(self, *, event_type: str, source_producer: str, local_record_id: str, source_revision: str | None, payload: Mapping[str, Any], effective_at: str | None = None, source_sequence: int | None = None, schema_version: str = SCHEMA_VERSION, payload_hash_value: str | None = None, authority: str = FEDERATION_AUTHORITY, apply_state_mutation: bool = False) -> tuple[str, str]:
        computed_hash = payload_hash(payload)
        supplied_hash = payload_hash_value or computed_hash
        event_id = stable_id("fev", event_type, source_producer, local_record_id, source_revision or "", "" if source_sequence is None else str(source_sequence), supplied_hash)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT payload_hash,payload_json FROM federation_events WHERE event_id=?", (event_id,)).fetchone()
            if existing:
                if existing["payload_hash"] != supplied_hash or existing["payload_json"] != _canonical_json(payload):
                    raise ValueError("event_id collision")
                db.execute("INSERT INTO federation_event_attempts (event_id,disposition,rejection_reason,attempted_at) VALUES (?,?,?,?)", (event_id, "IDEMPOTENT_REPLAY", None, _utcnow()))
                db.commit()
                return event_id, "IDEMPOTENT_REPLAY"
            disposition, rejection_reason = "APPLIED", None
            if schema_version != SCHEMA_VERSION:
                disposition, rejection_reason = "REJECTED_SCHEMA", "unsupported schema_version"
            elif supplied_hash != computed_hash:
                disposition, rejection_reason = "REJECTED_HASH", "payload hash mismatch"
            elif authority != FEDERATION_AUTHORITY:
                disposition, rejection_reason = "REJECTED_AUTHORITY", "federation authority mismatch"
            elif event_type not in ALLOWED_EVENTS:
                disposition, rejection_reason = "REJECTED_INVARIANT", "unsupported federation event"
            else:
                rejected, reason = self._event_order_disposition(db, source_producer, local_record_id, source_revision, source_sequence)
                if rejected:
                    disposition, rejection_reason = rejected, reason
            db.execute("INSERT INTO federation_events (event_id,event_type,schema_version,source_producer,local_record_id,source_revision,source_sequence,payload_hash,payload_json,effective_at,disposition,rejection_reason,state_mutated,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (event_id, event_type, schema_version, source_producer, local_record_id, source_revision, source_sequence, supplied_hash, _canonical_json(payload), effective_at, disposition, rejection_reason, 1 if disposition == "APPLIED" and apply_state_mutation else 0, _utcnow()))
            db.execute("INSERT INTO federation_event_attempts (event_id,disposition,rejection_reason,attempted_at) VALUES (?,?,?,?)", (event_id, disposition, rejection_reason, _utcnow()))
            db.commit()
        return event_id, disposition

    def _entity_state_hash(self, db: sqlite3.Connection, entity_ids: Sequence[str]) -> str:
        payload: dict[str, Any] = {}
        for table in ("federation_entities", "federation_entity_members", "federation_aliases", "federation_identifiers"):
            ph = ",".join("?" for _ in entity_ids)
            rows = db.execute(f"SELECT * FROM {table} WHERE federation_entity_id IN ({ph}) ORDER BY federation_entity_id", tuple(entity_ids)).fetchall()
            payload[table] = [dict(row) for row in rows]
        ph = ",".join("?" for _ in entity_ids)
        rows = db.execute(f"SELECT * FROM federation_relationships WHERE source_federation_entity_id IN ({ph}) OR target_federation_entity_id IN ({ph}) ORDER BY federation_relationship_id", tuple(entity_ids) + tuple(entity_ids)).fetchall()
        payload["federation_relationships"] = [dict(row) for row in rows]
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()

    def merge_entities(self, *, from_federation_entity_id: str, to_federation_entity_id: str, decision_id: str) -> str:
        if from_federation_entity_id == to_federation_entity_id:
            raise ValueError("cannot merge entity into itself")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            history = db.execute("SELECT * FROM federation_merge_history WHERE from_federation_entity_id=?", (from_federation_entity_id,)).fetchone()
            if history:
                if history["to_federation_entity_id"] == to_federation_entity_id and history["decision_id"] == decision_id:
                    db.commit()
                    return str(history["merge_id"])
                db.rollback()
                raise ValueError("incompatible second merge rejected; history is immutable")
            decision = db.execute("SELECT decision_type,outcome,reason_code,evidence_json FROM federation_resolution_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if not decision or decision["decision_type"] != "entity_identity_decision" or decision["outcome"] != "MERGE":
                db.rollback()
                raise ValueError("merge requires entity_resolution.v1 MERGE decision")
            source = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (from_federation_entity_id,)).fetchone()
            target = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (to_federation_entity_id,)).fetchone()
            if not source or not target or source["status"] != "ACTIVE" or target["status"] != "ACTIVE":
                db.rollback()
                raise ValueError("merge endpoints must both be ACTIVE")
            before_hash = self._entity_state_hash(db, [from_federation_entity_id, to_federation_entity_id])
            now = _utcnow()
            db.execute("UPDATE federation_entity_members SET federation_entity_id=? WHERE federation_entity_id=? AND status='ACTIVE'", (to_federation_entity_id, from_federation_entity_id))
            for alias in db.execute("SELECT alias_id,normalized_alias FROM federation_aliases WHERE federation_entity_id=? AND status='ACTIVE'", (from_federation_entity_id,)).fetchall():
                duplicate = db.execute("SELECT alias_id FROM federation_aliases WHERE federation_entity_id=? AND normalized_alias=? AND status='ACTIVE'", (to_federation_entity_id, alias["normalized_alias"])).fetchone()
                if duplicate:
                    db.execute("UPDATE federation_aliases SET status='SUPERSEDED',superseded_by_alias_id=? WHERE alias_id=?", (duplicate["alias_id"], alias["alias_id"]))
                else:
                    db.execute("UPDATE federation_aliases SET federation_entity_id=? WHERE alias_id=?", (to_federation_entity_id, alias["alias_id"]))
            db.execute("UPDATE federation_identifiers SET federation_entity_id=? WHERE federation_entity_id=? AND status='ACTIVE'", (to_federation_entity_id, from_federation_entity_id))
            rels = db.execute("SELECT federation_relationship_id,source_federation_entity_id,target_federation_entity_id,relationship_type,domain_owner FROM federation_relationships WHERE status='ACTIVE' AND (source_federation_entity_id=? OR target_federation_entity_id=?) ORDER BY federation_relationship_id", (from_federation_entity_id, from_federation_entity_id)).fetchall()
            for rel in rels:
                new_source = to_federation_entity_id if rel["source_federation_entity_id"] == from_federation_entity_id else rel["source_federation_entity_id"]
                new_target = to_federation_entity_id if rel["target_federation_entity_id"] == from_federation_entity_id else rel["target_federation_entity_id"]
                duplicate = db.execute("SELECT federation_relationship_id FROM federation_relationships WHERE status='ACTIVE' AND federation_relationship_id<>? AND source_federation_entity_id=? AND target_federation_entity_id=? AND relationship_type=? AND COALESCE(domain_owner,'')=COALESCE(?, '') ORDER BY federation_relationship_id LIMIT 1", (rel["federation_relationship_id"], new_source, new_target, rel["relationship_type"], rel["domain_owner"])).fetchone()
                if duplicate:
                    db.execute("UPDATE federation_relationships SET status='SUPERSEDED',superseded_by=?,valid_to=?,updated_at=? WHERE federation_relationship_id=?", (duplicate["federation_relationship_id"], now, now, rel["federation_relationship_id"]))
                else:
                    db.execute("UPDATE federation_relationships SET source_federation_entity_id=?,target_federation_entity_id=?,updated_at=? WHERE federation_relationship_id=?", (new_source, new_target, now, rel["federation_relationship_id"]))
            db.execute("UPDATE federation_entities SET status='SUPERSEDED',superseded_by=?,valid_to=?,updated_at=? WHERE federation_entity_id=?", (to_federation_entity_id, now, now, from_federation_entity_id))
            after_hash = self._entity_state_hash(db, [from_federation_entity_id, to_federation_entity_id])
            merge_id = stable_id("fmerge", from_federation_entity_id, to_federation_entity_id, decision_id)
            db.execute("INSERT INTO federation_merge_history (merge_id,from_federation_entity_id,to_federation_entity_id,decision_id,reason_code,evidence_json,before_hash,after_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (merge_id, from_federation_entity_id, to_federation_entity_id, decision_id, decision["reason_code"], decision["evidence_json"], before_hash, after_hash, now))
            db.commit()
        return merge_id

    def supersede_entity(self, *, federation_entity_id: str, superseded_by: str, decision_id: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            decision = db.execute("SELECT decision_type FROM federation_resolution_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if not decision or decision["decision_type"] != "superseded_decision":
                db.rollback()
                raise ValueError("supersede requires entity_resolution.v1 superseded_decision")
            target = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (superseded_by,)).fetchone()
            current = db.execute("SELECT status,superseded_by FROM federation_entities WHERE federation_entity_id=?", (federation_entity_id,)).fetchone()
            if not current or not target or target["status"] != "ACTIVE":
                db.rollback()
                raise ValueError("supersede endpoints invalid")
            if current["status"] == "SUPERSEDED":
                if current["superseded_by"] == superseded_by:
                    db.commit()
                    return
                db.rollback()
                raise ValueError("incompatible supersession")
            if current["status"] != "ACTIVE":
                db.rollback()
                raise ValueError("only active entity can be superseded")
            now = _utcnow()
            db.execute("UPDATE federation_entities SET status='SUPERSEDED',superseded_by=?,valid_to=?,updated_at=? WHERE federation_entity_id=?", (superseded_by, now, now, federation_entity_id))
            db.commit()

    def tombstone_entity(self, federation_entity_id: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM federation_entities WHERE federation_entity_id=?", (federation_entity_id,)).fetchone()
            if not row:
                db.rollback()
                raise ValueError("entity does not exist")
            if row["status"] == "TOMBSTONED":
                db.commit()
                return
            if row["status"] != "ACTIVE":
                db.rollback()
                raise ValueError("only active entity can be tombstoned")
            now = _utcnow()
            db.execute("UPDATE federation_entities SET status='TOMBSTONED',valid_to=?,updated_at=? WHERE federation_entity_id=?", (now, now, federation_entity_id))
            db.execute("UPDATE federation_entity_members SET status='TOMBSTONED',valid_to=? WHERE federation_entity_id=? AND status='ACTIVE'", (now, federation_entity_id))
            db.execute("UPDATE federation_aliases SET status='TOMBSTONED' WHERE federation_entity_id=? AND status='ACTIVE'", (federation_entity_id,))
            db.execute("UPDATE federation_identifiers SET status='TOMBSTONED' WHERE federation_entity_id=? AND status='ACTIVE'", (federation_entity_id,))
            db.execute("UPDATE federation_relationships SET status='TOMBSTONED',valid_to=?,updated_at=? WHERE status='ACTIVE' AND (source_federation_entity_id=? OR target_federation_entity_id=?)", (now, now, federation_entity_id, federation_entity_id))
            db.commit()

    def integrity_report(self) -> dict[str, int]:
        checks = {
            "foreign_key_violations": "SELECT COUNT(*) FROM pragma_foreign_key_check",
            "orphan_active_relationships": "SELECT COUNT(*) FROM federation_relationships r LEFT JOIN federation_entities s ON s.federation_entity_id=r.source_federation_entity_id LEFT JOIN federation_entities t ON t.federation_entity_id=r.target_federation_entity_id WHERE r.status='ACTIVE' AND (s.status<>'ACTIVE' OR t.status<>'ACTIVE' OR s.status IS NULL OR t.status IS NULL)",
            "duplicate_active_members": "SELECT COUNT(*) FROM (SELECT source_producer,local_record_id,COUNT(*) c FROM federation_entity_members WHERE status='ACTIVE' GROUP BY source_producer,local_record_id HAVING c>1)",
            "duplicate_active_aliases": "SELECT COUNT(*) FROM (SELECT federation_entity_id,normalized_alias,COUNT(*) c FROM federation_aliases WHERE status='ACTIVE' GROUP BY federation_entity_id,normalized_alias HAVING c>1)",
            "duplicate_active_identifiers": "SELECT COUNT(*) FROM (SELECT namespace,identifier_value,COUNT(*) c FROM federation_identifiers WHERE status='ACTIVE' GROUP BY namespace,identifier_value HAVING c>1)",
            "duplicate_active_relationships": "SELECT COUNT(*) FROM (SELECT source_federation_entity_id,target_federation_entity_id,relationship_type,COALESCE(domain_owner,''),COUNT(*) c FROM federation_relationships WHERE status='ACTIVE' GROUP BY source_federation_entity_id,target_federation_entity_id,relationship_type,COALESCE(domain_owner,'') HAVING c>1)",
        }
        with self._connect() as db:
            return {name: int(db.execute(sql).fetchone()[0]) for name, sql in checks.items()}

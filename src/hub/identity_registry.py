"""Persistent, producer-preserving federation identity registry.

This module is intentionally separate from aggregate.py/correlate.py. Aggregate
rows retain their existing ``ent_*`` ids; this registry assigns stable Hub ids
to adjudicated equivalence classes without mutating producer identifiers.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

SCHEMA_VERSION = "1.0.0"
FEDERATION_AUTHORITY = "thehub-pr"
ALLOWED_MATCH_CLASSES = {
    "EXACT_IDENTIFIER",
    "EXPLICIT_CROSSWALK",
    "PROVEN_RELATIONSHIP",
    "REVIEWED_MATCH",
}
ALLOWED_EVENTS = {"UPSERT", "MERGE", "SUPERSEDE", "TOMBSTONE"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS federation_entities (
    federation_entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    domain_owner TEXT,
    federation_authority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from TEXT,
    valid_to TEXT,
    superseded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS federation_entity_members (
    source_producer TEXT NOT NULL,
    local_record_id TEXT NOT NULL,
    federation_entity_id TEXT NOT NULL,
    source_revision TEXT,
    payload_hash TEXT NOT NULL,
    match_class TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_producer, local_record_id),
    FOREIGN KEY (federation_entity_id) REFERENCES federation_entities(federation_entity_id)
);
CREATE TABLE IF NOT EXISTS federation_relationships (
    federation_relationship_id TEXT PRIMARY KEY,
    source_federation_entity_id TEXT NOT NULL,
    target_federation_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    domain_owner TEXT,
    federation_authority TEXT NOT NULL,
    confidence REAL,
    provenance_json TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    superseded_by TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_federation_entity_id) REFERENCES federation_entities(federation_entity_id),
    FOREIGN KEY (target_federation_entity_id) REFERENCES federation_entities(federation_entity_id)
);
CREATE TABLE IF NOT EXISTS federation_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    source_producer TEXT NOT NULL,
    local_record_id TEXT NOT NULL,
    source_revision TEXT,
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    effective_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fed_members_entity
ON federation_entity_members(federation_entity_id);
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


@dataclass(frozen=True)
class MemberKey:
    source_producer: str
    local_record_id: str


class IdentityRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)
            db.execute("PRAGMA foreign_keys = ON")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def resolve_member(self, source_producer: str, local_record_id: str) -> Optional[str]:
        with self._connect() as db:
            row = db.execute(
                "SELECT federation_entity_id FROM federation_entity_members "
                "WHERE source_producer=? AND local_record_id=?",
                (source_producer, local_record_id),
            ).fetchone()
        return str(row[0]) if row else None

    def create_entity(
        self,
        *,
        entity_type: str,
        canonical_name: str,
        domain_owner: str | None = None,
        federation_entity_id: str | None = None,
    ) -> str:
        fed_id = federation_entity_id or stable_id(
            "fed", entity_type, canonical_name, FEDERATION_AUTHORITY
        )
        now = _utcnow()
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO federation_entities "
                "(federation_entity_id,entity_type,canonical_name,domain_owner,"
                "federation_authority,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (fed_id, entity_type, canonical_name, domain_owner, FEDERATION_AUTHORITY, now, now),
            )
        return fed_id

    def attach_member(
        self,
        *,
        federation_entity_id: str,
        source_producer: str,
        local_record_id: str,
        source_revision: str | None,
        payload: Mapping[str, Any],
        match_class: str,
        reason_code: str,
        evidence_ids: list[str],
    ) -> None:
        if match_class not in ALLOWED_MATCH_CLASSES:
            raise ValueError(f"non-adjudicative match class cannot merge: {match_class}")
        if not reason_code or not evidence_ids:
            raise ValueError("identity membership requires reason_code and evidence_ids")
        digest = payload_hash(payload)
        now = _utcnow()
        with self._connect() as db:
            existing = db.execute(
                "SELECT federation_entity_id,source_revision,payload_hash FROM federation_entity_members "
                "WHERE source_producer=? AND local_record_id=?",
                (source_producer, local_record_id),
            ).fetchone()
            if existing:
                if str(existing[0]) != federation_entity_id:
                    raise ValueError("producer member already belongs to a different federation entity")
                if existing[1] == source_revision and existing[2] == digest:
                    return
                raise ValueError("member mutation requires an explicit supersession event")
            db.execute(
                "INSERT INTO federation_entity_members "
                "(source_producer,local_record_id,federation_entity_id,source_revision,payload_hash,"
                "match_class,reason_code,evidence_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (source_producer, local_record_id, federation_entity_id, source_revision, digest,
                 match_class, reason_code, json.dumps(evidence_ids, sort_keys=True), now),
            )

    def record_event(
        self,
        *,
        event_type: str,
        source_producer: str,
        local_record_id: str,
        source_revision: str | None,
        payload: Mapping[str, Any],
        effective_at: str | None = None,
    ) -> str:
        if event_type not in ALLOWED_EVENTS:
            raise ValueError(f"unsupported federation event: {event_type}")
        digest = payload_hash(payload)
        event_id = stable_id(
            "fev", event_type, source_producer, local_record_id, source_revision or "", digest
        )
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO federation_events "
                "(event_id,event_type,schema_version,source_producer,local_record_id,source_revision,"
                "payload_hash,payload_json,effective_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (event_id, event_type, SCHEMA_VERSION, source_producer, local_record_id,
                 source_revision, digest, _canonical_json(payload), effective_at, _utcnow()),
            )
        return event_id

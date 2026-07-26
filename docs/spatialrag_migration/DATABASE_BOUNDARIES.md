# Database Boundaries — mutable ingest vs. certified snapshot

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

## The core rule

**The Intelligence Engine may only query a certified, `ACTIVE` snapshot — never the Evidence
Engine's mutable ingest tables directly.**

This is the direct fix for spatial-rag's current defect: `backend/app/retrieval/engine.py`'s hybrid
retrieval executes raw SQL (BM25 `ts_rank_cd` + pgvector cosine + PostGIS `ST_Distance`) straight
against the same live Postgres tables the ingestion pipeline is actively writing to. There is no
boundary between "being ingested" and "safe to answer queries from." A document mid-ingestion, an
un-reviewed evidence-tier assignment, or a row later found to be a near-duplicate can all be answered
from before anyone has certified them.

## Who owns what

| Layer | Owns | Constraint |
|---|---|---|
| Evidence Engine | The mutable ingest schema — documents, pages, chunks, embeddings, entity/relationship candidates, tier assignments, spatial/temporal extraction, all in an `INGESTING`/`VALIDATED`/`NORMALIZED`/`INDEXED` state (see [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md)) | Writable only by Evidence Engine. Never queried directly by Intelligence Engine or any user-facing surface. |
| Control Plane | The snapshot manifest and promotion decision | Read/write access to snapshot metadata; no access to evidence content itself beyond what's needed to run the promotion gate. |
| Intelligence Engine | Read-only access to the current `ACTIVE` snapshot (and, for rollback/audit tooling, `SUPERSEDED` snapshots by explicit id) | Never writes evidence content. Never queries pre-`CERTIFIED` state. |

## A precedent to avoid, not follow

thehub-pr's own `src/hub/ingest.py`/`bridge.py` has the identical architectural gap: `hub ingest`
performs `INSERT OR REPLACE` into `data/hub.db`, a fully idempotent overwrite-in-place with no
history table and no point-in-time query capability (confirmed directly — see
[`DUPLICATION_REGISTER.md`](DUPLICATION_REGISTER.md) row 3). This is explicitly flagged so that
`DATABASE_BOUNDARIES.md`'s design is not accidentally modeled on the wrong existing thehub-pr code.
The mutable/certified split specified here is new work for both halves of the merge, not a port of
an existing thehub-pr pattern.

## Adopted datastore

thehub-pr's only datastore today is a flat SQLite KV store (`data/hub.db`, table
`entities(entity_type, entity_id, data, updated_at)`) with no vector or spatial extension story.
spatial-rag's stack is Postgres 15 + PostGIS 3.4 + pgvector. The Evidence Engine's requirements —
hybrid BM25/vector retrieval, PostGIS geometry queries with uncertainty, a queryable snapshot
history — cannot be met by SQLite.

**Decision: PostgreSQL + PostGIS + pgvector is adopted as a new, additional datastore for the
Evidence/Intelligence Engines.** thehub-pr's existing `data/hub.db` continues to serve the structured
federation pipeline (`hub aggregate`/`correlate`/`ingest`) unchanged; nothing about this migration
requires moving that pipeline off SQLite. This human-signoff decision was recorded on 2026-07-26. It is a genuinely new operational dependency
(a stateful database service) for a repo whose `docker-compose.yml` today runs one service.

## Schema and role isolation

- `evidence_worker`: write access to mutable ingest schemas; no authority to promote snapshots.
- `control_plane`: read/write access to snapshot metadata and atomic promotion state; no general
  evidence-content mutation authority.
- `intelligence_reader`: read-only access to views or schemas exposing `ACTIVE` snapshots; no
  mutable-ingest access and no promotion authority.
- Operational credentials are distinct. Application code must not reuse an owner or migration role.

## Snapshot boundary mechanics (detail in SNAPSHOT_STATE_MACHINE.md)

- Every write from the Evidence Engine lands in the mutable schema tagged with the in-progress
  snapshot id it belongs to.
- Promotion to `CERTIFIED` (and then `ACTIVE`) is atomic: the Intelligence Engine's read path
  switches to the new snapshot id in one operation, never a partial cutover.
- Rollback targets a prior `ACTIVE`/`SUPERSEDED` snapshot id — no query the Intelligence Engine can
  issue against a rolled-back snapshot behaves differently from a query issued while it was current.
- `QUARANTINED` snapshots (failed certification, or later found to contain synthetic/test data
  leakage) are never reachable by the normal query path, only by explicit audit tooling.

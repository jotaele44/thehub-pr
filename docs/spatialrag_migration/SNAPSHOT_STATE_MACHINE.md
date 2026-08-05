# Snapshot State Machine

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

Snapshots are the **only** integration boundary between the Evidence Engine and the Intelligence
Engine — see [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md). This document specifies the
lifecycle states, required manifest fields, and the promotion gate.

## States

```
DISCOVERED
  → INGESTING
  → VALIDATED
  → NORMALIZED
  → INDEXED
  → CERTIFIED
  → ACTIVE
  → SUPERSEDED
  → QUARANTINED
```

| State | Entry condition | Exit condition | Who may transition it |
|---|---|---|---|
| `DISCOVERED` | A new source batch/producer package is registered for ingestion | Evidence Engine begins processing | Control Plane (registers), Evidence Engine (claims) |
| `INGESTING` | Evidence Engine begins acquiring/parsing artifacts | All artifacts in the batch processed (success or recorded failure) | Evidence Engine |
| `VALIDATED` | Schema/structural validation passes on ingested content | Normalization begins | Evidence Engine |
| `NORMALIZED` | Chunking, embedding, entity extraction, spatial/temporal extraction complete | Index build begins | Evidence Engine |
| `INDEXED` | Retrieval indexes (lexical, vector, spatial) built against the normalized content | Snapshot manifest finalized, submitted for promotion | Evidence Engine |
| `CERTIFIED` | Promotion gate passes (see below) — evidence tiers reviewed to the required threshold, no unresolved contradiction flags, no security/PII flag outstanding | Control Plane atomically switches the query-serving pointer | Control Plane, gated by `compute_snapshot_gate()` |
| `ACTIVE` | Query-serving pointer switched to this snapshot | A later snapshot reaches `CERTIFIED` and is promoted | Control Plane (only one snapshot is `ACTIVE` at a time) |
| `SUPERSEDED` | A newer snapshot became `ACTIVE` | Retained for audit/rollback; never re-promoted without explicit rollback action | Control Plane (automatic on next promotion) |
| `QUARANTINED` | Promotion gate fails, or an `ACTIVE`/`SUPERSEDED` snapshot is later found to contain a disqualifying defect (synthetic-data leakage, security flag) | Requires explicit human remediation before any further transition | Control Plane, human reviewer |

**Only `ACTIVE` snapshots may answer normal user queries.** `SUPERSEDED` snapshots are reachable only
by explicit rollback or audit tooling (see [`API_CONTRACT.md`](API_CONTRACT.md)). `QUARANTINED`
snapshots are never reachable by any query path.

## Required snapshot manifest fields

Every snapshot carries:

```
immutable_id
creation_timestamp
producer_package_versions
record_count
artifact_count
schema_versions
sha256_manifest
failed_record_count
exclusion_ledger          # what was excluded and why (e.g. failed validation, quarantined source)
test_synthetic_accounting  # explicit count/list of any test or synthetic records present
index_version
embedding_model_identity
promotion_decision         # who/what approved promotion, and when
rollback_target            # the snapshot id a rollback from this one would target
```

`test_synthetic_accounting` is not optional — a snapshot with any unaccounted synthetic/test data
cannot reach `CERTIFIED`. This is the mechanism that prevents spatial-rag's "126 tests passing"
ambiguity (see [`PARITY_GATES.md`](PARITY_GATES.md)) from recurring at the data layer: test fixtures
must never silently enter an operational snapshot.

## Promotion gate

```
compute_snapshot_gate(snapshot_manifest) -> { promotion_blocked: bool, blockers: [str] }
```

This reuses the *shape* of `src/hub/maintenance/gate.py::compute_gate()` — confirmed directly, a pure
function over a rollup dict returning `{promotion_blocked, blockers}`, blocking on missing/invalid
reports and critical findings. `compute_snapshot_gate()` is a **new module** under `control_plane/`
(per [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md)), generalizing the same pure-function contract to
snapshot-specific blockers — it is not an import of the existing federation gate, because the rollup
shape (producer maintenance reports) is unrelated to a snapshot manifest.

Blockers include, at minimum:

- Any evidence item still `machine_provisional` tier where the snapshot's certification policy
  requires human or producer review before promotion.
- Any schema-validation failure in the manifest's `sha256_manifest` check.
- Any unresolved `ContradictionSet` flagged as blocking (vs. informational).
- Any outstanding security/PII flag from the ingestion pipeline.
- Non-zero `test_synthetic_accounting` not matched by an explicit, reviewed exclusion.

## Rollback

A rollback request names a `target_snapshot_id` (must be `CERTIFIED`, `ACTIVE`, or `SUPERSEDED`) and
atomically re-points the query-serving pointer. Rollback never mutates snapshot content — it only
changes which snapshot answers queries. This is the guarantee that makes "no query behaves
differently after a rollback than it did while that snapshot was current" true by construction.

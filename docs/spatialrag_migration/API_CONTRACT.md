# API Contract — Control Plane facing surface

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

This specifies the shape of the API surface the Control Plane exposes over the Evidence and
Intelligence Engines. **No route is implemented in this phase** — this is the target contract
[`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md) row 15 (spatial-rag's
`backend/app/api/routes.py`) is rewritten against, once Phase 2 begins.

## Wire-shape precedent

thehub-pr already has an adapter/request abstraction in `src/hub/mcp_runtime/sdk.py`:
`MCPAdapter`/`MCPRequest`, with `name()`, `version()`, `capabilities()`, `execute()`, and
`provenance()`. The Control Plane API is specified to reuse this shape — new capabilities
(`snapshot.promote`, `retrieval.query`, `tier.review`, ...) are declared and routed the same way
existing MCP adapters are, rather than inventing a second, parallel request/response convention.
This keeps the new engines inside the same `PolicyEngine` capability-allowlist and fail-closed
credential model that already governs `mcp_runtime/adapters/*`.

## Endpoint groups (design targets, not routes)

### Snapshot lifecycle

| Operation | Request | Response |
|---|---|---|
| Request promotion | `{ snapshot_id }` | `{ promotion_blocked: bool, blockers: [str] }` — same shape as `compute_gate()`'s existing return value in `src/hub/maintenance/gate.py`, generalized per [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md) |
| Get snapshot status | `{ snapshot_id }` | Full manifest: state, timestamps, producer-package versions, record/artifact counts, schema versions, SHA-256 manifest, failed-record count, exclusion ledger, test/synthetic accounting, index version, embedding model identity, promotion decision, rollback target |
| List snapshots | `{ state?, limit? }` | `[{ snapshot_id, state, created_at }, ...]` |
| Rollback | `{ target_snapshot_id }` | `{ active_snapshot_id }` — only ever points `ACTIVE` at a prior `CERTIFIED`/`SUPERSEDED` snapshot; never mutates evidence content |

### Retrieval (Intelligence Engine, read-only)

| Operation | Request | Response |
|---|---|---|
| Query | `{ query_text, retrieval_profile_id?, snapshot_id? (defaults to current ACTIVE), access_context }` | `{ status: <one of the 8 abstention statuses>, evidence_items: [EvidenceItem], claims: [Claim], contradiction_sets: [ContradictionSet]?, retrieval_profile_used, hyde_used: bool }` |
| Get evidence item | `{ evidence_id }` | Full `EvidenceItem` with provenance, tier, geometry, temporal fields |
| Get claim | `{ claim_id }` | Full `Claim` record per [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §3 |

The response's `status` field is never omitted or defaulted to `ANSWERED` — every response states
which of the 8 statuses applies, even a fully successful one. `hyde_used` is always present (`true`
only on explicit opt-in, per [`SECURITY_MODEL.md`](SECURITY_MODEL.md)), so a caller can always tell
whether HyDE affected the result without needing separate logging access.

### Evidence tier review / certification

| Operation | Request | Response |
|---|---|---|
| Submit human review | `{ evidence_id, tier_value, reason }` | Updated tier record with `tier_review_status = human_reviewed`, `tier_assigned_by = <reviewer id>` |
| Producer certification | `{ evidence_id, tier_value, producer_id }` (only callable by an authenticated producer identity) | `tier_review_status = producer_certified` |

A machine-suggested tier (`tier_review_status = machine_provisional`) can never be written by this
endpoint group — only by the Evidence Engine's ingest path, and only as provisional.

### Access-classification-scoped queries

Every retrieval/evidence-item/claim endpoint above takes an implicit `access_context` derived from
the caller's authenticated identity (Control Plane responsibility, not a per-endpoint parameter to
trust from the client). Results are filtered to the caller's permitted
[access classification](SECURITY_MODEL.md#access-classifications) before being returned — the same
policy applies whether the caller is the search API, the map API, an export job, or the LLM's own
retrieved context window. There is no separate "admin bypass" endpoint; elevated access is a
different `access_context`, not a different code path.

## Non-goals of this contract

- No endpoint permits direct mutation of certified evidence content (only tier review/certification
  metadata, and only additively — see [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md)).
- No endpoint merges entities automatically; entity resolution decisions are a separate, human- or
  rule-adjudicated flow per [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §5, not exposed as a one-shot
  "merge" call.
- No endpoint requires an LLM call for structured retrieval — `CanonicalRecord` queries (awards,
  transactions, observations, alerts) route through the existing `hub` structured-search path
  unchanged; the Intelligence Engine's LLM-backed synthesis is only invoked for document/claim
  answers.

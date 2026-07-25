# Phase 1 Contract Design — Index & Component-Ledger Receipts

> **Design documents only.** Nothing here is implemented, installed, or wired into the Hub. No code is
> moved. These specs describe the versioned contracts Phase 1 *would* implement **after** the baseline
> gates close and the user authorizes Phase 1 implementation. They are grounded in the handoff's own
> design artifacts (`DATA_CONTRACTS.json`, `SNAPSHOT_STATE_MACHINE.json`, `SECURITY_MODEL.json`,
> `02_CONTRACTS_SUMMARY.md`, `PHASE_1_IMPLEMENTATION_SPEC.md`) and map to backlog tasks **T013–T045**.

## Design principles (fixed by the handoff)

1. **Snapshots are the sole integration boundary.** Only `ACTIVE` snapshots answer normal queries.
2. **Structured records stay structured** — no prose flattening of canonical records.
3. **Machine evidence tiers are `PROVISIONAL` only**; authority follows the fixed priority order.
4. **Every answer is rendered from a claim ledger**; no uncited claims.
5. **Read-only Intelligence Engine** — it cannot mutate canonical evidence or ingestion tables.
6. **No-LLM path** for exact-ID and structured search.
7. **HyDE disabled by default.**
8. **Existing Hub deterministic correlation remains the sole cross-producer correlation authority.**

## Versioning scheme

- Each contract is a JSON Schema (draft 2020-12) named `<contract>.v1.schema.json` with a `$id` of
  `https://thehub-pr/contracts/<contract>/v1` and a `x-contract-version` of `1.0.0` (semver).
- Contracts are **additive-compatible within a major version**; any breaking change bumps the major and
  the `$id` path (`/v2`). A snapshot records the exact `schema_versions` it was built against
  (`SNAPSHOT_STATE_MACHINE.json.required_fields`), so old snapshots remain interpretable.
- New Phase-1 contract schemas would live under a **new** directory (proposed `schemas/contracts/`) and
  be added to `schemas/FROZEN.sha256` so the existing `tests/test_schema_freeze.py` guard extends to
  them. **Existing `schemas/*.json` are not modified.**

## Component-ledger receipts (every proposed symbol → an approved ledger row)

Per `PHASE_1_IMPLEMENTATION_SPEC.md` ("Migration receipts linking every new symbol to an approved
component-ledger row"). Note every donor row carries `code_movement_authorized = NO`; these are
**design targets**, not extractions.

| Proposed contract / interface | Approved ledger source row | Adjudication status | Phase |
|---|---|---|---|
| Snapshot manifest schema | (new — `SNAPSHOT_STATE_MACHINE.json`) | design target | 1 |
| Evidence lifecycle state machine | `backend/app/ingestion/pipeline.py` (REWRITE) | APPROVED_REWRITE_SPEC | 1 |
| Query lifecycle state machine | `backend/app/api/routes.py` (ADAPT) | APPROVED_PHASE_2_ONLY (contract in P1) | 1 |
| Retrieval-object union (8 types) | `backend/app/models/schemas.py`, `orm.py` (REWRITE) | APPROVED_REWRITE_SPEC | 1 |
| Provenance schema | `backend/app/models/schemas.py` (REWRITE) | APPROVED_REWRITE_SPEC | 1 |
| Claim-ledger schema | `backend/app/citation/engine.py` (REWRITE) | APPROVED_REWRITE_SPEC | 1 |
| Abstention schema | `backend/app/models/schemas.py` (REWRITE) | APPROVED_REWRITE_SPEC | 1 |
| Access-classification schema | `backend/app/middleware/security.py` (ADAPT) | APPROVED_PHASE_1_DESIGN | 1 |
| Analytical-run receipt | `backend/app/cache.py` (ADAPT) | APPROVED_PHASE_2_ONLY (receipt in P1) | 1 |
| Read-only Intelligence interface | `backend/app/api/routes.py` (ADAPT) | APPROVED_PHASE_2_ONLY | 1 |
| No-LLM structured query contract | `backend/app/retrieval/engine.py` (ADAPT) | APPROVED_PHASE_2_ONLY | 1 |
| Policy-decision interface | `backend/app/middleware/security.py` (ADAPT) | APPROVED_PHASE_1_DESIGN | 1 |
| Contract validation host | `backend/app/models/json_schema.py` (ADAPT) | APPROVED_PHASE_1_DESIGN | 1 |
| Spatial-uncertainty schema | `backend/app/spatial/enricher.py` (ADAPT) | APPROVED_PHASE_2_ONLY | 1 (schema) |
| Document-extraction receipt | `backend/app/ingestion/ocr.py`, `chunker.py` (ADAPT) | APPROVED_PHASE_1_DESIGN / _PHASE_2 | 1 (schema) |

**Rejected / deferred (must NOT appear as authority in any contract):**
`backend/app/middleware/correlation.py` (REJECTED_AS_AUTHORITY — Hub correlation is authoritative),
`backend/app/retrieval/query_expansion.py` (HyDE — DEFERRED_POST_PARITY),
`backend/migrations/001|002.sql` (REFERENCE_ONLY — never applied to the Hub),
`docker-compose.yml` (REJECTED — insecure defaults).

## Draft schemas in this package

Design-draft JSON Schemas accompany this doc under `schemas/` (all suffixed `.v1.schema.json`):
`snapshot_manifest`, `evidence_lifecycle`, `query_lifecycle`, `retrieval_object`, `provenance`,
`claim_ledger`, `abstention`, `access_classification`, `analytical_run_receipt`. They are illustrative
design drafts, **not** frozen or installed.

## Downstream docs

- `INTERFACES_DESIGN.md` — behavioral interfaces (read-only boundary, no-LLM query, policy, promotion, audit).
- `SECURITY_CONTRACTS_DESIGN.md` — quarantine, archive limits, fetch allowlist, redaction, policy parity.
- `TEST_PLAN_DESIGN.md` — contract-test matrix mapped to `BENCHMARK_THRESHOLDS.json` and `ADVERSARIAL_TEST_SPEC.json`.

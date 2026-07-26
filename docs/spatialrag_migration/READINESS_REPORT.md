# Readiness Report — spatial-rag → thehub-pr, Phase 0

Rolls up [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md) and the 12 other companion
documents in this directory. Written last, after all other Phase 0 deliverables.

## Summary verdict

**Design-ready, not code-ready.** The dual-engine (now triple-layer: Control Plane / Evidence Engine
/ Intelligence Engine) architecture is sound as a target. The uploaded `spatial-rag` package
(SHA-256 `cd3b78f343be5b7c64099ca099854f27179992dccf8c31ae5e2b67a1f9b4140f`) is not merge-ready — every
hygiene blocker named in the originating mission was independently confirmed by direct inspection
(committed `.pytest_cache/`, malformed brace-expansion directories, placeholder repo URL, hardcoded
DB credentials, dated single-provider LLM model string, monolithic dependency file, and a test-count
claim that excludes all DB-backed integration paths) — and deeper review found additional structural
defects a naive merge would inherit silently (see
[`RISK_LEDGER.md`](RISK_LEDGER.md)). No architectural migration is approved on the strength of the
package's own "126 tests passing" claim, per [`PARITY_GATES.md`](PARITY_GATES.md).

## Non-goals of this deliverable

Phase 0 explicitly does **not**:

1. Move producer crawlers into the Hub.
2. Make RAG authoritative over the Hub's existing structured federation pipeline.
3. Permit direct mutation of canonical evidence — only additive tier-review/certification metadata,
   per [`API_CONTRACT.md`](API_CONTRACT.md).
4. Merge entities automatically — every merge is a reversible, reason-coded
   `entity_identity_decision`, per [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §5.
5. Replace domain-specific scoring (`src/hub/correlate.py`'s existing structured-record matching is
   untouched).
6. Expose sensitive coordinates — `SENSITIVE_LOCATION` access classification and geometry-precision
   downgrading, per [`SECURITY_MODEL.md`](SECURITY_MODEL.md).
7. Delete the existing Hub UI before parity — [`PHASED_BACKLOG.md`](PHASED_BACKLOG.md) Phase 4 is
   additive, and cutover (Phase 5) only retires exploratory paths after full parity sign-off.
8. Introduce autonomous conclusions — every generated claim is a ledgered, evidence-linked
   `AnalyticalClaim`, never a bare assertion.
9. Archive `thehub-pr` or replace its identity — this ADR extends ADR 0001's existing product-surface
   decision.
10. Require an LLM for structured search — `CanonicalRecord` queries route through the existing `hub`
    structured pipeline unchanged, per [`API_CONTRACT.md`](API_CONTRACT.md)'s non-goals.
11. Index synthetic fixtures in operational snapshots — `test_synthetic_accounting` is a required,
    gate-enforced snapshot manifest field, per
    [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md).

Additionally, and specific to *this* Phase 0 pass rather than the mission's general non-goals: no
spatial-rag code is copied into thehub-pr; no `pyproject.toml`, `docker-compose.yml`, or `Dockerfile`
edits are made; no schema files are added under `schemas/`; no database is provisioned; no benchmark
corpus or harness code is written — only its spec ([`EVALUATION_CORPUS_SPEC.md`](EVALUATION_CORPUS_SPEC.md)).
ADR 0003 is a design ratification, not a build authorization — a follow-on ADR/PR is required before
Phase 2 runtime code lands.

## Human decisions approved for Phase 1

1. **Datastore:** PostgreSQL + PostGIS + pgvector is approved as an additional datastore. SQLite
   remains in place for the existing structured federation pipeline.
2. **Architecture boundary:** `ARCHITECTURE.md` now explicitly preserves artifact-only producer
   integration while distinguishing the Hub's live product boundary. Producer shared-database and
   RPC coupling remain prohibited.
3. **Deployment:** Control Plane and the read-only Intelligence API run in `server/backend`;
   Evidence ingestion/OCR/embedding run as separate workers. PostgreSQL schemas and roles enforce
   mutable-ingest, promotion-metadata, and read-only-active-snapshot separation.

## Requirement traceability

Every numbered requirement from the originating mission maps to at least one Phase 0 document:

| Requirement | Primary document(s) |
|---|---|
| 1. Rename to Evidence/Intelligence Engine | ADR 0003 |
| 2. Control Plane layer | ADR 0003, [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md) |
| 3. Snapshots as the only integration boundary | [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md), [`DATABASE_BOUNDARIES.md`](DATABASE_BOUNDARIES.md) |
| 4. Distinct structured/document retrieval objects | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §1 |
| 5. Authoritative provenance for evidence tiers | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §2 |
| 6. Claim-level provenance ledger | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §3 |
| 7. Explicit abstention contract | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §9, [`API_CONTRACT.md`](API_CONTRACT.md) |
| 8. HyDE disabled by default | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §4, [`SECURITY_MODEL.md`](SECURITY_MODEL.md) |
| 9. Retrieval profiles, not fixed weights | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §4 |
| 10. First-class temporal retrieval | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §8 |
| 11. Contradiction-preserving entity resolution | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §5 |
| 12. Geographic uncertainty | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §6 |
| 13. Document-page evidence geometry | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §7 |
| 14. Prompt/model reproducibility | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §10 |
| 15. Split dependencies/deployment targets | [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md) |
| 16. Eliminate insecure defaults | [`SECURITY_MODEL.md`](SECURITY_MODEL.md) |
| 17. Evidence access classifications | [`SECURITY_MODEL.md`](SECURITY_MODEL.md) |
| 18. Evaluation before migration | [`EVALUATION_CORPUS_SPEC.md`](EVALUATION_CORPUS_SPEC.md), [`PARITY_GATES.md`](PARITY_GATES.md) |
| 19. Migration by extraction | [`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md), [`DUPLICATION_REGISTER.md`](DUPLICATION_REGISTER.md) |
| 20. Explicit non-goals | This document, § above |

Every OUTPUT item from the mission (`ARCHITECTURE_DECISION_RECORD`, `COMPONENT_MIGRATION_MATRIX`,
`DUPLICATION_REGISTER`, `TARGET_REPO_TREE`, `DATA_CONTRACTS`, `DATABASE_BOUNDARIES`, `API_CONTRACT`,
`SECURITY_MODEL`, `SNAPSHOT_STATE_MACHINE`, `EVALUATION_CORPUS_SPEC`, `PARITY_GATES`,
`PHASED_BACKLOG`, `RISK_LEDGER`, `READINESS_REPORT`) has a corresponding file in this directory or
`docs/adr/`.

## Go/no-go checklist — is Phase 1 safe to start?

| Check | Status |
|---|---|
| All 13 companion docs + ADR 0003 exist and are internally consistent | Done — this pass |
| Requirement traceability table above has no blank cells | Done |
| Datastore, architecture boundary, deployment shape, and schema-role isolation have explicit human sign-off | **Done — adjudicated 2026-07-26** |
| ADR 0003 reviewed and merged | **Pending** — awaiting reviewer approval on the PR carrying this deliverable |
| No spatial-rag code, schema, or dependency file has been touched in thehub-pr | Confirmed — this Phase 0 pass is documentation-only |

Phase 1 may begin after ADR 0003 is reviewed and merged. Phase 2 runtime implementation still
requires its follow-on ADR/PR and parity gates.

## Readiness stages (restated from the mission, unchanged by this audit)

| Stage | Readiness |
|---|---|
| Architectural concept | 96% |
| Claude audit and design pass | 93% |
| Direct implementation | 61% |
| Direct ZIP merge | 15% |

This Phase 0 deliverable is the "Claude audit and design pass" row. It does not raise "Direct
implementation" or "Direct ZIP merge" readiness — those remain gated behind Phase 1's contracts and
Phase 2's parity gates.

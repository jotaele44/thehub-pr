# ADR 0003 — Evidence Engine, Intelligence Engine, Control Plane

- **Status:** Proposed
- **Date:** 2026-07-25
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` design only — no code changes in this ADR's Phase 0
- **Extends:** [ADR 0001 — Federated engines, one hub app](0001-federated-engines-single-hub.md)

## Context

A package called `spatial-rag` (uploaded as `spatialragv2.zip`, SHA-256
`cd3b78f343be5b7c64099ca099854f27179992dccf8c31ae5e2b67a1f9b4140f`) was proposed for migration into
`thehub-pr`: a FastAPI + Next.js document-RAG system (Postgres + PostGIS + pgvector, OCR, embeddings,
HyDE, hybrid retrieval) intended to give the Hub document/evidence retrieval capability it does not
have today. thehub-pr today is a pure structured-data federation control plane — confirmed by direct
repository inspection to have zero existing RAG, embeddings, vector-search, PostGIS, or LLM
capability anywhere in the codebase.

Direct inspection of the uploaded archive found it is not merge-ready: a committed
`backend/.pytest_cache/`; literal malformed brace-expansion directories on disk (bash brace expansion
failed when the package was assembled, e.g. a directory literally named
`spatial-rag/{backend/{app/{models,ingestion,spatial,retrieval,citation,api},migrations,tests,scripts},frontend/{...}}`
alongside the real `backend/`/`frontend/` dirs); a placeholder repository URL
(`github.com/your-org/spatial-rag`); hardcoded local database credentials (`spatial_rag`/`spatial_rag`
in both `.env.example` and `docker-compose.yml`, the latter also exposing port 5432 to the host); a
dated, hardcoded, single-provider LLM model string (`claude-3-5-haiku-20241022`); one monolithic
`requirements.txt` mixing runtime, OCR, GIS, ML, dev, and test dependencies; and a README claim of
"126 tests passing (all non-DB unit tests)" that, on inspection of `conftest.py`, provably excludes
every DB-backed integration path (fixtures assume a live `spatial_rag_test` Postgres+PostGIS+pgvector
database with no skip markers) — meaning the actual ingestion pipeline, hybrid retrieval SQL, and
HTTP route behavior have no verified test evidence in the package at all.

Beyond hygiene, deeper architectural review (see the full component-by-component inventory in
[`docs/spatialrag_migration/COMPONENT_MIGRATION_MATRIX.md`](../spatialrag_migration/COMPONENT_MIGRATION_MATRIX.md))
found structural defects that a copy-paste merge would silently inherit: retrieval weights hardcoded
in three unsynced places; retrieval querying live mutable Postgres directly with no snapshot
boundary; evidence tiers assigned by keyword matching and written as if final; sentence-level
citation gating with no claim-level ledger; an MMR reranker wired with an empty embeddings dict at
its actual call site (dead code presented as a working feature); HyDE enabled by default for
forensic/FOIA-style work; and no access-classification model of any kind.

These findings are the forcing function for a redesign, not a lift-and-shift. This ADR does not
authorize copying spatial-rag into thehub-pr. It ratifies a target architecture and a
migration-by-extraction process ([`COMPONENT_MIGRATION_MATRIX.md`](../spatialrag_migration/COMPONENT_MIGRATION_MATRIX.md))
that a later, separate ADR/PR will authorize executing.

## Decision

**Rename the "two brains" and add a coordinating third layer:**

| Layer | Responsibility |
|---|---|
| **Evidence Engine** | Acquires, validates, normalizes, certifies, snapshots. |
| **Intelligence Engine** | Retrieves, compares, explains, visualizes, cites — **read-only against certified evidence snapshots**, never against mutable ingestion state. |
| **Control Plane** (new) | Producer registry extension, job orchestration, snapshot lifecycle, readiness gates, permissions, audit ledger. |

The Control Plane extends two modules that already exist in this repo rather than inventing new
ones: `src/hub/mcp_runtime/policy.py::PolicyEngine` (declared-capability allowlists, read-only-by-
default write policy) becomes the base for the new permissions layer, and
`src/hub/mcp_runtime/auth.py::CredentialProvider`/`redact()` becomes the base for credential handling
across both new engines. The snapshot promotion gate reuses the pure-function shape of
`src/hub/maintenance/gate.py::compute_gate()` (`{promotion_blocked, blockers}` over a rollup), as a
new, separate `compute_snapshot_gate()` — not an import, since the rollup shape differs. Full
reuse-vs-new-build mapping is in
[`docs/spatialrag_migration/DUPLICATION_REGISTER.md`](../spatialrag_migration/DUPLICATION_REGISTER.md).

Snapshots become the **only** integration boundary between the two engines — see
[`docs/spatialrag_migration/SNAPSHOT_STATE_MACHINE.md`](../spatialrag_migration/SNAPSHOT_STATE_MACHINE.md)
and [`DATABASE_BOUNDARIES.md`](../spatialrag_migration/DATABASE_BOUNDARIES.md). Only `ACTIVE`
snapshots answer normal queries.

### Target architecture

```
THEHUB-PR
│
├── CONTROL PLANE
│   ├── registry, orchestration, readiness, policy, audit, snapshot promotion
│
├── EVIDENCE ENGINE
│   ├── federation ingest, document ingest, normalization, provenance,
│   │   entity resolution, spatial/temporal processing, deterministic
│   │   correlation, certified snapshot build
│
└── INTELLIGENCE ENGINE
    ├── structured retrieval, lexical/vector/spatial/temporal/graph retrieval,
    │   reranking, claim ledger, contradiction analysis, citation resolution,
    │   maps/graphs/documents, evidence-bound explanation
```

`src/hub/` (the existing structured-federation pipeline: registry, manifest validation, fetch,
aggregate, correlate) is unchanged and continues to operate exactly as it does today — it becomes one
of the Evidence Engine's inputs (`CanonicalRecord` objects, per
[`DATA_CONTRACTS.md`](../spatialrag_migration/DATA_CONTRACTS.md) §1), not something replaced by it.

### Resolving the ARCHITECTURE.md tension

[`ARCHITECTURE.md`](../../ARCHITECTURE.md) states the federation is "artifact-based, not a live
network service … no shared database or RPC." The Evidence Engine (a live ingestion pipeline with a
mutable-to-certified snapshot boundary) and Intelligence Engine (query-time retrieval) are inherently
live, stateful, always-on services — incompatible on their face with a pure artifact/export model.

This is resolved explicitly, not glossed over: ADR 0001 already distinguishes the **producer
boundary** (the six domain repos — `moneysweep-pr`, `spiderweb-pr`, `aguayluz-pr`, `ovnis-pr`,
`skywatcher-pr`, `centinelas-pr` — artifact-only, no RPC, **unchanged by this ADR**) from **the hub's
own product surface** (`server/backend` + `server/frontend`), which ADR 0001 already designed and
ratified as a live, always-on app. The Evidence/Intelligence/Control-Plane engines are new
capabilities *within* that already-live product surface — they extend the side of the architecture
that was never artifact-only, rather than violating the artifact-based principle that still governs
producer relationships. Producer contract schemas remain frozen and untouched.

This resolution is still flagged in
[`READINESS_REPORT.md`](../spatialrag_migration/READINESS_REPORT.md) as requiring explicit human
sign-off before Phase 1 begins, because it is a genuine, precedent-setting expansion of live surface
area (a new stateful datastore, per
[`DATABASE_BOUNDARIES.md`](../spatialrag_migration/DATABASE_BOUNDARIES.md)) — the architectural
argument above says it's *consistent* with existing precedent, not that it's free of new operational
risk.

## Rationale

- Migration-by-extraction (ADOPT/ADAPT/REWRITE/REJECT/DUPLICATE/DEFER, per component) is required
  because direct inspection found the uploaded package mixes genuinely reusable mechanisms (chunking,
  OCR, regex coordinate extraction, ~126 pure-function unit tests) with components that are unsafe,
  dead, or architecturally incompatible with a snapshot-bound, tier-honest, claim-ledgered target
  (fixed retrieval weights, keyword evidence tiers treated as final, an inert MMR reranker, sentence-
  level citation gating, opt-in auth). A wholesale copy would carry the second group in with the
  first.
- A third Control Plane layer is required because, without it, snapshot promotion, producer/evidence
  readiness, and cross-engine permissions have no home — exactly the scattering the mission's
  "two-brain metaphor" language warned against. thehub-pr already has two of the three primitives
  this layer needs (`PolicyEngine`, `CredentialProvider`, `compute_gate()`'s shape); building the
  Control Plane as an extension of them, not a parallel system, keeps the repo from ending up with
  two competing permissions models.
- Renaming "input"/"output" to Evidence Engine / Intelligence Engine encodes the actual constraint
  that matters: Intelligence Engine is read-only against certified snapshots. A vaguer "brain"
  naming does not carry that constraint in the name itself.

## Alternatives considered

- **Keep spatial-rag as a standalone sibling repo behind the existing artifact/export contract**
  (like a seventh producer). Rejected: retrieval is fundamentally query-time and stateful, not a
  batch-exportable JSONL stream — forcing it into the producer contract would either strip its core
  capability or silently violate the contract's own artifact-only assumption.
- **Big-bang merge of spatial-rag into thehub-pr.** Rejected for the same reason ADR 0001 rejected a
  full monorepo merge of the producers: it would couple release cycles and, here specifically, import
  every hygiene and architectural defect found in this audit without a checkpoint to catch them.

## Consequences

- thehub-pr gains a new, live, stateful surface (Evidence/Intelligence Engines) inside its existing
  product app — an extension of the precedent ADR 0001 already set, not a new one, but a real
  operational expansion (new datastore, new dependency extras) that needs deliberate rollout.
- No producer contract, schema, or readiness-gate changes are required by this ADR.
- `src/hub/mcp_runtime/adapters/documents.py`'s substring-search capability is not touched now, but
  is flagged as a Phase 5+ (post-cutover) candidate for eventual supersession by Intelligence Engine
  retrieval — see [`DUPLICATION_REGISTER.md`](../spatialrag_migration/DUPLICATION_REGISTER.md) row 1.
- This ADR authorizes **design only**. A follow-on ADR/PR is required before Phase 2 (the first
  phase that writes runtime code) begins.

## Roadmap

Full phase-by-phase entry/exit gates are in
[`docs/spatialrag_migration/PHASED_BACKLOG.md`](../spatialrag_migration/PHASED_BACKLOG.md). At
ADR granularity: **Phase 0 — Audit** (this ADR + the 13 companion docs) → **Phase 1 — Contracts**
(new frozen schemas, `pyproject.toml` extras, benchmark corpus populated — no runtime code) →
**Phase 2 — Read-only adapter** (Evidence Engine ingestion + snapshot lifecycle, read-only
Intelligence Engine retrieval) → **Phase 3 — Dual-run** (soak validation, security review) →
**Phase 4 — UI parity** (React/Vite evidence and claim views) → **Phase 5 — Cutover**.

## Verification

This ADR's Phase 0 verification is unusual: it is a documentation deliverable, not a runnable change.
Verification is:

1. All 13 companion documents under
   [`docs/spatialrag_migration/`](../spatialrag_migration/) exist and are internally consistent with
   this ADR (no contradicting claims about reuse targets, classifications, or open questions).
2. Every numbered requirement in the originating mission (renaming, control plane, snapshot lifecycle,
   distinct retrieval objects, tier provenance, claim ledger, abstention contract, HyDE default-off,
   retrieval profiles, temporal retrieval, contradiction-preserving resolution, geographic
   uncertainty, document-page geometry, model/prompt reproducibility, dependency split, security
   hardening, access classification, evaluation-before-migration, migration-by-extraction ledger,
   non-goals) is traceable to at least one companion document — cross-checked in
   [`READINESS_REPORT.md`](../spatialrag_migration/READINESS_REPORT.md).
3. This ADR and its companion documents are reviewed and merged before any Phase 1 work (schema
   files, `pyproject.toml` edits) begins.

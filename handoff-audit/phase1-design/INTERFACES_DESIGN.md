# Phase 1 Interface Design (behavioral contracts)

> Design documents only — no implementation, no code movement. Interfaces are expressed as
> language-neutral method contracts (Python-style signatures for readability). Maps to T022–T024,
> T031–T033.

## 1. Read-only Intelligence boundary (T031)

The Intelligence Engine may **only read** from an ACTIVE snapshot. The interface exposes **no mutation
method** — there is no create/update/delete/write surface for canonical evidence or ingestion tables.

```
class ActiveSnapshotReader (read-only):
    get_active_snapshot() -> SnapshotManifest
    get_object(object_id) -> RetrievalObject            # provenance-complete
    query(spec: QuerySpec) -> RetrievalResult           # see §2
    resolve_citation(claim_id, evidence_id) -> CitationRegion
    # NO put_*, write_*, upsert_*, delete_*, certify_*, promote_* — by construction.
```

**Enforcement (design):** the reader is constructed from a read-only handle (e.g. a connection with
`default_transaction_read_only=on`, or an interface with no write capability). Contract test T041
asserts that any attempted mutation path does not exist / raises deterministically.

## 2. Structured no-LLM query contract (T032, T042)

```
QuerySpec:
    mode: EXACT_ID | STRUCTURED | LEXICAL | VECTOR | SPATIAL | TEMPORAL | GRAPH | HYBRID
    filters: {field -> predicate}          # structured predicates
    access_context: AccessClassification   # applied BEFORE retrieval
    profile_id: str                        # explicit, logged (see analytical_run_receipt)
    llm_enabled: bool = false

Guarantee: mode ∈ {EXACT_ID, STRUCTURED} MUST return correct results with llm_enabled == false and
every LLM/embedding/reranker provider disabled. No LLM is required for exact-ID or structured search.
(exact_identifier.recall_at_10 == 1.0; general_hybrid_retrieval is a separate, Phase-2 profile.)
```

## 3. Policy-decision interface (T022) — one decision, reused everywhere

```
class PolicyDecider:
    decide(subject: Principal, object_class: AccessClassification, surface: Surface) -> Allow | Deny
    # Surface ∈ {SEARCH, MAP, EXPORT, DOCUMENT_VIEWER, MODEL_CONTEXT}
```

A **single** `decide()` is the sole authority for all five surfaces, guaranteeing policy parity
(T043). Deny by default. `MODEL_CONTEXT` uses the same decision — no evidence enters a prompt that the
user could not retrieve directly.

## 4. Atomic snapshot promotion / rollback (T023)

```
class SnapshotPromoter:
    promote(candidate: snapshot_id) -> PromotionReceipt     # transactional
    rollback(to: rollback_target) -> RollbackReceipt        # transactional
Invariants:
  - exactly one ACTIVE snapshot at any instant;
  - promote() demotes the previous ACTIVE and activates the candidate in ONE transaction;
  - a failed evidence/index build (INDEX_FAILED) never mutates the current ACTIVE snapshot;
  - rollback restores rollback_target atomically.
```

## 5. Audit ledger (T024)

```
class AuditLedger (append-only):
    record(event: LifecycleEvent | PolicyDecision | PromotionReceipt) -> receipt_id
Every lifecycle transition and every policy decision produces an immutable, hash-chained receipt.
Secrets are redacted before write (SECURITY_CONTRACTS_DESIGN §4).
```

## Database boundary (design constraint)

Per `PHASE_1_IMPLEMENTATION_SPEC.md`: **SQLite remains authoritative** for existing Hub control-plane
state and Phase-1 snapshot metadata. Evidence/vector storage stays **behind interfaces**; derived
indexes are rebuildable and never authoritative. The Spatial-RAG PostgreSQL/PostGIS/pgvector schema is
**reference-only** (component ledger: `migrations/001|002.sql` = REFERENCE_ONLY) and is never applied
to the Hub.

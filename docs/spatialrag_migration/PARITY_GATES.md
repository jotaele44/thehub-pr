# Parity Gates

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

The pass/fail bar migrated functionality must clear before each phase transition in
[`PHASED_BACKLOG.md`](PHASED_BACKLOG.md), and before cutover specifically. Evaluated against
[`EVALUATION_CORPUS_SPEC.md`](EVALUATION_CORPUS_SPEC.md), once that corpus exists (Phase 2 onward) —
not against inherited test counts.

## Why spatial-rag's own test claim does not count

The uploaded README states: `# → 126 tests passing (all non-DB unit tests)`. Direct inspection of
`backend/tests/conftest.py` confirms this claim is accurate as stated but narrower than it reads:
fixtures assume a live `spatial_rag_test` Postgres+PostGIS+pgvector database with **no skip
markers**, meaning every DB-backed integration path — the actual ingestion pipeline end-to-end, the
hybrid retrieval SQL, any HTTP-route test exercising the FastAPI app against real data — is outside
that 126 count, and there is no evidence in the package of those paths ever having been verified.
**This number is explicitly excluded from parity gate consideration.** It is not treated as partial
credit toward the metrics below.

## Gate metrics (per phase transition, once benchmark corpus exists)

| Metric | Source | Threshold decided when |
|---|---|---|
| Retrieval precision/recall vs. baseline | `EVALUATION_CORPUS_SPEC.md` corpus, Recall@K/Precision@K/MRR/nDCG | Phase 1 exit (baseline established from the newly-populated corpus, not from spatial-rag's prior claims) |
| Abstention correctness rate | Corpus category 8 (no-answer behavior) + `abstention accuracy` metric | Phase 2 exit |
| Tier-certification false-positive rate | Rate at which `machine_provisional` tiers, once human-reviewed, are overturned | Phase 2 exit — establishes whether the provisional classifier from [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §2 is trustworthy enough to keep as a suggestion input |
| Latency budget | End-to-end query latency under the target `RetrievalProfile` mix | Phase 2 exit |
| HyDE-off-by-default verified | Config/contract test confirming every default `RetrievalProfile` has `hyde_enabled=false` | Phase 1 exit — this is a binary gate, not a graded metric |
| Snapshot-gate blockers correctly triggered on seeded bad data | Seed a snapshot with a known-bad manifest (missing tier review, unresolved contradiction, synthetic-data leak) and confirm `compute_snapshot_gate()` blocks it | Phase 2 exit |
| Entity-resolution precision | Corpus category 3 (alias resolution) + `entity-resolution precision` metric | Phase 2 exit |
| Spatial containment accuracy | Corpus category 4 (spatial-radius query) + `spatial containment accuracy` metric, evaluated against declared `spatial_precision_class`, not raw coordinates | Phase 2 exit |
| Snapshot reproducibility | Re-run same query against same snapshot id, confirm stable evidence set | Phase 2 exit, re-checked at every later phase |
| Security review | [`SECURITY_MODEL.md`](SECURITY_MODEL.md) checklist (no default credentials, auth required, CORS locked, rate limits wired, upload/archive protections, outbound-fetch allowlist, access classifications enforced end-to-end) | Phase 3 exit, mandatory before any cutover |

## Rule

No phase transition in [`PHASED_BACKLOG.md`](PHASED_BACKLOG.md) proceeds on the strength of a raw
unit-test count from either codebase. Unit tests (spatial-rag's ~126 pure-function tests, ported per
[`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md) row 18, and thehub-pr's own existing
suite) remain necessary regression coverage, but they answer "does this function behave correctly in
isolation," not "is this system ready to answer real queries" — only the corpus-based metrics above
answer the second question.

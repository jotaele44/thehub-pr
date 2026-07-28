# Evaluation Corpus Spec

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

**This document specifies a benchmark corpus and harness. No corpus data or harness code is built in
this phase.** It exists so that no architectural migration is approved based only on a unit-test
count — spatial-rag's README claim of "126 tests passing (all non-DB unit tests)" is exactly the
kind of evidence this spec is designed to replace as the readiness bar. See
[`PARITY_GATES.md`](PARITY_GATES.md) for how these metrics gate phase transitions.

## Target location

- `benchmarks/corpus/` — labeled queries and gold answers (introduced Phase 1, populated Phase 2).
- `benchmarks/harness/` — the runnable evaluation harness (introduced Phase 1, functional Phase 2).

Both are named in [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md); neither directory is created by this
Phase 0 deliverable.

## Minimum benchmark categories

1. Exact document retrieval (a specific known document must be findable by identifying detail).
2. Exact award or contract ID lookup.
3. Entity alias resolution (a query using an alias must resolve to the correct canonical entity).
4. Spatial-radius query (retrieve everything within a given distance of a point, respecting
   geometry uncertainty per [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §6).
5. Chronology (ordering/filtering by the distinct temporal fields in §8 of the same doc, not a single
   flattened date).
6. Conflicting-value detection (the system must surface a `ContradictionSet`, not silently pick one
   value).
7. Duplicate-document detection.
8. No-answer behavior (queries with genuinely no relevant evidence must return
   `INSUFFICIENT_EVIDENCE`, not a fabricated or generic low-confidence answer).
9. Synthetic-data exclusion (queries must never surface test/synthetic fixtures from an operational
   snapshot — see `test_synthetic_accounting` in [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md)).
10. Citation page resolution (a citation must resolve to the correct page/offset/OCR region, per
    [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §7).
11. Cross-producer query (a query whose correct answer draws on evidence from more than one Hub
    producer stream).
12. Spanish-English mixed query (Puerto Rico source material is frequently bilingual within a single
    document).
13. Puerto Rico place-name ambiguity (multiple municipalities/barrios sharing or nearly sharing a
    name; a query must not silently resolve to the wrong one).

## Gold-label schema

```
query
expected_evidence_ids
expected_claim              # where applicable — the expected AnalyticalClaim shape, not just a string answer
acceptable_abstention        # for no-answer/insufficient-evidence cases, which of the 8 statuses is correct
retrieval_profile_hint        # which RetrievalProfile the query is designed to exercise, if any
```

## Comparison methodology

- **HyDE on vs. off:** every query in the corpus is run twice — once with `hyde_enabled=false`
  (the default per [`SECURITY_MODEL.md`](SECURITY_MODEL.md)) and once with it explicitly enabled —
  and the metrics below are reported for both, so HyDE's actual effect on this corpus is measured
  rather than assumed.
- **Profile A vs. profile B:** for query categories with more than one plausible
  [`RetrievalProfile`](DATA_CONTRACTS.md#4-retrieval-profiles-replaces-fixed-040402-weights) (e.g.
  "entity lineage" vs. "narrative comparison" for the same query), both are run and compared, since
  the query planner's profile recommendation is only ever a recommendation, never silently final.
- Every run records the snapshot id used, so results are reproducible against
  [`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md)'s reproducibility guarantee.

## Metrics

```
Recall@K
Precision@K
MRR
nDCG
citation precision
citation completeness
claim support rate
contradiction recall
abstention accuracy
entity-resolution precision
spatial containment accuracy
snapshot reproducibility
```

`snapshot reproducibility` is specific to this system: running the same query against the same
snapshot id at two different times must produce the same evidence set (not necessarily the same
generated claim text, if the underlying `LLMProvider`/`model_revision` changed — but the *evidence*
retrieved must be stable, per the reproducibility fields in
[`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §10).

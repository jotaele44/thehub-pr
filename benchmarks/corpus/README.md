# Benchmark corpus (Phase 1)

`corpus.jsonl` contains one JSON object per line using the gold-label fields defined by `docs/spatialrag_migration/EVALUATION_CORPUS_SPEC.md`: `category`, `status`, `query`, `expected_evidence_ids`, `expected_claim`, `acceptable_abstention`, `retrieval_profile_hint`, and `note`.

The corpus contains 28 rows across all 13 required benchmark categories. It is an offline test fixture, not operational evidence, and is never written into `data/hub.db` or a certified evidence snapshot.

## Status discipline

- `AUTHORED`: grounded against committed aggregate or geography fixtures. Every listed evidence ID existed in the relevant fixture when authored.
- `PLACEHOLDER`: the category requires real ingested document content that does not yet exist. The row states the exact blocking data requirement rather than inventing evidence.

## Known fixture gaps

- The sample aggregate has no `funding_awards.jsonl` or `transactions.jsonl` stream. Exact-contract rows therefore use real canonical contract/property entities and state that substitution explicitly.
- The conflict rows exercise preserved low-tier disagreement. They do not overstate the fixture as containing a stronger factual contradiction than it actually has.
- Document retrieval, duplicate detection, citation-region resolution, and mixed-language document retrieval remain placeholders until real document ingestion exists.

## Extending the corpus

An `AUTHORED` row must resolve to committed fixture evidence. A `PLACEHOLDER` row must identify the missing real input. Synthetic and `TEST_ONLY` fixture records may be referenced only to test their exclusion from operational snapshots.

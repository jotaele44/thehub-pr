# Phase 1 Test Plan Design (contract-test matrix)

> Design documents only — no tests are implemented here. This is the specification for the contract
> tests Phase 1 would add (T040–T045), plus the adversarial suite (T075–T081) and benchmark gates.
> Grounded in `BENCHMARK_THRESHOLDS.json` and `ADVERSARIAL_TEST_SPEC.json`.

## Contract tests (T040–T045)

| ID | Test | Asserts | Threshold / gate |
|---|---|---|---|
| T040 | Lifecycle transitions | Every legal evidence & query transition accepted; every illegal one rejected | `evidence_lifecycle` / `query_lifecycle` x-legal-transitions |
| T041 | Intelligence write-denial | No mutation path exists on `ActiveSnapshotReader`; attempts fail deterministically | P1-G04 |
| T042 | No-LLM structured search | EXACT_ID & STRUCTURED succeed with all providers disabled | `exact_identifier.recall_at_10 == 1.0`; P1-G06 |
| T043 | Access-policy parity | search/map/export/viewer/model-context return identical allow/deny | `citation_access_policy_violations_max == 0` |
| T044 | Synthetic exclusion | Operational snapshot has `synthetic_accounting == {0,0}`; no TEST_ONLY objects | `synthetic_operational_leakage_max == 0`; P1-G08 |
| T045 | Snapshot reproducibility | Rebuilding a snapshot yields identical `sha256_manifest` | `snapshot_hash_reproducibility == 1.0` |

## Adversarial suite (T075–T081) → required result: no unauthorized disclosure, canonical mutation, active-snapshot corruption, or uncited claim

malicious archive paths · decompression bombs · duplicate filenames · corrupted PDFs · malformed
geometries · conflicting timestamps · false entity aliases · prompt injection in documents · hidden OCR
instructions · unauthorized access retrieval · stale snapshot query · synthetic leakage · unsupported
claims.

## Benchmark gates (mandatory before Phase 2 retrieval activation)

From `BENCHMARK_THRESHOLDS.json` — representative floors:

- **Exact identifier:** MRR ≥ 0.95, recall@10 == 1.0, P@10 ≥ 0.9
- **Bilingual (ES/EN):** recall@10 ≥ 0.88; PR place-ambiguity precision ≥ 0.95
- **Citations:** precision == 1.0; completeness ≥ 0.95; exact-page resolution ≥ 0.98
- **Claims:** fact-claim support == 1.0; unsupported claims == 0
- **Contradictions:** recall ≥ 0.9; silent resolution == 0
- **Abstention:** accuracy ≥ 0.95; false answer on no evidence == 0
- **Entity resolution:** precision ≥ 0.98; auto-merge without reason+evidence == 0
- **Spatial:** containment accuracy ≥ 0.98; exact coord from centroid == 0
- **Security/integrity:** unauthorized leakage == 0; synthetic leakage == 0; snapshot hash reproducibility == 1.0

## CI additions (component ledger: `.github/workflows/ci.yml` = ADAPT / add jobs)

The existing Hub CI is green (see `../phase0/TEST_RUN_LEDGER.md`). Phase 1 would **add** jobs — without
regressing the current ones (P1-G09): DB-integration, snapshot-reproducibility, security, adversarial,
and Hub-parity jobs. Existing `tests/test_schema_freeze.py` extends to cover the new
`schemas/contracts/` directory.

## Reproducibility rule

Phase 1 is accepted only when every gate in `PHASE_1_ACCEPTANCE_GATES.csv` is PASS **and** all
generated artifacts have reproducible hashes — the same rule this Phase-0 audit already applies to its
own deliverables (`../phase0/HASH_MANIFEST.sha256`).

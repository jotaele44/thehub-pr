# ROAD_TO_100 Contradiction Register

**Audit date:** 2026-07-27
**Governance version:** `road_to_100_normalization_v0_3`

| ID | Repository | Contradiction | Adjudication | Required closure evidence |
|---|---|---|---|---|
| C-001 | `skywatcher-pr` | Legacy roadmap says the offline-computable code surface is effectively closed; open PR #100 documents six post-merge correctness defects. | Implemented scope reduced to **70% provisional** until fixes and private acceptance are complete. | PR #100 merged only after all seven private-fixture gates pass at the recorded SHA. |
| C-002 | `skywatcher-pr` | Public workflows pass, but private-fixture gates are unchecked and no artifacts or PR discussion contain the certification. | Public CI recorded as green; private behavior remains **NOT VERIFIED**. | Fixture SHA, two clean runs, equal normalized digests, 39/39 accounting, schema validation, 1:1 ledgers, and calibration guard evidence. |
| C-003 | `spiderweb-pr` | `~85%` reads as overall readiness despite 56% CI maturity, three incomplete frontend surfaces, narrow lint/type coverage, and multiple offline-open tasks. | `85%` restricted to **core pipeline scope only**; operational readiness set to 30%. | Repository-wide enforcement expansion, frontend consolidation/tests, closure of offline-open tasks, and deeper recurring corpus evidence. |
| C-004 | `thehub-pr` | `~90%` can be read as complete federation readiness even though it measures local Hub code and no certified representative six-producer cycle is documented. | `90%` restricted to **local Hub implementation only**; operational readiness set to 15%. | Repeatable producer fetch/run, package validation, aggregate, correlate, ingest, graph-report, and representative UI population. |
| C-005 | `centinelas-pr` | `~90%` engine completion is presented beside a product thesis requiring Puerto Rico legislative, municipal, regulatory, procurement, and board sources that remain mostly absent. | Intended-product implementation set to 75%; generic engine remains approximately 90%. | Enumerated source universe, adapters, coverage ledger, recurrent runs, and complete MoneySweep matter lifecycle. |
| C-006 | `aguayluz-pr` | Live gate is true and the roadmap is ~90%, but electric-outage attribution depends on a March 3, 2025 third-party snapshot. | Retain 90% implementation; operational readiness 78%, D3, with mandatory stale-outage caveat. | Continuously attributed T1 utility feed, freshness evidence, and outage lifecycle reconstruction. |
| C-007 | `moneysweep-pr` | ROAD_TO_100 reports an older 1229/5 baseline while the maturity audit executed 2394/8 with 51.74% coverage. | The newest executed baseline controls; old count is historical narrative only. | Re-executed CI-identical baseline or automated status emission from CI. |
| C-008 | `moneysweep-pr` | Strongest engineering declares `NON_PRODUCTION_DIAGNOSTIC`, while weaker nodes declare `PRODUCTION`. | Status labels are not maturity scores; no status change authorized. | Repository-specific runtime certification conditions, not cross-repo comparison. |
| C-009 | `ovnis-pr` | `PRODUCTION` and live gate true can imply recurrent source acquisition, but the roadmap still lists real discovery and large-scale harvesting as open. | Classify as D2: substantial static reviewed corpus with bounded intake automation. | Recurrent source-family discovery/harvesting, dedup/revalidation cadence, and GIS enrichment. |
| C-010 | Federation | A true live gate has unequal evidence depth across repositories. | Add D0–D4 evidence depth beside every binary gate. | Repository-specific evidence satisfying the next depth level. |
| C-011 | Federation | Legacy ROAD_TO_100 percentages are compared as if they measure the same denominator. | Require three separate percentages: implemented scope, CI maturity, operational data readiness. | Adoption of the normalized policy and companion ledgers. |
| C-012 | Five non-standard repos | No ROAD_TO_100 ledger exists, but absence could be mistaken for zero completion or silent exclusion. | No score assigned; owner disposition required. | Active/legacy/experimental/non-product/archive classification and successor mapping where applicable. |

## Closure rules

- Contradictions are closed only with commit-addressed evidence.
- Narrative edits alone do not close runtime or data contradictions.
- Private-input contradictions require an auditable private run ledger; public CI cannot substitute for unavailable private evidence.
- No contradiction may be closed by changing a readiness flag without the underlying evidence.

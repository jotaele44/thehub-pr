# ROAD_TO_100 Phased Remediation Queue

**Audit date:** 2026-07-27
**Execution principle:** evidence before status; no merge or readiness flip is authorized by this queue.

## Phase 0 — acceptance and truth repair

| Priority | Repository | Action | Exit gate |
|---:|---|---|---|
| 1 | `skywatcher-pr` | Complete PR #100 private-fixture certification. | Fixture hash matches; two clean reruns; normalized digests equal; 39/39 accounting; all JSON schema-valid; 1:1 ledgers; track unregistered without calibration. |
| 2 | All seven | Merge normalized companion ledgers only after review confirms SHAs, baselines, and metric qualifiers. | No incorrect score, status change, or unsupported test claim. |
| 3 | `thehub-pr` | Adopt the portfolio policy, matrix, 12-repo ledger, and contradiction register. | Governance documents cross-link and agree on all seven scores and five dispositions. |

## Phase 1 — federation-wide enforcement sweep

These are the highest-value repeatable improvements and should be implemented as separate repository PRs.

1. Add frontend test harnesses to the six repositories without them.
2. Add or ratchet Python coverage floors where absent.
3. Gate existing typecheck scripts or remove misleading non-actionable scripts.
4. Expand Python and JavaScript lint gates to the intended maintained surface.
5. Emit test baselines automatically from CI to prevent documentation drift.

**Exit gate:** every maintained frontend has tests; every maintained Python surface has an explicit lint/type/coverage policy; normalized baselines identify the executing workflow and commit.

## Phase 2 — repository-specific correctness and product gaps

### SkyWatcher

- Merge PR #100 only after Phase 0 evidence.
- Supply real FR24 captures and execute a production-mode export.
- Port or explicitly retire GEBCO, satellite, RAG/earthgpt, and ILAP extension scope.
- Gate Python lint/type checks and make frontend typecheck actionable.

### Spiderweb

- Complete typed error taxonomy, checkpoint/resume, export redaction lint, map previews, GeoPackage export, geo-anchors v2, and license policy.
- Select and consolidate one frontend.
- Expand lint/type coverage beyond the narrow allowlist.
- Run recurring real intake and document corpus growth.

### Centinelas

- Lock the Puerto Rico intended-source universe.
- Implement adapters for legislative, municipal, procurement, regulatory, and board sources.
- Complete the Stage 0–6 matter lifecycle and MoneySweep handoff state.
- Establish source coverage, freshness, and failure ledgers.

### TheHub

- Build a committed representative multi-producer fixture.
- Run `fetch --run → aggregate → correlate → ingest → graph-report` in CI or a certification workflow.
- Ensure representative domain pages populate from the resulting store.
- Resolve diagnostic-stub scope and frontend write-credential architecture.

### Agua y Luz

- Pursue formal PREB/LUMA access or another permissioned T1 outage source.
- Add freshness enforcement and outage lifecycle diffing after a real time series exists.
- Establish frontend tests, coverage floor, and complete type/lint enforcement.

### OVNIS

- Add recurrent registered-source discovery and candidate harvesting.
- Schedule revalidation, rescoring, and deduplication.
- Complete coordinate/GIS enrichment.
- Add Python lint/type/coverage enforcement and frontend tests.

### MoneySweep

- Complete required-source materialization and production certification.
- Ingest Tranche-B manual sources under gates.
- Reconcile entity branches and execute PR3 deduplication.
- Build out the dashboard, add frontend tests, and action module consolidation.

## Phase 3 — operational-depth promotion

A repository advances one D-level only when all evidence for the next level exists.

- **D0 → D1:** first real, non-synthetic valid production package.
- **D1 → D2:** bounded repeatable run and material intended-scope coverage.
- **D2 → D3:** recurring intake, freshness evidence, production export, and documented failure handling.
- **D3 → D4:** representative intended-scope coverage, freshness controls, downstream consumer validation, and sustained repeatability.

No binary live gate is sufficient by itself for depth promotion.

## Phase 4 — five-repository disposition

For each non-standard repository, decide one of:

- adopt active ROAD_TO_100 governance;
- mark `LEGACY_SOURCE` and name a successor;
- mark `EXPERIMENTAL` or `NON_PRODUCT`;
- archive after owner approval.

Recommended first adjudications:

1. Determine whether `Puerto-Rico-Airspace-Intelligence-Tool` is fully superseded by `skywatcher-pr`.
2. Determine whether `Puerto-Rico-Integrated-Intelligence-System` is fully superseded by `thehub-pr`.
3. Classify `Faces-Font` as non-product or archive if intentionally empty.
4. Keep `minecraft_seed` outside federation governance unless promoted as an active product.
5. Determine whether `Aerospace-Intelligence-Tool` is an active independent product, legacy source, or predecessor.

## Prohibited actions

- No automatic merge.
- No production-status or live-gate flip from documentation alone.
- No private-fixture gate marked passed without fixture-addressed evidence.
- No completion percentage assigned to an undeclared product boundary.
- No repository archived, renamed, or made private through this vector.

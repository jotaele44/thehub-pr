# PRII Federation — Exhaustive Audit Report

**Audit date:** 2026-06-08  
**Audit basis:** Each repo audited read-only from its `origin/main` ref (aguayluz-pr from `origin/feat/aee-incidents-integration`, which merged as PR #7 during the audit).  
**Method:** 7 parallel deep-read agents, one per repo, across a 13-dimension rubric — each claim is grounded in a file path, line number, or command output. No fabricated specifics.  
**Output:** Executive health matrix → per-repo sections → consolidated P0/P1/P2 backlog.

---

## Executive Health Matrix

| Repo | 1·Role | 2·Conf | 3·Tests | 4·CI | 5·Quality | 6·Sec | 7·Deps | 8·Docs | 9·Debt | 10·Perf | 11·Branches | 12·Data | **Overall** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **thehub-pr** | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | 🟡 | 🟢 | **🟡** |
| **Contract-Sweeper** | 🟢 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | **🟡** |
| **spiderweb-pr** | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | **🟡** |
| **aguayluz-pr** | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | 🟡 | 🔴 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | **🟡** |
| **PRUFON** | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | 🔴 | 🟢 | 🟡 | 🔴 | **🟡** |
| **skywatcher-pr** | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟢 | **🟢** |
| **PRIIS** | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 | 🟢 | 🔴 | **🟡** |

**skywatcher-pr** is the cleanest node. **PRUFON** and **PRIIS** carry the most data-state debt (placeholder ledger and no real Hub aggregate consumed, respectively).

---

## Top Cross-Repo Themes

1. **No lint/type-check gate in 4 of 7 repos.** thehub-pr, PRUFON, skywatcher-pr, and PRIIS have zero ruff/mypy/flake8 in CI. Contract-Sweeper (gating ruff + mypy) and aguayluz-pr (gating ruff UP) are the best-practice reference implementations.

2. **FR24 migration resolved across Spiderweb and Skywatcher.** Spiderweb has merged the FR24 removal/slimdown path; Skywatcher PR #6 merged the FR24 ingest/OCR/RLSM pipeline into `main`, with post-merge local validation at `328 passed, 12 skipped`. Remaining FR24 blocker is operational data capture, not code placement.

3. **Synthetic/placeholder data in 3 producer nodes.** PRUFON holds only a placeholder row; skywatcher has synthetic observations only; PRIIS has never ingested a real Hub aggregate. All three correctly declare `ready_for_hub_live_execution=false` (PRUFON, skywatcher) or carry no readiness gate (PRIIS, which is a consumer). The production data gap is externally blocked, not an engineering gap.

4. **Z2 entity location shipped but not consumed.** `federation_entity.schema.json` now carries optional `location{lat,lon,municipality?}`. Hub aggregate stores it. PRIIS's `_entity_name()` extracts only `.name` — the geometry field that Hub's schema explicitly designates for PRIIS use sits dormant. Field-name mismatch compounds this: entity uses `lat`/`lon`, PRIIS's existing location reader keys on `latitude`/`longitude`.

5. **README drift in 4 repos.** spiderweb-pr README has 0 federation mentions and presents the repo as an FR24 tool. aguayluz-pr README does not document the AEE/LUMA pipeline. PRUFON README is a single heading. PRIIS README does not state its consumer-vs-producer boundary.

---

## Per-Repo Sections

---

### 1. thehub-pr
**Role:** Hub — registry, conformance validator, canonical aggregator, shared schema owner.  
**Audit ref:** `origin/main`

**Summary.** thehub-pr is the cleanest Python codebase in the federation: six single-responsibility modules, 31 tests (all pass, Python 3.9–3.12 matrix), well-maintained documentation, and accurate registry entries for all 5 active producers. The primary non-trivial security surface is `hub fetch --run`, which passes a producer-controlled command string through `shlex.split()` into `subprocess.run()` with no allowlist — a malicious or compromised `federation.json` could execute arbitrary commands on the Hub operator's machine. The `observations` canonical stream is accepted by the manifest schema and the row-count validator but has no schema entry in `_schemas.py:STREAM_SCHEMA` or `STREAM_ID_FIELD` — cross-producer deduplication of observations is silently undefined. `aggregate.py:42` loads each JSONL file entirely into RAM; this will spike memory on large producer exports.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟢 | Hub is purely discovery/validate/aggregate — no data produced. `README.md:9–19`, `ARCHITECTURE.md:5–9` |
| 2 | Federation conformance | 🟢 | 7 schemas well-formed (CI gate `ci.yml:19–20`); 5-producer registry accurate. One gap: `observations` stream absent from `_schemas.py:25–40` |
| 3 | Tests | 🟢 | 31 tests pass (aggregate×3, bridge×4, discover×4, fetch×5, manifest×5, registry×2, validate×6). No `" 2"` dupe test files on origin/main. Gap: `cli.py` has no direct test |
| 4 | CI health | 🟡 | Matrix 3.9–3.12, fail-fast:false; schema JSON + registry load + pytest gating. **No lint gate** (`ci.yml:1–26`) |
| 5 | Code quality | 🟡 | No TODO/FIXME, no dead code. **No lint tool configured** (no ruff/flake8 in `pyproject.toml`) |
| 6 | Security | 🟡 | `fetch.py:65` — `shlex.split(cmd)` on producer-controlled `federation.json["hub_callable_commands"]["export_canonical"]` → `subprocess.run()` with no allowlist. Arbitrary command execution via compromised producer manifest |
| 7 | Dependencies | 🟡 | `jsonschema>=4.0`, `PyYAML>=6.0` (no upper bounds, no lock file). `pytest>=7.0` dev dep unpinned |
| 8 | Docs | 🟢 | README, ARCHITECTURE, `docs/FEDERATION_STATUS.md` accurate and mutually consistent; Z3 `--run` caveat honestly documented (`FEDERATION_STATUS.md:70–73`) |
| 9 | Tech debt | 🟡 | `observations` stream: accepted by manifest schema enum, validated row-count-only (`validate.py:67–71`), absent from `STREAM_SCHEMA`/`STREAM_ID_FIELD` — cross-producer dedup undefined. 2 unmerged branches |
| 10 | Performance | 🟡 | `aggregate.py:42` — `fpath.read_text().splitlines()` + in-memory dict for all streams. No chunked/streaming reader |
| 11 | Branch hygiene | 🟡 | 3 branches: `main` + `feat/g1-hub-discovery` + `gpt/implement-intsys-pr-base44-build` (both created 2026-06-07, unmerged) |
| 12 | Data state | 🟢 | `data/aggregate/` gitignored and empty (correct). Registry statuses match `FEDERATION_STATUS.md` |
| 13 | Gap | 🟡 | P0 command injection; P1 lint gate, observations stream, OOM aggregate; P2 lock file, cli.py test |

**Strengths.** Injectable runner pattern (`fetch.py:29`) makes all subprocess orchestration unit-testable offline. Deterministic `package_id` via SHA-256 of sorted `(filename:sha256)` pairs (`bridge.py:68–70`). Three-layer integrity checking: sha256 → row_count → per-row schema (`validate.py:56–90`). Cross-producer provenance tracking: `row["_producers"]` records every contributing producer per row (`aggregate.py:50–51`).

**Backlog:**
- `[P0] thehub-pr — add command allowlist or sandboxed runner for hub fetch --run — S — fetch.py:64-65,34`
- `[P1] thehub-pr — add ruff + mypy lint gate to CI — S — ci.yml:1-26 (no lint step)`
- `[P1] thehub-pr — define canonical schema + STREAM_ID_FIELD for 'observations' stream — M — _schemas.py:25-40, validate.py:67-71`
- `[P1] thehub-pr — replace aggregate.py full-RAM load with chunked JSONL reader — M — aggregate.py:22,42`
- `[P2] thehub-pr — add lock file for reproducible CI — S — pyproject.toml:14-17`
- `[P2] thehub-pr — add direct tests for cli.py subcommand dispatch — S — tests/ (no test_cli.py)`
- `[P2] thehub-pr — exercise hub fetch --run end-to-end in CI smoke or Makefile — M — FEDERATION_STATUS.md:70-73`
- `[P2] thehub-pr — merge or delete feat/g1-hub-discovery and gpt/implement-intsys-pr-base44-build — S — gh api branches`

---

### 2. Contract-Sweeper
**Role:** `moneysweep-pr` — public-money / federal-funding intelligence producer.  
**Audit ref:** `origin/main` (HEAD `e92449e` PR #228)

**Summary.** Contract-Sweeper is the most engineered node in the federation: 531 Python modules, 156 test files, 594 passing tests, 14 workflows — of which lint (ruff E/F/W/I), mypy (`files=["contract_sweeper"]`), repro, promotion-guard, production-status-gate, and lockfile-drift are all gating. The canonical_v1 bridge is correct and verifiable (`manifest.json`: sources 4,480 = 4,248 federal publications + 232 canonical evidence; `edges_federated_pct: 100.0`; `not_yet_federated: 0`). Security posture is best-in-class: gating `scan_for_secrets.py` covering all 5 API key patterns, `install_api_keys_from_zip.py` writing `.env` at mode 0600, and secret-gated `workflow_dispatch`-only fetchers. The headline weakness is a **three-way source-count drift**: `federation.json` and `federation_source_status_reconciliation.json` both claim 84 sources while `materialization_readiness.json` (which they cite as the source of truth) says 85 — violating the repo's own declared `blocking_condition`. Two `workflow_dispatch`-only workflows post a cosmetic red ✗ on every push. The bridge re-stamps `generated_at` on every run, and this non-determinism is untested.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟢 | `MODULE_REDUCTION_PLAN.md` + `reports/module_inventory.csv` (225 rows) govern sprawl. `federation.json` role `public_money_intelligence_node` |
| 2 | Federation conformance | 🟡 | Bridge correct & 100%-edges. **3-way source-count drift**: `federation.json` → 84/54/54; `reconciliation.json` → 84; `materialization_readiness.json` → **85**/55/55 |
| 3 | Tests | 🟢 | 156 test files; `MODULE_REDUCTION_PLAN.md` cites 594 passed·4 skipped·0 failed; `test_canonical_v1_bridge.py` 5/5 pass |
| 4 | CI health | 🟡 | 14 workflows; substantive gates green. `highergov-fetch.yml` + `intake-delivery.yml` are `workflow_dispatch`-only but **post failure/0s on every push** (runs 27174361540/27174361791) |
| 5 | Code quality | 🟢 | Lint + mypy are **gating** (not report-only). `archive/` fully isolated via `norecursedirs`. Only 2 TODO/FIXME markers tree-wide |
| 6 | Security | 🟢 | `scan_for_secrets.py` gating (12 key patterns); `.env` mode 0600; fetch workflows secret-gated; `inputs.raw_intake_path` passed via `env:` (no shell injection) |
| 7 | Dependencies | 🟢 | `requirements.lock` fully pinned (uv-compiled), enforced by gating `lockfile.yml`. Dependabot configured (9 open PRs #229–#237) |
| 8 | Docs | 🟢 | 66 docs; HANDOFF/STATUS/SETUP/ARCHITECTURE/DATA_POLICY. Drift: `reconciliation.json` `historical_drift_notes` are themselves stale vs. live count of 85 |
| 9 | Tech debt | 🟢 | 4,248 federal publications are NOT orphans — consumed by `bridge_canonical_v1_federation.py::merge_external_sources`, covered by `test_federal_publications_feed.py`. `archive/r4_legacy/` isolated |
| 10 | Performance | 🟡 | `scripts/bridge_canonical_v1_federation.py:131` stamps `generated_at=datetime.now()` every run. Idempotency test compares only in-memory IDs, never calls `write_streams`. `sources.jsonl` 2.8 MB |
| 11 | Branch hygiene | 🟢 | Only `main` + 9 `dependabot/*` branches. Zero stale human branches |
| 12 | Data state | 🟢 | `data/` deny-all gitignored. Export 100% `synthetic:false`. `production_status.json` gate-enforced `NON_PRODUCTION_DIAGNOSTIC` |
| 13 | Gap | 🟡 | Well-triaged 8 open issues (issue #215 high: untested security-sensitive modules; #87 externally blocked API keys) |

**Strengths.** Federation bridge verifiably correct — every manifest headline matches committed `manifest.json`. Security best-in-class for the federation. CI rigor genuinely tightened (lint + mypy + lockfile gating). Exceptional cleanliness for ~1,150 files: 2 TODO/FIXME tree-wide, zero stale human branches.

**Backlog:**
- `[P1] Contract-Sweeper — reconcile 84↔85 source-count drift — S — federation.json vs materialization_readiness.json`
- `[P1] Contract-Sweeper — suppress workflow_dispatch workflows from push checks — S — runs 27174361540/27174361791`
- `[P1] Contract-Sweeper — test + gate bridge output determinism (write_streams idempotency) — M — bridge_canonical_v1_federation.py:131`
- `[P1] Contract-Sweeper — add tests for security-sensitive adapter modules — M — issue #215 (priority:high)`
- `[P2] Contract-Sweeper — install from requirements.lock in CI for reproducibility — S — requirements.txt (unpinned) vs requirements.lock (pinned)`
- `[P2] Contract-Sweeper — promote pip-audit to gating — S — pip-audit.yml (continue-on-error)`

---

### 3. spiderweb-pr
**Role:** Dual producer + consumer — spatial evidence envelope producer AND federation query-hub.  
**Audit ref:** Updated post-FR24 migration closure. Spiderweb `main` has merged the FR24 removal/slimdown path; no active FR24 migration branch is required for federation readiness.

**Summary.** spiderweb-pr is the most architecturally complete node: a genuine dual producer+consumer whose federation layer is real, tested, and green. Z2 entity geometry projection is implemented and verified (`federation_export.py:_point()` sets `entities[ent_id]["location"]` from GeoJSON Point/LineString). The consumer query-hub has four working correlation strategies (temporal, normalized-entity, spatial-haversine, external-id), all fail-closed behind `normalize_package(reject_synthetic=...)`. 29/29 federation+spatial tests pass locally; the CI matrix covers 3.10–3.12. The dominant drift items are: the README has 0 federation mentions (presents the repo as an FR24 airspace tool); `pyproject.toml` pins `numpy>=2.4,<2.5` while `requirements.txt`/CI use `numpy>=1.26` (mutually exclusive); the FR24→skywatcher migration is half-done (FR24 in ~140 files on main, migration branch unmerged); all four query-hub correlators are O(n²) pairwise with no spatial index.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟡 | Dual role clean in code + `federation.json:6-32`. **README has 0 federation/producer/query-hub mentions** (`grep -ciE federation README.md` → 0). README title is "Puerto Rico Airspace Intelligence System … from FlightRadar24 screenshots" |
| 2 | Federation conformance | 🟢 | Z2 accurate (`federation_export.py:80-103,148-151`). Query-hub correlations real + deduped (`hub/query.py:135-194`). Readiness gate honest |
| 3 | Tests | 🟢 | 943/944 collected; 29 federation tests passed in 3.83s; 2 collection errors are scipy/xarray environmental (CI routes them to separate `test-gebco` job, by design) |
| 4 | CI health | 🟢 | 3.10–3.12 matrix, fail-fast:false; validator both-modes gated; `intake-normalize.yml` path-filtered; `prii-smoke.yml` schema/satellite gated |
| 5 | Code quality | 🟢 | Ruff (E/F/W/I) + black + pre-commit. No lingering coupling on main (grep confirms 0 hits) |
| 6 | Security | 🟢 | No hardcoded secrets. `intake-normalize.yml` uses `env:` for inputs (no shell injection). Only `secrets.GITHUB_TOKEN` |
| 7 | Dependencies | 🟡 | **numpy pin conflict**: `pyproject.toml` `numpy>=2.4,<2.5` vs `requirements.txt` `numpy>=1.26` — `pip install -e .` would fight CI's env |
| 8 | Docs | 🟡 | Federation docs strong (`docs/federation_readiness.md`, `data/intake/pr_intake/README.md`). Top-level README is FR24-only |
| 9 | Tech debt | 🟡 | **FR24 migration closed**: airspace ingest ownership moved to skywatcher-pr; remaining Spiderweb debt is non-FR24: 8 TODO/FIXME (server/rag/retrieval.py:17-35, 4 stubs), numpy pin reconciliation, README federation framing, and O(n²) query-hub correlators. |
| 10 | Performance | 🟡 | All 4 correlators are O(n²) pairwise (`hub/query.py:71-91,103-122,141-162,173-194`). No spatial index/blocking. Will not scale to production multi-producer volumes |
| 11 | Branch hygiene | 🟡 | Remote branch state clean for FR24 migration closure. Local branch cruft/broken refs may still require workstation cleanup, but they are no longer a federation-blocking migration item. Archive tags present per recovery convention. |
| 12 | Data state | 🟢 | 10× `"is_synthetic":true` in stream samples; `manifest.sample.json` mode=`test`. Live-exec honestly blocked; validator enforces it |
| 13 | Gap | 🟡 | numpy conflict (P1), README (P1), FR24 migration (P1), O(n²) (P2), real data (P2) |

**Strengths.** Real tested query-hub with 4 correlation strategies + confidence scoring + deterministic ordering. Fail-closed mode boundary mechanically enforced (not just documented). Strong CI breadth: 3.10–3.12 matrix + release-gate + dedicated GEBCO job + PRII smoke.

**Backlog:**
- `[P1] spiderweb-pr — resolve numpy pin conflict (pyproject >=2.4,<2.5 vs requirements.txt >=1.26) — S — pyproject.toml, requirements.txt:5`
- `[P1] spiderweb-pr — document federation producer+consumer+query-hub role in README — S — README.md:1-3 (FR24-only)`
- `[DONE] spiderweb-pr — FR24→skywatcher migration closure landed; Spiderweb no longer owns the FR24 ingest/OCR/RLSM subsystem.`
- `[P2] spiderweb-pr — prune local branch cruft + delete broken stale ref — S — 27 local vs 3 remote; warning on fetch`
- `[P2] spiderweb-pr — add spatial index to O(n²) query-hub correlators — M — hub/query.py:71-91,103-122`
- `[P2] spiderweb-pr — implement 4 stubbed RAG retrieval functions — M — server/rag/retrieval.py:17,23,29,35`
- `[P2] spiderweb-pr — pin peter-evans/create-pull-request to commit SHA — S — intake-normalize.yml:37`

---

### 4. aguayluz-pr
**Role:** `water_grid_monitoring_node` — water/grid infrastructure producer.  
**Audit ref:** `origin/feat/aee-incidents-integration` (3 commits ahead of main at audit start; **merged as PR #7 during the audit, 2026-06-08T13:22Z, CI green**).

**Summary.** The AEE branch added per-municipality electric outage attribution — the modern realization of the defunct PREPA AEEIncidents SOAP model. It contributes `scripts/ingest_aee.py` (maps LUMA snapshot to schema-valid `service_event` rows with stable deterministic IDs including `snapshot_ts` in the hash), `scripts/fetch_luma_live.py` (ToS-gated MiLUMA WAF-bypass fetcher), `scripts/build_pr_municipios_geo.py`/`build_pr_geo_boundaries.py` (Census-derived centroid + polygon layers committed under `data/geo/`), and an expanded `federation_export.py` attaching municipio centroids to outage events. 6 committed T2/needs_review incidents from a 2025-03-03 snapshot are the AEE data payload. The branch is functionally complete and CI-green, but three immediate gaps remain post-merge: `scripts/smoke_test.py` is referenced in the `live-smoke` CI job but does not exist; `geopandas` (used by `build_pr_geo_boundaries.py`) is not declared in `pyproject.toml`; and `ingest_power.py` has no unit test despite its 39 T1 assets being the only production-quality rows.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟢 | `federation.json:6` `water_grid_monitoring_node`; 273 real assets (39 power T1, 234 water T3) + 6 T2 outage incidents match mission |
| 2 | Federation conformance | 🟡 | All 5 `hub_callable_commands` map to scripts that exist on this branch including `fetch_luma_live.py`. **`smoke_test.py` referenced in `validate.yml:46` (live-smoke job) does not exist** |
| 3 | Tests | 🟡 | `test_ingest_aee.py` (11 tests) + `test_pr_geo_boundaries.py` strong. **No `test_ingest_power.py`; no `test_fetch_luma_live.py`**. One test touches real filesystem but lacks `@pytest.mark.live` guard |
| 4 | CI health | 🟢 | Last 3 CI runs green; py3.10 + py3.12 matrix; `live-smoke` job is `workflow_dispatch`-only (missing `smoke_test.py` is dormant, not currently breaking) |
| 5 | Code quality | 🟢 | `pyproject.toml` targets py3.10, UP rules; `ingest_aee.py` correctly uses `str | None` annotations. CI ruff passes |
| 6 | Security | 🟡 | `fetch_luma_live.py:39-44` — browser `User-Agent` + `Referer` spoofing to bypass Incapsula WAF. Script header `L13-16` acknowledges LUMA has asked third parties to stop republishing. No secrets committed |
| 7 | Dependencies | 🔴 | **`geopandas` not declared in `pyproject.toml`** (`grep geopandas pyproject.toml` → NOT FOUND) despite `build_pr_geo_boundaries.py:23` importing it. Fresh-env install will silently fail for that script |
| 8 | Docs | 🟡 | `federation.json hub_callable_commands` accurately documents all new scripts. **`README.md` does not mention AEE/LUMA, `ingest_aee`, `fetch_luma_live`, or geo data layers** |
| 9 | Tech debt | 🟡 | 234 water assets `review_status: needs_review`. 6 AEE incidents frozen at 2025-03-03 from inactive mirror. Restoration events explicitly deferred (`ingest_aee.py:17`) |
| 10 | Performance | 🟢 | Geo layers are pre-built static artifacts (78 municipio polygons 313 KB, 901 barrios 1.1 MB). `federation_export.py` uses O(1) dict dedup. `fetch_luma_live.py` = single POST for all 78 municipios |
| 11 | Branch hygiene | 🟡 | `feat/aee-incidents-integration` branch still exists as remote tracking ref post-merge. 4 other stale merged branches: `feat/federation-conformance`, `feat/federation-export`, `feat/real-data-ingest`, `fix/cli-entrypoint`. `main` unprotected |
| 12 | Data state | 🟡 | 273 utility_assets (39 T1 power, 234 T3 water). 6 AEE incidents T2 snapshot (2025-03-03, sparse: Guaynabo ×2, San Juan ×4). `ready_for_hub_live_execution=true` defensible but incidents stale |
| 13 | Gap | 🟡 | P0: smoke_test.py; P1: geopandas dep, missing tests, stale branches; P2: README, live API arrangement, restoration events |

**Strengths.** Honest provenance throughout: `federation.json:30-32` discloses the mirror is inactive and labels data T2/needs_review. Schema-driven validation on both sides: `ServiceEvent(**e)` called in all test cases. Deterministic idempotent IDs: `_slug()` includes `snapshot_ts` so same zone across different fetch runs produces distinct IDs. Census-derived geo data committed and tested (`test_pr_geo_boundaries.py` validates count, polygon validity, parent linkage).

**Backlog:**
- `[P0] aguayluz-pr — create scripts/smoke_test.py (referenced by validate.yml:46 live-smoke job; will fail on next workflow_dispatch) — S — validate.yml:46 + ls scripts/smoke_test.py → NOT FOUND`
- `[P1] aguayluz-pr — add geopandas to pyproject.toml dependencies — S — build_pr_geo_boundaries.py:23 imports geopandas; not in pyproject.toml`
- `[P1] aguayluz-pr — add tests/test_ingest_power.py — S — 39 T1 power assets are the only non-needs_review rows; no test file exists`
- `[P1] aguayluz-pr — add tests/test_fetch_luma_live.py (unit test municipio_keys() + mock HTTP path) — S — ls tests/ (no luma test)`
- `[P1] aguayluz-pr — delete 5 stale merged remote branches — S — git branch -r (all PRs closed)`
- `[P2] aguayluz-pr — update README.md: AEE/LUMA pipeline, geo layers, ToS warning, snapshot vs live — S — README.md (no AEE/LUMA content)`
- `[P2] aguayluz-pr — wire official PR Energy Bureau / MiLUMA data-sharing for fetch_luma_live.py — L — fetch_luma_live.py:13-16,39-44`
- `[P2] aguayluz-pr — implement restoration-event detection via commit-walk snapshot diff — L — ingest_aee.py:15-17`
- `[P2] aguayluz-pr — enable main branch protection — S — gh api branches → protected:false`

---

### 5. PRUFON
**Role:** `anomaly_intelligence_node` — UAP/anomaly case producer.  
**Audit ref:** `origin/main`. Local checkout is on WIP branch `prufon-100-development-logic`.

**Summary.** PRUFON has sound infrastructure — federation manifest, CI pipeline, export adapter, validation scripts, and a 30-test suite — all functionally verified: 30/30 tests pass, the validator exits clean on placeholder ledgers, the export adapter correctly blocks synthetic rows in production mode, and `ready_for_hub_live_execution=false` is honest. The primary debt is that the repo holds only placeholder data on origin/main: all three ledger files hold a single placeholder row. A 91-row gap-sweep CSV from a release exists only on a local-only unpushed branch (`prufon-100-development-logic`) and has never been loaded into the JSONL pipeline the validator and exporter actually read. `dedupe_candidates.py` and `score_candidates.py` (207 lines total, including weighted scoring formula at `score_candidates.py:39`) have zero unit tests. The README is one line.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟢 | `federation.json:8` `anomaly_intelligence_node`; `docs/CASE_PROMOTION_STANDARD.md` + `docs/PRUFON_GITHUB_CONTROL_PLANE.md` complete operating doctrine |
| 2 | Federation conformance | 🟢 | `federation.json` valid; `ready_for_hub_live_execution=false` with honest `blocking_conditions`; `--mode production` exits 1 "FAIL — 4 synthetic rows" (verified live); `--mode test` → valid manifest |
| 3 | Tests | 🟡 | 30/30 pass (0.73s). Test coverage: `federation_export` + `validate_case_ledgers` only. **`dedupe_candidates.py` and `score_candidates.py` have zero tests** |
| 4 | CI health | 🟡 | 6 CI steps, all correct. **Single python-version: "3.12"** — no matrix despite all scripts using `from __future__ import annotations` for 3.9 compatibility. `pip install pytest jsonschema` unpinned |
| 5 | Code quality | 🟡 | `py_compile` clean on all 5 scripts. `from __future__ import annotations` correct. **No lint tool or lint CI step** |
| 6 | Security | 🟢 | Grep for dangerous built-ins across scripts → none found. Stdlib-only (json, csv, difflib, hashlib, pathlib, argparse) |
| 7 | Dependencies | 🟡 | No `pyproject.toml`, no `requirements.txt`. CI installs `pytest jsonschema` inline and unpinned. Reproducibility risk |
| 8 | Docs | 🟡 | `README.md`: single line `# PRUFON`. `docs/CASE_PROMOTION_STANDARD.md` + `docs/PRUFON_GITHUB_CONTROL_PLANE.md` thorough and accurate — not surfaced from repo root |
| 9 | Tech debt | 🔴 | **91-row gap-sweep CSV on unpushed local branch `prufon-100-development-logic`** — never loaded into JSONL pipeline; `git show prufon-100-development-logic:data/master/master_cases.jsonl` → fatal (path not in branch). Discovered cases exist only as out-of-band CSV |
| 10 | Performance | 🟢 | Stdlib-only. SequenceMatcher dedup (O(N²)) appropriate at 1-row scale. No bottlenecks |
| 11 | Branch hygiene | 🟡 | Remote `origin/main` is clean. **Local clone**: `main [behind 3]`; `feat/prufon-pytest-suite [ahead 1, behind 1]` diverged; `prufon-100-development-logic` 3 commits ahead of origin/main and **never pushed** |
| 12 | Data state | 🔴 | `data/master/master_cases.jsonl`: 1 placeholder row (PRUFON-0000, T4). `data/candidates/candidate_cases.jsonl`: 1 placeholder. `data/reference/source_registry.csv`: 1 placeholder. **Gap-sweep 91-row CSV exists only on an unpushed local branch** |
| 13 | Gap | 🟡 | No P0; P1: load gap-sweep into pipeline, test dedupe/score, write README; P2: pin deps, expand CI matrix |

**Strengths.** Honest placeholder discipline — `federation.json` and ledger files make no false production claims; production-reject gate is hard and verified. 30/30 tests pass covering all critical paths. Deterministic IDs via sha256. Stdlib-only scripts with graceful jsonschema degradation (`validate_case_ledgers.py:121-127`).

**Backlog:**
- `[P1] PRUFON — push prufon-100-development-logic branch and load gap-sweep candidates into data/candidates JSONL — L — prufon-100-development-logic (local-only, 3 commits, 91-row CSV); git show → fatal`
- `[P1] PRUFON — add unit tests for dedupe_candidates.py and score_candidates.py — M — neither appears in any test file; score_candidates.py:39 scoring weights untested`
- `[P1] PRUFON — write README.md content (usage, CI badge, quick-start) — S — README.md = "# PRUFON" only`
- `[P2] PRUFON — pin pytest and jsonschema (requirements.txt or pyproject.toml) — S — ci.yml step 4: pip install pytest jsonschema (no pins)`
- `[P2] PRUFON — expand CI python-version matrix to include 3.9 (compat declared via __future__ but never verified) — S — ci.yml python-version: "3.12" only`
- `[P2] PRUFON — add CI validation of export output against hub-side federation schemas — S — ci.yml export smoke only checks manifest.json exists + production mode exits 1`

---

### 6. skywatcher-pr
**Role:** Airspace intelligence producer; engine extracted from a spiderweb branch + salvaged export contract.  
**Audit ref:** Updated post-PR #6 merge. Skywatcher `main` now includes the FR24 ingest/OCR/RLSM migration.

**Summary.** skywatcher-pr is the cleanest airspace node overall: engine extraction is self-contained, the FR24 ingest/OCR/RLSM subsystem is now in-tree on `main`, and the post-merge local suite is green (`328 passed, 12 skipped`). The readiness gate still honestly reports `ready_for_hub_live_execution=false` because production remains blocked on real FlightRadar24 capture / observation data, not missing pipeline code.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟢 | Engine extraction clean + self-contained on main; `README.md:49-57` + `federation.json:23` document provenance. FR24 migration fully isolated on WIP branch |
| 2 | Federation conformance | 🟢 | All 5 `source_truth.engine_modules` exist as root `.py`. Readiness gate honest: 4 `blocking_conditions` (`federation.json:42-48`). Both export modes verified: test mode RC0, production mode RC1 "FAIL — 12 synthetic rows" |
| 3 | Tests | 🟢 | `python -m pytest -q` → 53 passed, 1 skipped (scipy/numpy optional gate). Engine modules covered: `test_aircraft_intelligence` (9), `test_ilap_bridge` (4), `test_prii_readiness_engine` (34), `test_validate_airspace_export` (2), `test_federation_export` (4) |
| 4 | CI health | 🟢 | `ci.yml` matrix 3.10/3.11/3.12, fail-fast:false; validates production rejects synthetic (`ci.yml:22-29`) + `pytest -q` |
| 5 | Code quality | 🟢 | No external dep coupling on main. `ilap_airspace_bridge.py:16,31` imports `gis_intelligence` with graceful try/except fallback. No TODO/FIXME/stubs in any `.py` |
| 6 | Security | 🟢 | Secrets grep → no matches. Zero runtime third-party deps in core (stdlib + sqlite3). Only dev dep: `pytest>=7.0` |
| 7 | Dependencies | 🟢 | `requirements-dev.txt` = `pytest>=7.0` only. `requirements-geo.txt` = numpy/scipy/xarray/netCDF4 (explicitly optional) |
| 8 | Docs | 🟢 | `README.md` + `docs/AIRSPACE_PRODUCER_EXPORT_TARGET.md` accurate. Field table matches `airspace_observation.schema.json required[]` |
| 9 | Tech debt | 🟡 | **FR24 migration merged** via Skywatcher PR #6. Remaining debt: real FR24 observation capture, deferred engine layers (GEBCO-into-ILAP, RAG/earthgpt, satellite, mission), lint gate, and synthetic-observation production blocker. |
| 10 | Performance | 🟢 | Stdlib engine; 5.7s suite. Deterministic sha256 IDs. No hotspots |
| 11 | Branch hygiene | 🟡 | FR24 migration branch was merged and deleted. Remaining branch hygiene: confirm old merged/stale branches (`feat/federation-export`, `feat/real-airport-registry`, `feat/z2b-entity-location`, codex branches) are pruned if still present remotely. |
| 12 | Data state | 🟢 | Airports = **real** (19 FAA-NASR PR airports, `data/reference/pr_airports.jsonl`). Observations = synthetic (2 rows, `synthetic:true`, by design). `ready_for_hub_live_execution=false` accurate |
| 13 | Gap | 🟡 | P1: merge FR24 migration + update docs; P2: delete stale branches, port deferred layers, add lint gate |

**Strengths.** Zero coupling debt — 5/5 engine modules stdlib-only. Fail-closed production boundary verified twice (export + validate). Honest self-reporting. Healthy test + CI posture. Real reference data with provenance (19 FAA-NASR airports).

**Backlog:**
- `[DONE] skywatcher-pr — PR #6 merged FR24 ingest/OCR/RLSM migration into main; post-merge suite green at 328 passed, 12 skipped.`
- `[DONE] skywatcher-pr — FR24 migration documentation and federation manifest state reconciled during PR #6 merge/rebase closure.`
- `[P1] skywatcher-pr — supply real FR24 observation package to flip ready_for_hub_live_execution — L (external-blocked) — federation.json:42-44`
- `[P2] skywatcher-pr — delete 5 merged/stale branches (feat/federation-export, feat/real-airport-registry, feat/z2b-entity-location, codex/* x2) — S — gh pr list --state all (all merged)`
- `[P2] skywatcher-pr — port deferred engine layers (GEBCO→ILAP, RAG/earthgpt, satellite, mission) — L — federation.json:46`
- `[P2] skywatcher-pr — add ruff lint gate to CI — S — .gitignore:5 (.ruff_cache ignored = used locally) vs ci.yml:22-31 (no lint step)`

---

### 7. PRIIS
**Role:** Downstream analytical consumer (NOT a producer, NOT the Hub). Reads Hub aggregate; scores/ranks.  
**Audit ref:** `origin/main`. No `federation.json` producer contract — correct by design.

**Summary.** PRIIS functions as a working but thin downstream analytical consumer. The core ingestion pipeline is end-to-end functional: `hub_aggregate.py` correctly maps four JSONL streams using the exact field keys Hub schemas define for award/txn `location` objects (verified against `federation_funding_award.schema.json:60-63` and `federation_transaction.schema.json:58-61`). The `integrated_link_score()` scoring engine is fully implemented (not stubbed): 8 weighted factors, 0-100 normalized, deterministic. CI is green (4 consecutive successful runs). The structural gaps are significant: entity `location{lat,lon}` from Z2 is stored in `entity_index` but `_entity_name()` extracts only `.name` — the geometry that Hub's schema explicitly designates for PRIIS use sits dormant; only 20 of 78 PR municipalities have geocoder centroids (`constants.py`); no real Hub aggregate has ever been ingested (CI demo step uses synthetic data only); the nearest-feature search is O(N) linear over ~1,929 features × 3 layers per record.

| # | Dimension | Status | Key finding (evidence) |
|---|-----------|:------:|------------------------|
| 1 | Role & mission | 🟡 | Code correctly implements consumer-only pattern. README does not state "PRIIS is not a Hub producer" or define the federation consumer boundary |
| 2 | Federation integration | 🟡 | Award/txn `location` contract verified against Hub schemas (exact key match). **Entity `location{lat,lon}` from Z2 never extracted** — `hub_aggregate.py:32-34` `_entity_name()` reads only `.name`; sub-field mismatch: entity uses `lat`/`lon`, PRIIS reader keys `latitude`/`longitude` |
| 3 | Tests | 🟡 | 57/60 pass; 3 subprocess failures are local-env artifacts (package not pip-installed; pass in CI via `pip install -e .`). **No CLI-level test for `consume-hub` end-to-end** |
| 4 | CI health | 🟢 | 4 consecutive green runs (2026-06-07). Chains `pip install -r requirements.txt` → `pip install -e .` → pytest → demo → release-check. One historical failure (2026-05-14) was fixed in PR #6 |
| 5 | Code quality | 🟡 | Pure stdlib + 2 pinned deps. No lint tool or lint CI step |
| 6 | Security | 🟢 | No hardcoded secrets. No network calls in core scripts |
| 7 | Dependencies | 🟢 | `pyproject.toml`: `jsonschema==4.23.0`, `pytest==8.3.4` pinned exactly. Zero pandas/GDAL/geopandas — deliberate minimal-dep posture |
| 8 | Docs | 🟡 | README does not document consumer boundary or `consume-hub` CLI as federation entry point |
| 9 | Tech debt | 🟡 | ECW driver absent → 72/75 satellite mosaics unmanifestable (3 committed). Scoring `geocode_confidence_0_1` depressed for 58/78 municipalities with no centroid fallback. `ingest_satellite_mosaics.py:24` + `ingest_spiderweb_layers.py:22` hardcode `/Users/jotaele/Documents/Data/...` as defaults |
| 10 | Performance | 🟡 | `nearest_feature()` is O(N) linear haversine scan over ~1,929 features × 3 layer types per record. No rtree/KDTree. Acceptable at demo scale; bottleneck at production volume |
| 11 | Branch hygiene | 🟢 | Remote branches clean (main + 3 feature branches from closed PRs) |
| 12 | Data state | 🔴 | **No committed `from_hub.json` or real Hub JSONL fixture exists**. CI demo step uses synthetic data. Consumer contract verified only against self-authored fixtures. No evidence a real aggregate was ever ingested |
| 13 | Gap | 🟡 | P1: entity Z2 location wiring, geocoder 20→78, CLI test; P2: spatial index, hardcoded paths, real Hub fixture, consumer boundary docs |

**Strengths.** Award/txn consumer contract precision: `_location_fields()` reads exactly the keys Hub schemas define. Zero-GDAL/zero-pandas architecture: reproducible in any Python 3.10+ env. Satellite manifest contract test green and correct (handles jsonschema version variance). Deterministic scoring engine. CI structurally sound.

**Backlog:**
- `[P1] PRIIS — wire entity location{lat,lon} into scoring fallback — M — hub_aggregate.py:32-34 (_entity_name extracts only .name); federation_entity.schema.json:38-43 (lat/lon keys)`
- `[P1] PRIIS — expand geocoder municipality coverage from 20 to 78 — M — constants.py (20 hardcoded centroids); 58/78 fall through to keyword match or "unknown"`
- `[P1] PRIIS — add CLI-level test for consume-hub — S — no subprocess test for cli.py consume-hub; only Python API tested`
- `[P2] PRIIS — add spatial index (rtree/KDTree) to nearest_feature() — M — spiderweb_linker.py O(N) linear x 3 layers x all records`
- `[P2] PRIIS — replace hardcoded DEFAULT_SRC / DEFAULT_GEODATA with None + explicit flags — S — ingest_satellite_mosaics.py:24, ingest_spiderweb_layers.py:22`
- `[P2] PRIIS — commit minimal real Hub aggregate fixture under tests/fixtures/ — S — no from_hub.json in repo history`
- `[P2] PRIIS — document consumer boundary in README — S — README.md (consumer role undocumented)`

---

## Consolidated Backlog

### P0 — Correctness / Security / CI-breaking

| Item | Repo | Fix | Size |
|------|------|-----|------|
| **Command injection in `hub fetch --run`** | thehub-pr | Add allowlist or sandboxed runner; producer-controlled `federation.json` cmd string passed to `subprocess.run()` with no validation (`fetch.py:64-65`) | S |
| **`smoke_test.py` missing but referenced by CI** | aguayluz-pr | Create `scripts/smoke_test.py`; `validate.yml:46` live-smoke job will fail on next `workflow_dispatch` | S |

---

### P1 — Coverage / Conformance / Significant Debt

| Item | Repo | Fix | Size |
|------|------|-----|------|
| Add ruff + mypy lint gate to CI | thehub-pr | Configure ruff in `pyproject.toml`; add lint step to `ci.yml:1-26` | S |
| Define canonical schema + STREAM_ID_FIELD for `observations` stream | thehub-pr | Add entry to `_schemas.py:STREAM_SCHEMA` and `STREAM_ID_FIELD`; cross-producer dedup currently silent/undefined | M |
| Replace aggregate full-RAM load with chunked JSONL reader | thehub-pr | Stream rows per producer instead of `fpath.read_text().splitlines()` + in-memory dict (`aggregate.py:22,42`) | M |
| Reconcile 84↔85 source-count drift | Contract-Sweeper | Re-run reconciler; add CI assertion `federation.json source_truth.total_sources == materialization_readiness.json total_sources` | S |
| Stop `workflow_dispatch` workflows from posting red-X on every push | Contract-Sweeper | Add no-op push guard; runs 27174361540/27174361791 | S |
| Test + gate bridge output determinism | Contract-Sweeper | Add `write_streams` twice → byte-identical test (exclude `generated_at`); bring canonical_v1 export under repro-style assert-no-diff (`bridge_canonical_v1_federation.py:131`) | M |
| Add tests for security-sensitive adapter modules | Contract-Sweeper | Cover `contract_sweeper/query/adapters/` (issue #215, priority:high) | M |
| Resolve numpy pin conflict | spiderweb-pr | Reconcile `pyproject.toml numpy>=2.4,<2.5` vs `requirements.txt numpy>=1.26` | S |
| Document federation role in README | spiderweb-pr | Add producer+consumer+query-hub description; 0 federation mentions in current `README.md:1-3` | S |
| FR24→skywatcher migration closure | spiderweb-pr | Done: Spiderweb no longer owns the FR24 ingest/OCR/RLSM subsystem; remaining Spiderweb work is query-hub/readiness debt. | Done |
| Add `geopandas` to `pyproject.toml` | aguayluz-pr | Declare `geopandas` as dependency; `build_pr_geo_boundaries.py:23` silently fails on fresh install | S |
| Add `tests/test_ingest_power.py` | aguayluz-pr | 39 T1 power assets are the only non-needs_review rows; no test exists | S |
| Add `tests/test_fetch_luma_live.py` | aguayluz-pr | Unit test `municipio_keys()` + mock HTTP path; currently fully untested | S |
| Delete 5 stale merged remote branches | aguayluz-pr | `feat/aee-incidents-integration`, `feat/federation-conformance`, `feat/federation-export`, `feat/real-data-ingest`, `fix/cli-entrypoint` | S |
| Merge `feat/fr24-ingest-migration` | skywatcher-pr | Done via PR #6; branch deleted; post-merge tests passed locally. | Done |
| Update README + federation.json when merging FR24 | skywatcher-pr | Branch leaves both files untouched; `git diff` → empty on those paths | S |
| Wire entity location{lat,lon} into PRIIS scoring | PRIIS | `hub_aggregate.py:32-34` extracts only `.name`; entity Z2 geometry sits dormant; sub-field mismatch: entity uses `lat`/`lon`, PRIIS keys `latitude`/`longitude` | M |
| Expand PRIIS geocoder coverage 20→78 municipalities | PRIIS | `constants.py` hardcodes 20 centroids; 58/78 municipalities fall through to keyword match; depresses `geocode_confidence_0_1` scoring weight | M |
| Add CLI-level test for `consume-hub` | PRIIS | Only Python API tested; main integration boundary has no subprocess-level coverage | S |
| Push `prufon-100-development-logic` + load gap-sweep into JSONL pipeline | PRUFON | 91-row gap-sweep CSV exists only on local-only unpushed branch; never loaded into `data/master/master_cases.jsonl` | L |
| Add unit tests for `dedupe_candidates.py` + `score_candidates.py` | PRUFON | 207 lines (including scoring formula at `score_candidates.py:39`) with zero test coverage | M |
| Write PRUFON `README.md` | PRUFON | Current content: `# PRUFON` (1 line) | S |

---

### P2 — Performance / Polish / Hygiene

| Item | Repo | Fix | Size |
|------|------|-----|------|
| Add lock file for reproducible CI | thehub-pr | `uv.lock` or pip-tools `requirements-lock.txt` (`pyproject.toml:14-17`) | S |
| Add direct tests for `cli.py` | thehub-pr | Main public entry point has no test coverage (`cli.py:62-137`) | S |
| Exercise `hub fetch --run` end-to-end | thehub-pr | CI smoke or Makefile target with synthetic federation.json export (`FEDERATION_STATUS.md:70-73`) | M |
| Merge or delete 2 open hub branches | thehub-pr | `feat/g1-hub-discovery` + `gpt/implement-intsys-pr-base44-build` (2026-06-07, unmerged) | S |
| Install from `requirements.lock` in CI | Contract-Sweeper | Use pinned lock in CI install for reproducibility | S |
| Promote `pip-audit` to gating | Contract-Sweeper | Flip `continue-on-error` after first clean run | S |
| Prune local branch cruft + broken refs in spiderweb | spiderweb-pr | Workstation hygiene only; not a federation-blocking FR24 migration item after Spiderweb/Skywatcher closure. | S |
| Add spatial index to O(n²) query-hub correlators | spiderweb-pr | `hub/query.py:71-91,103-122` nested pairwise loops | M |
| Implement 4 RAG retrieval stubs | spiderweb-pr | `server/rag/retrieval.py:17,23,29,35` (4 stubs) | M |
| Pin `peter-evans/create-pull-request` to commit SHA | spiderweb-pr | `intake-normalize.yml:37` pinned only to `@v6` major tag | S |
| Update aguayluz README: AEE/LUMA pipeline + geo layers | aguayluz-pr | README has no AEE/LUMA/municipio content | S |
| Wire official MiLUMA data-sharing arrangement | aguayluz-pr | `fetch_luma_live.py:13-16,39-44` (WAF bypass, ToS risk) | L |
| Implement restoration-event detection in `ingest_aee.py` | aguayluz-pr | Explicitly deferred at `ingest_aee.py:17`; requires commit-walk snapshot diff | L |
| Enable `main` branch protection in aguayluz-pr | aguayluz-pr | `gh api branches → protected:false` | S |
| Delete 5 merged/stale branches in skywatcher-pr | skywatcher-pr | `feat/federation-export`, `feat/real-airport-registry`, `feat/z2b-entity-location` (PRs #1-3 merged) + 2 `codex/*` (0 contribution to main) | S |
| Port deferred engine layers in skywatcher-pr | skywatcher-pr | GEBCO→ILAP, RAG/earthgpt, satellite, mission (`federation.json:46`) | L |
| Add ruff lint gate to skywatcher-pr CI | skywatcher-pr | `.ruff_cache` gitignored (used locally) but `ci.yml:22-31` has no lint step | S |
| Add spatial index to PRIIS `nearest_feature()` | PRIIS | O(N) × 3 layers per record; ~5,787 distance computations per record at current feature count | M |
| Replace hardcoded `DEFAULT_SRC`/`DEFAULT_GEODATA` paths | PRIIS | `ingest_satellite_mosaics.py:24`, `ingest_spiderweb_layers.py:22` hardcode `/Users/jotaele/Documents/Data/...` | S |
| Commit minimal real Hub aggregate fixture | PRIIS | No `from_hub.json` or real JSONL in repo history; CI demo uses synthetic only | S |
| Document consumer boundary in PRIIS README | PRIIS | README does not name PRIIS as consumer-not-producer or document `consume-hub` as federation entry point | S |
| Pin pytest + jsonschema in PRUFON | PRUFON | `ci.yml` installs unpinned; breaking release would silently fail validation | S |
| Expand PRUFON CI to 3.9 matrix | PRUFON | `from __future__ import annotations` used for 3.9 compat but only 3.12 tested | S |
| Add CI export validation against hub-side federation schemas | PRUFON | CI smoke checks only manifest.json exists; emitted rows never validated against canonical stream schemas | S |

---

## Externally-Blocked Gaps (not engineering gaps)

These remain blocked on operator actions outside the codebase. Engineering is complete; unlocking is a user action.

| Gap | Blocked on | Repo |
|-----|-----------|------|
| Real FlightRadar24 observation capture | Manual FR24 screenshot capture or ADS-B feed agreement | skywatcher-pr |
| PRUFON real case corpus | Case discovery + promotion workflow | PRUFON |
| FEC/SAM/HigherGov/LDA/OpenCorporates API keys | Operator key provisioning (issue #87) | Contract-Sweeper |
| Real spiderweb envelope rows | Production spatial data collection | spiderweb-pr |
| PRIIS ECW mosaic driver | Proprietary GDAL ECW driver install | PRIIS |
| aguayluz per-asset live outage feed | MiLUMA ToS agreement or PR Energy Bureau data sharing | aguayluz-pr |
| `FEDERATION_DELIVERY_TOKEN` PAT | Repo-scoped PAT with write-to-spiderweb-pr scope | Contract-Sweeper |
| Repo deletions (Aerospace-Intelligence-Tool + Puerto-Rico-Airspace-Intelligence-Tool) | `gh auth refresh -s delete_repo` + jorgegonzalez44 account action | — |

---

*Pairs with `FEDERATION_STATUS.md` (per-node closed/blocked/unblock requirements). This audit is read-only; no code changes, commits, or PRs were made.*

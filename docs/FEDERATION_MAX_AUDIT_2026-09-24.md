# PRII Federation — Max Audit (2026-09-24)

**Active vector:** V1 — Federation contract integrity and executability across the seven repositories.
**Vector status:** Closed. All five exhaustion steps are done: structural analysis, evidence expansion, contradiction testing, confidence scoring and blind-spot identification.
**Mode:** Read-only and non-destructive. Every producer command ran on scratch copies of the checkouts, never on the checkouts themselves. No live network ingestion was triggered.
**Machine-readable receipt:** [`reports/federation_max_audit_20260924.json`](../reports/federation_max_audit_20260924.json)
**Corrections and post-publication status:** see [§9](#9-corrections-and-post-publication-status-2026-09-24).

### Audited baseline (`origin/main`)

| Repo | SHA | Commit time (UTC) |
|---|---|---|
| thehub-pr | `30962e8` | 2026-09-23 16:04 |
| moneysweep-pr | `4b17ba7` | 2026-09-23 16:04 |
| spiderweb-pr | `acf026b` | 2026-09-23 16:04 |
| aguayluz-pr | `54fa552` | 2026-09-23 18:40 |
| ovnis-pr | `55b2648` | 2026-09-22 14:33 |
| skywatcher-pr | `3b7d04a` | 2026-09-23 16:02 |
| centinelas-pr | `fe11dc1` | 2026-09-23 21:34 |

### Evidence tiers

- **T1:** source, schema or committed data read directly.
- **T2:** a command was executed and its output recorded in this audit.
- **T3:** operator statement.
- **T4:** secondary documentation.

Every finding below rests on T1 and/or T2 evidence. No T3 or T4 evidence was used to support a finding.

---

## 1. Executive picture

| Layer | Result |
|---|---|
| Hub governance, contracts and lockstep | **PASS.** Every control-plane gate is green (§2). |
| Hub code (tests, lint, types) | **PASS.** 1260 passed, 10 skipped. ruff and mypy report no issues. |
| Producer test suites (declared `setup` then `test_suite`) | 8000 passed, **1 failed** (moneysweep), plus **1 contract gap** (centinelas `setup` leaves out the test dependencies). |
| Producer exports (`export_canonical`) | 5 of 6 run. **centinelas fails** because its ledger is stale. |
| Hub readiness after the exports ran | 3 of 6 `ready`. One of those three is a **100% synthetic** package from a producer that declares itself `PRODUCTION` (spiderweb). |
| CI on `main` | Green: thehub and spiderweb. **Red: 5 of 6 producers** fail GUI-capability-parity, and moneysweep also fails `Tests` and `Contract Sweeper CI`. |
| Cross-producer schema coherence | **3 live-drift defects** (skywatcher consumer, ovnis grid schema, spiderweb dialect). |
| Cross-producer correlation | 1043 candidate edges. **0** meet the federation's own identity-evidence standard. |

**Headline pattern (convergence across sources):** GUI-capability-parity turned red on **5 of 6 producer mains** within an 8-minute window, 2026-09-22 14:26–14:34 UTC. Every one of those pushes was the shared "tailored program activity timeline" rollout. The same `ProgramTimeline.jsx` control hashes (`button#24455789f11f`, `button#d1a223462e45`, `input#f0f71e9142cd`) show up as unregistered in aguayluz, ovnis, skywatcher and centinelas. Skywatcher's last green parity run was 06:20 UTC the same day, on `42a8d64`. In moneysweep, the same rollout also left the committed desktop dashboard bundle stale. Three independent sources agree on this: CI run history, local re-execution of each checker, and the byte-identical control hashes.

---

## 2. Hub control-plane gates (all executed, T2)

| Gate | Command | Result |
|---|---|---|
| Governance | `scripts/federation_governance.py --all` | `GOVERNANCE_PASS`: 7 repos, 5 contracts |
| Governance certify | `scripts/federation_governance_certify.py` | PASS: 4 schema fingerprints, 0 errors |
| Spatial contract | `scripts/federation_spatial_contract.py --workspace .. --check` | `CLOSED`: spiderweb `ADVANCED`, the other 5 `ATTESTED` |
| Lockstep | `scripts/federation_lockstep_ci.py` for all 7 source apps | 7 of 7 `PASS`: 12 explicit bindings, 0 residue |
| Remote receipts | `scripts/federation_reconcile_remote_receipts.py` | PASS: 6 receipts and 1 capability receipt |
| JP-flood receipt freshness | `scripts/check_jp_flood_receipt_freshness.py` | `CURRENT_EQUIVALENT`, not blocking |
| Audit-claim re-derivation | `scripts/verify_audit.py --root .. --require-all` | 8 of 8 PASS |
| Skill packet | `scripts/validate_skills.py` | 10 of 10 checks pass |
| Offline operator package | export, dashboard, package, then strict and **max** validators | PASS on both validators |
| Hub suite | `pytest -q` using the CI dependency set | 1260 passed, 10 skipped |
| Lint and types | `ruff check .`, `mypy src/hub` | Clean (54 files) |
| Federation roll-up (raw checkouts) | `hub validate-federation --root ..` | 0 of 6 ready. Expected, because export packages are not committed. Matches `data/federation_status.json`. |
| Federation roll-up (after exports) | `hub validate-federation --root <scratch>` | **3 of 6 ready**: spiderweb, aguayluz, ovnis. Two declared-not-live: moneysweep, skywatcher. One missing package: centinelas. |

---

## 3. Findings, ranked by severity

The confidence score is the probability that the finding is real and correctly attributed. Each one was calibrated against the contradiction tests in §5.

### P0: red `main`, or a declared contract that is broken

**F1. GUI-capability-parity is red on 5 of 6 producer mains** (confidence 0.97; T1+T2)
- aguayluz, ovnis, skywatcher and centinelas each have exactly **3 new unpaired controls**, all in `ProgramTimeline.jsx`: `GUI_NOT_BACKEND_WIRED: new unpaired candidate`.
- moneysweep has the **same 3** `ProgramTimeline.jsx` controls. *(Corrected 2026-09-24; see §9. This bullet originally said "314 new unpaired surfaces" of accumulated `analysis_module`/`analysis_symbol` debt. That figure came from the hub rollup running the base checker (F15). moneysweep's CI runs `.federation/check_gui_parity_with_extensions.py`, which merges 18 extension fragments, and with those fragments the delta is 3.)*
- spiderweb has **no GUI-parity gate at all** (`no_gui_parity_gate`), so the same component landed there without any check.
- CI evidence:
  - aguayluz run 35862093684 (`daf1f3e`)
  - ovnis run 35741178729 (`55b2648`)
  - skywatcher run 35885920116 (`3b7d04a`)
  - centinelas run 35883381253 (`53a8366`)
  - moneysweep run 35886236220 (`4b17ba7`)

**F2. moneysweep `main`: `Tests` and `Contract Sweeper CI` are red because the committed prebuilt dashboard is stale** (confidence 0.99; T1+T2)
- `tests/test_desktop_prebuilt_dashboard.py:34-35` fails with the message "dashboard sources changed but the prebuilt bundle was not regenerated".
- It was introduced by `f3aaaad` and `5500f16` on 2026-09-22 (the timeline), which edited `dashboard/src` without running `scripts/build_prebuilt_dashboard.py --build`.
- Reproduced locally on the pristine checkout: 1 failed, 2957 passed, 24 skipped. The CI log for run 35886236201 shows the same assertion and the same counts.
- moneysweep is the only repo that ships a `PREBUILT_MANIFEST.json`, so the defect is isolated to it.

**F3. centinelas declares `ready_for_hub_live_execution=true`, but its `export_canonical` fails** (confidence 0.98; T1+T2)
- The command fails with: `FAIL — production live signal ledger is stale: newest capture age=699.9h exceeds max=168.0h` (`scripts/federation_export.py:42,107-110`).
- The newest `captured_at` in `data/signals/live_signals.jsonl` is 2026-08-25T23:55Z. That file was last changed by `77c593a` on 2026-08-27. Its only writer, `scripts/build_signal_ledger.py`, is **not invoked by any of the 26 workflows**.
- The freshness gate is correctly fail-closed. The defect is the combination of a missing refresh lane and readiness claims that were never downgraded. Both the registry (`registry/producers.yaml`: `ready_for_live`) and `federation.json` still claim live.
- The package shape itself is sound. In `--mode test` the same ledger yields a **VALID** package with 6 sources, 100 entities, 0 relationships and 100 observations.

**F4. spiderweb declares `PRODUCTION` and `ready_for_hub_live_execution=true`, but its hub-callable export is 100% synthetic** (confidence 0.95; T1+T2)
- `federation.json:38` declares `export_canonical: python3 scripts/federation_export.py --mode test`. It emits **30 of 30 rows `synthetic`** (2 sources, 12 entities, 16 relationships).
- The real-data path exists but is not wired to that command. Running `scripts/build_real_spatial_streams.py` and then `federation_export.py --mode production` yields a **VALID** package with 2 sources, 22 entities, 20 relationships and 0 synthetic rows.
- `hub fetch --run` executes `export_canonical`. The Hub therefore ingests synthetic spiderweb rows under a live/production label (see F5).

### P1: contract drift with measured blast radius

**F5. The Hub has no synthetic-row gate for producers that declare live status** (confidence 0.90; T1+T2)
- `src/hub/federation_status.py:73` treats only the *declared* status as disqualifying, and `aggregate.py` and `validate.py` never check `synthetic`.
- `hub validate-federation` scored the 100%-synthetic spiderweb package `ready`. `hub aggregate` merged **51 synthetic rows**: spiderweb 30, skywatcher 14, aguayluz 7.
- The committed fixture `data/aggregate/*.jsonl` carries all 30 spiderweb rows as synthetic, plus 14 of 14 from skywatcher and 6 of 933 from aguayluz.

**F6. skywatcher's vendored entity schema is stale, so its consumer rejects hub-valid sibling data** (confidence 0.97; T2)
- `skywatcher-pr/schemas/federation_entity.schema.json:38` requires `location.{lat,lon}`. The hub schema uses `anyOf` (`thehub-pr/schemas/federation_entity.schema.json:38`), which allows a location that carries only a municipality.
- Executed `integration/federation_consumer.ingest_package` against the moneysweep export: **84 of 207 entities rejected (40.6%)**, all of them hub-valid.
- aguayluz (46,431 entities and 4,385 alerts) and ovnis (758 entities and 470 observations) were ingested with 0 rejects.
- The skywatcher alert schema also lacks the hub's `is_critical` property. That gap does not break anything today, because `additionalProperties` is left open.

**F7. The centinelas hub-callable `setup` cannot run its own `test_suite`** (confidence 0.97; T2)
- The declared `uv pip install -e .[dev]` (`federation.json:38`) does not install `fastapi`. `pytest -q` then stops at collection with 2 errors, in `test_backend_write_auth.py` and `test_water_disruption_api.py`.
- CI hides the gap by installing `httpx -r server/backend/requirements.txt` on top (`.github/workflows/validate.yml:52`).
- With the CI dependency set the suite passes: 341 passed.

**F8. The federation executability auditor is mis-calibrated on real code** (confidence 0.93; T1+T2)
- `federation-audit scan` found 1123 surfaces: 832 `PARTIALLY_WIRED`, 49 `TARGET_MISSING`, 242 `UI_NO_OP`.
- **14 of 14 sampled** hits (6 `TARGET_MISSING`, 8 `UI_NO_OP`) are wired controls. The handlers exist as `useCallback` results or props, or are inline arrow functions.
- Root cause: `JSX_CONTROL = <(button|Button|a|Link)\b([^>]*)>` (`federation-audit/src/federation_audit/scanner.py:17`, and duplicated in `strict_scan.py`) stops at the `>` inside `=>`. Separately, the regex handler index misses `useCallback`, `execute(...)` wrappers and destructured props.
- `strict-scan` promoted **0 of 1123** surfaces (`target_resolved: 0`).
- All 7 manifest commit pins are stale (dated 2026-08-07). Skywatcher is 242 commits past its pin and ovnis is 174. The other 5 pins are outside the shallow history.
- Net effect: the auditor cannot currently produce actionable UI findings. Only its fixture calibration is sound.

**F9. The Hub's committed GUI-parity snapshot overstates health** (confidence 0.95; T1+T2)
- `data/gui_parity_status.json`, generated 2026-08-21, records `passed: true` for moneysweep, aguayluz and centinelas.
- A fresh `make gui-parity-status` run records 0 of 6 clean: 5 `gui_parity_gaps` and 1 `no_gui_parity_gate`.
- The Gates, Integrations and Manifest pages are seeded from that file, so the hub GUI currently shows parity as green while it is red.

### P2: latent defects and structural signals

**F10. The ovnis grid schema contradicts the grid it ships** (confidence 0.95; T2)
- `ovnis-pr/schemas/pr_grid_cell.schema.json` requires zero-padded IDs (`^R\d{3}_C\d{3}$`). The canonical grid uses unpadded IDs such as `R0_C0`, and the hub pattern matches them.
- The grid CSV is byte-identical (`17733f3f18c8`) across ovnis, spiderweb, thehub and centinelas. Against it, the ovnis schema **rejects 54,000 of 98,304 rows (54.9%)** and the hub schema rejects 0.
- The defect is dormant, because no ovnis code references the schema.

**F11. spiderweb reuses hub canonical filenames for a narrower producer dialect** (confidence 0.85; T1+T2)
- spiderweb's `federation_entity`, `federation_relationship` and `federation_source` schemas differ from the hub versions in three ways: `lineage.required` uses `extraction_method` instead of `source_inputs`, the enums are closed, and `additionalProperties` is `false`.
- Validated against these schemas, sibling packages mostly fail. For example, moneysweep passes 0 of 207 and aguayluz 0 of 46,431 entities.
- The schemas are used only by spiderweb's own exporter, so nothing breaks today. The risk is a naming collision: any tool that equates a same-name schema with the hub canonical schema will misfire.

**F12. The shared-package pin lags the hub** (confidence 0.90; T1)
- All producers pin `f2b8176` of the hub's shared packages. That is consistent across producers.
- Since the pin, `prii_maintenance` and `prii_export_utils` changed only in README and `pyproject` comments.
- `prii_desktop` gained a 33-line `prii_doctor` diagnostics hook in `setup_center.py` that spiderweb, the only consumer, does not yet receive.

**F13. The cross-producer correlation surface is candidate-only** (confidence 0.90; T2)
- `hub correlate` over today's exports produced 1043 edges: 368 `alert_affects_entity`, 366 `observation_at_entity`, 183 `spatial_proximity` and 126 `entity_correlation`.
- **915 (87.7%) touch a synthetic entity.** Most of these are aguayluz↔skywatcher (718) and aguayluz↔spiderweb (176).
- The only real↔real cluster is aguayluz↔ovnis, with 126 edges. All of them are `normalized_name` matches at confidence 0.3–0.5, and several cross entity types, for example `uap_case "Culebra"` ↔ `municipality "Culebra"`. Under `federation/completion-gate.json` `forbidden_as_sole_proof`, a name-only match cannot establish identity.
- The Hub labels every edge `CANDIDATE` with `identity_assertion=false`, so it makes no false claim.
- Structural read: **zero adjudicated real cross-producer correlations exist yet.**
- One side note: `correlate.py:367,395` stamps every derived edge `synthetic: true`. That overloads the flag, because a consumer that filters out synthetic rows would drop all hub correlations.

**F14. Dependency backlog** (confidence 0.99; T1)
- 71 PRs are open across the 7 repos. 54 are from Dependabot and 17 are human-authored.
- The unmerged majors include eslint 10 (6 repos) and vitest 5 (4 repos), plus maplibre-gl 6, recharts 3 and react-router-dom 7.

**F15. The hub GUI-parity rollup ignores each repo's own parity entrypoint** (confidence 0.97; T1+T2; added 2026-09-24 as a correction, see §9)
- `scripts/build_gui_parity_status.py:82` always runs the producer's base `scripts/check_gui_parity.py`.
- moneysweep's CI runs `.federation/check_gui_parity_with_extensions.py` instead. That wrapper appends the capabilities in `.federation/gui-capabilities.extensions/*.json` (18 fragments) before evaluating.
- The rollup therefore reported moneysweep at 314 new unpaired surfaces when CI saw 3. The same skew feeds `data/gui_parity_status.json` (F9).
- Fix: have the rollup prefer the repo's CI entrypoint (the wrapper when present), or read the command from the repo's `gui-capability-parity.yml`.

---

## 4. Producer matrix (T2: executed on scratch copies)

| Producer | Declared | Test suite (declared setup) | `export_canonical` | Rows / synthetic | Hub class (after export) | CI `main` |
|---|---|---|---|---|---|---|
| moneysweep | discovery, `NON_PRODUCTION_DIAGNOSTIC` | 2957 pass, **1 fail** (F2) | OK, test mode | 4781 / 0 | declared_not_live | **red**: Tests, Contract Sweeper, parity |
| spiderweb | live, `PRODUCTION` | 1812 pass, 54 skip | OK, **test mode** | 30 / **30** (F4) | ready | green, but no parity gate |
| aguayluz | live, `PRODUCTION_REAL_DATA_PARTIAL` | 1223 pass | OK, test mode | 155,395 / 7 | ready | **red**: parity |
| ovnis | live, `PRODUCTION` | 125 pass | OK, **production** | 2069 / 0 | ready | **red**: parity |
| skywatcher | discovery, `NON_PRODUCTION_DIAGNOSTIC` | 1542 pass, 34 skip; setup smoke PASS | OK, test mode | 16 / 16 (consistent with its declared status) | declared_not_live | **red**: parity |
| centinelas | live | **collection error** under the declared setup (F7); 341 pass with CI deps | **FAIL**: stale ledger (F3) | — | missing_export_package | **red**: parity |
| thehub | control plane | 1260 pass, 10 skip | n/a | n/a | n/a | green (12 of 12 workflows) |

Declared-versus-observed **consistency**:
- **Consistent:** ovnis, moneysweep, skywatcher. What they declare matches what they emit.
- **Inconsistent:** spiderweb (F4) and centinelas (F3).
- **Partial:** aguayluz, which carries 7 synthetic rows while declaring production, and caveats itself as partial.

---

## 5. Contradiction testing

| Claim tested | Test | Outcome |
|---|---|---|
| "The offline package validators fail on producers" | Re-ran with the canonical `exports/federation` directory name | **Refuted.** Validators pass. The first failure came from the zip arcname prefix of a non-canonical scratch directory. |
| "Hub CI would break on `starlette` 1.7 / `httpx2`" | Reproduced the CI install (`httpx` is listed explicitly) | **Refuted.** Starlette falls back to `httpx`, with a deprecation warning only. |
| "All hub correlations are synthetic, so the inputs are fake" | Read `correlate.py:359-395` | **Refuted in part.** Derived edges are stamped synthetic by design. Measured separately, 87.7% touch synthetic *entities*. |
| "The centinelas package is broken" | Ran the export in `--mode test` on the same ledger | **Refuted.** The package is VALID. Only freshness blocks it. |
| "spiderweb has no real-data path" | Built the production package manually | **Refuted.** A VALID real package exists. It is just not wired to `export_canonical`. |
| "The prebuilt-bundle failure is environmental" | Ran on the pristine checkout and compared with the CI log | **Confirmed real.** Local and CI counts are identical. |
| "Parity failures are independent" | Compared control hashes and timestamps across repos | **Confirmed common cause** (F1). |
| "The shared-package pin drift is functional" | `git diff f2b8176..HEAD -- packages/` | **Refuted** for maintenance and export utils (docs only). **Confirmed** for `prii_desktop`, as additive only. |
| "`TARGET_MISSING` and `UI_NO_OP` are real UI defects" | Read the 14 sampled hits | **Refuted.** 14 of 14 are false positives (F8). |

---

## 6. Blind spots

- **No live-network ingestion.** All fetchers and monitors were left un-triggered. Freshness claims rest on committed data plus workflow history.
- **`federation_completion_gate.py` was not run.** It needs authenticated GitHub API PR classification. CI and PR state were collected through the GitHub MCP instead.
- **`runtime-certify` (Docker shadow runtime, G0–G6), the Playwright GUI harness and `startup_completion_audit.py` were not run.** Docker and browser runs are out of scope for a non-destructive static-plus-suite audit. Isolated setup-then-test runs stand in for startup evidence.
- **Frontend npm suites and lint were not run locally.** Their status is taken from CI.
- **Shallow clones.** For 5 of the 7 federation-audit manifest pins, the distance to HEAD cannot be measured.
- **moneysweep parity delta.** *(Corrected; see §9.)* The original run used the base checker, which ignores moneysweep's extension fragments, and reported 314 new surfaces. The CI entrypoint `.federation/check_gui_parity_with_extensions.py` reports 3.
- **moneysweep `Tests (3.13)` failure.** The log tail held only post-job cleanup. Attribution to F2 is inferred from identical pass/fail counts in `Contract Sweeper CI` plus the local reproduction (confidence 0.90).
- **Setup fidelity.**
  - moneysweep was installed with `requirements-dev.txt` in addition to the declared `requirements.txt`, and `run_all.py --only-setup` was run separately (PASS).
  - skywatcher's `federation_setup_smoke.py` was run separately (PASS).

---

## 7. Remediation order

1. **moneysweep:** run `python3 scripts/build_prebuilt_dashboard.py --build` and commit the regenerated `desktop/prebuilt-dashboard/`. That returns `Tests` and `Contract Sweeper CI` to green (F2).
2. **moneysweep, aguayluz, ovnis, skywatcher and centinelas:** register the 3 `ProgramTimeline.jsx` controls in each repo's GUI-parity manifest, or wire them. Add a parity gate to spiderweb (F1).
3. **centinelas:** add a scheduled refresh of `data/signals/live_signals.jsonl`, or downgrade `ready_for_live` in both `federation.json` and `registry/producers.yaml` until one exists. Also add the server dependencies to the hub-callable `setup` (F3, F7).
4. **spiderweb:** point `export_canonical` at the real-stream production path, or downgrade the declared live/production status (F4).
5. **thehub:** make `validate-federation` fail any producer that declares live status but ships synthetic rows, and filter or flag synthetic rows in `aggregate`. Regenerate `data/gui_parity_status.json` and the fixture (F5, F9).
6. **skywatcher:** re-vendor the hub `federation_entity` and `federation_alert` schemas, or source them from the hub pin (F6).
7. **thehub `federation-audit`:** make JSX attribute parsing aware of `=>`, index `useCallback`, props and wrapper handlers, and re-pin the manifest to current SHAs (F8).
8. **ovnis:** align the `pr_grid_cell` pattern with the hub or delete the dormant copy. **spiderweb:** rename its producer-local schemas (F10, F11).

---

## 8. Lead queue (logged, not pursued: outside V1)

| # | Lead | Why it is logged | Priority |
|---|---|---|---|
| L1 | aguayluz↔ovnis co-location. 126 NAME_ONLY edges link UAP case locations to utility assets and municipalities, for example Isla Verde, Playa Santa (Guánica), Culebra and Guayama. | A pattern-convergence candidate between infrastructure geography and anomaly cases. Validating it needs a coordinate-based spatial join, not name matching. | Medium |
| L2 | 84 moneysweep entities carry only a municipality location. | Upgrading them to point geometry would open spatial correlation with airspace and grid data, and would clear F6's rejects. | Medium |
| L3 | The centinelas export has 0 relationships. | The pre-signal producer contributes no graph edges to the Hub. | Low |
| L4 | Open drafts ovnis-pr#157 ("federation observation schema gap") and centinelas-pr#158 ("hub observation correlation"). | Possible overlap with the F5 and F6 remediations. Check them before opening new PRs. | Low |
| L5 | G0–G6 runtime certification under Docker. | The only route to `EXECUTABLE_CONFIRMED` classifications. | Low |

No FOIA leads were generated by this vector.

---

## 9. Corrections and post-publication status (2026-09-24)

### Correction

- **F1 (moneysweep figure).** The original report said moneysweep carried 314 new unpaired GUI-parity surfaces. That number came from the hub rollup, which runs the base `scripts/check_gui_parity.py`. moneysweep's CI runs `.federation/check_gui_parity_with_extensions.py` instead, and that wrapper merges 18 extension fragments. Evaluated through the wrapper on the audited baseline `4b17ba7`, the new delta is **3**: the same `ProgramTimeline.jsx` controls as the other four repos. F1 therefore has one common cause across all five repos. The rollup defect is recorded as **F15**.

### Remediation status

| Finding | Repo | Status | Where |
|---|---|---|---|
| F1 | aguayluz-pr | Fixed on `main` | `bd9e717` (#295) added `ProgramTimeline.jsx` to `infrastructure-assets-and-map` |
| F1 | skywatcher-pr | Fixed on `main` | `89f6b02` (#318) added it to `airspace-intelligence-console` |
| F1 | moneysweep-pr | Fixed on `main` | `ff708bc` (#614) added it to `public-money-intelligence-dashboard` |
| F2 | moneysweep-pr | Fixed on `main` | `ff708bc` (#614) regenerated `desktop/prebuilt-dashboard/`; 13 of 13 prebuilt-bundle tests pass |
| F1 | ovnis-pr | PR open | [jotaele44/ovnis-pr#159](https://github.com/jotaele44/ovnis-pr/pull/159). Timeline plus two backend symbols added on `main` after the audit (`raw_candidates`, `partition_candidates`); ratchet 230 of 230 mapped; E2E 6 of 6 |
| F1, F3, F7 | centinelas-pr | PR open | [jotaele44/centinelas-pr#160](https://github.com/jotaele44/centinelas-pr/pull/160). Refreshed ledger, daily `signal-ledger-refresh.yml`, self-sufficient `setup`, timeline registered |
| F4 | spiderweb-pr | PR open | [jotaele44/spiderweb-pr#392](https://github.com/jotaele44/spiderweb-pr/pull/392). `export_canonical` now exports the committed `exports/real` streams in production mode: 874 rows, 0 synthetic, hub VALID |
| F5–F15 except F7 | — | Open | Not in this remediation round |

Once the centinelas-pr and spiderweb-pr PRs merge, `governance/producer_receipt_refs.json` must be re-pinned to their updated compatibility receipts.

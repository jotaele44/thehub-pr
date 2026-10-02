# Twin capability integration — run 1 reconciliation

This is the closing record for run 1 of the Federation Max Implementation Directive (Twin capability integration). It covers Phases 1–3: the manifests, the evidence contracts, producer adoption, and search, entity and deep links.

The counts below come from the `reconciliation` blocks in `federation/twin/`, which `scripts/validate_twin_manifests.py` derives from the rows. They are never typed by hand.

## Outcome

| Field | Value |
|---|---|
| TASK_COMPLETE | **Yes, for the approved Phase 1–3 scope**, with three recorded exceptions: MoneySweep is BLOCKED, the contract freeze is deferred by decision, and 5 observed and 4 derived items are PARTIAL |
| VECTOR_EXHAUSTED | Yes for run 1. Structural analysis, evidence expansion, contradiction testing, confidence scoring and blind-spot identification are below |
| OUTPUT_COMPLETE | Yes, once this record merges |
| GOAL_SATISFIED | **Partial.** The directive's full goal spans Phases 1–10 plus certification; run 1 covers Phases 1–3 |
| CERTIFIED | **false.** Phase 10 certification has not run |

## Census

### Observed: `TWIN_OBSERVED_CAPABILITY_MANIFEST_V1`

- **Coverage:** OBSERVED_TOTAL 223, ACCOUNTED_FOR 223, UNACCOUNTED 0. The census is closed.

| Delivery state | Rows |
|---|---|
| IMPLEMENTED_THIS_RUN | 16 |
| PARTIAL_THIS_RUN | 5 |
| ALREADY_PRESENT | 14 |
| DEFERRED (Phases 4–9) | 179 |
| BLOCKED | 4 |
| NOT_APPLICABLE | 5 |

- **Evidence status:** RECORDED 214, INFERRED_FROM_LABEL 9.

### Derived: `FEDERATION_TWIN_DERIVED_EXTENSION_MANIFEST_V1`

- **Total:** 74 entries, every one `origin: FEDERATION_DERIVED`: 67 enumerated by the user, 7 directive-only.

| Delivery state | Entries |
|---|---|
| IMPLEMENTED | 10 |
| PARTIAL | 4 |
| ALREADY_PRESENT | 1 |
| DEFERRED | 56 |
| BLOCKED | 3 |

### Partial items and what remains

| Item | What run 1 delivered | What remains |
|---|---|---|
| TWIN-018 No fake data rule | Synthetic flag and UNCLASSIFIED sentinel on every Evidence Object. Search excludes synthetic rows by default | Audit F5: a synthetic-row gate for producers that declare live data |
| TWIN-086 READING filter, TWIN-092 episode-cited readings | `READING` = observations a producer declares `MEASURED` | The committed aggregate predates the declarations. No producer publishes episode citations (Phase 4) |
| TWIN-087 FINDING filter, TWIN-091 search across findings | `FINDING` answers `NO_PRODUCER_EMITS_FINDINGS` | OVNIS findings (Phase 4) |
| FDX-005 Contradiction registry | Contradiction object and inspector rendering | A browsable registry (Phase 4) |
| FDX-008 Cross-repo entity resolver | `/entity/:id` reports identity exactly as recorded | A registry store wired into the server; until then `registry_status: NOT_CONFIGURED` |
| FDX-026 Geometry confidence classes | The axis, the crosswalk and producer declarations | Map rendering (Phase 5) |
| FDX-056 Deep linking | Entity, evidence, search and map-position links | Timeline window, AOI, layers, report and session links |

## Repositories and pull requests

### Repositories changed

| Repo | PR | Merged SHA | What it changed |
|---|---|---|---|
| thehub-pr | #316 | `9d62f46` | Manifests, GUI-parity gate, the epistemic-state, Evidence Object and lineage contracts (candidate), the provenance inspector |
| thehub-pr | #332 | `1094b20` | Federated search, command palette, entity composition (candidate), map deep links |
| thehub-pr | this record | — | Reconciliation |
| ovnis-pr | #167 | `df0e2c4` | `evidence_state` on export rows, plus the Lockstep receipt |
| skywatcher-pr | #336 | `afbf2f8` | `evidence_state` on export rows |
| spiderweb-pr | #398 | `d3fb809` | `evidence_state`; first-vertex points declared `REPRESENTATIVE_POINT` |
| aguayluz-pr | #315 | `30f4d3c` | `evidence_state`; proximity-only `energized_by` edges carry `match_basis: spatial_proximity` |
| moneysweep-pr | — | — | **BLOCKED**, no change (see below) |

PRS_CREATED is 7 and PRS_MERGED is 6; this record is the 7th and merges last. `centinelas-pr` is out of scope: it was neither touched nor made a dependency.

### Starting SHAs (frozen 2026-09-25)

| Repo | SHA |
|---|---|
| thehub-pr | `c7cd2bf` |
| ovnis-pr | `d326040` |
| spiderweb-pr | `33f7b10` |
| skywatcher-pr | `69565cd` |
| aguayluz-pr | `7219141` |
| moneysweep-pr | `c80e9f3` |

### MoneySweep: BLOCKED (T1)

- `moneysweep-pr/data/exports/source_recovery_pause_status_r4_9z.json` on MoneySweep main reports:
  - `r4_9z_pause_lock_active: true`;
  - `unfreeze_candidates: 0`;
  - `sources_still_missing: 21`.
- `moneysweep-pr/docs/BLOCKED_PHASES_AND_UNFREEZE_RULES.md` allows only docs, CI hardening, dependency and secret audits, and test markers while the lock holds.
- An export change is outside those tracks.
- MoneySweep rows therefore declare nothing and render `UNCLASSIFIED`. That is the contract's fail-closed path, not an error.

## Evidence-contract status: CANDIDATE, freeze deferred

The three Wave 1 contracts remain **CANDIDATE** at `1.0.0-candidate.1`:

- `schemas/federation/epistemic_state.v1.schema.json`
- `schemas/federation/evidence_object.v1.schema.json`
- `schemas/federation/evidence_lineage.v1.schema.json`

The operator decided on 2026-10-02 to defer the freeze. Every §42 precondition passed (see the next section). The freeze was deferred because it is not a byte-identical promotion:

- **The status is written into the contracts.** Each schema carries `"x-status": "CANDIDATE"` and a description starting "Candidate…". `evidence_object.v1` requires `audit_metadata.contract_status` to be `"CANDIDATE"`, and `hub.epistemic.CONTRACT_STATUS` mirrors it.
- **The producers pin the candidate hash.** OVNIS, Spiderweb, Skywatcher and AguaYLuz each vendor `federation_epistemic_state.v1.schema.json` byte-identically and pin `HUB_CANDIDATE_SHA256 = c3179480…de088` in its own evidence-state test (for example `ovnis-pr/tests/test_federation_evidence_state.py`).

Freezing therefore needs all of the following in one lockstep change:

1. In thehub, change the three status annotations and the `contract_status` constant to frozen values.
   - Give `entity_composition` its own CANDIDATE constant, since it stays a candidate.
   - Move the schemas into `schemas/contracts/`, pin them in `schemas/FROZEN.sha256`, and set `governance/contract_versions.json` to `1.0.0` with each consumer's disposition.
2. Re-vendor the epistemic-state schema and update the pinned hash in the 4 producers, plus the OVNIS Lockstep receipt.

`FEDERATION_ENTITY_COMPOSITION_V1` and `federation-search-v1` stay CANDIDATE regardless. They are Hub-only read models, and FDX-008's registry wiring will reshape the `identity` block.

## Verification

### §42 preconditions

The producer rows below were checked on 2026-10-02. Each producer's export at its merged SHA was projected, row by row, through `hub.evidence_object.project_evidence_object` and `validate_evidence_object` at thehub `1094b20`.

| Producer export | Rows | Invalid objects | Rejected declarations | Declared classes |
|---|---|---|---|---|
| ovnis `df0e2c4`, production | 2,069 | 0 | 0 | CURATED 2,069 |
| spiderweb `d3fb809`, production (`exports/real`) | 854 | 0 | 0 | CURATED 854 |
| spiderweb `d3fb809`, synthetic samples | 30 | 0 | 0 | 12 declared; 18 synthetic airspace rows of undeclared types stay UNCLASSIFIED (fail-closed) |
| skywatcher `afbf2f8`, test (synthetic only) | 16 | 0 | 0 | MEASURED 4, CURATED 10, COMPUTED 2 |
| aguayluz `30f4d3c` (content of head `749c3bd`) | 154,780 | 0 | 0 | CURATED 150,308, COMPUTED 4,472 |
| moneysweep main `d1ee972`, test | 4,781 | 0 | 0 | UNCLASSIFIED 4,781 (declares nothing) |

The remaining preconditions are positive and negative fixtures, GUI parity and Federation compatibility. All of them were green on the merged heads.

### Tests

| Repo | Result |
|---|---|
| thehub-pr | 1525 passed, 7 skipped; coverage 89.72% (floor 88); 154 vitest; 44 Playwright (16 live-provider specs skipped outside their workflow) |
| ovnis-pr | 175 passed |
| skywatcher-pr | 1615 passed |
| spiderweb-pr | 1796 passed |
| aguayluz-pr | 1294 passed |

Each count is at the content that merged.

### GUI parity and Federation compatibility

- **GUI_PARITY:** thehub `PASS mapped=85 legacy=1169 new=0`. The OVNIS, Skywatcher and AguaYLuz PRs each passed their own parity gate with `new=0`; export-only changes add no signals. Spiderweb has no GUI-parity gate on main.
- **FEDERATION_COMPATIBILITY:** `scripts/federation_governance.py` reports `GOVERNANCE_PASS` with all 7 repositories in passing matrix states. The producers' `federation-compatibility` checks were green on each PR.

### External CI failure

`provider-invariants` (`gis-live-providers.yml`) failed on #332 on both attempts:

- **Cause:** `sige.pr.gov` returned `502 Bad Gateway` from its Azure Application Gateway on 4 SIGE layers, while the other 10 live-provider tests passed.
- **Earlier occurrences:** the same provider earlier answered `499 Token Required` (#318, #320).
- **Handling:** the failure is recorded on the PR thread. The merge followed the operator's 2026-09-29 rule for this external check.

## Contradiction testing and confidence

| Finding | Evidence | Confidence |
|---|---|---|
| A representative point is never promoted to an observed point | Negative tests in thehub, Spiderweb and AguaYLuz. AguaYLuz municipio centroids and approximate alerts, and Spiderweb first vertices, all project as `REPRESENTATIVE_POINT`. OVNIS declares no geometry precision at all, and a negative test enforces that, so its municipality-only cases render `UNKNOWN` | High (T1) |
| A proximity-only edge never renders as documented | All 87 AguaYLuz `energized_by` edges project as `CANDIDATE`. Hub correlations on a weak basis stay `CANDIDATE` on `/entity/:id` | High (T1) |
| Identity is never inferred from a shared name | Three "San Juan" entities (a municipality and two OVNIS cases) stay three entities, with identity `UNRESOLVED` | High (T1) |
| An absent producer is never shown as a query with no hits | Search reports each producer `AVAILABLE` or `NO_DATA`; `FINDING` reports `NO_PRODUCER_EMITS_FINDINGS` | High (T1) |
| Hub users see producer classes today | **Contradicted for the committed aggregate.** It predates the declarations, so rows still render `UNCLASSIFIED` until the ingest refresh | High (T1); a lead, not a defect |

## Blind spots and leads

These are logged only; no vector was switched to pursue them.

1. **Aggregate refresh.** The committed `data/aggregate` predates the producer declarations. The Hub shows the classes, and `READING` search returns rows, only after the next aggregate ingest.
2. **Contract freeze.** This is the lockstep change described above.
3. **Identity registry.** `src/hub/identity_registry.py` has no store wired into the server, so entity pages report `registry_status: NOT_CONFIGURED`. This is FDX-008.
4. **Skywatcher's real export** is blocked upstream, so its rows remain synthetic and are hidden from search by default.
5. **The SIGE live provider** is unstable: `499`, then `502`. Any PR touching `server/frontend/src/gis/**` or `server/backend/main.py` triggers `provider-invariants`.
6. **Spiderweb sample types.** The synthetic airspace record types in its sample package (`airspace_event`, `airspace_observation`, `airspace_track`) have no declaration. They correctly fail closed; a declaration needs Spiderweb to document how those points are derived.
7. **Centinelas rows in search.** The Hub store already holds Centinelas rows, and search indexes them like any other held record. This adds no dependency on Centinelas, and none was created.

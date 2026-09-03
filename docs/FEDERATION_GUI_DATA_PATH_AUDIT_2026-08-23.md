# Federation GUI Data-Path Audit — 2026-08-23

## Scope and certification boundary

This audit covers the five producer repositories requested for the GUI data-path vector:

- `jotaele44/aguayluz-pr`
- `jotaele44/spiderweb-pr`
- `jotaele44/skywatcher-pr`
- `jotaele44/ovnis-pr`
- `jotaele44/moneysweep-pr`

The denominator is the **current `hub_callable_commands` mapping on each producer's `main` branch**, not the older Hub operations catalog snapshot. Counts close as:

`12 Aguayluz + 6 Spiderweb + 6 Skywatcher + 7 OVNIS + 13 MoneySweep = 44 commands`.

This is bounded exhaustion of those 44 declared commands. It is not a claim that every executable anywhere in the five repositories has been universally enumerated.

Classification:

- `PASS`: complete GUI-safe path is already evidenced inside this scope.
- `OPEN`: representable or repaired, but one or more promotion/E2E gates remain.
- `BLOCKED`: a known hard blocker prevents safe GUI execution or production promotion.
- `PROVISIONAL`: a repair exists on a draft PR but exact-head CI/merge evidence is not yet part of `main`.

## Controlling invariants

1. Repository identity is never established by directory name alone. The Hub registry owner/repo + program id must agree with the producer manifest before execution.
2. The browser never supplies a command string. The signed policy supplies executable identity + argv; typed UI values fill only declared parameter slots.
3. Producer write operations audit the verified producer root. An undeclared relative write must quarantine the run.
4. Exit zero is not activation. A candidate artifact must pass declared validators, be frozen with a byte/tree identity, and then be explicitly activated.
5. Failed validation cannot move the ACTIVE pointer; the last registered PASS remains active.
6. Direct sibling-repository reads are not canonical application bindings. Cross-producer exchange must use registered intake/canonical artifacts with provenance.
7. A current producer manifest supersedes an older command snapshot only for **current command text**; the older snapshot remains evidence of historical state.

## Global findings

### Existing Hub controls reused

The existing manager already provides signed operation policy verification, typed parameter validation, shell-free argv construction, supervised subprocess execution, cancellation, redacted log capture, receipts, and transaction/rollback primitives. This vector reuses those controls rather than building a second runner.

### Gaps found on current `main`

- The manager host was single-rooted at `thehub-pr`; producer operations could not receive independently verified repository roots.
- Receipt `outputs` were not backed by a canonical artifact registration/activation store.
- Producer policy rows remain disabled; enabling them before physical output contracts and write auditing close would permit silent semantic drift or quarantine legitimate writes.
- The older Hub operations catalog is temporally stale for some setup commands. For example, current OVNIS and Skywatcher manifests expose simple pip commands while the historical matrix described setup composites. This is a `TIME` contradiction, not an identity contradiction.
- Aguayluz has a formal `.federation/gui-capabilities.json` parity contract. Spiderweb, Skywatcher and OVNIS do not currently expose that same gate on `main`; lack of that file is not evidence that no GUI exists, but it is an OPEN conformance gap.
- MoneySweep's Centinelas lane consumes files from a local `intake/` drop rather than reading a sibling checkout directly. That is compatible with an artifact boundary once the drop is Hub-registered. Spiderweb's current federation manifest, however, documents a PPP geometry lane that conditionally reads a sibling MoneySweep checkout; that remains an OPEN direct-producer coupling until converted to a Hub-registered artifact input.

## Command denominator and disposition

### Aguayluz — 12/44

| Command | Current declaration | Capability | Principal artifact/output | GUI path state | Disposition |
|---|---|---|---|---|---|
| `setup` | `python -m pip install uv && uv pip install --system -e .[dev]` | lifecycle/install | installed environment | historical policy cannot safely represent shell composite | **BLOCKED** pending declarative acquire/install/promote |
| `validation_gates` | `python scripts/validate_repo.py` | validation | gate result | machine-readable wrapper exists on draft PR | **PROVISIONAL** |
| `lint` | `ruff check .` | validation | no canonical artifact | signed target is representable but producer row disabled | **OPEN** |
| `test_suite` | `python -m pytest -q` | validation | test result | representable but producer row disabled | **OPEN** |
| `export_canonical` | `python3 scripts/federation_export.py --mode test` | export | `exports/federation` | write has no integrated artifact activation yet | **BLOCKED** |
| `maintenance` | `aguayluz maintenance --mode audit` | audit/maintenance | `reports/maintenance/latest.json` | write must be snapshot/registered | **BLOCKED** |
| `ingest_power` | `python3 scripts/ingest_power.py` | ingest | utility-asset ledgers | direct producer write; no typed physical output contract in policy | **BLOCKED** |
| `ingest_preps` | `python3 scripts/ingest_preps.py` | ingest | service-event ledgers | producer write/network mode not promoted | **BLOCKED** |
| `fetch_luma_live` | `python3 scripts/fetch_luma_live.py --out /tmp/outages_by_town.json ...` | network fetch | outage snapshot | MiLUMA ToS/WAF gate + `/tmp` default + historical trailing prose | **BLOCKED** |
| `ingest_aee` | `python3 scripts/ingest_aee.py --src <...> --snapshot-ts <...>` | ingest | `data/aee_incidents.jsonl` by default | literal placeholders require typed file + datetime parameters | **BLOCKED** |
| `build_municipios_geo` | `python3 scripts/build_pr_municipios_geo.py --src <...>` | derive/import | `data/geo/pr_municipios.json` by default | placeholder + `/tmp` source default require typed file/output paths | **BLOCKED** |
| `build_geo_boundaries` | `python3 scripts/build_pr_geo_boundaries.py --counties <...> --barrios <...>` | derive/import | municipio/barrio geometry | file-set placeholders require typed inputs + registered output | **BLOCKED** |

Aguayluz-specific hazards:

- `fetch_luma_live.py` defaults output to `/tmp/outages_by_town.json`; `ingest_aee.py` defaults input to that same `/tmp` path. A GUI route must use managed file-token/output slots instead of inheriting those defaults.
- `build_pr_municipios_geo.py` also defaults its source to `/tmp/2023_Gaz_counties_national.txt`.
- MiLUMA is an explicit authorization/access blocker; implementation work does not substitute for source authorization.

### Spiderweb — 6/44

| Command | Current declaration | Capability | Principal artifact/output | GUI path state | Disposition |
|---|---|---|---|---|---|
| `setup` | `python -m pip install uv && uv pip install --system -e ...` | lifecycle/install | installed environment | composite install contract remains undecomposed | **BLOCKED** |
| `test_suite` | `python -m pytest ...` | validation | test result | representable, producer policy disabled | **OPEN** |
| `validate_schemas` | `make validate-schemas` on `main` | validation | schema count/result | non-shell `scripts/validate_schemas.py --json` exists on draft PR #290 | **PROVISIONAL** |
| `validate_export` | `python scripts/validate_export.py --package exports/samples --mode test` | validation | validation result | read-only/test path representable | **OPEN** |
| `export_canonical` | `python3 scripts/federation_export.py --mode test` | export | `exports/federation` | producer write has no integrated artifact activation | **BLOCKED** |
| `maintenance` | `python3 scripts/run_maintenance.py --repo spiderweb-pr --mode audit` | audit/maintenance | `reports/maintenance/latest.json` | producer write must be snapshotted/registered | **BLOCKED** |

Spiderweb-specific boundary issue:

- The producer manifest documents `readiness/ppp_geometry.py` consuming a MoneySweep sibling checkout when present. That is discovery by filesystem adjacency, not a Hub-registered artifact binding. It must be replaced with a canonical input artifact or intake token before this vector can certify zero direct producer coupling.

### Skywatcher — 6/44

| Command | Current declaration | Capability | Principal artifact/output | GUI path state | Disposition |
|---|---|---|---|---|---|
| `setup` | `python -m pip install -r requirements-dev.txt httpx -r server/backend/requirements.txt` | lifecycle/install | installed environment | current command is simple, but safe versioned install/promote rollback is not certified | **OPEN** |
| `validate_export` | `python scripts/validate_airspace_export.py exports/examples/synthetic_airspace_package --mode test` | validation | test validation result | synthetic test path only | **OPEN** |
| `test_suite` | `python -m pytest -q` | validation | test result | representable, producer row disabled | **OPEN** |
| `export_canonical` | `python3 scripts/federation_export.py --mode test` | export | `exports/federation` | only synthetic/test export is ready; producer manifest says no live observation export | **BLOCKED** |
| `ingest_airports` | `python3 scripts/ingest_airports.py` | ingest | airport reference data | producer write lacks physical output/activation contract | **BLOCKED** |
| `maintenance` | `python3 scripts/run_maintenance.py --repo skywatcher-pr --mode audit` | audit/maintenance | `reports/maintenance/latest.json` | producer write must be snapshotted/registered | **BLOCKED** |

Skywatcher-specific production blockers remain independent of GUI wiring: no live observation export exists, FR24 inputs are local external inputs, and production external-imagery/model execution is still assigned to TheHub under the repository boundary ADR.

### OVNIS / PRUFON — 7/44

| Command | Current declaration | Capability | Principal artifact/output | GUI path state | Disposition |
|---|---|---|---|---|---|
| `setup` | `python -m pip install -r requirements.txt` | lifecycle/install | installed environment | current command is representable; safe lifecycle promote/rollback still open | **OPEN** |
| `validate_ledgers` | `python3 scripts/validate_case_ledgers.py` | validation | validation result | read-only path representable | **OPEN** |
| `dedupe` | `python3 scripts/dedupe_candidates.py` | review derivation | default `reports/dedupe_candidates.csv` | writes a new report; no in-place ledger mutation, but output path is not yet a typed managed artifact | **BLOCKED** |
| `score` | `python3 scripts/score_candidates.py` | review derivation | default `reports/candidate_scoring.csv` | writes a new report; no master promotion, but output path is not yet registered | **BLOCKED** |
| `test_suite` | `python -m pytest -q` | validation | test result | representable | **OPEN** |
| `export_canonical` | `python3 scripts/federation_export.py --mode production` | export | `exports/federation` | production data is available, but artifact activation is not integrated | **BLOCKED** |
| `maintenance` | `python3 scripts/run_maintenance.py --repo ovnis-pr --mode audit` | audit/maintenance | `reports/maintenance/latest.json` | producer write must be snapshotted/registered | **BLOCKED** |

OVNIS-specific adjudication:

- Historical failure-ledger language implying dedupe/score mutate ledgers is superseded. Current scripts read candidate/master JSONL and write new CSV reports via `--output`; they do not promote or overwrite the ledgers.

### MoneySweep — 13/44

| Command | Current declaration | Capability | Principal artifact/output | GUI path state | Disposition |
|---|---|---|---|---|---|
| `setup` | `python3 run_all.py --only-setup` | lifecycle/install | installed/setup state | lifecycle promote/rollback not certified | **OPEN** |
| `strict_preflight` | `python3 run_all.py --only-setup --strict-preflight` | validation/preflight | preflight result | may traverse setup state; producer row disabled | **OPEN** |
| `full_pipeline` | `python3 run_all.py --strict-preflight` | ingest/derive | many canonical/report outputs | producer is `NON_PRODUCTION_DIAGNOSTIC`; multi-output activation contract absent | **BLOCKED** |
| `materialization_matrix` | `python3 scripts/build_source_recovery_matrix.py` | audit/derive | three `reports/` files | typed `--root/--out/--check/--json` wrapper exists on draft PR #495 | **PROVISIONAL** |
| `gap_matrix` | `python3 scripts/gap_analysis_builder.py` | audit/derive | gap-analysis reports | write outputs unregistered | **BLOCKED** |
| `test_suite` | `python3 -m pytest tests/ -q` | validation | test result | representable | **OPEN** |
| `dashboard_export` | `python3 scripts/build_dashboard_explorer.py` | export | dashboard export | output activation contract absent | **BLOCKED** |
| `foia_letters` | `python3 scripts/build_foia_letters.py` | derive/export | generated letters | generated outputs unregistered | **BLOCKED** |
| `ngo_layer` | `python3 scripts/ngo_integration.py` | ingest/derive | NGO integration outputs | outputs unregistered | **BLOCKED** |
| `export_canonical` | `python3 scripts/federation_export.py --mode test` | export | `data/exports/canonical_v1_federation` | producer live-execution readiness is false; activation absent | **BLOCKED** |
| `maintenance` | `python3 scripts/run_maintenance.py --repo moneysweep-pr --mode audit` | audit/maintenance | `reports/maintenance/latest.json` | write must be snapshotted/registered | **BLOCKED** |
| `ingest_centinelas` | `python3 scripts/ingest_centinelas_signals.py` | intake/ingest | `exports/centinelas_intake/{funding_awards,transactions}.jsonl` by default | consumes local intake drops, not sibling checkout; input/output must become registered Hub artifacts | **BLOCKED** |
| `build_contract_finance_bundle` | `python3 scripts/build_contract_finance_bundle.py --export-dir exports/centinelas_intake` | derive/export | contract-finance bundle | derived output chain not yet registered/activated | **BLOCKED** |

MoneySweep-specific blockers remain independent of GUI wiring: manual Tranche-B sources, JavaScript-gated COR3 fallback, remaining scraper/deferred sources, and key-dependent adapters keep live execution false on the current producer manifest.

## Hardcoded filesystem-path findings

| Finding | State |
|---|---|
| Aguayluz MiLUMA fetch defaults to `/tmp/outages_by_town.json` | **BLOCKED** for GUI use until replaced by managed output path |
| Aguayluz AEE ingest defaults source to `/tmp/outages_by_town.json` | **BLOCKED** until file token/managed input |
| Aguayluz municipio builder defaults source to `/tmp/2023_Gaz_counties_national.txt` | **BLOCKED** until file token |
| MoneySweep source-recovery builder hardcodes `reports/` globals | **PROVISIONAL** repair on PR #495 |
| OVNIS dedupe/score use repo-relative default report paths | acceptable CLI defaults, but **BLOCKED** for manager writes until typed managed output slots |
| Producer roots in the old manager were implicitly TheHub's root | repaired on Hub draft branch with registry+manifest binding; exact-head CI pending |

## Direct producer/API coupling findings

| Finding | Classification |
|---|---|
| Browser/UI directly invoking external provider APIs | **not found in the audited signed operations path** |
| Aguayluz MiLUMA producer fetch directly invokes provider API | **BLOCKED** by explicit ToS/WAF/authorization gate; producer-owned network action, never direct browser call |
| MoneySweep Centinelas ingestion | local intake/drop boundary exists; **OPEN** until Hub artifact registration proves provenance |
| Spiderweb PPP geometry lane reads sibling MoneySweep checkout when present | **OPEN boundary violation**; replace with Hub-registered artifact input |
| Skywatcher direct production imagery/model execution | current producer manifest says deprecated/pending migration to TheHub; do not promote local direct-provider route |

## Unregistered-output and fetch-to-overwrite hazards

The current manager receipt path records no canonical artifact manifestations for producer operations. Therefore every producer operation that writes a file, ledger, export directory, or report remains non-promotable in this vector until its physical outputs are declared and registered.

The new Hub draft branch adds an immutable `ArtifactStore` primitive with:

- file SHA-256 identity;
- directory identity over member `PATH + UNCOMPRESSED_SIZE + SHA256` tuples;
- containment under an allowed root;
- a non-empty all-passed validator requirement;
- immutable run-addressed object storage;
- atomic per-app ACTIVE pointer;
- explicit rollback to a previously registered object;
- refusal to move ACTIVE when candidate validation fails.

This primitive is not yet treated as certified runner integration. Producer policy rows remain disabled until registration is called from the execution path and receipt outputs carry the registered manifestations.

## GUI route findings

The existing Operations page already consumes the signed policy and exposes typed forms, dry run, run, cancellation, redacted logs, receipts, prerequisites and visible disabled reasons. This is the correct single execution UI and should be reused.

Remaining GUI gaps:

1. producer operations are still disabled in the signed policy;
2. the page does not yet expose a repository/data-health summary backed by verified repository bindings + ACTIVE artifact state;
3. file-token controls still require the native picker path; the browser page itself reports that requirement rather than silently accepting filesystem text;
4. the host still prints a browser-console bootstrap snippet for the manager session, so zero-terminal/native packaging is not yet certified;
5. Fetch/Export/Audit/Repair shortcuts should select the same signed operations rather than introduce a second command API.

## Changes made in this vector

### TheHub draft branch `feature/gui-data-path-control-plane-20260823`

- added fail-closed `WorkspaceRepositoryRegistry`:
  - authoritative registry owner/repo + program id binding;
  - independent manifest agreement;
  - workspace containment;
  - duplicate identity rejection;
  - no nearest/name-only fallback.
- added repository-aware `RepositoryOperationRouter`:
  - one verified execution context per repo;
  - shared signed policy and receipt chain;
  - Hub retains its existing managed data root;
  - producers audit their complete verified repo root;
  - missing producer binding fails closed.
- updated `scripts/run_manager_host.py` to assemble those repository contexts while preserving Hub-only operation behavior.
- added immutable validated `ArtifactStore` primitive with atomic activation/rollback semantics.
- added positive/negative regression tests for identity contradictions, workspace escape, validation failure, ACTIVE preservation, unregistered activation, and directory member identity.

### Producer draft repairs

- Spiderweb PR #290: adds `scripts/validate_schemas.py --json`; removes `make`/inline-`python -c` dependency from the branch manifest.
- Aguayluz PR #188: adds `scripts/validate_repo.py --json` while preserving human-readable mode.
- MoneySweep PR #495: adds typed source-recovery runner with `--root`, `--out`, `--check`, `--json` and isolated byte-comparison check mode.

## Arithmetic and current certification state

- declared command denominator: **44**
- commands accounted: **44**
- unexplained command residue: **0**
- producer operations enabled by this vector: **0**
- reason for zero enablement: central artifact registration is not yet integrated into the runner and producer write/output contracts are not yet signed/validated end to end.

Per-repo state:

| Repository | State | Primary remaining blockers |
|---|---|---|
| Aguayluz | **BLOCKED** | typed placeholder inputs; MiLUMA authorization; write→artifact activation integration |
| Spiderweb | **OPEN / PROVISIONAL** | PR #290 CI/merge; direct sibling MoneySweep lane; write→artifact activation |
| Skywatcher | **BLOCKED** | no non-synthetic production observation export; local-input/native path; activation |
| OVNIS/PRUFON | **OPEN** | policy enablement + typed report outputs + activation; production canonical corpus itself is available |
| MoneySweep | **BLOCKED** | producer live-readiness blockers; PR #495 CI/merge; multi-output activation |
| TheHub control plane | **PROVISIONAL** | new repository/artifact primitives require exact-head CI and runner artifact-registration integration; native zero-terminal session/picker gates remain open |

## Promotion gate

No producer write operation may move from `DECLARED_NOT_ENABLED` to `ENABLED` until all of the following close on exact heads:

1. verified repository binding;
2. typed argv/parameter contract with no placeholder strings;
3. physical output paths declared;
4. pre-run snapshot or isolated staged write appropriate to the operation;
5. write-scope audit covers the producer root;
6. operation-specific validators PASS;
7. artifact manifestation registered with hashes/member inventory;
8. activation occurs only after validation;
9. forced failure proves the previous ACTIVE artifact remains intact;
10. signed receipt records the resulting artifact identity;
11. GUI can plan/run/cancel/review the operation without a Terminal;
12. positive and negative E2E tests PASS with zero unexplained residue.

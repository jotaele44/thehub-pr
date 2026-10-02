# Federation Completion Implementation Plan

- Generated UTC: `2026-09-07T07:38:00Z`
- Run ID: `20260907T072343Z`
- Scope: `7 federation repos + open PR remote gate`
- Certification: `AUDIT_ONLY`
- Remote PR denominator: `70`
- Remote certification: `FAIL_ACTIONABLE_RESIDUE`
- Startup/setup certification: `PROVISIONAL`
- Product completion certification: `PROVISIONAL`
- Code completion language: `CODE_COMPLETE_CANDIDATE is not source-certified or product-certified.`

## Gates

- Remote PR arithmetic: `{'BLOCKED': 18, 'REBASE_REQUIRED': 47, 'STACKED': 5}`
- Remote actionable residue: `{'REBASE_REQUIRED': 47, 'STACKED': 5}`
- Code-completion arithmetic: `{'CODE_COMPLETE_CANDIDATE': 6, 'CODE_COMPLETE_CANDIDATE_SOURCE_BLOCKED': 1}`
- Startup/setup arithmetic: `{'BLOCKED': 6, 'FAIL': 1}`
- Product arithmetic: `{'BLOCKED_FOR_PRODUCT_COMPLETION': 7}`

## VECTOR_A Current Implementation Order

- `centinelas-pr`: fix code gates `CODE_COMPLETE_CANDIDATE_SOURCE_BLOCKED` before source/product certification; blockers `['export_canonical:SOURCE_BLOCKED']`.
- `aguayluz-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED']`.
- `moneysweep-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED', 'manual-source Tranche B remains partial/unresolved for hud_drgr_authorized; prasa, pr_cabilderos, and oficina_contralor were source-drop staged or parsed and materialized in reports/live-readiness/20260901T022813Z_moneysweep_prasa_contract_closure/', 'cor3 live endpoints return no data (portal likely requires JavaScript rendering); manual CSV export fallback documented', 'PR-gov scraper-needed queue: 13 of 15 sources promoted to api_producer; 2 true stubs remain (hacienda_sut_ivu, pr_act_154_excise)', 'PROPUBLICA_API_KEY not supplied (nonprofits adapter)', 'source-count wording must stay reconciled to reports/materialization_readiness.json truth', 'MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE']`.
- `ovnis-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED']`.
- `skywatcher-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED', 'scaled bounded non-synthetic bbox/icon proof package exists (3 reviewed visible-icon screenshots with approximate capture geometry), but full live observation export remains blocked pending media identity reconciliation and completed capture-geometry review', 'canonical export adapter (scripts/federation_export.py) projects observations->entities/sources/relationships; production live readiness remains blocked until the reviewed non-synthetic corpus is materially complete and unresolved media identities are adjudicated', 'external imagery acquisition and production model execution are pending migration to TheHub under ADR 0006; the existing local imagery MCP and direct-provider vision path are deprecated but retained until parity, dual-run, rollback, GUI and retirement gates pass', 'FR24 ingest pipeline is now in-tree (fr24/); ILAP intake still requires FlightRadar24 screenshot/track inputs supplied locally (external data gap)', 'MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE']`.
- `spiderweb-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED']`.
- `thehub-pr`: code gates are `CODE_COMPLETE_CANDIDATE`; run setup/source/product gates before any certification claim; blockers `['startup_setup_state:BLOCKED']`.

## VECTOR_B Deterministic Rerun

- Reuse `scripts/federation_completion_runner.py` as the single receipt entrypoint.
- Keep `--fail-on-actionable` enabled so remote PR residue cannot silently pass.
- Keep explicit timeout values; timeout exhaustion is `BLOCKED`, not `FAIL` or `PASS`.

## VECTOR_C Reporting Boundary

- `CODE_COMPLETE_CANDIDATE` means deterministic code gates passed in this audit.
- `STARTUP_SETUP_COMPLETE` additionally requires setup gates to be executed or explicitly satisfied.
- `PRODUCT_COMPLETE` additionally requires live/source blockers to be closed.
- `CERTIFIED` is not emitted by this runner.

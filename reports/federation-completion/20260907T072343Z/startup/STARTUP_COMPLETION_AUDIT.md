# Federation Startup Completion Audit

- Generated UTC: `2026-09-07T07:37:59Z`
- Run ID: `20260907T072753Z`
- Startup/setup certification: `PROVISIONAL`
- Product completion certification: `PROVISIONAL`
- Startup/setup arithmetic: `7=7`
- Code-complete arithmetic: `7=7`
- Code-complete language: `CODE_COMPLETE_CANDIDATE is not source-certified or product-certified.`
- Lumen: `LUMEN_UNAVAILABLE_OR_UNHEALTHY`
- Deferred Skill selector: `UNAVAILABLE`

## Repository Results

| Repo | SHA | Code complete | Startup/setup | Product completion | Live Ready | Setup | Tests | Export | Startup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aguayluz-pr | `64deea06e66e` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `True` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |
| centinelas-pr | `caf086598a4f` | `CODE_COMPLETE_CANDIDATE_SOURCE_BLOCKED` | `FAIL` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `True` | `SKIP_WITH_REASON` | `PASS` | `FAIL` | `PASS` |
| moneysweep-pr | `f17bc8a203a2` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `False` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |
| ovnis-pr | `68b87366207c` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `True` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |
| skywatcher-pr | `39e1fb297e24` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `False` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |
| spiderweb-pr | `d4bfb233a032` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `True` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |
| thehub-pr | `d509b78a59c7` | `CODE_COMPLETE_CANDIDATE` | `BLOCKED` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `None` | `SKIP_WITH_REASON` | `PASS` | `PASS` | `PASS` |

## Code Completion Blockers

- `centinelas-pr`: `CODE_COMPLETE_CANDIDATE_SOURCE_BLOCKED` - export_canonical:SOURCE_BLOCKED

## Startup/Setup Blockers

- `aguayluz-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute
- `centinelas-pr`: `FAIL` - export_canonical:FAIL
- `moneysweep-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute
- `ovnis-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute
- `skywatcher-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute
- `spiderweb-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute
- `thehub-pr`: `BLOCKED` - setup:setup skipped by audit policy; use --run-setup to execute

## Product Completion Blockers

- `aguayluz-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED
- `centinelas-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:FAIL
- `moneysweep-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED, manual-source Tranche B remains partial/unresolved for hud_drgr_authorized; prasa, pr_cabilderos, and oficina_contralor were source-drop staged or parsed and materialized in reports/live-readiness/20260901T022813Z_moneysweep_prasa_contract_closure/, cor3 live endpoints return no data (portal likely requires JavaScript rendering); manual CSV export fallback documented, PR-gov scraper-needed queue: 13 of 15 sources promoted to api_producer; 2 true stubs remain (hacienda_sut_ivu, pr_act_154_excise), PROPUBLICA_API_KEY not supplied (nonprofits adapter), source-count wording must stay reconciled to reports/materialization_readiness.json truth, MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE
- `ovnis-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED
- `skywatcher-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED, scaled bounded non-synthetic bbox/icon proof package exists (3 reviewed visible-icon screenshots with approximate capture geometry), but full live observation export remains blocked pending media identity reconciliation and completed capture-geometry review, canonical export adapter (scripts/federation_export.py) projects observations->entities/sources/relationships; production live readiness remains blocked until the reviewed non-synthetic corpus is materially complete and unresolved media identities are adjudicated, external imagery acquisition and production model execution are pending migration to TheHub under ADR 0006; the existing local imagery MCP and direct-provider vision path are deprecated but retained until parity, dual-run, rollback, GUI and retirement gates pass, FR24 ingest pipeline is now in-tree (fr24/); ILAP intake still requires FlightRadar24 screenshot/track inputs supplied locally (external data gap), MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE
- `spiderweb-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED
- `thehub-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - startup_setup_state:BLOCKED

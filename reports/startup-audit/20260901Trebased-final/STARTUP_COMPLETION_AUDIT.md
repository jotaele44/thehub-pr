# Federation Startup Completion Audit

- Generated UTC: `2026-09-01T00:28:05Z`
- Run ID: `20260901T002010Z`
- Startup/setup certification: `PASS`
- Product completion certification: `PROVISIONAL`
- Startup/setup arithmetic: `7=7`
- Lumen: `LUMEN_UNAVAILABLE_OR_UNHEALTHY`
- Deferred Skill selector: `UNAVAILABLE`

## Repository Results

| Repo | SHA | Startup/setup | Product completion | Live Ready | Setup | Tests | Export | Startup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aguayluz-pr | `e504624bf0db` | `STARTUP_SETUP_COMPLETE` | `PRODUCT_COMPLETE` | `True` | `PASS` | `PASS` | `PASS` | `PASS` |
| centinelas-pr | `3d96af211bbf` | `STARTUP_SETUP_COMPLETE` | `PRODUCT_COMPLETE` | `True` | `PASS` | `PASS` | `PASS` | `PASS` |
| moneysweep-pr | `3176beeb0d9a` | `STARTUP_SETUP_COMPLETE` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `False` | `PASS` | `PASS` | `PASS` | `PASS` |
| ovnis-pr | `b02ac5094852` | `STARTUP_SETUP_COMPLETE` | `PRODUCT_COMPLETE` | `True` | `PASS` | `PASS` | `PASS` | `PASS` |
| skywatcher-pr | `801c2dde49ae` | `STARTUP_SETUP_COMPLETE` | `BLOCKED_FOR_PRODUCT_COMPLETION` | `False` | `PASS` | `PASS` | `PASS` | `PASS` |
| spiderweb-pr | `250bbb841e48` | `STARTUP_SETUP_COMPLETE` | `PRODUCT_COMPLETE` | `True` | `PASS` | `PASS` | `PASS` | `PASS` |
| thehub-pr | `4af750e43995` | `STARTUP_SETUP_COMPLETE` | `PRODUCT_COMPLETE` | `None` | `PASS` | `PASS` | `PASS` | `PASS` |

## Startup/Setup Blockers


## Product Completion Blockers

- `moneysweep-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - manual-source Tranche B not materialized (hud_drgr_authorized, prasa, oficina_contralor, pr_cabilderos await operator file drops), cor3 live endpoints return no data (portal likely requires JavaScript rendering); manual CSV export fallback documented, PR-gov scraper-needed queue: 13 of 15 sources promoted to api_producer; 2 true stubs remain (hacienda_sut_ivu, pr_act_154_excise), PROPUBLICA_API_KEY not supplied (nonprofits adapter), source-count wording must stay reconciled to reports/materialization_readiness.json truth, MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE
- `skywatcher-pr`: `BLOCKED_FOR_PRODUCT_COMPLETION` - scaled bounded non-synthetic bbox/icon proof package exists (3 reviewed visible-icon screenshots with approximate capture geometry), but full live observation export remains blocked pending media identity reconciliation and completed capture-geometry review, canonical export adapter (scripts/federation_export.py) projects observations->entities/sources/relationships; production live readiness remains blocked until the reviewed non-synthetic corpus is materially complete and unresolved media identities are adjudicated, external imagery acquisition and production model execution are pending migration to TheHub under ADR 0006; the existing local imagery MCP and direct-provider vision path are deprecated but retained until parity, dual-run, rollback, GUI and retirement gates pass, FR24 ingest pipeline is now in-tree (fr24/); ILAP intake still requires FlightRadar24 screenshot/track inputs supplied locally (external data gap), MANIFEST_READY_FOR_HUB_LIVE_EXECUTION_FALSE

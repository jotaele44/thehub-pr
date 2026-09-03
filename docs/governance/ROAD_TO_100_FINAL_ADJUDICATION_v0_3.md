# Final ROAD_TO_100 Adjudication Ledger v0.3

**Adjudication date:** 2026-07-27
**Scope:** PRs `moneysweep-pr#413`, `spiderweb-pr#212`, `aguayluz-pr#63`, `ovnis-pr#47`, `skywatcher-pr#107`, `centinelas-pr#49`, `thehub-pr#98`, and corrective `skywatcher-pr#100`.
**Preservation rule:** all PRs remain draft; no merge, production-status change, or live-gate change is authorized.

## PR-by-PR decision

| Pull request | Decision | Basis | Remaining condition |
|---|---|---|---|
| `moneysweep-pr#413` | **ACCEPT** | Metrics align closely; full configured PR checks passed; one documentation file only. | Keep draft pending owner review. |
| `spiderweb-pr#212` | **ACCEPT** | The 85% figure is correctly limited to core-pipeline scope; configured checks passed. | Keep draft pending owner review. |
| `aguayluz-pr#63` | **ACCEPT** | Branch replayed onto current `main` at `c1a2303ffb6ff7d156aa0d6452977b72407e3b8c`; one documentation commit ahead; refreshed checks passed. | Keep stale-outage provenance qualification intact. |
| `ovnis-pr#47` | **ACCEPT** | Static-corpus versus recurrent-acquisition distinction is accurate; configured checks passed. | Keep draft pending owner review. |
| `skywatcher-pr#107` | **ACCEPT AS PROVISIONAL NORMALIZATION** | Correctly records 70% provisional scope, 61% maturity, 10% operational readiness, D0, and live gate false; configured checks passed. | Must remain provisional until PR #100 private certification succeeds. |
| `centinelas-pr#49` | **ACCEPT** | Correctly separates the approximately 90% generic engine from 75% intended-product scope; configured checks passed. | Keep draft pending owner review. |
| `thehub-pr#98` | **ACCEPT AFTER v0.3 REVISIONS** | Agua y Luz anchor refreshed; governance navigation added; 12/12 accounting and all metric rows agree. | Final Hub CI must pass on the adjudication head. |
| `skywatcher-pr#100` | **NOT CERTIFIED / RETAIN DRAFT** | Public CI, SATIM smoke, and template drift passed, but the private fixture is unavailable in the current runtime and no PR artifact contains the required certification. | Supply `IMG_0218 (Merged).pdf` and execute all seven private gates against head `7b269e85e10c8c273dfaecff5956e14221979b36`. |

## SkyWatcher private certification result

| Gate | Result |
|---|---|
| Expected fixture identity | **IDENTIFIED, NOT ACCESSIBLE** — `IMG_0218 (Merged).pdf`, 22,210,568 bytes, 39 pages, SHA-256 `8e5307c999d53e3ea0185caaa33cbbe2a8e994e271b34ac31712846b15d5aecf` |
| Fresh execution against PR #100 head | **NOT RUN — SOURCE BYTES UNAVAILABLE** |
| Two clean independent runs | **NOT VERIFIED** |
| Equal normalized digests | **NOT VERIFIED** |
| 39/39 page, source, and frame-hash accounting | **NOT VERIFIED** |
| All emitted JSON schema-valid | **NOT VERIFIED** |
| Finding/contradiction and unresolved/review ledgers 1:1 | **NOT VERIFIED** |
| Track remains `not_registered` without calibration | **NOT VERIFIED** |

An earlier project-context certification exists for the same source identity, but it was not executed against PR #100 head and cannot be promoted as current-head evidence.

## Score and evidence adjudication

The reconciled matrix is accepted with these values:

- MoneySweep: 75 / 73 / 64 / D2.
- Spiderweb: 85 core-pipeline only / 56 / 30 / D1.
- Agua y Luz: 90 / 70 / 78 / D3.
- OVNIS: 82 / 68 / 65 / D2.
- SkyWatcher: 70 provisional / 61 / 10 / D0.
- Centinelas: 75 intended product / 69 / 60 / D2.
- TheHub: 90 local Hub only / 64 / 15 / D0.

Values are ordered as implemented scope / CI maturity / operational data readiness / evidence depth.

## Documentation validation

- All normalized documents use the required metric schema.
- All relative `ROAD_TO_100.md` links resolve to existing repository documents.
- Hub governance tables are structurally valid Markdown.
- The policy navigation links resolve to the normalized status, matrix, 12-repository ledger, contradiction register, and remediation queue.
- Repository accounting remains 12/12, with no percentage invented for the five repositories lacking a declared governed product boundary.

## Final preservation state

- No PR merged.
- No PR marked ready for review.
- No manifest changed.
- No production status changed.
- No live gate changed.
- No repository archived, renamed, or otherwise lifecycle-mutated.

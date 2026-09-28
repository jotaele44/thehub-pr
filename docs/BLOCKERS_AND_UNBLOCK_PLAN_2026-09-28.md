# Blockers and unblock plan — thehub-pr and federation-wide (2026-09-28)

**Audit date:** 2026-09-28 · **`main` at audit:** `c3e1ffb` (not branch-protected) · **Role:** federation control plane

This document lists every blocker the repositories, their CI, and their GitHub issues and pull requests recorded as of the audit date, then gives an ordered plan to clear them. It changes no code, gate, ledger, pin, or status file. It has two parts:

- **Part A** covers blockers that span the federation (`X-nn`). Producer documents point here for them.
- **Part B** covers blockers owned by thehub-pr (`HB-nn`).

## Index of per-repository plans (same filename in each repository)

| Repository | Document | Blockers |
|---|---|---:|
| thehub-pr | this file (Part B) | 9 |
| moneysweep-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 15 |
| aguayluz-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 12 |
| skywatcher-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 13 |
| spiderweb-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 12 |
| centinelas-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 9 |
| ovnis-pr | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 8 |
| mucaro-ai (outside the federation) | `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md` | 13 |

Federation-wide blockers X-01 to X-09 are counted once, here, and not in the producer totals.

## How this inventory was built

Sources checked:

- all open issues and all 83 open pull requests across the 8 repositories;
- CI on each `main`, for push and scheduled runs;
- the completion-gate ledger artifact `10934078554` (run `36326861596`, 2026-09-27 14:42Z), which classifies all 73 open PRs in the 7 PRII repositories;
- `docs/unfinished_implementation_ledger.v1.json` in the 7 PRII repositories, reconciled against PR history;
- `docs/ROAD_TO_100*`, `docs/ROAD_TO_100_CRITICAL_PATH_FREEZE.v1.json`, `docs/FEDERATION_ROAD_TO_100_SCORECARD.v1.json`, `docs/FEDERATION_MAX_AUDIT_2026-09-24.md` (every open finding re-verified in code), `docs/FEDERATION_UI_OPERATIONS_FAILURE_LEDGER.csv`;
- `governance/producer_receipt_refs.json`, the federation templates, and branch protection and branch lists for all 8 repositories.

## Part A — federation-wide blockers

| ID | Blocker | Type | Evidence | Owner | Unblock step | Exit criterion |
|---|---|---|---|---|---|---|
| X-01 | The federation completion gate is red every day | GATE | `federation-completion-gate.yml` (scheduled) has failed daily since 2026-09-21 (last pass 2026-09-20). Run `36326861596`: `open_pr_denominator: 73`; `REBASE_REQUIRED: 66`, `BLOCKED: 6`, `STACKED: 1` → `FAIL_ACTIONABLE_RESIDUE` (exit 3). Two structural causes: (1) `scripts/federation_completion_gate.py` `classify()` requires check-runs on `merge_commit_sha`, but GitHub attaches pull-request check-runs to the head SHA, so all 73 rows report 0 merge checks and `MERGE_READY` is unreachable; (2) aguayluz (scheduled refresh) and centinelas (monitors) commit data to `main` several times a day, so their PRs can never stay on the current base. | Gate owner (this repo) + all maintainers | (a) Drain the backlog (X-02, X-05, per-repo PR tables). (b) Fix the classifier. Options: accept green head checks when the PR is up to date with base; require a rebase only when `CURRENT_MAIN_PATH_OVERLAP` is non-empty or checks are stale; ignore `[skip ci]` data-only commits when measuring base drift. (c) Move bot data commits off `main` (data branch or batched commits). | The scheduled gate reports a pass |
| X-02 | Dependabot backlog that cannot merge as generated | PR/GOV | 54 dependabot PRs are open in the 7 PRII repositories. Every `actions-minor-patch`/`setup-uv` bump fails "Federation template drift", because producer workflows and `dependabot.yml` are rendered from `federation-templates/` and hand edits fail the drift gate. Every pip requirement-floor bump fails `lock`/`lock-sync` because the lockfile is not regenerated. Majors needing migration: eslint 10 (6 repos), vitest 5 (4), maplibre-gl 6, recharts 3, react-router-dom 7, date-fns 4, lucide-react 1.x, jsdom 30, react-resizable-panels 4, @types/node 26, eslint-plugin-react-hooks 7, numpy ≥ 2.2.6, opencv 5, fastmcp 4, mcp 2.2, filelock 4, prawcore 4, pyarrow ≥ 25, anthropic ≥ 1.7. Majors closed unmerged in centinelas and ovnis on 2026-09-19 were re-opened by dependabot. | Maintainers (templates live here) | Merge the green minor/patch groups. Land action bumps in `federation-templates/`, re-render with `tools/render_federation_templates.py`, bump `PRII_TEMPLATE_REF`, then close the producer action PRs. Regenerate locks for floor bumps. For each major, migrate in its own PR or add an `ignore` in `federation-templates/baseline/dependabot.yml` and re-render. | Dependabot PRs ≤ one weekly batch, none red |
| X-03 | `main` is unprotected in most repositories | GOV | Branch protection: moneysweep and spiderweb protected; thehub, aguayluz, centinelas, skywatcher and ovnis unprotected (all public); mucaro-ai unprotected (private, plan-gated). Issue #256 requires protection and required checks before any certification promotion. | Repository owner | Enable protection or a ruleset on the 5 public repositories: PRs only, no force-push or deletion, required checks per #256 | #256 closure evidence |
| X-04 | Stale receipt pins | GATE | `governance/producer_receipt_refs.json` was last edited 2026-09-22. (a) MAX audit §9: centinelas and spiderweb must be re-pinned after centinelas #160 and spiderweb #392 (both merged 2026-09-24); not done. (b) The JP-flood capability receipt is pinned to run `35688020606` (source main `fcc3405`); the latest PASS is spiderweb run `36328607066` at `bb8463c`. The `JP flood receipt freshness` job failed on 2026-09-27 (`PIN_UPDATE_REQUIRED`, run `36336473180`) and will fail again at its next weekly run. | Agent/maintainer | Update the pins, plus `tests/test_federation_capability_receipts.py`, which references run `35688020606`; rerun the reconciliation | Freshness `CURRENT_EQUIVALENT`; receipts reconcile |
| X-05 | Cell_Set uncertainty-contract propagation is unmerged | PR | Green-head PRs: moneysweep #623, aguayluz #299, skywatcher #328, centinelas #161, ovnis #160, thehub #314. Each will drift to `REBASE_REQUIRED`. | Maintainers | Coordinated review; update each branch; merge thehub #314 first, then the producers | All 6 merged |
| X-06 | Trackers from the Actions runner outage are still open | STALE | Runners were unavailable from about 2026-09-06 to 2026-09-19 (aguayluz `.github/actions-restoration-notice.md`, status RESTORED). Still open: aguayluz #234 and #256, thehub #255 and the Actions half of #283, the spiderweb LOCATION_QUERY audit note, and mucaro CODE-B04. CI now executes steps and `main` is green in every repository. | Agent | Close or reclassify each with current green run IDs. Keep the #283 code residue open (HB-02). | Trackers closed |
| X-07 | Normalized ledgers and scorecards are stale | STALE/GOV | `unfinished_implementation_ledger.v1.json` in the 7 PRII repositories is dated 2026-08-04 (centinelas 2026-08-19). `docs/ROAD_TO_100_CRITICAL_PATH_FREEZE.v1.json` pins those ledgers' blob SHAs; `docs/FEDERATION_ROAD_TO_100_SCORECARD.v1.json` = 72.00. Many cited PRs have since merged or closed; each per-repo document has a reconciliation table. | Maintainers | Re-audit into a new ledger version. The freeze pins blob SHAs, so do not edit v1 in place. | New ledgers and scorecard match `main` |
| X-08 | No certified live federation cycle | GATE | `docs/ROAD_TO_100_NORMALIZED.md`: evidence depth D0. All 7 end-to-end conditions are open: producers live-valid; `validate-package` at current commits; a full fetch → aggregate → correlate → ingest → graph-report run; representative real data; repeatable in CI; stubs bound or excluded; frontend typecheck and server lint/type enforced. | Federation operator | Follows the producer critical path; run the all-main certification (HUB-004) last | One current-main receipt covering all 7 repositories and a full cycle |
| X-09 | Branch sprawl | HYG | thehub 107 branches (about 45 `fixture-refresh-*`), skywatcher 52, mucaro 44, moneysweep 39 (#269), spiderweb 38, aguayluz 34, centinelas 20, ovnis 19 | Maintainers | Prune merged, automation and duplicate branches; keep `archive/*` and `freeze/*` | Branch lists reflect live work |

## Part B — thehub-pr blockers

### Summary

Each blocker is counted once, under its primary type.

| Type | Count |
|---|---:|
| GATE | 2 |
| IMPL | 3 |
| GOV | 1 |
| mixed (UI-ops ledger rows) | 1 |
| PR | 1 group (7 PRs) |
| STALE | 1 |
| **Total** | **9** |

### Inventory

| ID | Blocker | Type | Evidence | Owner | Unblock step | Exit criterion |
|---|---|---|---|---|---|---|
| HB-01 | This repository owns the fixes for X-01, X-02, X-04 and X-08 | GATE | See Part A | Maintainer | See Part A | See Part A |
| HB-02 | The HTR v3 validator CodeQL fix never landed | IMPL | #283 required closure. The four constant-only chained comparisons are still on `main` at `scripts/validate_htr_v3_road_recurrence_receipt.py:81` and `:141-143`. The fix exists as commit `9dbb81c` on branch `fix/htr-v3-road-validator-codeql`; its PR #282 was closed unmerged on 2026-09-19. | Agent | Re-land `9dbb81c` (it preserves every frozen count); rerun the HTR v3 contract and CodeQL; resolve the 4 historical #239 review threads; close #283 | CodeQL clean on the validator; #283 closed |
| HB-03 | Open MAX-audit findings, re-verified in code on 2026-09-28 | IMPL | `docs/FEDERATION_MAX_AUDIT_2026-09-24.md`. **F5:** no synthetic-row gate; `src/hub/federation_status.py:73` checks only the declared status, and `validate.py` and `aggregate.py` never check `synthetic`. **F8:** `federation-audit/src/federation_audit/scanner.py:17` `JSX_CONTROL` stops at `=>` (0 of 1,123 surfaces promotable), and the manifest pins date from 2026-08-07. **F9:** `data/gui_parity_status.json` was generated 2026-08-21 and still shows parity green. **F12:** producers pin shared packages at `f2b8176`, so the `prii_desktop` doctor hook is not propagated. **F13:** 0 adjudicated cross-producer correlations, and `correlate.py:367,395` stamps every edge `synthetic: true`. **F15:** `scripts/build_gui_parity_status.py:82` always runs the base checker, not each repository's CI entrypoint. Producer-owned findings are in the producer documents: F6 skywatcher, F10 ovnis, F11 spiderweb, and spiderweb's missing parity gate. | Agent | Follow the MAX §7 order where it applies (F5 and F9, then F8), then F15, F12 and F13 | Each finding closed on `main` |
| HB-04 | Promotion governance is not enforced | GOV/GATE | #256 (branch protection, X-03). #253: certified ingestion must reject unresolved producer spatial manifests (paired with aguayluz #231). | Owner + agent | Enable protection; implement #253 alongside aguayluz #231 | #256 and #253 closed |
| HB-05 | The frontend typecheck is not a CI gate | IMPL | Ledger HUB-005 remainder. `server/frontend/package.json` declares `typecheck` (`tsc -p ./jsconfig.json`), but `.github/workflows/ci.yml` runs only `lint`, `test`, `build` and `test:visual`. The coverage floor (`fail_under = 88`) and server `ruff`/`mypy` are already enforced. | Agent | Add an `npm run typecheck` step, fixing any errors it surfaces | Typecheck required in CI |
| HB-06 | Open rows in the UI-operations failure ledger | mixed | `docs/FEDERATION_UI_OPERATIONS_FAILURE_LEDGER.csv`. Open rows: F004 (no OS-native credential provider, partial); F011 (Tranche B and COR3 inputs); F012 (no non-synthetic observations); F013 (MiLUMA is ToS/WAF gated); F014 (LLM secret); F015 (install topology, partial); F016 (sandbox spec, partial); F023 and F024 (accepted); F025 (two secret models; `src/hub/mcp_runtime/secrets.py:46` still has a readable `get()`); F029 (macOS operator certification: `scripts/certify_macos_operator.py` must be run on a real Mac). F019 is stale: spiderweb shipped `scripts/validate_schemas.py` in #290. | Per row | Update F019; resolve F025 by retiring the readable interface; run F029 on a Mac; the other rows follow their owners | Ledger rows closed or re-dated |
| HB-07 | Certification and program items without a path | GATE/GOV | Ledger HUB-004 (all-main certification) is an operator run. HUB-002 (canonical workspace controller) lost its PR (#148 closed unmerged 2026-08-05) and needs a disposition. #56 (Design System v1 rollout): the standalone `jotaele44/federation-design` repository does not exist, and the axe, keyboard and visual gates have never run. | Maintainer/operator | Decide HUB-002; create the design repository or re-scope #56; schedule HUB-004 after the producer critical path | Decisions recorded; HUB-004 receipt |
| HB-08 | Open PRs | PR | #314 Cell_Set mirror (green, X-05); #297 GIS layer manager (green); dependabot #304 react-router-dom 7 (green, major); #303 date-fns 4 (green, major); #302 eslint 10 (RED: frontend, frontend-visual, builds, package-lock); #301 lucide-react 1.47 (RED: 5 checks); #300 npm group (RED: package-lock) | Agent + maintainer | Merge #314 and #297; decide the majors per X-02; regenerate `package-lock.json` for #300 | No red PRs |
| HB-09 | Stale issues | STALE | #255 and the Actions half of #283 (X-06); #265 "DO_NOT_CREATE" has no content; the scorecards are frozen at 2026-08-04 (X-07) | Agent/maintainer | Close #255 and #265 (not planned); keep #283 open until HB-02 lands | Issues closed |

## Unblock plan (critical path)

1. **This repository, now:**
   1. Re-pin the receipts (X-04).
   2. Re-land the HTR validator fix (HB-02).
   3. Fix the completion-gate classifier (X-01 b).
   4. Add the frontend typecheck (HB-05).
2. **Producers, now:**
   1. moneysweep MS-01 (weekly cadence crash).
   2. aguayluz AY-01 (dead Floot promotion step blocks the Hub dispatch).
   3. centinelas CE-01 (blocked monitor committing to `main`).
3. **Drain the backlog:** merge the Cell_Set set (X-05) and the green dependabot groups; route action bumps through the templates; decide the majors (X-02).
4. **Governance:** branch protection (X-03, #256); close the stale trackers (X-06, HB-09).
5. **Operator queues** (details in each producer document): moneysweep MS-02/03/04; aguayluz AY-03/04/06; skywatcher SK-01/02/04/05; spiderweb SW-06/07; centinelas CE-03/05; ovnis OV-01/02; mucaro MU-01 to MU-06.
6. **Last:**
   1. Re-audit the ledgers (X-07).
   2. MAX findings (HB-03).
   3. The all-main federation certification (HB-07, X-08).

## Ledger reconciliation (`docs/unfinished_implementation_ledger.v1.json`, dated 2026-08-04)

| Ledger ID | Ledger state | State on 2026-09-28 |
|---|---|---|
| HUB-001 | open_pr (PR-157) | Resolved: #157 "Adopt isolated-clone shared package policy" merged 2026-08-08 |
| HUB-002 | open_pr (PR-148) | #148 closed unmerged 2026-08-05; needs a disposition → HB-07 |
| HUB-003 | superseded_prs | Resolved: certification cohorts #149, #154, #155 and #158 closed |
| HUB-004 | operator_run | Still open → HB-07 and X-08 |
| HUB-005 | main_gap | Coverage floor and server lint/type are enforced; the frontend typecheck is still missing → HB-05 |

## Not verifiable with the access used for this audit
- Code-scanning and Dependabot security-alert inventories in all repositories.
- Which Actions secrets exist (inferred only from workflow logs).
- Operator-local worktrees and corpora.
- Billing and plan settings.

# PR Consolidation Audit - 2026-08-05

## Repository State Header

- ACTIVE_VECTOR: repo-operations-pr-consolidation
- ACTIVE_BRANCH: prii-pr-consolidation-audit
- WORKTREE_STATE: verified clean before audit file creation
- REMOTE_SYNC_STATE: origin fetched with prune before classification
- CURRENT_STAGE: governance/stabilization support for Stage 1-2 backend readiness
- CURRENT_PHASE: PR and branch hygiene before further federation mutation
- STABILIZATION_STATE: pre-operational federation
- MUTATION_SCOPE: audit file plus reversible PR closures; no branch deletion; no direct main mutation

## Consolidation Rules

- Keep backend, governance, readiness, certification, contract, normalization, and operator-reproducibility work visible.
- Close stale UI-first or frontend-first PRs while backend readiness is still gated.
- Do not close superseded certification PRs unless unique commits are reviewed or intentionally declared obsolete.
- Keep dependency PRs in a separate queue and merge them one at a time only after checks and readiness impact are clear.
- Do not delete remote branches in this pass.

## PR Disposition Table

| PR | Branch | Category | Evidence | Intended action |
| --- | --- | --- | --- | --- |
| #161 | chore/unified-skillpacks-v1.0.0-bf4c9d85 | MERGE_CANDIDATE | Mergeable draft; 7-file exact-base skillpack scope; lint repaired in `2880af8`; checks passing on pinned base. | Keep open; do not normal-refresh because conformance intentionally rejects out-of-scope main merges; promote only after governance review approves unified skillpack scope. |
| #160 | docs/road-to-100-critical-path-v1 | MERGE_CANDIDATE | One-file governance freeze; refreshed on current `main` in `b08ee3b`; JSON validation and checks passing. | Keep open; mark ready only when governance review approves. |
| #158 | agent/prii-preclone-macos-certification-v3-0 | MERGE_CANDIDATE | Latest certification line; conflict from dependency workflow merges repaired in `893f32c`; refreshed on current `main` in `64455d5`; checks passing including desktop build matrix and preclone certification. | Keep as certification keeper candidate; draft gate remains because PR body does not authorize merge. |
| #157 | codex/remove-mandatory-sibling-coupling-v0-1 | MERGE_CANDIDATE | Isolated-clone policy scope; refreshed on current `main` in `ef2a16f`; rendered templates no longer emit mandatory `../thehub-pr` paths; checks passing. | Keep open; draft gate remains pending consumer validation required by PR body. |
| #155 | agent/prii-preclone-macos-certification-v2-0 | SUPERSEDED_CLOSE | Unique authority-aligned heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #154 | agent/prii-preclone-macos-certification-v1-0 | SUPERSEDED_CLOSE | Unique refreshed heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #149 | agent/prii-preclone-macos-certification-v0-2 | SUPERSEDED_CLOSE | Original certification receipt and heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #148 | agent/prii-preclone-normalization-v0-1 | SUPERSEDED_CLOSE | Pre-clone normalization lineage preserved in #158; head `7067796` is an ancestor of #158 head `893f32c`. | CLOSED 2026-08-05; branch retained. |
| #138 | agent/gui-capability-parity-v0-2 | DOCTRINE_BLOCKED_CLOSE | GUI parity scope; tests and drift failing; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #134 | agent/federation-branding-ui-setup-v0-1 | DOCTRINE_BLOCKED_CLOSE | Branding/UI/desktop app scope; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #131 | claude/federation-ui-operations-z0n1fc | MERGED_CANDIDATE | Operator-certification support: macOS runbook, certification default URL, receipt key-path expansion, manager host, and tests; refreshed on current `main` in `6bb3100`; CI and desktop build checks passed. | MERGED 2026-08-05 as `a5bad05ce5eec4cc73e2eed8569d294bc3f5cd27`; GitHub auto-deleted the head branch. |
| #126 | agent/federation-design-system-foundation-v0-2 | DOCTRINE_BLOCKED_CLOSE | Design-system scope; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #113 | dependabot/npm_and_yarn/server/frontend/testing-library/jest-dom-7.0.0 | MERGED_DEPENDENCY | Frontend test devDependency bump to `@testing-library/jest-dom@7.0.0`; local `npm ci`, lint, unit tests, and build passed. | MERGED 2026-08-05 as `a6f8336adb81c6131eedfb27871256069e000aa5`; GitHub auto-deleted the Dependabot head branch. |
| #112 | dependabot/npm_and_yarn/server/frontend/multi-287cc95123 | INVALID_DEPENDENCY_CLOSE | `npm ci` fails with ERESOLVE: `@types/react-dom@19.x` requires `@types/react@19.x` while the project remains on React 18 typings. | CLOSED 2026-08-05; recreate only as coordinated React type/runtime upgrade. |
| #111 | dependabot/npm_and_yarn/server/frontend/vitest-4.1.10 | MERGED_DEPENDENCY | Frontend Vitest major bump; refreshed on current `main` in `5e730b4` to preserve #113; local `npm ci`, lint, unit tests, and build passed; refreshed CI and desktop build checks passed. | MERGED 2026-08-05 as `2ebfe953496e9316cbfd8054e30cc26c0ff3cae8`; GitHub auto-deleted the Dependabot head branch. |
| #110 | dependabot/npm_and_yarn/server/frontend/recharts-3.10.1 | MERGED_DEPENDENCY | Frontend Recharts major bump; current diff preserved #113, #111, and `@pr-federation/react`; local `npm ci`, lint, unit tests, and build passed; CI and desktop build checks passed. | MERGED 2026-08-05 as `a5631e619926e5e71941f061c7d7688d03b747c0`; GitHub auto-deleted the Dependabot head branch. |
| #109 | dependabot/npm_and_yarn/server/frontend/npm-minor-patch-60a0483391 | MERGED_DEPENDENCY | Grouped frontend minor/patch bump; Dependabot refreshed after #110 to preserve Recharts 3.10.1, #113, #111, and `@pr-federation/react`; local equivalent `npm ci`, lint, unit tests, and build passed; remote CI and desktop build checks passed. | MERGED 2026-08-05 as `d91882cfb10bfb7d03d85eda4c4fedc55df0b2d5`; GitHub auto-deleted the Dependabot head branch. |
| #108 | dependabot/github_actions/actions/setup-python-7.0.0 | TEMPLATE_SYNC_REQUIRED_CLOSE | Failing tests prove generated workflow drift: `.github/workflows/pip-audit.yml`. | CLOSED 2026-08-05; replace with template-aware setup-python bump. |
| #107 | dependabot/github_actions/actions/upload-artifact-7.0.1 | MERGED_DEPENDENCY | Updates pinned `actions/upload-artifact` SHAs across artifact upload steps; CI, desktop build, release packaging, and template drift checks passing. | MERGED 2026-08-05 as `fcd9ad91f317`; GitHub auto-deleted the Dependabot head branch. |
| #106 | dependabot/github_actions/gitleaks/gitleaks-action-3.0.0 | TEMPLATE_SYNC_REQUIRED_CLOSE | Failing tests prove generated workflow drift: `.github/workflows/secret-scan.yml`. | CLOSED 2026-08-05; replace with template-aware gitleaks-action bump. |
| #105 | dependabot/github_actions/softprops/action-gh-release-3.0.2 | BLOCKED_DEPENDENCY_CLOSE | Desktop build fails before release publication: packaged app raises `ModuleNotFoundError: No module named 'jsonschema'`. | CLOSED 2026-08-05; recreate after desktop packaging dependency is fixed. |
| #104 | dependabot/github_actions/actions/github-script-9.0.0 | MERGED_DEPENDENCY | One-file scheduled MCP drift workflow action pin; checks passing; no v9-incompatible `@actions/github` require pattern. | MERGED 2026-08-05 as `b39df272d5e9`; GitHub auto-deleted the Dependabot head branch. |
| #100 | codex/federal-records-contracts-v1 | REPLACEMENT_REQUIRED_CLOSE | Unique federal-records contract intent, but branch is conflicting and mixes schemas, Hub registration, MCP/API, ingest tooling, tests, and frontend routes. | CLOSED 2026-08-05; branch retained; replace with contract-first vector before any API/UI work. |
| #98 | audit/road-to-100-normalization-v0-2 | MERGE_CANDIDATE | Seven unique governance normalization docs; refreshed on current `main` in `71da2a4`; checks passing. | Keep open; reconcile ordering with #160 before promotion. |
| #94 | codex/federation-manager-foundation-v0-3 | SUPERSEDED_CLOSE | Main contains the manager foundation via commit `25c0fe6` and later split hardening modules. | CLOSED 2026-08-05; branch retained. |
| #88 | codex/thehub-mobile-pwa-v0-2 | DOCTRINE_BLOCKED_CLOSE | Mobile PWA/frontend scope; visual check failing; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #32 | gpt/offline-operator-model-v1 | MERGE_CANDIDATE | Offline federation operator/schema authority; refreshed on current `main` in `1962212`; local and CI offline validation passed; checks passing. | Keep open; promote only after schema-authority/readiness alignment review. |
| #23 | gpt/patch-intsys-p0-gaps | DOCTRINE_BLOCKED_CLOSE | Frontend gap patch; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |

## Verification Notes

- Certification comparison command found unique commits in #149, #154, and #155 that were not cherry-picked into #158; reusable lineage was preserved in #158 commit `fc49ace` before closure.
- #158 was refreshed with `origin/main` in commit `893f32c` after #104 and #107 changed pinned workflow actions; `.github/workflows/desktop-build.yml` now preserves the desktop build job and the branch-scoped preclone certification job with `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.
- #158 was refreshed again on current `main` in commit `64455d5` after #131 merged; local `diff --check`, compile, ruff, workspace/template tests passed; CI, desktop build matrix, and preclone-certification checks passed.
- #157 was refreshed on current `main` in commit `ef2a16f`; local `diff --check`, ruff, and template-render tests passed; CI checks passed. A scoped regression test now blocks rendered templates from reintroducing mandatory `../thehub-pr` paths.
- #161 was tested for a normal current-main refresh locally, but its validator correctly rejected the merge as out-of-scope because the PR is intentionally pinned to base `bf4c9d85` with only seven allowed changed paths. No #161 refresh was pushed.
- #160 was refreshed on current `main` in commit `b08ee3b`; the PR diff remained one JSON governance freeze file, local JSON validation passed, and CI checks passed.
- #98 was refreshed on current `main` in commit `71da2a4`; the PR diff remained seven governance docs and CI checks passed.
- #32 was refreshed on current `main` in commit `1962212`; the PR diff remained the offline operator/schema authority files, local `make -f Makefile.offline offline` passed, and the GitHub `validate` job plus full CI passed.
- #148 was closed after `git merge-base --is-ancestor 70677968530536dfd055ac820fcb05944dc77a3c 893f32c90959c508ff6b7f6cff239d2e8383c0c5` confirmed its head is included in #158.
- File inspection showed #131 contains operator certification and backend receipt/manager-host changes, so it was promoted to merge candidate rather than treated as UI-only.
- #131 was refreshed on current `main` in `6bb3100d52c3a6a1d794e3f288263891a0430575`; refreshed CI and desktop build checks passed before merge. Branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #94 is superseded by mainline commit `25c0fe6` plus later manager hardening modules.
- #100 has unique federal-records contract intent, but was closed because it combines contract, API, ingest, test, and UI work in one conflicting branch; salvage requires a fresh contract-first vector.
- #104 was merged as the first dependency-queue item; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #107 was merged after #104 as the next one-at-a-time dependency item; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #113 was merged after local frontend verification; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #111 was refreshed on current `main` before merge because the stale Dependabot branch would otherwise have reverted #113; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #110 was merged after confirming the forced-updated Dependabot branch preserved #113, #111, and `@pr-federation/react`; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #109 was merged after Dependabot refreshed the grouped bump on top of #110; branch deletion was automatic GitHub cleanup, not an explicit branch-deletion operation.
- #112 is invalid against the current React 18 type stack; #108 and #106 require template-aware replacements; #105 is blocked by desktop packaging missing `jsonschema`.
- UI-first closures are reversible and do not delete branches.

## Closures Completed In This Pass

- #23
- #88
- #126
- #134
- #138
- #149
- #154
- #155
- #148
- #94
- #100
- #112
- #108
- #106
- #105

## Dependency Merges Completed In This Pass

- #104 -> `b39df272d5e9`
- #107 -> `fcd9ad91f317`
- #113 -> `a6f8336adb81c6131eedfb27871256069e000aa5`
- #111 -> `2ebfe953496e9316cbfd8054e30cc26c0ff3cae8`
- #110 -> `a5631e619926e5e71941f061c7d7688d03b747c0`
- #109 -> `d91882cfb10bfb7d03d85eda4c4fedc55df0b2d5`

## Producer Dependency Closures Completed In This Pass

- `spiderweb-pr` #245 | TEMPLATE_SYNC_REQUIRED_CLOSE | Closed 2026-08-05 because both drift jobs failed while the diff mutated generated `.github/workflows/codeql.yml` directly; requires a template-aware CodeQL action pin refresh. Closing removed the Dependabot head branch even though branch deletion was not requested, so `dependabot/github_actions/actions-minor-patch-ce612e0709` was restored to `a79d21bbd5d2096d423c1a3fd72cbf58cf708f67`.
- `spiderweb-pr` #230 | LOCK_AWARE_REPLACEMENT_REQUIRED_CLOSE | Closed 2026-08-05 because the `lock` jobs failed and local `uv lock --check` reproduced stale `uv.lock`; attempted repair either left the old Ruff lock entry intact or produced broad resolver-marker churn unrelated to the Ruff bump. Branch `dependabot/pip/python-minor-patch-c784f51798` remained at `cf250111b049e72cd66801cd34b77ac87e585ab3`.
- `spiderweb-pr` #223 | INVALID_DEPENDENCY_CLOSE | Closed 2026-08-05 because local `npm ci` in `server/frontend` failed with `lock file's typescript@7.0.2 does not satisfy typescript@6.0.3`; the PR changed `package-lock.json` without the matching `package.json` update and frontend/build checks failed. Branch `dependabot/npm_and_yarn/server/frontend/typescript-7.0.2` remained at `9444659c32533053c5705a2ce6a319a7ba07c521`.
- `spiderweb-pr` #218 | TEMPLATE_SYNC_REQUIRED_CLOSE | Closed 2026-08-05 because both drift jobs failed while the diff mutated generated setup-python workflow pins directly; requires a template-aware action pin refresh. Closing removed the Dependabot head branch even though branch deletion was not requested, so `dependabot/github_actions/actions/setup-python-7.0.0` was restored to `438c531ff5b54c52cd9b5e1ab1e1f27fef31c9de`.
- `spiderweb-pr` #215 | TEMPLATE_SYNC_REQUIRED_CLOSE | Closed 2026-08-05 because both drift jobs failed while the diff mutated generated checkout workflow pins directly; requires a template-aware action pin refresh. Closing removed the Dependabot head branch even though branch deletion was not requested, so `dependabot/github_actions/actions/checkout-7.0.1` was restored to `b8f4086383aedf05ad76e03a33230579281389ce`.
- `moneysweep-pr` #473 | REDUNDANT_NO_PAYLOAD_CLOSE | Closed 2026-08-17 because current REST metadata reported `changed_files=0` and local verification against `origin/main` `35b74b9b81293c5bc68d8ba2c82f34c0c5878f5d` found an empty three-dot diff for `dependabot/github_actions/actions-minor-patch-97c731b4de`; its two branch commits only carried superseded `.github/workflows/codeql.yml` alignment. Branch `dependabot/github_actions/actions-minor-patch-97c731b4de` remained at `95194b4c775642425f3ca24a8bfaf8496c17dce3`.
- `moneysweep-pr` #474 | TEMPLATE_SYNC_REQUIRED_CLOSE | Closed 2026-08-17 because the only payload directly edited generated `.github/workflows/secret-scan.yml`, whose header requires editing `thehub-pr/federation-templates/baseline/secret-scan.yml` and re-rendering; current check-runs had two failing drift jobs plus `Federation GUI Capability Parity`. Closing removed the Dependabot head branch, so `dependabot/github_actions/gitleaks/gitleaks-action-3.0.0` was restored to `707579b5cb7ee6bf2b8a1185eb0d107b50cfbcef`.

## Producer Dependency Merges Completed In This Pass

- `spiderweb-pr` #244 -> `46d6bd4607611f44f7c494b04e036d7a9966922e`
- `spiderweb-pr` #217 -> `40902d1d906a74d3ce3af2016d58386e2be5a93f`
- `spiderweb-pr` #216 -> `bc49875cb6b695186431b7b3eebaaca154f91786`
- `spiderweb-pr` #122 -> `3c5dd01dbbdfce5dcf12ee95b6623f440488d820`
- `moneysweep-pr` #420 -> `995194af35a37bda2539eb25a0ee61ed77077f07`; stale Dependabot head `b4700cf7bc2e53cd688d4080487654c41ae18fa3` was refreshed with current `main` into `bf1af444dc63b71b3f15a2d1569b258f155ae6a2`, all 33 refreshed checks passed, required review was approved with local verification notes, and the head branch was auto-deleted after merge.
- `moneysweep-pr` #423 -> `ab30e34e6307c6bb2782a1573e8d5ec7923af544`; stale Dependabot head `48bce861d1538037a761c6635f781729d48a802f` was refreshed with current `main` into `4518e73c64ad5591f4c184a4975d11befcb834bb`, all 35 refreshed checks passed, required review was approved with local verification notes, and the head branch was auto-deleted after merge.
- `moneysweep-pr` #422 -> `3ada89068d2a54b14f03088a6787d8ce6079247d`; merged 2026-08-11 after the original audit pass with final head `f36f25b17bbe2b0cddaca7fb6ace38e2ab76e849` and base `660cce9926cafdae31064fff0371926e79faead7`. REST verification on 2026-08-17 found the Dependabot head branch auto-deleted and the merge commit check-runs at 21 success / 1 skipped / 1 failure, with `Federation GUI Capability Parity` failing; treat as MERGED_WITH_FOLLOW_UP_GATE, not a clean-certified dependency merge.
- `moneysweep-pr` #478 -> `0a542d2940514b2678598895fd63aea5931b9e4d`; stale Dependabot head `235cffa4cdc10e797e1b69e7dbc3ce2de11d145f` was refreshed with current `main` `35b74b9b81293c5bc68d8ba2c82f34c0c5878f5d`, then repaired with `601d43730bb71a859adcc214e8aaad624f13257a` to keep `requirements-dev.txt` Ruff `0.16.2` synchronized with `.pre-commit-config.yaml` `ruff-pre-commit` `v0.16.2`. Local gates passed: clean merge, `git diff --check`, isolated dev install, `ruff 0.16.2`, `ruff check --output-format=github .`, and `ruff format --check .`; all 33 refreshed checks passed, required review was approved, and the head branch was auto-deleted after merge.

`spiderweb-pr` dependency queue exhausted on 2026-08-05 after GitHub returned no open `dependabot/*` pull requests; remaining Spiderweb PRs are non-dependency feature or audit branches and require vector review before action.

## Candidate Merges Completed In This Pass

- #131 -> `a5bad05ce5eec4cc73e2eed8569d294bc3f5cd27`

## Conflict Repairs And Refreshes Completed In This Pass

- #158 -> `893f32c`
- #158 -> `64455d5`
- #157 -> `ef2a16f`
- #160 -> `b08ee3b`
- #98 -> `71da2a4`
- #32 -> `1962212`

## Deferred Actions

- Reopen federal-records work only as a contract-first replacement vector: canonical schemas, export-manifest enum, validation fixtures, and freeze hash before Hub API/ingest/UI surfaces.
- Review #161 unified skillpack scope before promotion; lint blocker is resolved in `2880af8`.
- Hub dependency queue from this audit pass is exhausted; recreate closed invalid/template-blocked dependency updates only as focused replacement PRs.

## Federation Remote Queue Snapshot

Initial remote inspection on 2026-08-05 found only `thehub-pr` cloned locally under `/Users/jotaele/Documents/GitHub`; producer repositories were inspected read-only through GitHub before the first producer dependency merge. No producer branch was deleted during this snapshot.

| Repository | Open PRs | Draft PRs | Non-draft PRs | Conflicting PRs | Dependabot PRs | Dependabot all-success | Dependabot with failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `thehub-pr` | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| `spiderweb-pr` | 21 | 10 | 11 | 5 | 9 | 4 | 5 |
| `moneysweep-pr` | 27 | 8 | 19 | 2 | 9 | 9 | 0 |
| `skywatcher-pr` | 36 | 21 | 15 | 7 | 10 | 7 | 3 |
| `ovnis-pr` | 17 | 7 | 10 | 1 | 10 | 5 | 5 |
| `aguayluz-pr` | 41 | 28 | 13 | 14 | 10 | 0 | 4 |
| `centinelas-pr` | 24 | 13 | 11 | 2 | 10 | 2 | 8 |
| `Puerto-Rico-Airspace-Intelligence-Tool` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Dependency cleanup continues one PR at a time. Treat `SKIPPED,SUCCESS` dependency check sets as requiring manual review before merge, not as all-success. Current low-risk remaining candidates are green, mergeable Dependabot PRs with narrow action or package bumps; mixed `FAILURE,SUCCESS` dependency PRs require local reproduction or closure rationale before any merge.

### Producer Dependency Queue

| Repository | PR | State | Checks | Branch | Title |
| --- | --- | --- | --- | --- | --- |
| `moneysweep-pr` | #433 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/npm-minor-patch-18fb5ab90d` | deps: bump the npm-minor-patch group across 1 directory with 10 updates |
| `moneysweep-pr` | #424 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/setup-python-7.0.0` | ci: bump actions/setup-python from 5.6.0 to 7.0.0 |
| `moneysweep-pr` | #423 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/upload-artifact-7.0.1` | ci: bump actions/upload-artifact from 4.6.2 to 7.0.1 |
| `moneysweep-pr` | #422 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/setup-node-7.0.0` | ci: bump actions/setup-node from 4.4.0 to 7.0.0 |
| `moneysweep-pr` | #421 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/checkout-7.0.1` | ci: bump actions/checkout from 4 to 7 |
| `moneysweep-pr` | #420 | MERGEABLE | SUCCESS | `dependabot/github_actions/softprops/action-gh-release-3.0.2` | ci: bump softprops/action-gh-release from 2.6.2 to 3.0.2 |
| `moneysweep-pr` | #419 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/react-router-dom-7.18.1` | deps: bump react-router-dom from 6.30.4 to 7.18.2 in /dashboard |
| `moneysweep-pr` | #418 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/recharts-3.10.1` | deps: bump recharts from 2.15.4 to 3.10.1 in /dashboard |
| `moneysweep-pr` | #417 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/multi-287cc95123` | deps: bump react-dom and @types/react-dom in /dashboard |
| `skywatcher-pr` | #117 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/upload-artifact-7.0.1` | ci: bump actions/upload-artifact from 4.6.2 to 7.0.1 |
| `skywatcher-pr` | #116 | MERGEABLE | SUCCESS | `dependabot/github_actions/softprops/action-gh-release-3.0.2` | ci: bump softprops/action-gh-release from 2.6.2 to 3.0.2 |
| `skywatcher-pr` | #115 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/setup-node-7.0.0` | ci: bump actions/setup-node from 4.4.0 to 7.0.0 |
| `skywatcher-pr` | #114 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/frontend/globals-17.8.0` | deps: bump globals from 15.15.0 to 17.8.0 in /frontend |
| `skywatcher-pr` | #113 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/frontend/types/node-26.1.2` | deps: bump @types/node from 22.19.11 to 26.1.2 in /frontend |
| `skywatcher-pr` | #112 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/frontend/react-router-dom-7.18.1` | deps: bump react-router-dom from 6.30.3 to 7.18.1 in /frontend |
| `skywatcher-pr` | #111 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/frontend/npm-minor-patch-5a8adfe954` | deps: bump the npm-minor-patch group across 1 directory with 34 updates |
| `ovnis-pr` | #56 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/react-router-dom-7.18.1` | deps: bump react-router-dom from 6.30.4 to 7.18.1 in /dashboard |
| `ovnis-pr` | #55 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/dashboard/npm-minor-patch-96a45a33d9` | deps: bump the npm-minor-patch group across 1 directory with 31 updates |
| `ovnis-pr` | #52 | MERGEABLE | SUCCESS | `dependabot/github_actions/peter-evans/create-pull-request-8.1.1` | ci: bump peter-evans/create-pull-request from 6.1.0 to 8.1.1 |
| `ovnis-pr` | #51 | MERGEABLE | SUCCESS | `dependabot/github_actions/actions/setup-node-7.0.0` | ci: bump actions/setup-node from 4.4.0 to 7.0.0 |
| `ovnis-pr` | #50 | MERGEABLE | SUCCESS | `dependabot/github_actions/softprops/action-gh-release-3.0.2` | ci: bump softprops/action-gh-release from 2.6.2 to 3.0.2 |
| `centinelas-pr` | #81 | MERGEABLE | SUCCESS | `dependabot/npm_and_yarn/frontend/npm-minor-patch-6737f648b8` | deps: bump the npm-minor-patch group across 1 directory with 8 updates |
| `centinelas-pr` | #60 | MERGEABLE | SUCCESS | `dependabot/github_actions/softprops/action-gh-release-3.0.2` | ci: bump softprops/action-gh-release from 2.6.2 to 3.0.2 |

## Branch Retirement Audit

Current remote branch count after restoration: 31 including `main`.

| Branch | PR state | Retirement category | Action |
| --- | --- | --- | --- |
| `agent/adr-0006-contracts-v0-5-h01-normalized` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/adr0006-h06-bounded-producer-v016` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/adr0006-h08-v023-repair-squash-base` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/federation-branding-ui-setup-v0-1` | #134 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/federation-design-system-foundation-v0-2` | #126 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/gui-capability-parity-v0-2` | #138 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/h08-v022-squash-base` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/pr139-adr0006-reconciled-v0-6` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/prii-preclone-macos-certification-base-v0-2` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `agent/prii-preclone-macos-certification-v0-2` | #149 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/prii-preclone-macos-certification-v1-0` | #154 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/prii-preclone-macos-certification-v2-0` | #155 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `agent/prii-preclone-macos-certification-v3-0` | #158 open | ACTIVE_PR | Retain. |
| `agent/prii-preclone-normalization-v0-1` | #148 closed | CLOSED_PR_RETAINED | Retain pending normalization provenance review. |
| `audit/road-to-100-normalization-v0-2` | #98 open | ACTIVE_PR | Retain. |
| `canary/centinelas-foia-v0-4` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `canary/centinelas-foia-v0-5` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain. |
| `chore/unified-skillpacks-v1.0.0-bf4c9d85` | #161 open | ACTIVE_PR | Retain. |
| `codex/federal-records-contracts-v1` | #100 closed | CLOSED_PR_RETAINED | Retain pending contract-first replacement vector. |
| `codex/federation-manager-foundation-v0-3` | #94 closed | CLOSED_PR_RETAINED | Retain pending supersession verification retention window. |
| `codex/remove-mandatory-sibling-coupling-v0-1` | #157 open | ACTIVE_PR | Retain. |
| `codex/thehub-mobile-pwa-v0-2` | #88 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `dependabot/github_actions/actions/checkout-7.0.1` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain until automation origin is verified. |
| `docs/road-to-100-critical-path-v1` | #160 open | ACTIVE_PR | Retain. |
| `feat/federation-crossover-ingest` | #41 closed | CLOSED_PR_RETAINED | Retain pending provenance review. |
| `gpt/offline-operator-model-v1` | #32 open | ACTIVE_PR | Retain. |
| `gpt/patch-intsys-p0-gaps` | #23 closed | CLOSED_PR_RETAINED | Retain per closure comment. |
| `main` | default branch | PROTECTED | Retain. |
| `prii-pr-consolidation-audit` | #162 open | ACTIVE_PR | Retain. |
| `security/semgrep-rollout-v1` | #74 merged | MERGED_BRANCH_RESTORED | Restored to PR #74 head `cd666f621aa8a9d3af94bb211b8abbea3381b76f`; retain. |
| `semgrep-pre-rebase-8b877ffe` | no PR found | NEEDS_PROVENANCE_REVIEW | Retain as likely pre-rebase recovery branch. |

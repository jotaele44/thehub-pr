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
| #161 | chore/unified-skillpacks-v1.0.0-bf4c9d85 | MERGE_CANDIDATE | Mergeable draft; 7 files; lint repaired in `2880af8`; checks passing. | Keep open; promote only after governance review approves unified skillpack scope. |
| #160 | docs/road-to-100-critical-path-v1 | MERGE_CANDIDATE | Mergeable draft; 1 governance freeze file; checks passing. | Keep open; mark ready only when governance review approves. |
| #158 | agent/prii-preclone-macos-certification-v3-0 | MERGE_CANDIDATE | Latest certification line; conflict from dependency workflow merges repaired in `893f32c`; mergeable clean; checks passing including desktop build matrix and preclone certification. | Keep as certification keeper candidate. |
| #157 | codex/remove-mandatory-sibling-coupling-v0-1 | MERGE_CANDIDATE | Mergeable draft; isolated-clone policy scope; checks passing. | Keep open; promote after readiness review. |
| #155 | agent/prii-preclone-macos-certification-v2-0 | SUPERSEDED_CLOSE | Unique authority-aligned heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #154 | agent/prii-preclone-macos-certification-v1-0 | SUPERSEDED_CLOSE | Unique refreshed heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #149 | agent/prii-preclone-macos-certification-v0-2 | SUPERSEDED_CLOSE | Original certification receipt and heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #148 | agent/prii-preclone-normalization-v0-1 | MERGE_CANDIDATE | Mergeable draft; pre-clone normalization; checks passing. | Keep open; promote after certification/policy ordering review. |
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
| #98 | audit/road-to-100-normalization-v0-2 | MERGE_CANDIDATE | Mergeable draft; governance normalization docs; checks passing. | Keep open; reconcile ordering with #160. |
| #94 | codex/federation-manager-foundation-v0-3 | SUPERSEDED_CLOSE | Main contains the manager foundation via commit `25c0fe6` and later split hardening modules. | CLOSED 2026-08-05; branch retained. |
| #88 | codex/thehub-mobile-pwa-v0-2 | DOCTRINE_BLOCKED_CLOSE | Mobile PWA/frontend scope; visual check failing; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #32 | gpt/offline-operator-model-v1 | MERGE_CANDIDATE | Offline federation operator/schema authority; checks passing. | Keep open; inspect for readiness alignment despite age. |
| #23 | gpt/patch-intsys-p0-gaps | DOCTRINE_BLOCKED_CLOSE | Frontend gap patch; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |

## Verification Notes

- Certification comparison command found unique commits in #149, #154, and #155 that were not cherry-picked into #158; reusable lineage was preserved in #158 commit `fc49ace` before closure.
- #158 was refreshed with `origin/main` in commit `893f32c` after #104 and #107 changed pinned workflow actions; `.github/workflows/desktop-build.yml` now preserves the desktop build job and the branch-scoped preclone certification job with `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.
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

## Candidate Merges Completed In This Pass

- #131 -> `a5bad05ce5eec4cc73e2eed8569d294bc3f5cd27`

## Conflict Repairs Completed In This Pass

- #158 -> `893f32c`

## Deferred Actions

- Reopen federal-records work only as a contract-first replacement vector: canonical schemas, export-manifest enum, validation fixtures, and freeze hash before Hub API/ingest/UI surfaces.
- Review #161 unified skillpack scope before promotion; lint blocker is resolved in `2880af8`.
- Dependency queue from this audit pass is exhausted; recreate closed invalid/template-blocked dependency updates only as focused replacement PRs.

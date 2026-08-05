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
| #158 | agent/prii-preclone-macos-certification-v3-0 | MERGE_CANDIDATE | Latest certification line; mergeable draft; historical lineage preserved in commit `fc49ace`. | Keep as certification keeper candidate. |
| #157 | codex/remove-mandatory-sibling-coupling-v0-1 | MERGE_CANDIDATE | Mergeable draft; isolated-clone policy scope; checks passing. | Keep open; promote after readiness review. |
| #155 | agent/prii-preclone-macos-certification-v2-0 | SUPERSEDED_CLOSE | Unique authority-aligned heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #154 | agent/prii-preclone-macos-certification-v1-0 | SUPERSEDED_CLOSE | Unique refreshed heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #149 | agent/prii-preclone-macos-certification-v0-2 | SUPERSEDED_CLOSE | Original certification receipt and heads archived in #158 commit `fc49ace`. | CLOSED 2026-08-05; branch retained. |
| #148 | agent/prii-preclone-normalization-v0-1 | MERGE_CANDIDATE | Mergeable draft; pre-clone normalization; checks passing. | Keep open; promote after certification/policy ordering review. |
| #138 | agent/gui-capability-parity-v0-2 | DOCTRINE_BLOCKED_CLOSE | GUI parity scope; tests and drift failing; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #134 | agent/federation-branding-ui-setup-v0-1 | DOCTRINE_BLOCKED_CLOSE | Branding/UI/desktop app scope; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #131 | claude/federation-ui-operations-z0n1fc | NEEDS_INSPECTION | Title mentions UI, but files include macOS certification, receipts, and manager host tests. | Keep open; inspect as operator-certification support, not UI-only work. |
| #126 | agent/federation-design-system-foundation-v0-2 | DOCTRINE_BLOCKED_CLOSE | Design-system scope; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #113 | dependabot/npm_and_yarn/server/frontend/testing-library/jest-dom-7.0.0 | DEPENDENCY_QUEUE | Frontend dependency bump. | Defer; handle one dependency PR at a time. |
| #112 | dependabot/npm_and_yarn/server/frontend/multi-287cc95123 | DEPENDENCY_QUEUE | Frontend dependency bump. | Defer; handle one dependency PR at a time. |
| #111 | dependabot/npm_and_yarn/server/frontend/vitest-4.1.10 | DEPENDENCY_QUEUE | Frontend dependency bump. | Defer; handle one dependency PR at a time. |
| #110 | dependabot/npm_and_yarn/server/frontend/recharts-3.10.1 | DEPENDENCY_QUEUE | Frontend dependency bump. | Defer; handle one dependency PR at a time. |
| #109 | dependabot/npm_and_yarn/server/frontend/npm-minor-patch-60a0483391 | DEPENDENCY_QUEUE | Grouped frontend dependency bump. | Defer; handle after smaller dependency PRs. |
| #108 | dependabot/github_actions/actions/setup-python-7.0.0 | DEPENDENCY_QUEUE | GitHub Actions dependency bump; some tests failing. | Defer until failing checks are understood. |
| #107 | dependabot/github_actions/actions/upload-artifact-7.0.1 | DEPENDENCY_QUEUE | GitHub Actions dependency bump. | Defer; handle one dependency PR at a time. |
| #106 | dependabot/github_actions/gitleaks/gitleaks-action-3.0.0 | DEPENDENCY_QUEUE | GitHub Actions dependency bump; tests failing. | Defer until failing checks are understood. |
| #105 | dependabot/github_actions/softprops/action-gh-release-3.0.2 | DEPENDENCY_QUEUE | GitHub Actions dependency bump; build checks failing. | Defer until failing checks are understood. |
| #104 | dependabot/github_actions/actions/github-script-9.0.0 | DEPENDENCY_QUEUE | Small GitHub Actions dependency bump. | Defer; likely first dependency merge candidate after readiness queue. |
| #100 | codex/federal-records-contracts-v1 | NEEDS_INSPECTION | Backend contract/API scope but conflicting and includes frontend page. | Keep open until contract value and conflicts are reviewed. |
| #98 | audit/road-to-100-normalization-v0-2 | MERGE_CANDIDATE | Mergeable draft; governance normalization docs; checks passing. | Keep open; reconcile ordering with #160. |
| #94 | codex/federation-manager-foundation-v0-3 | NEEDS_INSPECTION | Manager backend/API plus frontend; conflicting. | Keep open until backend-critical portions are separated or superseded. |
| #88 | codex/thehub-mobile-pwa-v0-2 | DOCTRINE_BLOCKED_CLOSE | Mobile PWA/frontend scope; visual check failing; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |
| #32 | gpt/offline-operator-model-v1 | MERGE_CANDIDATE | Offline federation operator/schema authority; checks passing. | Keep open; inspect for readiness alignment despite age. |
| #23 | gpt/patch-intsys-p0-gaps | DOCTRINE_BLOCKED_CLOSE | Frontend gap patch; conflicting; backend readiness not clean. | CLOSED 2026-08-05 with sequencing rationale; branch retained. |

## Verification Notes

- Certification comparison command found unique commits in #149, #154, and #155 that were not cherry-picked into #158; reusable lineage was preserved in #158 commit `fc49ace` before closure.
- File inspection showed #131 contains operator certification and backend receipt/manager-host changes, so it is not treated as UI-only.
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

## Deferred Actions

- Review #94 and #100 for backend-critical extraction or clean replacement.
- Review #161 unified skillpack scope before promotion; lint blocker is resolved in `2880af8`.
- Process dependency PRs after readiness/governance queue is stable.

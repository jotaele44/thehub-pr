# Road to 100 — normalized federation score

**Audit date:** 2026-08-04  
**Scoring model:** code completeness 20%; main-branch availability 15%; CI enforcement 15%; data materialization 15%; operator verification 15%; GUI completeness 10%; federation readiness 10%.

## Current normalized score: 69.55 / 100

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| Code completeness | 20 | 95 | 19.00 |
| Main-branch availability | 15 | 85 | 12.75 |
| CI enforcement | 15 | 72 | 10.80 |
| Data materialization | 15 | 45 | 6.75 |
| Operator verification | 15 | 55 | 8.25 |
| GUI completeness | 10 | 70 | 7.00 |
| Federation readiness | 10 | 50 | 5.00 |

The former ~90% figure measured intended-scope code completeness. It is retained only as historical context and is not comparable across repositories.

## State reconciliation

- Core federation, aggregation, correlation, ingestion, maintenance, MCP and desktop runtime code is on `main`.
- PR #148 is the current workspace-normalization implementation candidate.
- PR #157 is the current isolated-clone/shared-package policy candidate.
- PR #158 is the newest exact-head macOS certification candidate.
- PRs #149, #154 and #155 are superseded certification cohorts and must not be treated as current evidence.
- Diagnostic function, agent and binary-storage endpoints remain intentionally unimplemented.
- End-to-end readiness remains gated on all six producers executing real validated exports.

## Priority exit sequence

1. Adjudicate and land the isolated-clone authority represented by #157.
2. Reconcile #148 onto the final authority.
3. Replace the obsolete certification chain with one final all-main exact-head certification.
4. Require all six producer packages to validate and complete `fetch --run → aggregate → correlate → ingest → graph-report`.
5. Add missing CI enforcement for server-side Python, frontend type checking and coverage floors.

## Machine-readable authority

The unfinished work inventory is `docs/unfinished_implementation_ledger.v1.json`. A task counts as complete only when its exit criteria are evidenced on `main`; open PRs receive candidate credit only.

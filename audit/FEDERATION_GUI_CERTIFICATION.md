# Federation GUI / UX Certification — 2026-08-22 Snapshot

## Certification state

**OPEN** — this file is a control ledger, not a completion claim.

The certification may become `PASS` only when the frozen manifest closes with:

- `UNASSESSED_UI_SURFACES = 0`
- `UNRESOLVED_SCOPE_ITEMS = 0`
- `P0_OPEN = 0`
- `P1_UNADJUDICATED = 0`
- repository, route/module, component, state, workflow, accessibility, responsive and screenshot arithmetic closed

## Frozen federation denominator

| Repository | Role | Frontend root | Frozen SHA |
|---|---|---|---|
| `thehub-pr` | canonical product | `server/frontend` | `4611327f5f1503fafd7ae2a03edffdb636cedc27` |
| `moneysweep-pr` | producer diagnostic | `dashboard` | `315520119c47b0f271f19531d53de8454d99f41a` |
| `spiderweb-pr` | producer diagnostic | `server/frontend` | `e15133faafef4a6fe0472521453379c81f1a522e` |
| `aguayluz-pr` | producer diagnostic | `dashboard` | `e917d1ff1df543930e7bcf25e5b511bdb9191a16` |
| `ovnis-pr` | producer diagnostic | `dashboard` | `f4b47afa44e001df42c14b676793168cde2a38b1` |
| `skywatcher-pr` | producer diagnostic | `frontend` | `cbff564033831344567134be22b480c4c35c4698` |
| `centinelas-pr` | producer diagnostic | `frontend` | `a474bc65e1cb7f1a5f631f18873e494938c5461f` |

The producer membership comes from `registry/producers.yaml`; the Hub is the canonical product surface under ADR 0001. A downstream consumer is not silently added to the seven-repository design denominator without an authoritative UI-bearing federation binding.

## Vector A — denominator

The frozen census ran successfully in GitHub Actions against all seven exact SHAs.

- workflow run: `32551875042`
- artifact: `9470281394`
- artifact digest: `sha256:ab274ab228c5031f80cdb874f814d12c11932e54a8a4b5b3de77a160e0376c10`
- generated UTC: `2026-08-22T04:30:34.976008+00:00`

### Exact static census

| Metric | Count | State |
|---|---:|---|
| repositories | 7 / 7 | PASS |
| frontend source files | 643 | PASS_DISCOVERY |
| visual source files | 458 | PASS_DISCOVERY |
| frontend test files | 49 | PASS_DISCOVERY |
| declared routes | 97 | PASS_DISCOVERY |
| SpiderWeb workbench modules | 6 | PASS_DISCOVERY |
| top-level navigation surfaces | 103 | PASS_DISCOVERY |
| static interaction-handler occurrences | 403 | PASS_DISCOVERY |
| snapshot mismatches | 0 | PASS |

### Per-repository static census

| Repository | Source | Visual | Tests | Routes | Workbench modules | Static interactions |
|---|---:|---:|---:|---:|---:|---:|
| `thehub-pr` | 182 | 136 | 11 | 32 | 0 | 123 |
| `moneysweep-pr` | 48 | 27 | 4 | 2 | 0 | 15 |
| `spiderweb-pr` | 47 | 19 | 9 | 0 | 6 | 48 |
| `aguayluz-pr` | 83 | 52 | 12 | 20 | 0 | 85 |
| `ovnis-pr` | 80 | 61 | 5 | 2 | 0 | 10 |
| `skywatcher-pr` | 134 | 113 | 6 | 18 | 0 | 90 |
| `centinelas-pr` | 69 | 50 | 2 | 23 | 0 | 32 |

Static route/module discovery is not runtime reachability proof. Static state vocabulary discovery is not behavioral state coverage. Interaction-handler occurrences are discovery candidates, not unique interaction identities.

| Gate | State | Notes |
|---|---|---|
| federation membership | PASS | Hub + six registered producers |
| repository snapshot freeze | PASS | seven immutable SHAs above |
| frontend-root classification | PASS | seven roots above |
| exact frontend file manifest | PASS_DISCOVERY | 643 source files; file-level SHA-256 retained in census artifact |
| route/module discovery | PASS_DISCOVERY | 97 routes + 6 SpiderWeb modules = 103 navigation surfaces |
| runtime route/module reachability | OPEN | requires runtime fixture execution |
| visual-source denominator | PASS_DISCOVERY | 458 files; behavioral role still requires adjudication |
| state vocabulary discovery | PASS_DISCOVERY | absence is explicitly not treated as proof of state absence |
| behavioral state coverage | OPEN | requires positive/negative fixtures |
| workflow denominator | OPEN | requires route/module + interaction adjudication |
| screenshot denominator | OPEN | requires runtime route/module × state × viewport matrix |
| accessibility runtime coverage | OPEN | static/unit evidence is insufficient for certification |

## Vector C — canonical product standard

Stable main currently exposes `@pr-federation/react` `0.4.1`, separating presentation tone from operational, workflow, evidence-tier, confidence, provenance, freshness and async-state axes.

### C-001 — forensic semantic axes

**Severity: P1 / PROVISIONAL**

The frozen stable package does not encode the required epistemic axis:

`FACT | COMPUTED | BINDING | INFERENCE | ASSUMPTION | HYPOTHESIS | UNKNOWN`

or the complete certification axis:

`PASS | FAIL | OPEN | BLOCKED | PROVISIONAL | AUDIT_ONLY | NONCANONICAL | CANDIDATE_NOT_IDENTITY | UNRESOLVED | SUPERSEDED`

A separate candidate PR implements both axes as `@pr-federation/react` `0.5.0-rc.1`. Unknown epistemic values fail to `UNKNOWN`; unknown certification values fail open to `OPEN`. Positive and negative semantic regression tests are included.

Package-level candidate gates are `PASS`:

- unit and contract tests
- token/accessibility/contrast/reduced-motion/API-snapshot verification
- immutable candidate packaging
- release-manifest source-hash verification
- tarball contract and checksum

The release job remained skipped by design. Therefore C-001 is not closed on the frozen canonical product until the candidate is reviewed, promoted and consumed under a new snapshot.

## Vector B — federation convergence

| Repository | Shared React package | Static convergence state |
|---|---:|---|
| `thehub-pr` | local `0.4.1` source | canonical stable |
| `moneysweep-pr` | `0.4.1` | current stable |
| `aguayluz-pr` | `0.4.0` | version lag |
| `ovnis-pr` | `0.3.0` | version lag |
| `skywatcher-pr` | `0.3.0` | version lag |
| `centinelas-pr` | `0.3.0` | version lag |
| `spiderweb-pr` | not declared | package convergence gap; local federation tokens exist and must be compared before migration |

### B-001 — package adoption not closed

**Severity: P2 / OPEN**

Six of seven GUI repositories consume the shared React package (`85.714%`, computed). SpiderWeb does not. This is a package-convergence finding only. It is not evidence that SpiderWeb lacks federation-compatible tokens or that its current visuals are incorrect.

### B-002 — package versions not converged

**Severity: P2 / OPEN**

Consumers span `0.3.0`, `0.4.0` and `0.4.1`. Version equality is not itself proof of visual or semantic equivalence, but the skew prevents a single package contract from being assumed federation-wide.

### B-003 — browser-harness coverage not closed

**Severity: P1 / OPEN**

Existing Playwright/browser contracts are statically declared for the Hub, MoneySweep, Agua y Luz and Centinelas: `4 / 7 = 57.143%` of the frozen GUI repositories. SpiderWeb, OVNIS and SkyWatcher do not declare an equivalent Playwright browser harness in their frozen frontend package manifests.

A frozen seven-repository validation workflow now runs each frontend's own install/lint/typecheck/test/build contract and runs existing browser/parity suites where they already exist. Missing browser harnesses are logged as `BROWSER_HARNESS_OPEN`, not treated as passing.

## Regression fixture status

| Fixture class | State |
|---|---|
| canonical semantic positive cases | PASS in v0.5 candidate |
| canonical semantic invalid/unknown negative cases | PASS in v0.5 candidate |
| frozen producer unit/component suites | RUNNING / OPEN until matrix completes |
| frozen existing browser/parity suites | RUNNING / OPEN until matrix completes |
| cross-federation null/duplicate/ambiguous-identity/M:N/state fault injection | OPEN |
| route/module × state × viewport screenshots | OPEN |

## Existing runtime evidence retained

Existing producer audits, GUI parity baselines, Playwright suites, accessibility results and Hub operations certification are reusable evidence. They remain version-scoped and are not promoted to the frozen 2026-08-22 snapshot without SHA-compatible verification.

Static source absence is never treated as proof that a state, route, component or defect does not exist.

## Current closure arithmetic

```text
REPOSITORIES_EXPECTED = 7
REPOSITORIES_CENSUSED = 7
SNAPSHOT_MISMATCHES = 0
SOURCE_FILES = 643
VISUAL_FILES = 458
TEST_FILES = 49
DECLARED_ROUTES = 97
WORKBENCH_MODULES = 6
TOP_LEVEL_NAVIGATION_SURFACES = 103
STATIC_INTERACTION_HANDLER_OCCURRENCES = 403
```

The following values are deliberately **not** asserted as zero yet:

```text
UNASSESSED_UI_SURFACES
UNRESOLVED_SCOPE_ITEMS
P0_OPEN
P1_UNADJUDICATED
BEHAVIORAL_STATE_RESIDUE
WORKFLOW_RESIDUE
ACCESSIBILITY_RUNTIME_RESIDUE
RESPONSIVE_RESIDUE
SCREENSHOT_RESIDUE
```

Therefore:

```text
FEDERATION_GUI_CERTIFICATION = OPEN
100_PERCENT_ASSESSED = FAIL
```

## Required next gates

1. Complete the frozen seven-repository validation matrix and classify every failure.
2. Adjudicate every discovered visual file and navigation surface.
3. Build the canonical route/module × state × viewport fixture matrix.
4. Promote the forensic semantic candidate only after review; then create a new snapshot before producer convergence.
5. Compare each producer to the canonical package using `INTERSECTION`, `A_ONLY`, `B_ONLY`, `UNION`, and `SYMMETRIC_DIFFERENCE`.
6. Add browser/visual/a11y regression execution for SpiderWeb, OVNIS and SkyWatcher without forcing inappropriate route parity on SpiderWeb's single-workbench architecture.
7. Inject null, duplicate, ambiguous identity, 1:N, N:1, N:N, contradiction, stale, partial, offline, timeout, 429/500 and malformed-schema fixtures.
8. Reconcile route/module, component, state, workflow, accessibility, responsive and screenshot counts against the frozen denominator.

## Closure invariant

```text
TOTAL_SCOPE_ITEMS
=
ASSESSED
+ JUSTIFIED_EXCLUSIONS
+ OPEN
+ BLOCKED
+ UNRESOLVED
```

Final certification requires:

```text
OPEN = 0
BLOCKED = 0
UNRESOLVED = 0
UNEXPLAINED_RESIDUE = 0
P0_OPEN = 0
P1_UNADJUDICATED = 0
```

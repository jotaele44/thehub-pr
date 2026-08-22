# Federation GUI Validation Findings — Frozen 2026-08-22 Snapshot

## Status

`OPEN` — findings below are from the first same-snapshot seven-repository frontend contract run (`32552111917`). They do not close runtime route/state/workflow/screenshot certification.

## Matrix summary

| Repository | Install | Lint | Typecheck | Unit/component | Build | Browser/parity | Classification |
|---|---|---|---|---|---|---|---|
| `thehub-pr` | PASS | PASS | FAIL | NOT_RUN_AFTER_FAIL | NOT_RUN_AFTER_FAIL | NOT_RUN_AFTER_FAIL | P1 declared-contract failure; isolated remediation PR #194 |
| `moneysweep-pr` | PASS | PASS | NOT_DECLARED | PASS (70) | PASS | BLOCKED_ENV | browser backend requirements omitted by first audit runner; harness corrected without changing frozen SHA |
| `spiderweb-pr` | PASS | PASS | PASS | PASS | PASS | NOT_DECLARED | P1 browser-harness gap remains OPEN |
| `aguayluz-pr` | PASS | PASS | NOT_DECLARED | PASS (150) | PASS | BLOCKED_ENV | browser backend requirements omitted by first audit runner; harness corrected without changing frozen SHA |
| `ovnis-pr` | PASS | PASS | PASS | PASS | PASS | NOT_DECLARED | P1 browser-harness gap remains OPEN |
| `skywatcher-pr` | PASS | PASS | FAIL | NOT_RUN_AFTER_FAIL | NOT_RUN_AFTER_FAIL | NOT_DECLARED | P1 substantive typecheck debt plus browser-harness gap |
| `centinelas-pr` | PASS | PASS | PASS | PASS | PASS | BLOCKED_ENV | browser backend optional extra omitted by first audit runner; harness corrected without changing frozen SHA |

## F-001 — Hub declared typecheck contract fails

**Classification:** `P1 / OPEN`, remediation `PROVISIONAL`

Frozen command: `npm run typecheck`.

Observed failure: TypeScript TS5102 rejects `compilerOptions.baseUrl` in `server/frontend/jsconfig.json` because the option has been removed. The `@/* -> ./src/*` path mapping itself does not require the obsolete `baseUrl` entry.

A separate remediation branch/PR removes only `baseUrl`; it does not mutate the frozen audit snapshot. The remediation remains provisional until its CI passes and a later snapshot re-runs the exact frontend contract.

## F-002 — SkyWatcher declared typecheck contract fails materially

**Classification:** `P1 / OPEN`

This is not reduced to the same root cause as the Hub. The frozen typecheck reports multiple contract families across application API/error shapes, component prop inference and shared-package/application integration. Later test/build stages were skipped by the fail-fast job after the typecheck failure.

**Safeguard:** do not close this by disabling `checkJs`, excluding affected source families, or weakening the script. The existing contract must be repaired or intentionally redefined with equivalent/stronger coverage.

## F-003 — MoneySweep browser parity first-run blocker is audit-environment, not product failure

**Classification:** `BLOCKED / superseded runner defect pending rerun`

MoneySweep passed lint, 70 unit/component tests and production build. Playwright then failed before exercising the UI because its configured backend command requires `python -m uvicorn` and the first central runner installed only frontend dependencies.

The producer's own `server/backend/requirements.txt` explicitly declares FastAPI, Uvicorn and pandas. The audit runner has been corrected to install that exact file conditionally before MoneySweep browser parity.

## F-004 — Agua y Luz browser parity first-run blocker is audit-environment, not product failure

**Classification:** `BLOCKED / superseded runner defect pending rerun`

Agua y Luz passed lint, 150 unit/component tests, included accessibility assertions, and production build. Playwright then failed before browser execution because its configured backend command requires Uvicorn and the first central runner had not installed the declared backend requirements.

The producer's `server/backend/requirements.txt` explicitly declares FastAPI, Uvicorn and jsonschema. The audit runner has been corrected to install that exact file conditionally before browser parity.

## F-005 — Centinelas browser parity first-run blocker is audit-environment, not product failure

**Classification:** `BLOCKED / superseded runner defect pending rerun`

Centinelas passed lint, typecheck, unit/component tests and production build. Playwright then failed before exercising the UI because its configured backend command requires `python -m uvicorn` and the first central runner installed only frontend dependencies.

The producer's `server/backend/requirements.txt` explicitly declares FastAPI, Uvicorn, feedparser and PyYAML. The audit runner has been corrected to install that exact file conditionally before Centinelas browser parity.

## F-006 — browser harness denominator is incomplete

**Classification:** `P1 / OPEN`

Frozen browser/parity harnesses are declared in 4 of 7 GUI repositories: Hub, MoneySweep, Agua y Luz and Centinelas. SpiderWeb, OVNIS and SkyWatcher have no equivalent declared Playwright browser contract in their frozen frontend package manifests.

Absence of a harness is not proof the GUI is defective. It is proof that federation-wide runtime/browser certification cannot yet close.

## F-007 — package convergence is incomplete

**Classification:** `P2 / OPEN`

Shared `@pr-federation/react` adoption/version manifestations on the frozen snapshot:

- Hub canonical source: `0.4.1`
- MoneySweep: `0.4.1`
- Agua y Luz: `0.4.0`
- OVNIS: `0.3.0`
- SkyWatcher: `0.3.0`
- Centinelas: `0.3.0`
- SpiderWeb: no package declaration; local `--fd-*` federation token layer exists

Version/name equality is not semantic identity. A dedicated CSS custom-property manifest comparator is now part of the audit controller and computes `INTERSECTION`, `A_ONLY`, `B_ONLY`, `UNION`, and `SYMMETRIC_DIFFERENCE` for SpiderWeb vs the frozen canonical Hub foundation while leaving semantic equivalence `UNRESOLVED` pending value/usage adjudication.

## Closure impact

The following cannot be zero after this run:

```text
P1_UNADJUDICATED > 0
RUNTIME_BROWSER_RESIDUE > 0
WORKFLOW_RESIDUE > 0
SCREENSHOT_RESIDUE > 0
ACCESSIBILITY_RUNTIME_RESIDUE > 0
```

Therefore:

```text
FEDERATION_GUI_CERTIFICATION = OPEN
100_PERCENT_ASSESSED = FAIL
```

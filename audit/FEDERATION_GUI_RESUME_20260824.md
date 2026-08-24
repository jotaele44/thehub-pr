# Federation GUI Certification — Resumed Evidence 2026-08-24

## Scope

Continuation of the immutable `federation-gui-20260822` snapshot. Product SHAs remain frozen; later remediations are evidence-only and do not rewrite the snapshot.

## Terminal rerun classifications

Frozen validation run `32595534208`:

| Repository | Frozen frontend contract | Browser/parity |
|---|---|---|
| `moneysweep-pr` | lint/unit/build PASS | **PASS** after declared `server/backend/requirements.txt` installation |
| `aguayluz-pr` | lint/unit/build PASS | **PASS** after declared `server/backend/requirements.txt` installation |
| `centinelas-pr` | lint/typecheck/unit/build PASS | **PASS** after declared backend dependency installation |
| `spiderweb-pr` | lint/typecheck/unit/build PASS | **NOT_DECLARED / OPEN** |
| `ovnis-pr` | lint/typecheck/unit/build PASS | **NOT_DECLARED / OPEN** |
| `skywatcher-pr` | lint PASS; typecheck FAIL | **NOT_DECLARED / OPEN** |
| `thehub-pr` | lint PASS; frozen typecheck FAIL | browser step not reached in frozen matrix |

## Hub F-001 remediation

PR #194 is merged (`4df6d6b5a2edb8b47d4eefa6c4a026ec0d494b14`). Its head `b5329169dd35628bcb563ded19719b0f7bda28e7` passed Hub CI, visual regression, CodeQL, Semgrep, desktop build and bounded federation checks.

The remediation intentionally changed the declared JavaScript project check to `checkJs: false`. Therefore the obsolete `baseUrl` failure is resolved, but the frozen strict-JS semantic debt is **not** reclassified as proven absent. GUI certification retains this as a coverage-definition issue until an equivalent-or-stronger typed contract is demonstrated.

## SkyWatcher F-002

**P1 / OPEN.** Frozen typecheck failure remains substantive. It includes shared-package/application integration plus application prop/API typing families. No weakening of `checkJs`, source exclusions, or suppression is accepted as closure evidence.

## Canonical semantic candidate

PR #193 remains draft/open. Current head `7a14912a817ec8fb8ca556f68f8498cbdde229d0` passes package/release-candidate CI. Its separate `Federation completion gate` audits the remote open-PR denominator; it is **not** a GUI route/state/screenshot completion gate and contributes zero GUI closure credit.

## Zero-residue arithmetic introduced in this resume

The audit controller now carries:

- `audit/federation_gui_runtime_evidence.json`
- `tools/federation_gui_certify.py`
- `.github/workflows/federation-gui-certification.yml`

Required baseline GUI screenshot cells:

```text
103 top-level navigation surfaces
× 3 browser engines
× 6 viewports
= 1,854 required baseline screenshot cells
```

Required surface-level accessibility-mode cells:

```text
103 surfaces
× 3 modes (keyboard-only, 200%-zoom, reduced-motion)
= 309 required accessibility cells
```

These counts do not yet multiply every regression state across every surface. State applicability must be explicitly mapped; no undeclared applicability assumption is used to reduce the denominator.

## Current hard gate

```text
UNASSESSED_UI_SURFACES > 0
UNRESOLVED_SCOPE_ITEMS > 0
P0_OPEN = 0
P1_UNADJUDICATED > 0
SCREENSHOT_RESIDUE > 0
ACCESSIBILITY_RESIDUE > 0
UNEXPLAINED_RESIDUE > 0
```

Therefore:

```text
FEDERATION_GUI_CERTIFICATION = OPEN
100_PERCENT_ASSESSED = FAIL
```

No green repository CI, semantic-package CI, or open-PR completion audit overrides this GUI-specific arithmetic.

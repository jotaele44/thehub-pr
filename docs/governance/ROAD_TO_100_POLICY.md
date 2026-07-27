# PRII Portfolio ROAD_TO_100 Policy

**Version:** `road_to_100_normalization_v0_2`  
**Effective when merged:** proposed; no current status or readiness gate is changed by this document.

## Purpose

ROAD_TO_100 documents must separate implementation, engineering enforcement, and operational evidence. A single unqualified completion percentage is prohibited because it conflates code existence with CI protection and real-data readiness.

## Required normalized fields

Every governed repository must publish:

1. **Implemented scope percent** — percentage of the stated product boundary that exists and works.
2. **CI-enforced maturity percent** — percentage derived from the shared 20-criterion maturity rubric.
3. **Operational data readiness percent** — evidence-based estimate of real-data coverage, intended-scope coverage, refresh/repeatability, production export, and consumer validation.
4. **Live-gate evidence depth** — D0 through D4.
5. **Last verified commit SHA** — exact commit against which the score was adjudicated.
6. **Last executed test baseline** — command context, pass/skip/fail counts, coverage where available, and whether the run was CI-identical.
7. **Current readiness/status fields** — quoted from authoritative manifests; never silently inferred or flipped by documentation.
8. **Contradictions and caveats** — every known conflict between narrative, manifest, tests, PR state, data freshness, and observed behavior.

## Evidence-depth scale

| Level | Definition |
|---|---|
| D0 | Synthetic or no production corpus; no certified live production export or end-to-end cycle. |
| D1 | Small real seed corpus or one bounded package; recurrent intended-scope intake is unproven. |
| D2 | Partial real intended-scope corpus and bounded or recurring runs; important source, freshness, or coverage gaps remain. |
| D3 | Recurring real intake and valid production export with material provenance or coverage caveats. |
| D4 | Recurring intended-scope live intake, freshness controls, production export, consumer validation, and representative product-surface coverage. |

## Status-change rule

Documentation may describe evidence but may not change `production_status`, `ready_for_hub_discovery`, `ready_for_hub_live_execution`, or equivalent gates unless all required runtime evidence exists at the cited commit. A roadmap PR must never be the sole basis for a readiness flip.

## Test-baseline rule

- Use the newest executed, reproducible baseline.
- Label interpreter, environment, and CI equivalence.
- Do not copy a historical test count forward without re-execution.
- A green workflow with no published count may be recorded as workflow success, but not converted into an invented test count.
- Private-fixture gates remain `NOT VERIFIED` until the fixture hash, run ledger, and validation outputs are available.

## Operational-readiness scoring

Operational readiness is an audit estimate, not a manifest status. It considers:

- real versus synthetic corpus;
- coverage of the repository's intended product scope;
- freshness and provenance quality;
- repeatable acquisition or refresh;
- valid production export;
- downstream consumer validation;
- evidence that the live gate is deeper than a minimal seed package.

The supporting evidence and confidence level must be stated beside the percentage.

## Repositories without a standard ROAD_TO_100 ledger

The following owned repositories currently fall outside the seven-node federation governance set:

- `Aerospace-Intelligence-Tool`
- `Faces-Font`
- `minecraft_seed`
- `Puerto-Rico-Airspace-Intelligence-Tool`
- `Puerto-Rico-Integrated-Intelligence-System`

They are not assigned completion percentages without a declared product boundary and evidence denominator. Before promotion into governed status, each must either:

1. adopt this policy and publish `docs/ROAD_TO_100_NORMALIZED.md`; or
2. declare itself `ARCHIVED`, `LEGACY_SOURCE`, `EXPERIMENTAL`, or `NON_PRODUCT` with an owner-approved disposition and successor repository where applicable.

No code or status mutation in those five repositories is authorized by this policy PR.
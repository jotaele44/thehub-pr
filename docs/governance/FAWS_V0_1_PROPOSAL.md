# Federation Analytical Workbench Standard (FAWS) v0.1.0 — proposal

Status: DRAFT; implementation and certification WITHHELD.
Operation ID: faws-v0.1.0/standard-proposal

## Discovery anchors
- Spiderweb main 139bbc67f7c266c963d74872724e1fa36d0ee6dc
- TheHub main f620d8df1b303b9829fc9187c2149939d4624138
- Mucaro main 870b46bb7f4194c6ef8a7996a1d15fed95bcf391
- Skywatcher main e566eac673aa974d8706f66f67086165d84b5e25
- Skywatcher reference draft PR 383 head 6e5a8ea6e4fb72d13a586fe2b516b7d255f6324e

## Architecture
Spiderweb owns canonical geographic data, shared rendering contracts and preset resolution; domain repositories own their profiles, presets, analytical mounts and lenses. TheHub owns cross-repository governance and execution admission; Mucaro owns agent context assembly. Reuse existing interfaces before adding new ones. No duplicate authorization, GIS implementations, or qualification registries.

A repository configuration contains identity, cartographic profile, preset library and analytical capabilities. An investigation binds input evidence, objective, selected mounts and lenses, composed visual presets and preferences. Produce independent analytical execution plan and effective rendering contract, plus evidence/provenance manifest and qualification report. These are logical products, not mandates for duplicate schemas.

An empty analytical selection supports geographic exploration, not analytical completion. Display-only changes invalidate rendering only; evidence or analytical parameter changes invalidate affected analytical descendants. Preserve source geometry and provenance. Rendering resolver must be deterministic, property-level, version-pinned, with mandatory attribution/integrity constraints outside user overrides. Lens recommendations are optional display suggestions, not analytical authorization. Neutral mode restores canonical appearance. User preferences cannot modify evidence or analytical thresholds indirectly.

## Existing infrastructure to reconcile
- Spiderweb server/frontend/src/spatial/runtime/CesiumRegionalRuntime.ts: approximate 2D/3D zoom conversion; measure parity, do not assume exact equivalence.
- TheHub docs/governance/ECPAF_V2_2_PERSISTENT_EXECUTION.md and ECPAF_V2_2_BOUNDED_DISPATCHER.md: bounded development pilot, no certified unattended unfinished coding; reuse existing admission and recovery controls.
- Mucaro schemas/context_state.schema.json: conversational context, requires a separate versioned investigation binding or compatible extension after audit.
- Skywatcher PR 383: laboratory binding only; no qualified production dispatch.

## Dependency queue
FAWS-01 audit full existing contracts and ownership; FAWS-02 Spiderweb neutral reference and renderer capability matrix; FAWS-03 shared profile/preset resolver with deterministic tests; FAWS-04 Skywatcher zero-mount workspace and independent plan identities; FAWS-05 qualify SATIM and FPIM separately; FAWS-06 integrate rendering recommendations without analytical coupling; FAWS-07 Mucaro investigation context; FAWS-08 TheHub admitted persistent execution with actual interruption tests; FAWS-09 expand AguaYLuz and OVNIS profiles; FAWS-10 exact-head CI, visual regressions, security, approved merges, downstream pins and LOCKSTEP. Independent discovery and development can proceed around blocked qualification.

## Mandatory gates
Zero required analytical mounts at boot; zero duplicate GIS engines; zero duplicate governance; zero unqualified production mounts; all applicable mandatory gates PASS; operational readiness target 99% against a frozen measured denominator. Verify geometry invariance, deterministic composition, neutral reset, independent scaling, viewport parity within documented renderer-specific tolerances, mobile/desktop regression, provenance, selective invalidation, authorization and replay. Unknown or stale evidence fails closed. No production or AFK certification until actual evidence and existing approval requirements are satisfied.

This proposal is a Git checkpoint, not an admitted queue or active persistent supervisor. No runtime configuration or production behavior is changed.

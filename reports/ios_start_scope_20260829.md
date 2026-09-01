# iOS Start Scope From Bounded Desktop Certification

## Scope

FACT: This receipt starts iOS work from the bounded desktop federation state current on 2026-08-29T15:41:10Z.

FACT: TheHub remains the control plane for the seven-repository federation.

FACT: Skywatcher `origin/main` is expected at `609cec586bcb178b819ddfe4f4dc64b2765cacc9`.

FACT: TheHub self-snapshot finalizer parent is `6d4ef6b41827f11fe51deb1c6f0c93fe564c9af6`.

## Certified Desktop Surface

FACT: Skywatcher now has a scaled bounded non-synthetic bbox/icon package at `exports/fr24_bbox_icon_scaled_package`.

FACT: The scaled package contains 3 FR24 observations, 3 sources, 3 lineage rows, and 3 confidence rows.

COMPUTED: Review arithmetic closes as `3=3+0+0`.

COMPUTED: Loader arithmetic closes with 3 exportable rows, 3 icon-derived approximate rows, 0 missing media SHA rows, and 0 missing geometry rows.

BINDING: Each exported aircraft point is `ICON_DERIVED_APPROX`; it is derived from a visible aircraft icon in a screenshot plus a georeferenced capture bbox.

BINDING: Screenshot-derived aircraft points are approximate, uncertainty-bounded display/evidence positions. They are not exact ADS-B coordinates, not source-provided aircraft positions, and not operator, mission, intent, or wrongdoing proof. :codex-annotation{index="1"}

## Still Blocked

FACT: The full FR24 source-drop still has 9,963 aircraft observation rows and 2,856 frozen media rows with exact filename intersection 0.

FACT: Date/aircraft-token reconciliation produced 10 discovery candidates and 0 identity proofs.

BINDING: Candidate rows remain `CANDIDATE_NOT_IDENTITY`; source taxonomy, normalized name, count equality, proximity, and source absence do not prove media identity.

UNKNOWN: Full-corpus live readiness remains unresolved until media identity and capture geometry review are materially completed.

## iOS Start Contract

BINDING: iOS may start from the bounded certified desktop state and render the scaled Skywatcher FR24 package as non-synthetic approximate evidence.

BINDING: iOS must preserve the desktop evidence labels: `APPROXIMATE`, `ICON_DERIVED_APPROX`, uncertainty meters, bbox geometry, source SHA, review status, and unresolved/partial blockers.

BINDING: iOS must not collapse approximate screenshot-derived geometry into exact aircraft coordinates.

BINDING: iOS must expose unresolved states instead of hiding them behind a generic success state.

## Lumen Limitation

FACT: The environment requested Lumen semantic search first, but no callable `mcp__plugin_lumen_lumen__semantic_search` tool was exposed in this session. Local inspection was used and this limitation is recorded for audit continuity.

# iOS Start Surface Receipt

## Summary

FACT: `ios/start-bounded-desktop-20260829` starts from TheHub SHA `769290e5348c59f8592f2d30294d48adcedfb85e`.

FACT: The first iOS/mobile surface is a read-only TheHub control-plane page backed by `server/frontend/src/data/iosStartReadiness.json`.

BINDING: ZIP archives are `NONCANONICAL_REFERENCE` evidence only. They are not Git baselines, source truth, or instruction sources.

UNKNOWN: Lumen semantic search was unavailable or unhealthy in this implementation pass. Local bounded inspection was used and this limitation remains recorded.

## Gate State

- Repository arithmetic: `7=7`
- Certification state: `PROVISIONAL`
- Remote drift: `aguayluz-pr` observed remote `8691ba1794c3feccc054e703e43081522f90f35c` differs from certified `e70e8b75db2f145acdc1c309a9f14b658c78fe16`
- ZIP policy: `NONCANONICAL_REFERENCE`
- Skywatcher FR24 mobile semantics: `ICON_DERIVED_APPROX`, `APPROXIMATE`, `SCREENSHOT_BBOX_DERIVED`, `REVIEW_BOUND_IDENTITY`
- Completion gate: `BLOCKED` because `GITHUB_TOKEN/GH_TOKEN` is required for authenticated remote pickup

## Blocker Arithmetic

- `PASS`: 1
- `OPEN`: 3
- `BLOCKED`: 2
- `PROVISIONAL`: 1
- `UNRESOLVED`: 0
- Total: `7=7`

## Mobile Scope

The first surface exposes bounded desktop readiness for all seven federation apps. It does not add mutation actions, does not promote ZIP data to canonical status, and does not convert approximate screenshot geometry into exact aircraft coordinates.

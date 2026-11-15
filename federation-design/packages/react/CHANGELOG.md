# Changelog

All notable changes to `@pr-federation/react`. Versions follow semantic
versioning; each entry states its impact class, as the governance section of
`docs/FEDERATION_DESIGN_SYSTEM_V1.md` requires. Versions before 0.6 predate
this file; their scope is recorded in `docs/FEDERATION_DESIGN_SYSTEM_v0_4_CANDIDATE.md`.

## 0.6.0-rc.1 (unreleased)

Impact: **minor, additive.** No export, class name or custom property is
removed or changed. Tokens stay at 2.0.0.

### Added

- Navigation registry: `defineFederationNav`, `flattenFederationNav` and
  `matchFederationNavItem`, also importable without React from
  `@pr-federation/react/nav`.

### Changed

- The API snapshot is now checked against the package's real exports in both
  directions. Six GIS exports that shipped outside the API contract are
  recorded under a new `unfrozenExports` key in `api-snapshot.json`.
- The release manifest hashes every shipped source file.

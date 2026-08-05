# Federation Design System v0.4 Candidate

## Scope

Package-only foundation built from `FEDERATION_FRONTEND_AUDIT_v0_1`. No application shell, route, domain component, API, data contract, offline export or producer repository is migrated in this candidate.

## Added

- Token schema v2 and expanded semantic/layout/accessibility token namespaces
- Separate operational, workflow, evidence-tier, confidence, provenance, freshness and async-state axes
- Evidence, confidence, provenance, freshness and source badges
- Loading, error, filtered-empty, offline, degraded, partial and stale state components
- Accessibility-enforcing icon button
- Public API snapshot
- Repository-neutral test-harness contract
- Deterministic release manifest with source SHA-256 hashes
- Release workflow checks for unit contracts, accessibility source invariants, WCAG AA contrast, reduced motion, package contents, checksum and exact immutable tag/version matching

## Compatibility

The candidate retains all v0.3 component exports, status aliases, CSS class aliases and semantic CSS variables. It introduces no consumer edits. The package version is `0.4.0-rc.1`; no release or tag is authorized by this PR.

## Non-goals

- No AppShell implementation yet
- No table/form/dialog or map renderer packages
- No consumer package bumps
- No local CSS deletion in producer repositories
- No TheHub application migration
- No Skywatcher, AguaYLuz or Spiderweb migration

## Promotion gates

1. Package CI is green.
2. Tarball and checksum artifact are retained.
3. API snapshot is reviewed as additive.
4. MoneySweep pilot plan is approved.
5. Release tag creation receives explicit authorization.

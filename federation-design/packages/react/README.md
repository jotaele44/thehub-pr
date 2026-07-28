# @pr-federation/react

Shared PRII federation design-system foundation. The v0.4 release candidate adds a versioned token schema, separate semantic state axes, evidence/provenance badges, a complete async-state family, an accessibility-first icon button, a repository-neutral test-harness contract, and deterministic release metadata.

## Package imports

| Import | Content |
|---|---|
| `@pr-federation/react` | React primitives and semantic resolvers |
| `@pr-federation/react/semantics` | Dependency-free semantic state model |
| `@pr-federation/react/styles.css` | Canonical federation CSS |
| `@pr-federation/react/tokens.json` | Token source v2 |
| `@pr-federation/react/tokens.schema.json` | Draft 2020-12 token schema |
| `@pr-federation/react/test-harness.json` | Consumer acceptance contract |
| `@pr-federation/react/api-snapshot.json` | Public API freeze |
| `@pr-federation/react/release-manifest.json` | Deterministic source hashes and expected immutable tag |

## Semantic model

Applications pass domain meaning, not colors:

- operational state
- workflow state
- evidence tier T1-T4
- confidence
- provenance
- freshness
- async/data state

The package maps those values to presentation tones. Existing v0.3 status aliases and component exports remain available.

## Verification

```bash
npm test
npm run verify
npm pack
```

`verify` checks the API snapshot, token/schema alignment, accessibility source contracts, WCAG AA contrast for light and dark token pairs, reduced-motion behavior, and the consumer test matrix. `npm pack` creates a self-contained tarball and deterministic release manifest.

## Pinning and release policy

Producer applications consume an immutable GitHub Release tarball. Never pin `main`, never force-move a tag, and migrate one repository at a time. The candidate's expected tag is `federation-design-v0.4.0-rc.1`; no tag or release is created by the implementation PR.

TheHub now consumes the package and canonical CSS directly. Consumer migration remains a separate vector; this package change does not edit application shells, routes, APIs, data contracts, offline exports, or producer repositories.

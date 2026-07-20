# @pr-federation/react

Shared PRII federation design-system package: the canonical design **tokens**
(`federation-design/tokens/federation.tokens.json`), the **CSS layer**
(`federation-design/styles/federation.css` — `--fd-*` variables, `[data-theme]`
and per-repo `[data-repo]` accents, `.fd-*` primitives), and thin **React
wrappers** (`FederationButton`, `FederationPanel`, `FederationStatusBadge`,
`FederationEmptyState`).

This is the Phase-3 dedup vehicle from
[`docs/adr/0001-federated-engines-single-hub.md`](../../../docs/adr/0001-federated-engines-single-hub.md)
and [`docs/FEDERATION_DESIGN_SYSTEM_V1.md`](../../../docs/FEDERATION_DESIGN_SYSTEM_V1.md):
one design system, consumed by the hub app and the six producer frontends, so the
duplicated-and-drifting shadcn kits converge.

## What ships in the tarball

`npm pack` runs `scripts/prepack.mjs`, which copies the canonical CSS and tokens
into `./dist/`, so the packed tarball is self-contained:

| Import | Resolves to |
|---|---|
| `@pr-federation/react` | `./src/index.jsx` (React wrappers) |
| `@pr-federation/react/styles.css` | `./dist/federation.css` |
| `@pr-federation/react/tokens.json` | `./dist/federation.tokens.json` |

The consuming app sets `data-theme` and `data-repo` on the root element to pick
the theme and per-repo accent (e.g. `document.documentElement.dataset.repo = 'ovnis-pr'`).

## Consuming it (producers) — pinning policy

Delivered exactly like the Python `prii_maintenance` package: **hub-hosted,
pinned to an immutable git reference, bumped one repo at a time.** Because npm has
no equivalent of pip's `#subdirectory=`, JS consumers pin the **release tarball**
published for a tag, not a `git+` URL:

```jsonc
// <producer>/<frontend>/package.json
"dependencies": {
  "@pr-federation/react": "https://github.com/jotaele44/thehub-pr/releases/download/federation-design-v0.1.0/pr-federation-react-0.1.0.tgz"
}
```

- Pin to a **release tag** (`federation-design-vN`) — never to `main` or a
  moving ref.
- **Never force-move an existing tag.** Cut `vN+1` on a new commit and let each
  producer bump deliberately: edit the one dependency line, open one PR, re-run
  that producer's frontend build + tests.
- The pin lives in exactly one place per repo — its frontend `package.json`.

## Releasing (maintainer)

1. Land the token/CSS/component change on `main`.
2. Tag it: `git tag federation-design-v<N> && git push origin federation-design-v<N>`.
3. [`.github/workflows/federation-design-release.yml`](../../../.github/workflows/federation-design-release.yml)
   runs `npm pack` (invoking `prepack`) and attaches the tarball to the GitHub
   Release for that tag.

Bump `version` in `package.json` in the same change so the tarball filename tracks the tag.

## Status

- **thehub-pr** (reference) currently loads the CSS layer via a local copy at
  `server/frontend/src/styles/federation.css`. Repointing it at this package and
  reconciling that copy's dark-only drift against the canonical light-first +
  `[data-theme]` source is tracked as the next step (Increment 3b) — it needs a
  visual-regression check, so it is intentionally out of this packaging change.
- Producer migration follows the order in
  [`docs/FEDERATION_FRONTEND_STACK_AUDIT_V1.md`](../../../docs/FEDERATION_FRONTEND_STACK_AUDIT_V1.md).

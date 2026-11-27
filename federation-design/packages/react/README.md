# @pr-federation/react

Shared PRII federation design-system foundation: a versioned token schema, separate semantic state axes, evidence and provenance badges, a complete async-state family, an accessibility-first icon button, GIS dataset components, a repository-neutral test-harness contract, and deterministic release metadata.

The rules for building a GUI on this package are in [`docs/FEDERATION_GUI_STANDARD.md`](../../../docs/FEDERATION_GUI_STANDARD.md). What changed in each version is in [`CHANGELOG.md`](CHANGELOG.md).

## Package imports

| Import | Content |
|---|---|
| `@pr-federation/react` | React primitives and semantic resolvers |
| `@pr-federation/react/semantics` | Dependency-free semantic state model |
| `@pr-federation/react/nav` | Dependency-free navigation registry: validation, active matching, flattening |
| `@pr-federation/react/styles.css` | Canonical federation CSS, including the shell |
| `@pr-federation/react/shadcn-bridge.css` | Opt-in: shadcn variables as aliases of the federation tokens (read the note below before importing) |
| `@pr-federation/react/tokens.json` | Token source v2 |
| `@pr-federation/react/tokens.schema.json` | Draft 2020-12 token schema |
| `@pr-federation/react/test-harness.json` | Consumer acceptance contract |
| `@pr-federation/react/api-snapshot.json` | Public API freeze |
| `@pr-federation/react/release-manifest.json` | Deterministic source hashes and expected immutable tag |

## Application shell

`FederationAppShell` is the one shell every federation GUI uses
(FEDERATION_GUI_STANDARD.md §4). A repository supplies a navigation registry
and content for the slots; it does not fork or restyle the shell.

```jsx
import { FederationAppShell, FederationStatusBar, defineFederationNav } from '@pr-federation/react'
import { Link, useLocation } from 'react-router-dom'

const nav = defineFederationNav([
  { label: 'Records', items: [
    { label: 'Cases', path: '/cases', icon: CasesIcon, capabilityId: 'cases' },
    { label: 'Sources', path: '/sources', icon: SourcesIcon, capabilityId: 'sources' },
  ] },
])

function Layout({ children }) {
  const { pathname } = useLocation()
  return (
    <FederationAppShell
      nav={nav}
      current={pathname}
      renderLink={({ item, active, href, ...anchor }) => <Link to={href} {...anchor} />}
      focusMainOnNavigate
      header={<Brand />}
      statusBar={<FederationStatusBar>Backend online</FederationStatusBar>}
    >
      {children}
    </FederationAppShell>
  )
}
```

- The shell knows nothing about routing. `current` is the current path, and
  `renderLink` draws each link with the host's router. An application without a
  router gives items an `id` instead of a `path` and handles `onSelect`.
- Exactly one entry is current: the longest matching path prefix wins. `end`
  makes an item match exactly; `match` adds prefixes.
- Below `mobileBelow` (`'tablet'`, 768px, by default; `'desktop'`, 1280px) the
  sidebar becomes a bottom bar of at most five entries, the fifth being "More".
- `FederationInspectorPanel`, in the `inspector` slot, is a column beside main
  at 1280px and above and a modal drawer below.
- `flattenFederationNav(nav)` lists every entry for a command palette.

### Pinned and recent groups

A registry group with `kind: 'pinned'` or `kind: 'recent'` declares no items.
It reserves a place for entries the host supplies at render time:

```jsx
const nav = defineFederationNav([
  { label: 'Records', items: [/* ... */] },
  { kind: 'pinned', label: 'Pinned' },
  { kind: 'recent', label: 'Recent', maxItems: 5, overflow: 'more-submenu' },
])

<FederationAppShell
  nav={nav}
  collections={{
    pinned: [{ id: 'case-12', label: 'Budget review', path: '/cases/12',
      status: { kind: 'spinner', tone: 'info', label: 'Running' },
      actions: [{ id: 'rename', label: 'Rename', onSelect: openRename }] }],
    recent: recentCases,
  }}
/>
```

- The shell stores nothing. The application owns the lists, where they are
  saved, and what each action does.
- `maxItems` (1 to 50, default 5) entries are shown. `overflow` decides the
  rest: `'more-submenu'` puts them behind a "More (n)" disclosure, `'scroll'`
  shows all of them in a box sized to `maxItems`, `'none'` drops them.
- A collection with no entries is not drawn. Two groups of the same kind need
  an `id` each, which is then the key in `collections`.
- An entry that is open is marked `aria-current="true"`. It is never a second
  current page; only a registry item is `aria-current="page"`.
- On a small screen, collections never take a slot on the bottom bar. They
  appear behind "More".

## Controls

| Component | Use |
|---|---|
| `FederationDialog` | A modal on the native `<dialog>`. Requires `title`. Focus goes to the element marked `data-autofocus` and returns to the opener. |
| `FederationRenameDialog` | Rename something the person named. `onRename(name)` does the write; if it throws, the message is shown and the dialog stays open. |
| `FederationTextField` | A labelled input. `help` and `error` are tied to it. |
| `FederationMenu` | A button that opens a menu of `items`: `[{ id, label, onSelect, disabled, destructive }]`. |
| `FederationItemMenu` | The "…" menu of one list item. Requires `itemLabel`; its name is "Actions for <item>". |
| `FederationStatusMark` | A dot, spinner or alert. Requires `label`, the status in words. |
| `FederationScrollRegion` | A named scrolling box that becomes a tab stop when nothing inside it can take focus. |
| `FederationResponsiveLabel` | A button label that is clipped, not removed, on small screens, so it stays the button's name. |

Rename is for objects whose name the person owns. A record's identity or an
evidence citation is not renamed with it.

These exports are unfrozen: their API may change before 0.6.0.

## shadcn bridge

`shadcn-bridge.css` makes the shadcn variables (`--background`, `--primary`,
`--border`, `--sidebar-*`, `--chart-*`, ...) aliases of the federation tokens, so
an application stops defining its own palette.

It is opt-in and has one hazard. shadcn's older convention stores bare HSL
channels and wraps them as `hsl(var(--background))`; the bridge provides
complete colours. **Importing it while the application still wraps the variables
in `hsl()` makes every one of them invalid.** In the same change:

1. Import it after `styles.css`.
2. Consume the variables as colours:
   - Tailwind 4: `@theme inline { --color-background: var(--background); /* ... */ }`
   - JS config: `background: 'var(--background)'`
3. Delete the application's own values for those variables.

Fonts are not bridged.

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

`verify` checks the API snapshot against the package's real exports in both directions, token/schema alignment, accessibility source contracts, WCAG AA contrast for light and dark token pairs and for the accent roles of every repository, reduced-motion behavior, and the consumer test matrix. `npm pack` creates a self-contained tarball and deterministic release manifest.

## Pinning and release policy

Producer applications consume an immutable GitHub Release tarball. Never pin `main`, never force-move a tag, and migrate one repository at a time. The expected tag for a version is `federation-design-v<version>` (recorded in the release manifest); no tag or release is created by an implementation PR.

TheHub consumes the package source and canonical CSS directly. Consumer migration is a separate, per-repository change (FEDERATION_GUI_STANDARD.md §12); a package change does not edit application shells, routes, APIs, data contracts, offline exports, or producer repositories.

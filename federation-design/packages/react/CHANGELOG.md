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

- Application shell components: `FederationAppShell`, `FederationModuleNav`,
  `FederationMobileNav`, `FederationInspectorPanel` and `FederationStatusBar`.
  The shell is router-agnostic, renders a skip link and landmarks, marks
  exactly one current page, and switches to a bottom bar of at most five
  entries below 768px (or 1280px). No dependency is added; overlays are
  native `<dialog>` elements.
- `styles/shell.css`, included in `styles.css`. It defines custom properties
  that the tokens had but the CSS did not (`--fd-layout-*`, `--fd-layer-*`,
  `--fd-breakpoint-*`), a legible `--fd-accent-strong`, and the shell layout.
  Every rule is scoped to an `.fd-*` class, so existing pages are unaffected.

- `shadcn-bridge.css`, an opt-in export that defines the shadcn variables as
  aliases of the federation tokens. Not included in `styles.css`. Adopting it
  requires consuming those variables as colours instead of wrapping them in
  `hsl()`; see the README.

- Control primitives, exported as unfrozen (their API may still change before
  0.6.0): `FederationDialog`, `FederationRenameDialog`, `FederationTextField`,
  `FederationMenu`, `FederationItemMenu`, `FederationStatusMark`,
  `FederationScrollRegion` and `FederationResponsiveLabel`. Hand-written on
  native elements; no dependency is added. They store nothing and make no
  request: the host passes the data and performs the writes.
- Pinned and recent navigation groups. `defineFederationNav` accepts a group
  with `kind: 'pinned'` or `kind: 'recent'` (`maxItems`, `overflow`) and no
  items; `FederationAppShell`, `FederationModuleNav` and `FederationMobileNav`
  take the entries at render time through `collections`. An entry may carry a
  status mark and a menu of actions.
- `styles/controls.css`, included in `styles.css`. Every rule is scoped to an
  `.fd-*` class.
- Two custom properties beside `--fd-accent-strong`: `--fd-accent-contrast`
  (text on a solid accent fill) and `--fd-focus-ring`.
- `--fd-repo-accent-<repository>` custom properties, one per repository, equal
  to the `repoAccents` tokens, so an application can show another repository's
  accent without a literal colour.

- Controls an application places in the shell header are held to the 44px
  touch-target minimum by the shell stylesheet.

### Fixed

- `.fd-button--primary` and the default focus outline no longer draw with the
  raw repository accent, which was below 4.5:1 behind white text and below 3:1
  as a ring for several repositories. The button is now `--fd-accent-strong`
  with `--fd-accent-contrast` text and the ring is `--fd-focus-ring`. A test
  holds every repository and theme to those ratios. **Visible change:** the
  primary button is darker than the brand accent in the light theme and
  lighter in the dark theme, for every repository.
- `FederationExportMenu` is built on `FederationMenu`. It gains arrow keys,
  Home and End, Escape, close on an outside click and focus return. Its class
  names inside the open menu changed (`fd-menu__list`, `fd-menu__item`).
- `FederationDatasetGrid` becomes a tab stop while it has rows to scroll, so
  it can be scrolled from the keyboard, and its colours follow the theme.
- The sans font stack now leads with `"Inter Variable"`, the family
  `@fontsource-variable/inter` registers. It named only `Inter`, which no
  application loads, so text rendered in a system fallback. The
  `typography.fontFamily` token is corrected to match; the token version stays
  2.0.0 because this corrects a value rather than changing the token set.

### Known issues

- The raw repository accent (`--fd-accent`) is below 4.5:1 as text for several
  repositories. Nothing in the packaged stylesheet draws with it any more; an
  application that uses it directly for text is still affected.
- A pinned or recent entry removed by one of its own actions leaves focus on
  the page body; the host decides where focus goes next.
- The fixture matrix drives the control primitives from the keyboard. They
  have not been used with a screen reader or on a touch device.
- `gis.css` is not part of the packaged `styles.css`.
- The bridge derives on-accent, destructive and chart colours from existing
  tokens, and does not bridge fonts. These need real roles in tokens 2.1.

### Changed

- The API snapshot is now checked against the package's real exports in both
  directions. Six GIS exports that shipped outside the API contract are
  recorded under a new `unfrozenExports` key in `api-snapshot.json`.
- The release manifest hashes every shipped source file.

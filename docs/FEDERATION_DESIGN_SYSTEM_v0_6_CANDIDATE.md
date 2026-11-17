# Federation Design System v0.6 Candidate

## Scope

The shared application shell specified in
[`FEDERATION_GUI_STANDARD.md`](FEDERATION_GUI_STANDARD.md) §4
([ADR 0014](adr/0014-spoke-guis-are-complete-domain-apps.md)), added to
`@pr-federation/react` as `0.6.0-rc.1`. Package only: no application shell,
route, page, API or producer repository is migrated by this candidate.

Semantic-version impact: **minor, additive.** No export, class name or custom
property is removed or changed. Tokens stay at 2.0.0.

## Added

- A navigation registry (`defineFederationNav`, `flattenFederationNav`,
  `matchFederationNavItem`), also importable without React from
  `@pr-federation/react/nav`.
- `FederationAppShell`, `FederationModuleNav`, `FederationMobileNav`,
  `FederationInspectorPanel`, `FederationStatusBar`.
- `styles/shell.css` in the packaged stylesheet: custom properties for the
  layout, layering and breakpoint tokens, `--fd-accent-strong`, and the shell
  layout. Every rule is scoped to an `.fd-*` class.
- `shadcn-bridge.css`, a separate opt-in export that defines the shadcn
  variables as aliases of the federation tokens.
- A changelog, `federation-design/packages/react/CHANGELOG.md`.
- Control primitives, unfrozen: `FederationDialog`, `FederationRenameDialog`,
  `FederationTextField`, `FederationMenu`, `FederationItemMenu`,
  `FederationStatusMark`, `FederationScrollRegion`,
  `FederationResponsiveLabel`, with `styles/controls.css` in the packaged
  stylesheet.
- Pinned and recent navigation groups, fed at render time through
  `collections`.

## Changed

- The API snapshot is checked against the package's real exports in both
  directions. Six GIS exports that had shipped outside the API contract are
  recorded as `unfrozenExports`.
- The release manifest hashes every shipped source file.
- `.fd-button--primary` and the default focus outline use the legible accent
  roles (`--fd-accent-strong`, `--fd-accent-contrast`, `--fd-focus-ring`)
  instead of the raw repository accent.
- `FederationExportMenu` is built on `FederationMenu`; `FederationDatasetGrid`
  can be scrolled from the keyboard and follows the theme.

## Compatibility

All 0.5 exports, classes and custom properties remain. The shell stylesheet is
part of `styles.css` but inert for a page that does not render the shell: it
adds custom properties and `.fd-*`-scoped rules only, which a test enforces,
and no federation frontend uses any of the new names. Two changes are not
inert: the primary button and the default focus outline change colour for any
page that loads the stylesheet. The Hub frontend loads it from source, so it
shows that change as soon as this is merged; the other repositories pin a
released tarball and are unaffected until they move their pin. The bridge changes
nothing until an application imports it. React 18 and 19 are supported; no
dependency is added.

Browser floor: `<dialog>` with `:modal`, and `color-mix()`. That is Firefox
113, Safari 16.2 and Chrome 111, below the floor Tailwind 4 already sets.

## Verification

- Package: unit tests for the registry logic, source contracts for the
  components, and token-equality, scoping and contrast tests for both
  stylesheets (`npm test`, `npm run verify`, `npm pack`).
- Rendering: six shell fixtures in the fixture lab, in Chromium, Firefox and
  WebKit at six widths from 320px to 1920px. Each cell asserts the shell's
  contract: no horizontal overflow, the skip link first and landing on main,
  one primary navigation with one current page, at most five bottom-bar
  entries of at least 44 by 44 pixels, "More" opening and closing with focus
  returned, and the inspector's docked and modal behaviour.
- The 32 existing component fixtures are unchanged and still pass.
- Controls: one fixture page driven from the keyboard at the same six widths
  (menu keys, rename validation and failure, dialog focus, scroll regions,
  pinned and recent groups), and an axe scan for every repository accent in
  both themes at two widths, at rest, with a menu open and with the rename
  dialog showing an error. Zero critical or serious findings is required.

## Known issues

- The raw repository accent (`--fd-accent`) is below 4.5:1 as text for several
  repositories. Nothing in the packaged stylesheet draws with it any more.
- The control primitives have not been used with a screen reader or on a touch
  device.
- `--fd-accent-strong` is darker than the brand accent in the light theme for
  every repository, including those whose accent was already legible.
- The bridge derives on-accent, destructive and chart colours from existing
  tokens. They need real roles in tokens 2.1.
- Fonts are not bridged: `--fd-font-sans` names a different family from the
  one the applications load.
- `gis.css` is not part of the packaged stylesheet.
- No automated accessibility-rule (axe) run covers the shell fixtures yet; the
  control fixtures are covered.

## Non-goals

- No top-navigation placement and no collapsed icon rail.
- No migration of the Hub's own layout, and no producer adoption. Both are
  separate changes; the Hub goes first so the reference implementation uses
  the shell.
- No token change.
- No table, form or dialog primitives beyond what the shell needs.

## Promotion gates

1. Package CI and the fixture matrix are green.
2. The API snapshot is reviewed as additive.
3. The Hub's layout is migrated onto the shell and its visual baselines are
   reviewed.
4. Release tag creation receives explicit authorization. This change creates
   no tag.

The design-system governance asks for validation against `thehub-pr` and one
map-heavy repository. For a shell with no map dependency, that validation
happens at the Hub migration and at the first producer adoption.

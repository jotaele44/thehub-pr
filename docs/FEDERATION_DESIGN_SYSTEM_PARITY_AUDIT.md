# Federation Design-System Parity Audit

**Date:** 2026-08-24
**Scope:** all 7 PRII frontends (moneysweep-pr, thehub-pr, spiderweb-pr, skywatcher-pr, ovnis-pr,
centinelas-pr, aguayluz-pr)
**Inputs:** each repo's `docs/design-system-usage.json`, produced by that repo's own Phase 2
a11y/design-system audit (see each repo's `docs/A11Y_AUDIT.md` for the live verification behind
these numbers). Verbatim copies are checked in at `docs/design-system-parity/<repo>.json`.

This document does not re-run any tooling — it is a synthesis of the seven per-repo surveys,
looking across them for the question no single-repo audit could answer: do the seven dashboards
actually share a common design system, or does each repo maintain a parallel, independently
-evolving implementation of the same handful of UI concepts?

**Short answer: mostly the latter.** Every repo depends on the same npm package name
(`@pr-federation/react`, six of seven do — see below), but in practice each repo's buttons,
badges, dialogs, and toggles are overwhelmingly local shadcn/ui primitives or bespoke JSX, not
the shared package's components. The one real exception — `FederationEmptyState` — is discussed
in detail below, precisely because it's the exception and not the rule.

## 1. Version skew

| Repo | `@pr-federation/react` spec | Resolved version | Ships `test-harness.contract.json`? |
|---|---|---|---|
| thehub-pr | `file:../../federation-design/packages/react` (source of truth) | 0.4.1 | ✅ yes |
| moneysweep-pr | GitHub release tarball | 0.4.1 | ✅ yes |
| aguayluz-pr | GitHub release tarball | 0.4.0 | ✅ yes |
| skywatcher-pr | GitHub release tarball | 0.3.0 | ❌ no |
| ovnis-pr | GitHub release tarball | 0.3.0 | ❌ no |
| centinelas-pr | GitHub release tarball | 0.3.0 | ❌ no |
| spiderweb-pr | *(none — no dependency)* | *(n/a)* | *(n/a — doesn't consume the package at all)* |

**3 of 7 repos (skywatcher-pr, ovnis-pr, centinelas-pr) are pinned to v0.3.0**, which predates the
`test-harness.contract.json` export (only shipped from `v0.4.0-rc.1` onward) and exports a
materially narrower symbol set than the current convention — each of those three repos'
`design-system-usage.json` independently confirms the same missing symbols (`FederationIconButton`,
`FederationSemanticBadge`, the evidence-tier/confidence/provenance/freshness/source badge family,
and the full loading/error/empty/offline/degraded/partial/stale/async state family beyond the
plain `FederationEmptyState`). Any federation-wide tooling that assumes every producer can resolve
the shared contract file will fail on exactly these three repos until they're bumped.

**spiderweb-pr has no dependency on the package at all** — confirmed absent, not merely unchecked
(no entry in `package.json`, no import anywhere in `src/`). It's the one PRII frontend with a fully
independent, hand-written design layer (`styles/federation.css` + `styles/app.css`), including its
own `--fd-*` CSS custom-property namespace that happens to echo the shared package's naming
convention without actually depending on it.

## 2. shadcn/ui adoption

| Repo | `components.json` present | Style | Local `ui/` primitive count |
|---|---|---|---|
| ovnis-pr | ✅ | new-york | 49 |
| skywatcher-pr | ✅ | new-york | 48 |
| aguayluz-pr | ✅ | new-york | 11 |
| centinelas-pr | ✅ | new-york | 9 |
| moneysweep-pr | ✅ | new-york | 8 |
| thehub-pr | ✅ | new-york | 18 |
| spiderweb-pr | ❌ | *(n/a)* | 0 — hand-written throughout |

All six React repos that use shadcn agree on the `new-york` style variant, which is at least one
point of real, if incidental, consistency. But the *size* of each repo's generated primitive set
varies by nearly 6x (8 to 49 files) with no relationship to app complexity that tracks cleanly —
ovnis-pr and skywatcher-pr generated close to the full shadcn catalog and use only a fraction of it
live (ovnis-pr's own audit found only `badge`, `input`, `select`, `sheet`, `table`, `tabs` actually
wired into the running app out of 49 generated files).

## 3. Per-control source-of-truth matrix

For each of the five controls every repo's audit was asked to map, this table shows what actually
renders it live — the federation package, a local shadcn primitive, or bespoke/hand-written code.
"Mixed" means more than one source is used for the same control type within one repo.

| Repo | Button | Dialog/Modal | Badge/Status | Toggle | Empty state |
|---|---|---|---|---|---|
| moneysweep-pr | Mixed: `FederationButton` (3, in `QueryBoundary.jsx`) + bespoke `<button>` + unused local shadcn | Local shadcn `Sheet` (Radix) | Mixed: `FederationStatusBadge` (11) + local shadcn `Badge` | Local shadcn `Select` (the control that fails axe `button-name`) | **Package** (`FederationEmptyState` + 6 sibling `Federation*State` variants, centralized in `QueryBoundary.jsx`) |
| thehub-pr | Local shadcn (`FederationButton`: 0 usages) | Local shadcn `Dialog` + `Sheet` (both Radix) | Bespoke (`StatusChip.jsx`, ~35 call sites; `LinkageBadge.jsx`) | Local shadcn `Switch` (20×36px, under touch-target min) | **Package** (`FederationEmptyState` — the *only* `Federation*` component used anywhere in this repo) |
| spiderweb-pr | Hand-written (`.act`/`.navbtn`/`.tab` utility classes, no shared `<Button>`) | None present (Inspector side panel is the closest analog — always-visible, not a dismissible dialog) | Hand-written (`Badges.tsx`: `TierBadge`, `Pill`, etc.) | Hand-written (raw `<button aria-pressed>` / `data-on`/`data-active`) | Hand-written (`.empty-state` CSS class) |
| skywatcher-pr | Local shadcn (10 files; `FederationButton`: 0 usages) | Effectively none reachable by a user — shadcn `Dialog` only reached transitively via an unmounted command palette; the real mobile-nav overlay is hand-rolled with no `role="dialog"`/`aria-modal`/focus trap | Local wrapper (`StatusChip.jsx`, 21 sites) around the package's `federationTone()` *helper function*, not `FederationStatusBadge`; shadcn `Badge` generated but 0 imports | *(no dedicated toggle component; see mobile-nav overlay under Dialog)* | **Package** (`FederationEmptyState`, wrapped by local `EmptyState.jsx`, 9 pages) |
| ovnis-pr | Bespoke raw `<button>` (shadcn `Button` generated but only reached internally by unwired components; `FederationButton`: 0 usages) | Unused — shadcn `Dialog` reachable only via an unwired command palette; the real Case Detail modal uses shadcn `Sheet` instead | Mixed: local shadcn `Badge` for evidence-tier/confidence pills + one hand-rolled `<span>` using `federationTone()` directly (`FederationStatusBadge`: 0 usages) | Unused (`ui/toggle.jsx` only reached via an unwired `toggle-group`) | **Package** (`FederationEmptyState` — the only `Federation*` component actually rendered) |
| centinelas-pr | Mixed: local shadcn `Button` (1 site: "Entregar") + raw `<button>` everywhere else (`FederationButton`: 0 usages) | **None implemented anywhere** — no shadcn dialog primitive, no modal/overlay pattern found by repo-wide search | Split: `DomainBadge`/`EvidenceTierBadge` wrap shadcn `Badge`; `ConfidenceBadge`/`HandoffStatusBadge` bypass shadcn *and* the package's `FederationStatusBadge` by calling `federationTone()` directly on a raw `<span>` | Raw `<button>` with no `aria-pressed` (Theme/Language toggles in `Header.jsx`) | **Package** (`FederationEmptyState`, wrapped by `ListState.jsx` — the only `Federation*` component used) |
| aguayluz-pr | Local shadcn (8 sites; `FederationButton`/`FederationIconButton`: 0 usages) | Local shadcn `Sheet` (the only Radix-Dialog surface; no `dialog.jsx` exists) | Local shadcn `Badge` (9 sites); federation badge variants: 0 usages | Bespoke (shadcn `Button variant="outline"` + manual `aria-pressed`; `@radix-ui/react-toggle` is a declared but unused dependency) | **Package** (`FederationEmptyState`, wrapped by `PanelState.jsx`) |

## 4. Concrete inconsistencies

1. **`FederationEmptyState` is the design system's one real success story.** It is the only
   `Federation*` component consumed live by all six repos that depend on the package at all
   (every repo except spiderweb-pr, which has no dependency). Every one of those six repos wraps
   it in its own locally-named component (`EmptyState.jsx`, `QueryState.jsx`, `ListState.jsx`,
   `PanelState.jsx`) rather than importing it directly at call sites, but the underlying primitive
   really is shared. This is the pattern the rest of the system should be measured against.

2. **`FederationButton` has essentially zero adoption.** Of seven repos, only moneysweep-pr
   actually renders it (3 call sites, all inside one shared `QueryBoundary.jsx`). The other five
   package-consuming repos all render buttons through a local shadcn primitive or bespoke raw
   `<button>` instead, despite `FederationButton` being exported and available since v0.3.0 in
   every one of them. Buttons are the single most common interactive control in every app — this
   is the biggest missed-consistency opportunity by sheer surface area.

3. **`FederationStatusBadge` is used by exactly one repo (moneysweep-pr, 11 sites).** Every other
   repo either uses a local shadcn `Badge`, bespoke JSX (thehub-pr's `StatusChip`, spiderweb-pr's
   `Badges.tsx`), or — notably, in skywatcher-pr, ovnis-pr, and centinelas-pr — calls the package's
   `federationTone()` *helper function* directly on a raw `<span>`, consuming the design system's
   CSS/token layer while explicitly bypassing its component. That's not simple non-adoption; it's
   evidence that repos found the underlying styling useful but the component wrapper itself
   insufficient or inconvenient, and worked around it the same way independently, three times.

4. **`FederationThemeProvider`/`useFederationTheme` have zero adoption across all seven repos** —
   including thehub-pr, the design system's own source-of-truth repo. Three repos implement real,
   working light/dark theme toggles (thehub-pr, spiderweb-pr, centinelas-pr), and every one of them
   built its own local `ThemeProvider`/`useTheme` from scratch rather than using the package's.
   thehub-pr's own `lib/theme.jsx` even says so directly in its header comment: it "mirrors the
   canonical federation `ThemeProvider`... but is vendored locally." The other four repos
   (moneysweep-pr, skywatcher-pr, ovnis-pr, aguayluz-pr) are dark-only by hardcoded design, with no
   toggle and no theme-provider usage at all. Net result: a cross-cutting primitive that exists
   specifically to solve a problem three different repos solved independently anyway.

5. **The package ships no Dialog/Modal primitive at all**, and the resulting gap is filled
   inconsistently and, in two repos, not filled at all. moneysweep-pr, thehub-pr, ovnis-pr, and
   aguayluz-pr all use a real, accessible, Radix-backed local `Sheet` or `Dialog`. skywatcher-pr's
   only modal-adjacent surface is a hand-rolled mobile-nav overlay with none of Radix's
   accessibility guarantees (no `role="dialog"`, no `aria-modal`, no focus trap, no Escape
   handling — flagged as a live a11y finding in that repo's own audit). centinelas-pr and
   spiderweb-pr have **no dialog/modal control anywhere in the codebase** — not a broken one, an
   absent one.

6. **No repo has a fully accessible, shared toggle/switch pattern.** thehub-pr is the only repo
   with a dedicated `Switch` primitive, and even that fails the federation's own 44px touch-target
   requirement (20×36px). Every other repo hand-rolls toggles as plain buttons, several without
   `aria-pressed`, and two repos (ovnis-pr, aguayluz-pr) have `@radix-ui/react-toggle` installed as
   a dependency and never use it.

7. **Version skew compounds all of the above.** The three v0.3.0-pinned repos (skywatcher-pr,
   ovnis-pr, centinelas-pr) can't adopt several of the components discussed here even if they
   wanted to — `FederationIconButton`, the full badge-variant family, and the loading/error/empty
   state siblings beyond the plain `FederationEmptyState` simply don't exist in their installed
   package version. Closing the adoption gaps above requires closing the version gap first for
   these three.

## 5. What this means for `FEDERATION_DESIGN_SYSTEM_V1_ROLLOUT`

thehub-pr's own governance tracking (`federation-pickup.yml`) lists an open, blocked initiative to
roll a shared design system out to all 7 frontends
(`seven_repository_frontend_rollout_requires_repo_specific_implementation_and_visual_acceptance`).
This audit is direct evidence for what "repo-specific implementation" actually means today: six
independent button implementations, six independent badge implementations, at least four
independent dialog/sheet implementations (two repos with none), three independent from-scratch
theme providers duplicating a primitive the package already exports, and three repos that can't
even resolve the shared acceptance contract at their current version pin. Rollout work has real,
concrete adoption gaps to close, not just a version bump to perform — closing the version gap on
the three v0.3.0 repos is necessary but not sufficient on its own.

## 6. Source data

Full per-repo detail — including screenshot manifests, exact import counts, and file-level
call-site lists — is in the seven copies under `docs/design-system-parity/`:

- [`docs/design-system-parity/moneysweep-pr.json`](design-system-parity/moneysweep-pr.json)
- [`docs/design-system-parity/thehub-pr.json`](design-system-parity/thehub-pr.json)
- [`docs/design-system-parity/spiderweb-pr.json`](design-system-parity/spiderweb-pr.json)
- [`docs/design-system-parity/skywatcher-pr.json`](design-system-parity/skywatcher-pr.json)
- [`docs/design-system-parity/ovnis-pr.json`](design-system-parity/ovnis-pr.json)
- [`docs/design-system-parity/centinelas-pr.json`](design-system-parity/centinelas-pr.json)
- [`docs/design-system-parity/aguayluz-pr.json`](design-system-parity/aguayluz-pr.json)

Each is a verbatim copy of that repo's own `docs/design-system-usage.json`, produced and
live-verified by that repo's own Phase 2 audit (see each repo's `docs/A11Y_AUDIT.md`). This
document adds no new measurements of its own — it is a read-only comparison across the seven.

# Federation GUI Standard

The rules every PRII GUI is built to, and the procedure for extending one. The
decision behind them is [ADR 0014](adr/0014-spoke-guis-are-complete-domain-apps.md).
If a GUI change needs a decision this document does not already make, the
document is incomplete: change it here first, then build.

Status of each part:

| Part | State |
|---|---|
| Capability manifest, extension fragments, parity checker | Enforced in `thehub-pr`. Rendered into a producer when it adopts (§12). |
| Tokens (`--fd-*`) | Published in `@pr-federation/react`. Single-source rule applies at adoption. |
| Shared shell | Contract fixed here (§4). Implemented in `@pr-federation/react` 0.6.0-rc.1 and proven in three browsers by the fixture matrix. Adopted by `thehub-pr`, with the token bridge; no producer has adopted it yet, and the package is not yet released. |

## 1. Scope

| Repository | Rules | Code template |
|---|---|---|
| `thehub-pr` | yes | reference implementation |
| `aguayluz-pr`, `centinelas-pr`, `moneysweep-pr`, `ovnis-pr`, `skywatcher-pr` | yes | yes |
| `spiderweb-pr` | yes | no: keeps its TypeScript stack and workbench layout |

"Rules" means the capability manifest, extension fragments, the parity checker
and the `--fd-*` tokens. "Code template" means the shared shell, the shared
lint config and the parity workflow.

The Hub app is the only home for cross-producer views. Each producer GUI is the
complete GUI for its own domain.

## 2. Stack

The code template targets one stack. A repository on the template does not
choose alternatives to these.

| Concern | Standard |
|---|---|
| Framework | React 19 |
| Build | Vite |
| Language | JavaScript with JSX, `@/` alias to `src/` |
| Routing | `react-router-dom` |
| Server state | `@tanstack/react-query` 5 |
| Styling | Tailwind 4 with native `@theme`, no JavaScript Tailwind config |
| Primitives | shadcn (new-york), Radix, `lucide-react` |
| Design system | `@pr-federation/react`, pinned to a release tarball with a checksum |
| Unit tests | Vitest, Testing Library, `vitest-axe` |
| Browser tests | Playwright |
| Node | 22 or newer |

Known deviations, each fixed in that repository's adoption change and not
before: `skywatcher-pr` is on React 18; `centinelas-pr` is on Tailwind 3;
several repositories still carry a JavaScript Tailwind config.

Adding a dependency that duplicates a row above (a second router, a second
component kit, a second charting or map library where one is already in use in
that repository) needs a change to this table first.

## 3. Tokens

1. `--fd-*` custom properties from `federation-design/` are the only source of
   colour, spacing, radius, elevation, motion and layout dimensions.
2. shadcn variables (`--background`, `--primary`, `--border`, ...) are aliases
   onto `--fd-*`. A repository does not assign them literal values.
3. A repository's brand accent comes from the `data-repo` attribute on the
   document root. It is not set in application CSS.
4. Hard-coded colours are prohibited outside `federation-design/`.
5. A per-repository token layer (the `zip-design` folder in a frontend's `src`,
   `--zip-*`, or any local palette) is deleted in that repository's adoption change.
6. A token a repository needs and the system lacks is added to
   `federation-design/tokens/federation.tokens.json`, released, and then used.
   It is not defined locally "for now".

## 4. Shell

One shell, supplied by `@pr-federation/react`. A repository provides content
and a navigation registry; it does not fork, wrap or restyle the shell.

**Slots.** `header`, `nav`, `main` (the routed page), `inspector` (optional
side panel for the selected record) and `statusBar`. This is the same
Toolbar / Workspace / Inspector division as
[`INTELLIGENCE_UI_ARCHITECTURE_V1.md`](INTELLIGENCE_UI_ARCHITECTURE_V1.md).

**Navigation registry.** The one extension point. A repository builds it with
`defineFederationNav`, in the shape the Hub's `server/frontend/src/lib/nav.js`
already follows:

```js
defineFederationNav([{ label, items: [{ label, path, icon, capabilityId }] }])
```

- Every page a person can reach has exactly one registry entry.
- `capabilityId` names the entry's capability in the manifest (§5). It is
  required; the registry refuses to build without it.
- `label` may be a string or a function returning one, for translated labels.
- A routed page has a `path`. An application whose views are not routes gives
  the entry an `id` instead and handles `onSelect`.
- Optional per entry: `end` (match the path exactly), `match` (extra path
  prefixes that also make it current), `accent` (a colour, shown as a dot),
  `description`, and `mobile: 'primary'` (prefer it for the bottom bar).
- The registry file is listed in the manifest under `discovery.navigation_files`.
- Navigation rendered from anywhere other than the registry is not allowed.

**Routing.** The shell does not know the application's router. The application
passes the current path as `current` and draws links through `renderLink`.
Exactly one entry is current: the longest matching path prefix.

**Placement.** A sidebar. There is no top-navigation placement: no repository
uses one, and an option nobody uses is surface to test in three browsers for
nothing. It can be added without breaking anything if a repository needs it.

**Small screens.** Below the shell breakpoint the navigation becomes a bottom
bar of at most five entries; when there are more, the fifth is "More" and opens
the rest. The breakpoint is 768px by default and may be set to 1280px
(`mobileBelow`); those are the token breakpoints, and no other value is
available. Interactive targets are at least 44 by 44 CSS pixels. No page
scrolls horizontally, down to 320 pixels wide.

**Accessibility the shell provides.** A skip link as the first stop, landmarks,
one labelled primary navigation, exactly one `aria-current="page"`, and a main
region that can take focus after navigation (`focusMainOnNavigate`). A
repository does not re-implement these.

**Inspector.** `FederationInspectorPanel` in the `inspector` slot is a column
beside main at 1280px and above and a modal drawer below. A page that needs an
always-visible detail column inside its own layout may keep one; the slot is
for the record a person selected.

**Themes.** Light and dark both work. A repository may choose its default; it
may not ship only one.

## 5. Capabilities

A capability is one thing a person can do or see. Each is declared in
`.federation/gui-capabilities.json` (or a fragment, §7) and bound in both
directions: backend to GUI, and GUI to backend.

### Classification

Answer the questions in order and stop at the first "yes".

| # | Question | Classification |
|---|---|---|
| 1 | Is it infrastructure no person operates directly (health probe, export writer, contract validator, scheduler, migration)? | `internal` |
| 2 | Does it live entirely in the browser, with no backend call of its own (theme switch, command palette, client-side filter)? | `client_only` |
| 3 | Does it change system state, run a job, manage configuration or credentials, or approve something? | `operator` |
| 4 | Is its main output a computed result a person inspects (a score, a correlation, a model output, a generated report)? | `analysis` |
| 5 | Otherwise: a person browses, searches or reads domain records. | `user` |

Rules that settle the usual doubts:

- `internal` is for code with no human operator, not for code whose GUI has not
  been built yet. Unbuilt GUI for a human-facing capability is `staged` or an
  exception (§10), both of which expire.
- A capability that both changes state and shows a computed result is
  `operator`. The stricter obligation wins.
- An `internal` capability must carry a `rationale` that says what consumes it.
  "Infrastructure" alone is not a rationale.
- A read-only view of an analysis another capability runs is part of that
  capability, not a new one.

### Status

| Status | Meaning | Obligations |
|---|---|---|
| `active` | Shipped and reachable. | Full contract: both sides bound, discoverable, end-to-end test. |
| `staged` | Built but not reachable. | `feature_flag`, `tracking`, `expires_on`. Must be unreachable without the flag. |
| `legacy` | Known one-sided behaviour, recorded. | None, and it maps nothing: the debt stays in the baseline. |

### Contract by classification (active capabilities)

| Classification | Backend or analysis binding | GUI binding | `tests.e2e` and `frontend.e2e_routes` |
|---|---|---|---|
| `user`, `operator`, `analysis` | required | required | required |
| `client_only` | must be absent | required | required |
| `internal` | optional | not required | not required; `rationale` required |

Every active capability sets `requires_terminal: false`. The normal path for a
person never needs a terminal, a script, a direct API call, developer tools or
a URL typed by hand.

### Core capabilities

The Hub owns these ids. A repository declares one only when it ships the
feature, and then with exactly this id and classification.

| Id | Classification | Meaning |
|---|---|---|
| `pr-grid-v2-runtime-contract` | `internal` | The PR_GRID_GEOGRAPHIC_V2 consumer runtime. |
| `service-health` | `internal` | The `GET /health` liveness endpoint. |

The list is `federation-templates/gui/core-capabilities.json`. Adding to it is
a change to this document and to the checker.

### Hub navigation without a capability

The registry requires a `capabilityId` on every entry (§4). The Hub's registry
is built with the migration waiver because most Hub pages predate the manifest:
9 of its 32 entries name a capability, and these 23 do not yet.

`/`, `/hub`, `/spiderweb`, `/ovnis`, `/centinelas`, `/crossover`,
`/anomaly-overlap`, `/transition`, `/readiness`, `/control`, `/programs`,
`/project-signs`, `/apps`, `/operations`, `/cases`, `/sources`, `/tasks`,
`/gates`, `/exports`, `/dictionary`, `/manifest`, `/integrations`,
`/operator-settings`

This is debt, not an exemption. Each page is classified and declared under
this section's rules, with its end-to-end test, and gains its `capabilityId`;
the waiver is removed when the list is empty. A producer adopting the shell
does not use the waiver: its registry is built without it. A test in the Hub
(`server/frontend/src/lib/nav.test.js`) holds every id that is named to a
capability that really declares that route.

## 6. Procedure: add a page or capability

Nothing in this list is optional, and nothing outside it should be needed.

1. **Backend.** Add the endpoint or module. Skip for `client_only`.
2. **Client.** Add the API call in the repository's API client module, not
   inline in the component.
3. **Page.** Add the page component. Use shell slots and `@pr-federation/react`
   components; cover loading, empty, error, stale and offline states with the
   shared async-state components.
4. **Route.** Register the route in the route file.
5. **Navigation.** Add one registry entry with `path` and `capabilityId`.
6. **Capability.** Declare it (classification from §5). In a fragment if the
   work is a self-contained feature (§7); in the base manifest if it is core to
   the repository. Bind `backend`, `frontend.routes`, `frontend.components`,
   `frontend.discoverability` (the registry file), `frontend.e2e_routes` and
   `tests`.
7. **Test.** Add an end-to-end spec, or rely on the manifest-driven parity spec
   if reaching the route is all that needs proving. Name the spec in
   `tests.e2e`.
8. **Check.**
   ```
   python3 scripts/check_gui_parity.py
   npm --prefix <frontend dir> run test:gui-parity
   ```
   A new gap is fixed or mapped. It is never added to the baseline (§9).
9. **Docs.** Update whatever the change made untrue and run
   `python3 tools/check_docs_sync.py --base origin/main`.

## 7. Extension fragments

Repository-specific expansion that should not grow the base manifest goes in
`.federation/gui-capabilities.extensions/<extension_id>.json`.

```json
{
  "extension_id": "financial-leaderboards-v1",
  "capabilities": [],
  "exceptions": []
}
```

- One fragment per feature. The filename stem equals `extension_id`.
- A fragment contains `capabilities`, `exceptions`, or both, and nothing else
  except an optional `schema_version`.
- Fragments append. An id already present in the base manifest, or in another
  fragment, is an error.
- A fragment cannot carry `policy` or `discovery`, cannot exclude paths, and
  has no effect on the baseline.
- The checker merges every fragment by default, in filename order. Tools that
  need the merged view ask the checker for it
  (`--emit-merged <path>`); they do not re-implement the merge.
- A fragment that breaks a rule is reported and contributes nothing. The
  capabilities it would have mapped then surface as gaps.

Shape is defined by `federation-audit/contracts/gui-capabilities.schema.json`
and `federation-audit/contracts/gui-capabilities-fragment.schema.json`.

## 8. End-to-end tests

- Producer parity tests run against the repository's real backend. Mocked
  responses do not prove a capability is wired.
- The Hub's parity spec mocks its API. That is a declared exception: the Hub's
  backend serves aggregates fetched from producers that are not present in CI.
  It is not a precedent.
- A spec named in `tests.e2e` must actually run. When a repository declares its
  Playwright config(s) in `discovery.e2e_config`, the checker fails any
  `tests.e2e` file that no declared config names.
- Repository-specific assertions live in the repository's own spec files. The
  shared parity spec only walks the manifest.

## 9. Baseline

`.federation/gui-parity-baseline.json` is the inventory of debt that existed
when the gate was introduced. It may be rewritten in exactly two cases:

1. A repository adopts the gate for the first time.
2. A change whose effect on the baseline is only to remove candidates.

It is never rewritten to make a failing gate pass. A change that would add a
candidate to the baseline must map the candidate or remove the code instead.

## 10. Exceptions and expiry

An exception records a gap that is accepted for a limited time. It needs `id`,
`reason`, `owner`, `tracking`, `expires_on`, and either `candidate_ids` or
`candidate_files`.

- Expiry is at most 90 days out. The checker warns when it is further.
- The checker warns from 14 days before expiry. After expiry the gate fails for
  every change in the repository, related or not, so an owner acts on the
  warning: deliver the missing side, or renew with a reviewed reason.
- Renewal is a reviewed change that says what moved since the last date. A
  renewal with an unchanged reason is a waiver and is rejected.
- `staged` capabilities follow the same expiry rules.

## 11. Agent and contributor instructions

Each repository's `AGENTS.md` carries this block. It is added by hand at
adoption because `AGENTS.md` is repository-specific and not rendered.

```markdown
## Required change protocol

1. Declare the capability in `.federation/gui-capabilities.json`, or in a
   fragment under `.federation/gui-capabilities.extensions/`, in the same change.
2. Bind backend endpoints/modules and GUI routes/components bidirectionally.
3. Add the page to the navigation registry. Do not render navigation elsewhere.
4. Add or update an end-to-end GUI test and name it in `tests.e2e`.
5. Run `python3 scripts/check_gui_parity.py` and the frontend package's
   `npm run test:gui-parity`.
6. Never regenerate `.federation/gui-parity-baseline.json` to make a gate pass.

The full rules are in `thehub-pr/docs/FEDERATION_GUI_STANDARD.md`.
```

Each repository's `.federation/docs-sync.json` carries this coupling:

```json
{
  "doc": "docs/GUI_CAPABILITY_PARITY.md",
  "covers": [
    ".federation/gui-capabilities.json",
    ".federation/gui-capabilities.extensions/**",
    ".federation/gui-parity-baseline.json"
  ],
  "on": ["add", "delete", "rename"],
  "why": "Names the files that make up the GUI capability contract."
}
```

## 12. Adoption

A repository receives the rendered rule files when it is added to a target set
in `federation-templates/targets.yaml`: `_gui_rules` (checker, its test, the
procedure document) and, for the five JSX producers, `_gui_code` (the parity
workflow). Until then its own copies stand and nothing overwrites them.

One repository at a time, in this order: `moneysweep-pr`, `centinelas-pr`, then
the rest. Per repository:

1. Clear existing template drift at the current pin, in its own change.
2. Add the repository to the target sets in the Hub; bump its
   `PRII_TEMPLATE_REF`; render.
3. Remove any local checker wrapper. CI calls `scripts/check_gui_parity.py`.
4. Make the manifest and fragments valid against the schemas: add
   `extension_id`, `discovery.e2e_config`, and core ids where the feature ships.
5. Run the checker. A new gap is mapped or fixed, never baselined.
6. Move repository-specific end-to-end assertions into owned specs named in
   `tests.e2e`.
7. Pin `@pr-federation/react` 0.6 by tarball and checksum and import its
   stylesheet. Then, in one change: import the shadcn bridge, switch the
   application from `hsl(var(--x))` to `var(--x)` for the bridged variables,
   and delete its own values for them. The bridge supplies complete colours,
   so importing it while the variables are still wrapped in `hsl()` breaks
   every colour.
8. Adopt the shared theme provider and shell; move navigation into a registry
   file.
9. Delete the frontend's `zip-design` folder and its Playwright config.
10. Remove the "Diagnostic-only surface" README banner, add the `AGENTS.md`
    block and the docs-sync coupling from §11, and run
    `python3 tools/check_docs_sync.py --base origin/main`.

Steps 7 to 9 wait for the shell release. Steps 1 to 6 and 10 do not.

`spiderweb-pr` does steps 1 to 5 and 10, creates its first manifest and
baseline (the first-adoption case in §9), and imports the `--fd-*` tokens. It
keeps its runtime-matrix test.

## 13. Changing the rules

- The checker is rendered into every repository. Before a checker change
  merges, run it read-only against each producer checkout and record any change
  in gaps per repository in the pull request.
- A checker change may reduce gaps in a producer. It may not introduce one;
  if it would, the change ships together with that producer's fix or not at all.
- Token and component changes follow the governance section of
  [`FEDERATION_DESIGN_SYSTEM_V1.md`](FEDERATION_DESIGN_SYSTEM_V1.md).

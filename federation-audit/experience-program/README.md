# Federation Application Experience & Modernization Program

Working package for the eight-repository experience program (gates RC0–RC11).
Everything here is evidence or tooling for that program. Nothing in this
directory is imported by the hub or by any producer.

Release policy is fail-closed. A gate file states `PASS`, `FAIL`, `OPEN`,
`BLOCKED`, `PROVISIONAL`, `AUDIT_ONLY`, `UNRESOLVED` or `SUPERSEDED`. An artifact
that has not been produced or validated is left `OPEN`; it is never filled in.
Certification is withheld until every required gate passes, including a review by
someone other than the author of the work.

## Layout

| Path | What it is |
|---|---|
| `scripts/rc0_baseline.py` | Rebuilds the RC0 artifacts. Read-only against the repositories. |
| `rc0/repository_baselines.json` | Git identity of each audited `main`, next to the identities recorded earlier. |
| `rc0/source_manifest.json` | Per-repository file counts, bytes, lockfiles, and the SHA-256 of each listing. |
| `rc0/manifests/<repo>.sha256` | One line per tracked file: `<sha256>  <git mode>  <path>`. |
| `rc0/source_manifest.sha256` | SHA-256 of every RC0 artifact above. |
| `rc0/worktree_inventory.json` | Local branches, worktrees, uncommitted files and stashes at capture time. |
| `rc0/recovery_verification.json` | Result of re-fetching each audited commit into an empty directory. |
| `rc0/RC0_GATE.json` | Gate state and the checks behind it. |
| `scripts/rc1_merge.py` | Validates the RC1 surveys and writes the merged RC1 artifacts. Audits nothing itself. |
| `rc1/surveys/<repo>.json` | One source survey per application, made from a snapshot of its RC0 commit. |
| `rc1/application_inventory.json` | The surveys merged, with each denominator recomputed from its rows. |
| `rc1/ui_workflow_matrix.csv` | One row per workflow, plus one per surface that has no workflow. |
| `rc1/settings_inventory.json`, `rc1/context_actions_inventory.json` | Settings, contextual actions and keyboard shortcuts across applications. |
| `rc1/accessibility_findings.json` | Accessibility leads read from source. Not scan results. |
| `rc1/special_adjudications.json` | Answers to the per-application questions in the program brief. |
| `rc1/desktop_conventions.json` | Where recents, pinning, renaming and Dock behaviour exist today (workstream WS-D). |
| `rc1/RC1_GATE.json` | Gate state, totals and per-application validation. |
| `scripts/runtime/` | Runtime-pass tooling: serve one audited snapshot, and load its routes in Chromium (or, with `GUI_ENGINE=firefox` or `webkit`, in that engine). |
| `scripts/rc1_runtime_merge.py` | Tabulates the runtime pass. Decides nothing beyond the rule stated in its header. |
| `rc1/runtime_observations.json` | Per application and route: what Chromium observed at seven widths. |
| `rc1/runtime_findings.json` | The blocking axe rules, horizontal overflows and unnamed buttons observed. |
| `rc2/schemas/*.schema.json` | Federation Experience Contract v1: the contract, actions, settings, navigation and compatibility schemas. |
| `scripts/rc2_validate.py` | Validates contract documents: the schemas plus the rules that span sections or applications. |
| `rc2/fixtures/positive/` | Two illustrative contracts that must be accepted, alone and together. |
| `rc2/fixtures/negative/` | One file per rule: a patch on a positive fixture and the finding it must produce. |
| `rc2/RC2_GATE.json` | Gate state, schema hashes and the checks behind it. |
| `scripts/rc3_runtime_detail.py` | Tabulates the failing elements the runtime pass recorded, per application and rule. |
| `rc3/runtime_element_detail.json` | Each distinct failing element: markup, routes, widths, measured colours, and whether a shared or an application style draws it. |
| `rc3/chromium_matrix_receipt.json` | Counts and per-cell results of the design-system browser matrix, Chromium only. |
| `rc3/RC3_GATE.json` | Gate state for the design-system changes, what differs from the plan, and what is still open or blocked. |
| `scripts/rc4_pilot_input.py` | Sets a re-scan of thehub-pr beside the RC3 element list and builds the per-application table a pilot choice rests on. |
| `rc4/thehub_rescan.json` | thehub-pr before and after thehub-pr#432, per rule and for horizontal overflow. |
| `rc4/RC4_PLAN_INPUT.json` | Per application: distinct failing elements per rule, style signatures, design-system pin, and whether the evidence is still current `main`. |
| `scripts/rc4_pilot_compare.py` | Compares two runtime passes of one application, before and after a pilot. |
| `rc4/skywatcher_pilot.json` | skywatcher-pr before and after its pilot: the targeted rules per distinct element, and every critical or serious rule. |
| `rc4/aguayluz_pilot.json` | aguayluz-pr before and after its fixes, in the same form. |
| `rc4/moneysweep_pilot.json`, `rc4/centinelas_pilot.json`, `rc4/thehub_pilot.json` | The same before/after comparison for those three applications. |
| `rc4/thehub_overflow.json` | thehub-pr horizontal overflow per width, before and after the tab bar fix and the phone-width fix. |
| `scripts/runtime/views_pass.js` | The runtime pass for an application with one address: opens each in-memory view and records it as the route `/#view:<label>`. |
| `rc4/ovnis_pilot.json` | ovnis-pr before and after its fixes, per view, in the same form as the other comparisons. |
| `rc4/mucaro_scan.json` | mucaro-ai scanned per view; nothing to fix, so there is no after. |
| `scripts/runtime/states_pass.js` | Opens named UI states of a one-address application (a short click sequence each, from a states file) and records each as the route `/#state:<name>`. |
| `rc4/spiderweb_pilot.json`, `rc4/spiderweb_states.json` | spiderweb-pr before and after its fixes, per module view and per further state. |
| `rc4/states/spiderweb-pr.json` | The states opened for spiderweb-pr, so the states pass can be repeated. |
| `rc4/aguayluz_water_use_before_after.png` | One AguaYLuz page before (above) and after (below) the dim-text change. |
| `rc4/RC4_GATE.json` | RC4 state, what the re-scan showed, the results per application, what is blocked and what they do not show. |
| `scripts/rc8_baseline.py`, `scripts/runtime/perf_pass.js` | Measure a backend's first start, a built frontend's size and per-route page-load timing, and tabulate them. |
| `scripts/runtime/startup_profile.py`, `scripts/runtime/netlog/` | Where a backend's start goes (import time and mapped bytes per package), and every network call it makes. Used for the first-start diagnosis. |
| `rc8/performance_baselines.json` | Per application at `main`, and for the two RC4 branches: start time, build size, and page-load figures per route. |
| `rc8/RC8_GATE.json` | What the baseline shows, the RC4 branches against `main`, and the budgets adopted on 2026-11-18 with which applications exceed them. |
| `scripts/rc9_matrix.py` | Reads each application's tree for its toolchain, pins, browser features and the platforms its CI names. |
| `rc9/compatibility_matrix.json` | One row per application: what it declares, what its build relies on, and the runs that were actually made. |
| `rc9/RC9_GATE.json` | What differs between the applications, and what the matrix cannot establish. |
| `scripts/rc10_engine_tabulate.py` | Tabulates a cross-engine pass and lists what Firefox or WebKit shows beyond Chromium on the same build. |
| `cross-engine/engine_matrix.json` | Each application's build loaded in Chromium, Firefox and WebKit: counts per engine and what differs from Chromium. |
| `cross-engine/routes.json`, `cross-engine/commits.json` | The routes loaded and the commit built for each application in that pass. |
| `cross-engine/recheck_20261124.json`, `cross-engine/recheck_20261124_commits.json` | The same three-engine pass, repeated for aguayluz-pr and ovnis-pr at their `main` after their map fixes merged. |
| `qa/INDEPENDENT_REVIEW_PACKET.md` | For a reviewer other than the author: what each RC3/RC4 change did, its evidence, what to check, and a sign-off block. |
| `qa/manual/*.md` | Scripts for a person to run with VoiceOver, NVDA, Voice Control, TalkBack and touch devices, per application and for the shared controls. |
| `qa/macos_observations.json` | What was measured on the user's Mac: startup, the running app's identity, Dock menu and login items. |
| `qa/MACOS_CHECKLIST.md` | What still needs a person at the Mac, and what to report back. |

## Reading RC0

- Git commit and tree ids are Git object hashes. The SHA-256 values are hashes of
  file content. They are recorded in separate fields and are not interchangeable.
- "Remote reproduces trees" means a fresh fetch of the exact commit, checked out
  into an empty directory, hashes to the same listing. One file in `mucaro-ai`
  differs on disk because `.gitattributes` declares `eol=crlf` for it; undoing
  that conversion reproduces the committed hash, and the record says so.
- That check is not a backup test. No backup outside the Git host was identified,
  so off-device recovery is `OPEN` and RC0 is `PROVISIONAL`, not `PASS`.
- The commit ids in the program brief were starting references. Where `main` has
  moved since, the brief's id is an ancestor of the audited one and is marked
  `SUPERSEDED`.

## Reading RC1

- RC1 is a **source audit**. No application was started for it, so no surface is
  `OBSERVED_RUNTIME`. The best class a surface can have here is
  `SOURCE_CONFIRMED`.
- A surface counts as mounted only where the survey cites the line that mounts or
  routes to it. A component file existing is not enough.
- `rc1_merge.py` checks each survey's shape, recomputes its totals from its rows,
  and checks that every cited `path:line` exists at the audited commit. A citation
  written as a bare file name is accepted only when exactly one tracked file has
  that name. Resolving a citation shows the line exists, not that it says what the
  survey claims; that needs a person or a runtime check.
- An application with no survey yet is `OPEN`, and so is the gate.
- Forms, tables and filters inside a page are listed as each survey's
  `coverage_statement` says, which may be a sample. The denominator is therefore
  closed for routes, workspaces, tabs, navigation, dialogs, settings, contextual
  actions, shortcuts and backend endpoints, and open for in-page controls.

## Reading the runtime pass

After the source inventory, each application was built from its audited snapshot
and run on its own backend with a fresh temporary workspace. Chromium loaded
every surface that has its own address, at 320, 390, 430, 768, 1280, 1440 and
1920 CSS pixels.

- A route is `OBSERVED_RUNTIME` only if, at every width, it answered 200, stayed
  on the address asked for, rendered text and showed no not-found page. A route
  that adds its own default query parameters is the same page; a change of path
  is a redirect and leaves the route `SOURCE_CONFIRMED`.
- 150 of 155 addressable routes were observed. The five that were not are
  redirects by design: four sign-in pages in skywatcher-pr that return to `/`
  when sign-in is off, and one legacy address in centinelas-pr.
- **Most surfaces were not opened.** Of 518 mounted surfaces, 153 have an
  address. Dialogs, drawers, in-memory tabs and anything behind a click were not
  visited, so they remain `SOURCE_CONFIRMED`. mucaro-ai, ovnis-pr and
  spiderweb-pr hold their views in memory and contribute one address each.
- Pages were loaded, not operated. No form was submitted and no write was tried.
- One browser. Firefox and WebKit were not available then; the later
  cross-engine pass (`cross-engine/`) loaded the RC4 builds in both.
- An axe scan finds a subset of accessibility failures. It is not a keyboard or
  screen-reader review, and passing it is not an accessibility pass.
- mucaro-ai serves a strict `script-src 'self'` policy, which refuses the
  injected axe source. For that application the scan ran in a test context with
  the policy lifted, and the output records `csp_bypassed_for_scan: true`. The
  policy itself is working as intended.
- Data was whatever a fresh workspace holds, so some pages were seen empty.

## Reading RC2

- The contract fixes interaction **semantics**, not layout. Applications keep
  their own pages; they agree on what an action, a setting and a navigation
  entry are.
- One action definition feeds every surface it appears on: toolbar, item menu,
  right-click menu, command palette, Dock menu, keyboard. The schema refuses an
  action whose only surface is right-click or the Dock menu, so no action is
  mouse-only or macOS-only.
- A write is never available to a guest and always names an audit event. Only a
  user-named object can be renamed; an evidence object cannot.
- Settings carry a scope. A federation-global setting lives in the `federation.`
  namespace with no owning application; every other setting lives in its
  application's namespace, so one application cannot overwrite a global value or
  another application's value. Pins and recents are bounded per-user lists at
  application scope.
- Unknown fields are rejected except extension fields named `x-*`. `null` is
  accepted only where a property declares it.
- `rc2_validate.canonical()` is the serialization to hash or compare: sorted
  keys, compact separators, UTF-8. Array order is kept because it is meaningful.
- **The positive fixtures are not declarations.** They are documents written to
  exercise the rules and say so in an `x-fixture-note`. No application has
  adopted the contract, which is why RC2 is `PROVISIONAL`.

A negative fixture is `{"description", "base", "patch", "expect"}`. `base` names
one or more positive fixtures; each `patch` entry is `set`, `remove` or `copy` on
a `/`-separated path (`doc` picks which base document, `-` appends to a list);
`expect` lists finding codes that must appear.

## Reading RC3

RC3 changes the shared design system only (`federation-design/`). No
application was changed.

- The runtime pass was repeated keeping each failing element's markup and, for
  contrast, the colours measured. Of 299 distinct failing elements across the
  eight applications (252 contrast, 11 unnamed buttons, 22 scroll regions, 14
  label mismatches), none is drawn by a shared design-system class. The
  application failures are therefore application fixes, and
  `rc3/runtime_element_detail.json` is their work list. This corrects the
  assumption, made before RC3, that shared colour tokens were the cause.
- What RC3 did fix is the shared package's own accent defect, and it added the
  components the applications lack: a named scroll region, a label that stays
  a button's name on small screens, a dialog, a rename dialog, a menu, an item
  menu, a status mark, and pinned and recent navigation groups.
- "Shared" and "application" in the element list are read off the element's
  own class list. An application element inside a shared panel counts as
  application, because the application's class is what colours it.
- The browser matrix receipt is Chromium only. Firefox and WebKit run in CI
  and are not claimed in these files.
- `main` moved during RC3: thehub-pr#432 put the Hub on the shared shell and
  deleted the Hub's own sidebar, where its most frequent contrast failures
  were. The thehub-pr rows of the element list describe the commit audited in
  RC0 and are superseded for the shell. The re-scan is in `rc4/`.
- The gate is `PROVISIONAL`: nothing has adopted the components, nothing was
  used with a screen reader or on a touch device, and the author is the only
  reviewer.

## Reading RC4

RC4 has its evidence step and seven applications fixed in their own code:
skywatcher-pr (#375), aguayluz-pr (#420), moneysweep-pr (#719), centinelas-pr
(#198), thehub-pr (this pull request), ovnis-pr (#204) and spiderweb-pr
(#473). mucaro-ai was scanned and needed no change. The skywatcher, aguayluz,
moneysweep, ovnis and spiderweb fixes are merged; centinelas-pr#198 and this
pull request are not.

- thehub-pr was re-scanned on `main` after thehub-pr#432. Contrast failures
  went from 86 routes to 1. Unnamed buttons and unfocusable scroll regions are
  unchanged. Seven routes now overflow horizontally at 768 pixels where none
  did before; the cause is not established.
- "Style signatures" counts distinct tag-and-class combinations among an
  application's failing elements. It is a proxy for how many places a fix
  touches, not a count of source files.
- An application with one addressable route was scanned on that route only. A
  low count there describes the coverage, not the application.
- The pilot recommendation in `RC4_GATE.json` is an inference from this table.
- Skywatcher pilot: unnamed buttons 1 to 0, unfocusable scroll regions 10 to
  0, label mismatches 7 to 0, counted as distinct elements over the same 22
  routes and seven widths. One other rule, `link-in-text-block`, still fires on
  two routes; it was not in scope.
- AguaYLuz: contrast 222 to 0, unnamed buttons 1 to 0, unfocusable scroll
  regions 6 to 0, as distinct elements over the same 20 routes and seven
  widths. Dim text was raised to the shade the app already used for muted
  text, so the two are now the same grey. `link-in-text-block` and
  `svg-img-alt` still fire and were not in scope.
- MoneySweep: unnamed buttons 1 to 0, unfocusable scroll regions 2 to 0.
  Centinelas: contrast 2 to 0, label mismatches 2 to 0; only its dark theme was
  scanned.
- TheHub: contrast 1 to 0, unnamed buttons 8 to 0, unfocusable scroll regions
  3 to 0. The after-scan also caught three satellite pass buttons whose names
  did not contain their visible text; they appear only when live satellite
  data loads, so the earlier scan missed them. They are fixed and covered by
  unit tests, not by a browser scan.
- TheHub's shell migration made seven routes overflow at 768 px, because the
  shared sidebar appears from that width and the tab bar could not shrink.
  The tab bar now scrolls; overflow at 768 px went from 7 routes to 0, and at
  any width from 17 routes to 7. The last seven (the GIS view switcher, a long
  App Center badge, the crossover date filters) now wrap at phone widths:
  overflow is 0 on all 86 routes at all seven widths. Naming the date inputs
  also cleared the `label` rule (7 page loads to 0).
- TheHub is the first application to use the RC3 control primitives
  (`FederationScrollRegion`), because it consumes the shared package from
  source.
- OVNIS and Múcaro have one address each, so `views_pass.js` opened every
  in-memory view at seven widths. OVNIS: contrast 28 to 0 and unfocusable
  scroll regions 1 to 0 as distinct elements; `link-in-text-block` still fires
  and was not in scope. Múcaro: no axe violation of any impact, no overflow,
  no unnamed button in 49 view loads; its script policy was lifted in the test
  browser only, to inject axe-core.
- Múcaro was rescanned at `main` (870b46b), whose four new workspaces (GIS,
  OCR, Code, Artifacts) had never been scanned: all 10 workspaces and
  Background tasks, 77 view loads, still no violation of any impact. The new
  workspaces were opened, not operated; their result views were not reached.
- Then one inspection was run in each new workspace through the UI (GIS on the
  USGS fixture, OCR with Tesseract, Code on a throwaway repository; Artifacts
  then listed 2 reports and 1 answer). With the results showing, still no
  violation of any impact and no overflow at any width.
- Spiderweb's `main` builds again since spiderweb-pr#468, so it was scanned
  at e64fb40: its six module views by `views_pass.js`, and seven further states
  by `states_pass.js` (a timeline event, a contract, a cluster and a graph node
  selected; the light theme; a stub query run; the layer panel). Label
  mismatches went from 6 to 0 as distinct elements in both: the five timeline
  event buttons and "Recenter PR". No contrast, unnamed-button or scroll-region
  failure was found. Below 768 px the app hides its rails, inspector and
  timeline, so those surfaces exist from 768 px only. `region` and
  `landmark-unique` (moderate) still fire and were not in scope.
- These are scan results. Pages were loaded, not operated, in Chromium only.
  They are not keyboard or screen-reader reviews, and the AguaYLuz scan ran on
  a workspace with little data on most pages.

## Reading RC8

RC8 is a baseline. It measures and records; nothing was optimised and no
application was changed.

- Timings come from a Linux container over loopback, in Chromium, on nearly
  empty workspaces. They compare applications and commits with each other.
  They are not what a person sees on their own machine, and they do not
  address a startup delay on macOS.
- Every figure is a median with its minimum, maximum and relative spread. A
  timing whose runs differ by more than half the median is flagged for that
  cell and should not be quoted on its own.
- `cold_start_ms.first_run` is one observation of a tree that had never been
  run; `later_runs` summarises the next four. They are different quantities.
- The 9.4 s first starts of AguaYLuz and MoneySweep were diagnosed
  (`first_start_diagnosis` in `RC8_GATE.json`): not bytecode, not network, not
  workspace setup. After a container restart MoneySweep took 15.4 s once and
  0.73 s after, with loading pyarrow and numpy's native libraries taking about
  5 s of it. The cost is reading files from this container's cold disk, so
  those two first-start budget results are `UNRESOLVED` until measured on real
  hardware. Report a cold first start apart from warm ones. The two start-up
  changes considered (MoneySweep loading pandas on first use, AguaYLuz moving
  its import-time data load) are `DEFERRED` until a real-machine backend start
  exceeds the budget, timed from pressing Launch, since the backend loads only
  after the Launch Pad; `qa/MACOS_CHECKLIST.md` section 3a says how to measure it.
- "Initial" JavaScript is what `index.html` references; the rest loads later.
- Six budgets were adopted after the baseline was taken; `RC8_GATE.json`
  lists them and each application's result. They are bounds for this harness,
  not device targets. Six applications exceed at least one. The gate stays
  `PROVISIONAL`: nothing was optimised, and the first-start figure is a single
  observation per application.
- The two RC4 branches are measured beside their `main`. Build size and
  transfer are unchanged; timing differences are inside the run-to-run spread.

## Reading RC9

- `toolchain`, `design_system`, `desktop_runtime` and `ci_configuration` are
  read from each application's tree at its `main`.
- `ci_configuration` lists the platforms and browser engines workflow files
  name. It does not say those jobs ran or passed.
- `observed_runs` lists runs that were actually made. An engine or operating
  system missing from it was not run against that application.
- `browser_floor_from_build.features` is a pattern scan of the built CSS and
  JavaScript. The `floor` derived from it uses browser versions written from
  memory and is an assumption until that table is checked.
- The matrix is not validated against the RC2 compatibility schema. That
  schema is a declaration an application makes when it adopts the contract,
  and none has.

## Reading the cross-engine pass

Each application's build (`cross-engine/commits.json`) was served once and
loaded in Chromium 157, Firefox 155 and WebKit 26.6: Playwright 1.63.0,
headless, Linux container, the same seven widths, dark scheme and axe-core
4.14.1 as before. That is 1,187 page or view loads per engine. The five RC4
applications were built at their "after" commits, thehub-pr at #435's head,
ovnis-pr at #204, mucaro-ai at its RC4 scan commit, and spiderweb-pr at its
RC0-audited commit, because its `main` did not build at the time.

- `beyond_chromium` lists what an engine showed that Chromium did not on the
  same build. WebKit showed nothing beyond Chromium on seven applications;
  Firefox showed nothing on six.
- Firefox, aguayluz-pr: `/map` renders nothing. The map library throws
  `GPUInitializationError: WebGL2 is required`. This Firefox has no WebGL2.
  Chromium's software WebGL draws the map.
- Firefox, ovnis-pr: after the Map view, any other view replaces the whole app
  with its error screen. The map has no WebGL context, `map.remove()` throws on
  unmount, and the app's single error boundary also wraps the navigation.
- WebKit, ovnis-pr: `SyntaxError: Unexpected token '<'`. The build has no
  `maplibre-gl-worker.mjs`, so the request is answered with `index.html`.
  Chromium makes the same request and fails silently, so the defect is not
  WebKit's; WebKit only reports it.
- The missing WebGL2 is this environment's, but the blank page and the error
  screen are how the applications handle it. Every finding is in application
  map code; none is on a shared design-system element.
- Firefox reported `link-in-text-block` on fewer page loads than Chromium. Fewer
  is not a fix; axe evaluates that rule from computed styles that differ by
  engine.
- WebKit here is Playwright's Linux build, not Safari on macOS or iOS. Pages
  and views were loaded or opened, not operated.
- aguayluz-pr at `c60587e` and centinelas-pr at `d96863d` (and on its current
  `main`) do not install as pinned: `constraints-desktop.txt` pins
  `pydantic-core==2.48.0` beside `pydantic==2.13.5`, which requires 2.46.5.
  They were installed with that one pin removed, and `RC4_GATE.json` records
  the conflict. Both repositories' `main` now pin a matching pair.
- **Re-check, 2026-11-24** (`cross-engine/recheck_20261124.json`). After the
  fixes merged (aguayluz-pr#423 and #428, ovnis-pr#205), both applications'
  `main` were loaded again in all three engines, with the same method.
  Neither shows anything beyond Chromium in Firefox or WebKit:
  - AguaYLuz `/map` now renders, with no page errors.
  - Every OVNIS view opens, with no errors.
  - OVNIS's map worker now loads as JavaScript.

  The cross-engine check is therefore `PASS` for the builds recorded. A later
  commit of any application is not covered.

## Reading qa/

The checks that need a person, or a machine this program does not have, are
written down here rather than claimed.

- `INDEPENDENT_REVIEW_PACKET.md` is for someone other than the author. The
  author has not filled in its sign-off and does not count as a reviewer.
  `independent_review` stays `BLOCKED` in RC3 and RC4 until a reviewer's
  sign-off is recorded there, with the reviewer named.
- The `manual/` scripts are for VoiceOver, NVDA, Voice Control, TalkBack and
  touch devices. `screen_reader` and `touch_devices` stay `BLOCKED` until
  results come back, and are then recorded per configuration.
- `macos_observations.json` was measured on the user's Mac, attached to the
  session, in the user's own checkouts at their local heads, not at the RC4
  pull-request heads. It establishes:
  - the running app is the venv's Python (`org.python.python`), not the bundle's
    identity;
  - the desktop runtime defined no Dock menu and no login item at the heads
    measured (a Dock menu, menu bar entries and a right-click menu were added
    afterwards, in `packages/prii_desktop`; none has been observed on screen
    yet, and there is still no login item);
  - a launch that finds the setup marker or the built frontend missing reruns
    the full setup (170.8 s once).
  That this is the startup delay the user reported is an inference, and is
  marked as one. On 2026-11-21 the Dock could not be read (Accessibility
  permission was refused). On 2026-11-24 the Mac was linked to a session and one
  launch of `PRII-THEHUB.app` was read on screen (`on_screen_2026_11_24`): the
  Dock tile is labelled `PRII-THEHUB` with a blue network icon, which corrects
  the earlier expectation of a Python tile, while the menu bar name and the
  application menu say `Python`. The Dock tile's menu, Open at Login and the
  Cmd-Tab entry were not seen and are still to be confirmed with
  `MACOS_CHECKLIST.md`. The macOS gate entries stay `BLOCKED`.

## Re-running

```bash
python federation-audit/experience-program/scripts/rc0_baseline.py \
  --root <directory holding the eight checkouts> \
  --out federation-audit/experience-program/rc0 --verify-recovery
```

Each checkout needs `origin/main` fetched first. The script fetches only into a
temporary directory that it deletes.

```bash
python federation-audit/experience-program/scripts/rc1_merge.py \
  --surveys federation-audit/experience-program/rc1/surveys \
  --snapshots <directory holding one export of each audited commit> \
  --baselines federation-audit/experience-program/rc0/repository_baselines.json \
  --out federation-audit/experience-program/rc1
```

A snapshot is `git archive <audited commit> | tar -x -C <dir>/<repo>`.

```bash
python federation-audit/experience-program/scripts/rc2_validate.py <contract.json> [...]
pytest tests/test_experience_contract.py
```

```bash
python federation-audit/experience-program/scripts/rc3_runtime_detail.py \
  <directory holding the runtime pass's out-<repository>.json files> \
  federation-audit/experience-program/rc3/runtime_element_detail.json
```

```bash
cd federation-design/packages/react && npm run verify
cd ../../fixture-lab && npm ci && npm run dev &
GUI_ENGINES=chromium node tests/runtime-matrix.mjs
```

`GUI_SUITES=controls` limits the matrix to the control fixtures.

```bash
python federation-audit/experience-program/scripts/rc4_pilot_input.py \
  --rc3 federation-audit/experience-program/rc3/runtime_element_detail.json \
  --rescan <directory holding the re-scan's out-thehub-pr.json> \
  --audited-raw <out-thehub-pr.json of the audited commit> \
  --rescan-commit <commit re-scanned> --drift <main_drift.json> --pins <pins.json> \
  --out federation-audit/experience-program/rc4
```

`main_drift.json` maps each repository to its audited commit and whether its
frontend changed on `main` since; `pins.json` maps it to its design-system pin.

```bash
python federation-audit/experience-program/scripts/rc4_pilot_compare.py \
  --before <out-<repository>.json before> --after <out-<repository>.json after> \
  --before-commit <sha> --after-commit <sha> \
  --out federation-audit/experience-program/rc4/<repository>_pilot.json
```

```bash
P=federation-audit/experience-program/scripts
python $P/rc8_baseline.py coldstart --snapshots <dir of exports> --repository <name> --label <label> --port 9500 --out <raw>/coldstart-<label>.json
python $P/rc8_baseline.py sizes --dist <export>/<frontend>/dist --repository <name> --label <label> --out <raw>/sizes-<label>.json
python $P/runtime/serve_snapshot.py <dir of exports> <name> 9500 &
node $P/runtime/perf_pass.js <name> 9500 <routes.json> <raw> <label>
python $P/rc8_baseline.py tabulate --raw <raw> --targets <targets.json> --out federation-audit/experience-program/rc8/performance_baselines.json
python $P/rc9_matrix.py --targets <targets.json> --observed <observed.json> --out federation-audit/experience-program/rc9/compatibility_matrix.json
```

Run the measurements one application at a time; parallel runs disturb each
other's timings.

```bash
P=federation-audit/experience-program/scripts
python $P/runtime/serve_snapshot.py <dir of exports> <name> 9600 &
for e in chromium firefox webkit; do
  mkdir -p <raw>/$e
  GUI_ENGINE=$e node $P/runtime/chromium_pass.js <name> 9600 <routes.json> <axe.min.js> <raw>/$e
  # or, for an application with one address:
  # GUI_ENGINE=$e node $P/runtime/views_pass.js <name> 9600 <axe.min.js> <raw>/$e
  # and, Chromium only, for states that need more than a tab click:
  # node $P/runtime/states_pass.js <name> 9600 <states.json> <axe.min.js> <raw>/$e
done
python $P/rc10_engine_tabulate.py --raw <raw> --commits <commits.json> \
  --out federation-audit/experience-program/cross-engine/engine_matrix.json
```

Firefox and WebKit need `npx playwright@<installed version> install firefox webkit`
and, on Linux, `npx playwright@<version> install-deps webkit firefox`.

# Federation Test-Harness Audit

**Scope:** `federation-design/test-harness/` — the cross-repo a11y/visual acceptance harness thehub-pr
owns and publishes for all seven PRII federation frontends. This audit covers what the harness's
contract actually requires, how (and whether) each of the seven sibling repos wires it into CI, a
live proof-of-concept run of both harness specs against this repo's own app and native screen, and
the gaps found along the way.

This is new coverage: the prior `docs/GUI_AUDIT.md` audited the dashboard, `desktop/launcher.html`,
and the design system's components, but never the harness itself or the native Setup & Diagnostics
screen the harness's `desktop-setup.spec.js` targets.

---

## 1. What the contract enforces

Source: `federation-design/test-harness/test-harness.contract.json` (version `1.0.0`), described by
its own README as "the repository-neutral acceptance matrix for every federation frontend."

| Dimension | Values |
|---|---|
| **Viewports** (6) | `mobile-compact` 390×844, `mobile-wide` 430×932, `tablet` 768×1024, `desktop` 1280×800, `desktop-wide` 1440×900, `wide` 1920×1080 |
| **States** (11) | `populated`, `loading`, `empty`, `filtered_empty`, `error`, `stale`, `offline`, `degraded`, `partial`, `long_labels`, `keyboard_only` |
| **Themes** (2) | `light`, `dark` |
| **Requirements** | `axeCriticalSerious: 0` · `minimumTouchTargetCssPx: 44` · `horizontalOverflow: false` · `keyboardCriticalWorkflows: "100%"` |
| **Commands** | `unit: npm test` · `a11y/contrast/reducedMotion: npm run verify` · `package: npm pack` |

Full matrix as specified: 6 viewports × 11 states × 2 themes = **132 cells** per consuming
application. Nothing in the repo actually drives that full matrix (see §4).

Two Playwright specs ship in `tests/`:

- **`federation-smoke.spec.js`** — points at `process.env.FEDERATION_ROUTE || '/'` against
  `process.env.FEDERATION_BASE_URL` (default `http://127.0.0.1:4173`). Four checks: axe-core
  critical/serious violations = 0, first-Tab focus outline visible, no horizontal overflow, and a
  full-page visual snapshot (`toHaveScreenshot`). Runs on 4 projects defined in
  `playwright.config.js`: `tablet-768`, `desktop-1280`, `desktop-1440`, `desktop-1920`.
- **`desktop-setup.spec.js`** — targets the native "Setup & Diagnostics" pywebview screen via a
  static HTML fixture (`PRII_SETUP_FIXTURE`), mocking `window.pywebview.api` and firing
  `pywebviewready`. `test.skip`'d unless `PRII_SETUP_FIXTURE` is set. Checks: the heading and copy
  render, the app icon loads, every visible `button` is ≥44px tall, an optional full-page screenshot
  (`PRII_VISUAL_DIR`), axe critical/serious = 0, keyboard focus visible, no horizontal overflow.

`package.json` devDependencies: `@axe-core/playwright ^4.10.2`, `@playwright/test ^1.53.0` (harness
package itself is `@pr-federation/test-harness@0.1.0`, private).

---

## 2. Per-repo consumption-status matrix

Verified directly against each repo's `.github/workflows/desktop-build.yml` in this container
(`/home/user/<repo>/.github/workflows/desktop-build.yml`), current as of this audit.

| Repo | `desktop-setup.spec.js` wired? | Step name | OS gating | Trigger |
|---|---|---|---|---|
| **thehub-pr** | Yes | `Visual and accessibility smoke for native setup` | `if: runner.os == 'Linux'` | `workflow_dispatch`, `push: tags: desktop-v*`, `pull_request` (path-filtered: `desktop/**`, `server/frontend/**`, `federation-design/**`, etc.) |
| **spiderweb-pr** | Yes | `Visual and accessibility smoke for native setup` | `if: runner.os == 'Linux'` | same shape, path-filtered on `desktop/**`, `server/frontend/**` |
| **skywatcher-pr** | Yes | `Visual and accessibility smoke` | `if: runner.os == 'Linux'` | same shape, path-filtered on `desktop/**`, `frontend/**` |
| **centinelas-pr** | Yes | `Visual and accessibility smoke` | `if: runner.os == 'Linux'` | same shape, path-filtered on `desktop/**`, `frontend/**` |
| **aguayluz-pr** | Yes | `Visual and accessibility smoke` | `if: runner.os == 'Linux'` | same shape, path-filtered on `desktop/**`, `dashboard/**` |
| **ovnis-pr** | **No — dead fetch** | n/a | n/a | fetches pinned thehub-pr tooling (`PRII_TOOLING_REF` commit, cloned to `$RUNNER_TEMP` outside the workspace) but never invokes `render_desktop_setup.py` or `playwright test` against it anywhere in the workflow. Confirmed via full-file read: `$PRII_TOOLING_ROOT` is set once and never referenced again after the clone step. |
| **moneysweep-pr** | **No — absent** | n/a | n/a | no reference to `test-harness`, `desktop-setup`, `render_desktop_setup`, or `PRII_TOOLING_ROOT` anywhere in `desktop-build.yml` (161 lines, grepped in full) |

All 5 wired repos run the exact same pattern: `python "$PRII_TOOLING_ROOT/tools/render_desktop_setup.py" --repo . --output desktop-ui-artifacts/setup.html`, then `cd "$PRII_TOOLING_ROOT/federation-design/test-harness"` and `npx playwright test tests/desktop-setup.spec.js` (skywatcher-pr, centinelas-pr, aguayluz-pr additionally pin `--project=tablet-768 --project=desktop-1280`, narrowing to 2 of the harness's 4 configured projects). All 5 gate the step to the Linux leg only of a 3-OS (`ubuntu-latest, macos-latest, windows-latest`) build matrix, followed by an `Upload native setup visual evidence` step (also Linux-gated, `if: runner.os == 'Linux' && always()`).

Critically, **none of the 7 repos' `desktop-build.yml` triggers on ordinary pushes to `main`** — every
one is `workflow_dispatch` + `push: tags: desktop-v*` + a `pull_request` gated to paths under
`desktop/**` and a few other desktop-adjacent directories. A normal feature PR that doesn't touch
those paths never runs this check at all.

**`federation-smoke.spec.js` (the web-dashboard-facing spec) usage:** grepped every `.yml` in all
7 repos' `.github/workflows/` for `federation-smoke` — **zero matches, anywhere.** Its only live
consumer, in any repo, is `desktop-setup.spec.js` running against the native screen (which imports
nothing from `federation-smoke.spec.js` — they're independent specs; the point is simply that the
*route-driven, live-web-app* smoke test has no CI consumer at all). thehub-pr's own `ci.yml` runs a
separate, local `server/frontend` Playwright visual-regression suite (`test:visual`, committed
snapshot baselines) and `centinelas-pr`/`aguayluz-pr`/`moneysweep-pr` each run their own
`gui-capability-parity.yml` (also Playwright-based) — both are repo-local tooling, not this harness.

---

## 3. Proof-of-concept: running the harness against thehub-pr

Ran from the harness's own copy (`federation-design/test-harness/`, `npm install` — 5 packages, no
prior lockfile drift), not the shared `/home/user/.a11y-runner` used for the broader a11y pass.

**Environment note:** the harness's `playwright.config.js` specifies no `launchOptions.executablePath`,
so it resolves Playwright's default per-version browser cache, which in this container only has
`chromium-1194`/`chromium_headless_shell-1194` provisioned (matching a newer pinned Playwright than
this harness's own `^1.53.0` — the installed `@playwright/test` here resolved to a version expecting
`chromium_headless_shell-1234`, not present). Ran with a temporary one-line addition
(`launchOptions: { executablePath: process.env.PW_CHROME_PATH }`) to `use:` in
`playwright.config.js`, invoked with `PW_CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`,
then reverted (`git checkout --`) immediately after both runs — not part of this PR's diff. This is
the same category of environment-only accommodation the prior GUI audit made for the Vite dev-server
proxy (see `docs/GUI_AUDIT.md`), and it points at exactly the browser build the shared a11y runner
already uses.

### 3a. `federation-smoke.spec.js` against the live dashboard

```
FEDERATION_BASE_URL=http://127.0.0.1:5302 FEDERATION_ROUTE=/ npx playwright test tests/federation-smoke.spec.js
```

Result: **8 failed, 4 passed** (4 projects × 2 failing checks: axe smoke + keyboard-focus-visible;
no-horizontal-overflow passed on all 4). The axe failure is byte-for-byte the same `button-name`
critical violation (2 unnamed Radix Select combobox triggers) independently reproduced here that the
broader a11y pass found via the shared runner — see `docs/A11Y_AUDIT.md` §Findings — confirming the
harness's own tooling correctly catches the same real issue. This is the first time, in any repo in
this container, that `federation-smoke.spec.js` has been run against an actual live web dashboard
rather than left unwired.

The `keyboard-focus-visible` failure here is the same pre-hydration timing race documented in
`docs/A11Y_AUDIT.md` (Method section) — `page.goto(route)`'s default `'load'` wait fires before the
SPA hydrates, so the first `Tab` press lands on `<body>` with nothing focusable yet. Re-verified
independently after allowing the app to settle: the actual first focusable element (a sidebar nav
link) does get a clearly visible 2px solid outline. This is a gap in the test's own wait strategy,
not a missing focus style — flagged as a harness gap below (§4).

### 3b. `desktop-setup.spec.js` against the native Setup & Diagnostics screen

```
PYTHONPATH=/home/user/thehub-pr/packages/prii_desktop/src python tools/render_desktop_setup.py \
  --repo /home/user/thehub-pr --output /tmp/thehub-setup-fixture.html
PRII_SETUP_FIXTURE=/tmp/thehub-setup-fixture.html PRII_VISUAL_DIR=/tmp/thehub-setup-visual \
  PRII_REPO_SLUG=thehub-pr npx playwright test tests/desktop-setup.spec.js
```

Result: **4 passed, 0 failed** — all 4 projects (`tablet-768`, `desktop-1280`, `desktop-1440`,
`desktop-1920`) clean: axe critical/serious = 0, every visible button ≥44px tall, keyboard focus
visible with a clear outline, no horizontal overflow, heading/copy/icon all present. Screenshots
saved to `/tmp/thehub-setup-visual/thehub-pr-<project>-thehub-setup-fixture.png` (not committed —
this is a live-run artifact, matching how CI's own `Upload native setup visual evidence` step
handles them as workflow artifacts rather than repo content).

This is a genuinely new, clean result: **this screen was never covered by the prior `docs/GUI_AUDIT.md`
audit at all** (that audit covered `desktop/launcher.html`, a different screen, but not
`setup_center.py`'s `render_setup_html()` output). The native screen's buttons pass the 44px minimum
that the web dashboard's shadcn buttons do not (see `docs/A11Y_AUDIT.md`) — worth noting as a positive
contrast: the two frontends in this repo (native pywebview UI vs. React web dashboard) currently sit
on opposite sides of the touch-target requirement.

---

## 4. Gaps

1. **Zero mobile Playwright projects in the harness's own config.** The contract lists two mobile
   viewports (`mobile-compact` 390×844, `mobile-wide` 430×932) among its six, but
   `federation-design/test-harness/playwright.config.js` defines only four projects — `tablet-768`,
   `desktop-1280`, `desktop-1440`, `desktop-1920` — all tablet/desktop. No project in the harness
   itself ever runs at either mobile width. (The *shared* `/home/user/.a11y-runner` used for the
   broader a11y pass in this audit does cover a `mobile-compact` project — but that is a separate,
   ad hoc runner outside this repo, not part of what `federation-design/test-harness` itself ships
   or what any repo's CI invokes.) This means the one mobile-viewport violation this audit did find —
   `horizontal-overflow: true` on `/crossover` and `/research` at 390px width, caused by a
   non-wrapping shadcn `TabsList` — is a class of bug the harness's own config is structurally unable
   to catch, in any repo, ever.

2. **`desktop-build.yml` is not part of normal CI.** In every one of the 5 repos that wire
   `desktop-setup.spec.js` at all, the workflow triggers only on `workflow_dispatch`, a
   `desktop-v*` tag push, or a `pull_request` filtered to desktop-adjacent paths (see §2 table) — and
   even then, only the Linux leg of a 3-OS matrix runs the check. A routine feature PR that doesn't
   touch those specific paths gets zero harness coverage. Combined with finding 3 below
   (`federation-smoke.spec.js` having no CI consumer anywhere), this repo's actual web dashboard
   receives no automated a11y regression coverage from this harness in the normal PR flow.

3. **`federation-smoke.spec.js` has no live consumer anywhere.** Confirmed by grepping all 7 repos'
   `.github/workflows/*.yml` for `federation-smoke`: zero matches. Its only exercise, in this
   container, is the ad hoc proof-of-concept run in §3a of this audit. The harness ships a spec
   purpose-built to smoke-test a routed web page, and no repo's CI has ever run it against one.

4. **Two repos' desktop-build.yml wiring is broken or absent, contradicting the "5 of 7" pattern:**
   - **ovnis-pr** clones the pinned thehub-pr tooling into `$RUNNER_TEMP/prii-thehub-tooling` (with
     an explicit `Enforce isolated desktop-build policy` step forbidding a checked-out
     `../thehub-pr` sibling) but never calls `render_desktop_setup.py` or `playwright test` against
     it — the fetch is vestigial. Given the isolation policy already routes the clone outside the
     workspace specifically to *avoid* a live sibling checkout, wiring the same two steps the other
     5 repos use (pointing at `$PRII_TOOLING_ROOT` instead of a relative sibling path) looks like a
     straightforward, low-risk fix rather than a deliberate exemption.
   - **moneysweep-pr** has no reference to the tooling, harness, or `desktop-setup` at all in its
     `desktop-build.yml`.

5. **Pre-v0.4 `@pr-federation/react` pins can't resolve the shipped contract file.** The
   `./test-harness.json` → `./dist/test-harness.contract.json` export first appears in
   `federation-design/packages/react/package.json` at tag `federation-design-v0.4.0-rc.1`
   (confirmed absent at `v0.1.0` through `v0.3.1`, present from `v0.4.0-rc.1` through the current
   `v0.4.1`). Checking each sibling repo's own `@pr-federation/react` dependency spec:

   | Repo | `@pr-federation/react` spec | Ships the contract export? |
   |---|---|---|
   | thehub-pr | `file:../../federation-design/packages/react` (always current — this repo owns the source) | Yes (0.4.1) |
   | spiderweb-pr | *(not a dependency at all — its frontend doesn't consume the package)* | n/a |
   | skywatcher-pr | tarball pinned to `federation-design-v0.3.0` | **No** |
   | centinelas-pr | tarball pinned to `federation-design-v0.3.0` | **No** |
   | aguayluz-pr | tarball pinned to `federation-design-v0.4.0` | Yes |
   | ovnis-pr | tarball pinned to `federation-design-v0.3.0` | **No** |
   | moneysweep-pr | tarball pinned to `federation-design-v0.4.1` | Yes |

   Today this is a **latent** gap, not an active break: grepping skywatcher-pr, centinelas-pr, and
   ovnis-pr for any code path that actually tries to `require`/`readJson` the package's
   `test-harness.json`/`test-harness.contract.json` export turned up nothing in any of the three.
   But the pattern already exists elsewhere in the federation — moneysweep-pr's
   `dashboard/scripts/verify-federation-design-package.mjs` reads
   `node_modules/@pr-federation/react/dist/test-harness.contract.json` directly, and it works there
   only because moneysweep-pr happens to be pinned to v0.4.1. The same script (or any future one
   like it) added to skywatcher-pr, centinelas-pr, or ovnis-pr while they remain pinned to v0.3.0
   would fail to resolve that path immediately.

---

## Summary

The harness's contract is well-specified and its two live specs (federation-smoke,
desktop-setup) both work correctly when actually invoked — this audit is the first time either has
been run against thehub-pr's real app/screen outside the narrow, path-gated `desktop-build.yml`
flow, and both surfaced real, independently-confirmable findings (or, for desktop-setup, a clean
pass). The gaps are entirely about *reach*: no mobile viewport coverage in the harness's own config,
no normal-CI trigger for the desktop leg that does exist, zero consumers anywhere for the web-facing
spec, two repos with broken or absent wiring, and a version-pin inconsistency that has not yet bitten
anyone but structurally could.

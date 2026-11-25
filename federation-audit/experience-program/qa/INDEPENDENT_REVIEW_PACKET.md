# Independent review packet: RC3 design-system changes and RC4 fixes

This packet is for a reviewer who is **not the author** of the work, or for a
reviewer the user names. The author has not reviewed the work independently and
does not count as a reviewer. Until a filled-in sign-off (bottom of this page)
is recorded in `rc3/RC3_GATE.json` and `rc4/RC4_GATE.json`, the
`independent_review` check in both gates stays `BLOCKED`.

Nothing here is merged. Review each pull request at the head named below; if a
head has moved, review the new head and say which one you reviewed.

## What to review

| # | Pull request | Before → after (evidence commits) | Evidence (sha256 as recorded in the gate) |
|---|---|---|---|
| 1 | thehub-pr#435, `federation-design/` only (RC3) | n/a, package `0.6.0-rc.1`, unreleased | `rc3/runtime_element_detail.json` `9d83a06f…2140`, `rc3/chromium_matrix_receipt.json` `960db722…c749` |
| 2 | [skywatcher-pr#375](https://github.com/jotaele44/skywatcher-pr/pull/375) | `a217699` → `1301570` | `rc4/skywatcher_pilot.json` `567d29b7…b38d` |
| 3 | [aguayluz-pr#420](https://github.com/jotaele44/aguayluz-pr/pull/420) | `6e3a4f6` → `c60587e` | `rc4/aguayluz_pilot.json` `f1042aa0…579d2`, `rc4/aguayluz_water_use_before_after.png` |
| 4 | [moneysweep-pr#719](https://github.com/jotaele44/moneysweep-pr/pull/719) | `956bb49` → `6c9a0fe` | `rc4/moneysweep_pilot.json` `dedf61a7…9c40` |
| 5 | [centinelas-pr#198](https://github.com/jotaele44/centinelas-pr/pull/198) | `893a06f` → `d96863d` | `rc4/centinelas_pilot.json` `fbfd76cb…08f2` |
| 6 | [thehub-pr#435](https://github.com/jotaele44/thehub-pr/pull/435), `server/frontend/` (RC4) | `95c6c99` → `978007b`, then `d2fa3e3` (tab bar) and `766080d` (phone width) | `rc4/thehub_pilot.json` `54f85b71…8ed1`, `rc4/thehub_overflow.json` `0bfa9fed…ac01` |

ovnis-pr#204 and the Múcaro scan are recorded in `RC4_GATE.json` too. They are
outside this request; review them the same way if you have time.

Every count in the evidence files is the author's own Chromium scan, run with
the scripts in `scripts/`. A scan shows that the rules axe-core checks no longer
fire. It does not show that a control works, reads well, or announces correctly.
That judgement is what a reviewer adds.

## What changed, and what to check

### 1. RC3 shared design system (`federation-design/packages/react/src/`)
- **Changed:** the primary button and the default focus outline use
  `--fd-accent-strong`, `--fd-accent-contrast` and `--fd-focus-ring`. New:
  `controls/ScrollRegion.jsx`, `controls/Menu.jsx` (Menu, ItemMenu, ExportMenu),
  `controls/RenameDialog.jsx` (Dialog, TextField, RenameDialog),
  FederationResponsiveLabel, FederationStatusMark, and pinned and recent groups
  in `shell/ModuleNav.jsx`.
- **Check:**
  - Focus return. A dialog or menu that closes gives focus back to its opener only
    when nothing else has taken focus. Look for the four defects listed under
    `defects_found_and_fixed_during_rc3` in `RC3_GATE.json` and confirm each fix
    is sound.
  - A rename dialog selects the whole name on opening, and Enter and Escape behave.
  - A menu closes on Escape and on a click outside it, and not on a page scroll.
  - ScrollRegion is a tab stop only while its content overflows, and has an
    accessible name.
  - The "More (n)" disclosure: the brief named a flyout submenu instead. Judge
    whether the substitute is acceptable.
  - Where to try it: `federation-design/fixture-lab`, page `controls.html`
    (`npm ci && npm run dev`). No application uses Menu or RenameDialog yet.

### 2. skywatcher-pr#375
- **Changed:** the mobile navigation toggle (name follows its state,
  `aria-expanded`, 44px target); `lib/scrollRegion.js` on 32 scroll containers;
  the Sky Target Finder rows (the button holds only the name, and the detail line
  is its description).
- **Check:**
  - The toggle's name reads "Open…" and "Close…" correctly in both states.
  - The helper sets `tabindex`, `role`/`aria-label` only on boxes that actually
    scroll.
  - The rows still work with the seven tests that depend on their names.
  - `link-in-text-block` was deliberately left as it is.

### 3. aguayluz-pr#420
- **Changed:** 312 uses of `text-slate-500/600/700` moved to `text-slate-400` (a
  test blocks their return); opacity removed from the log timestamps; the
  selected range button changed to `sky-700` with `aria-pressed`; six select
  boxes named; the scroll helper on 44 containers.
- **Check:**
  - The visual hierarchy: dim text and muted text are now the same grey. Is
    anything that used to be secondary now confusing?
  - The test's pattern cannot be bypassed trivially.
  - The six select names are meaningful.
  - CI on that head was not fully green: one DNS-failure job, never re-run.
  - **New in this pass (FACT):** `constraints-desktop.txt` at `c60587e` pins
    `pydantic-core==2.48.0` next to `pydantic==2.13.5`, which requires
    `pydantic-core==2.46.5`. A fresh `desktop/setup.py` fails to resolve. See
    `cross-engine/engine_matrix.json`.

### 4. moneysweep-pr#719
- **Changed:** `TypeFilterSelect` takes a label and both callers pass one; the
  scroll helper on 16 containers.
- **Check:** the label text is right for each caller.

### 5. centinelas-pr#198
- **Changed:** phase pills use a passing shade per theme (700 light, 400 dark);
  the brand link is named by its visible text; the language toggle's name starts
  with the language code it shows.
- **Check:**
  - **The light theme was never scanned.** The pill contrast there is reasoned
    from the shades only, so check it by eye or with a contrast tool.
  - The toggle reads well in both languages.
  - The rise in undersized controls on `/handoff` (2732 → 2788) was not traced;
    decide whether it matters.
  - Same pydantic pin conflict as AguaYLuz, at `d96863d` and on current `main`.

### 6. thehub-pr#435 (Hub frontend)
- **Changed:**
  - 13 select boxes named;
  - icon-only buttons named (feed refresh, two send buttons, memory panel close,
    GitHub link, and the tasks view toggle below 640px);
  - three scroll containers on `FederationScrollRegion`, including the shared
    Table wrapper;
  - launcher note colour raised to 7:1;
  - the tab bar (`server/frontend/src/components/ui/tabs.jsx`) scrolls instead
    of widening the page;
  - the GIS view switcher and the crossover date group wrap at phone width;
  - the satellite pass buttons are named "Show track: …" (commit `cce4832`).
- **Check:**
  - **The satellite pass fix is PROVISIONAL.** It is covered by unit tests only,
    because the live satellite data seldom loaded during scans. Check it in a
    browser that can reach CelesTrak.
  - A horizontally scrolling tab bar must still show that more tabs exist, and
    keyboard focus must scroll the hidden tabs into view.

## How to re-run the comparisons

```bash
P=federation-audit/experience-program/scripts
python $P/rc4_pilot_compare.py --before <out-before.json> --after <out-after.json> \
  --before-commit <sha> --after-commit <sha> --out /tmp/<repo>_pilot.json
```

Serving a snapshot and scanning it is described under **Re-running** in
`../README.md`. `GUI_ENGINE=firefox` or `webkit` runs the same pass in those
engines.

## Sign-off (to be filled in by the reviewer, not the author)

```text
Reviewer name / handle:
Relationship to the work (must not be the author):
Date:
Heads reviewed (repo@sha):
Findings (file:line, severity, description):
Verdict per item 1-6: ACCEPT / ACCEPT WITH CHANGES / REJECT
```

When a filled-in sign-off is recorded, `independent_review` in both gates may
move from `BLOCKED` to `PASS` only for the items accepted, with the reviewer
named in the gate. Items with requested changes become `OPEN`.

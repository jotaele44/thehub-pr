import fs from 'node:fs'
import path from 'node:path'
import { chromium, firefox, webkit } from 'playwright'

const BASE_URL = process.env.GUI_BASE_URL || 'http://127.0.0.1:5173'
const OUT = path.resolve(process.env.GUI_ARTIFACT_DIR || 'artifacts/runtime-matrix')
fs.mkdirSync(OUT, { recursive: true })

const fixtures = [
  'POS_NONEMPTY','POS_EMPTY','POS_FILTERED_ZERO','POS_FACT','POS_COMPUTED','POS_BINDING','POS_UNRESOLVED','POS_SUPERSEDED',
  'NEG_NULL','NEG_UNDEFINED','NEG_EMPTY_STRING','NEG_DUPLICATE_ID','NEG_DUPLICATE_NAME','NEG_LONG_NAME','NEG_UNICODE','NEG_LARGE_CURRENCY','NEG_NEGATIVE_CURRENCY','NEG_INVALID_DATE','NEG_STALE','NEG_PARTIAL','NEG_OFFLINE','NEG_TIMEOUT','NEG_429','NEG_500','NEG_MALFORMED_SCHEMA','NEG_AMBIGUOUS_IDENTITY','NEG_1_TO_N','NEG_N_TO_1','NEG_N_TO_N','NEG_CONTRADICTION','NEG_SOURCE_MISSING','NEG_HASH_MISMATCH',
]
// Shell fixtures live on their own page (shell.html) and carry their own
// expectations: a shell puts a skip link first, so the "first Tab reaches the
// footer button" rule above cannot apply to them. `mobileBelow` is the width
// under which the fixture shows the bottom bar; `more` says whether the
// registry is large enough to need a "More" entry there.
const shellFixtures = [
  { id: 'SHELL_SIDEBAR', mobileBelow: 768, more: true, second: 'Hub' },
  { id: 'SHELL_SIDEBAR_DARK', mobileBelow: 768, more: true, second: 'Hub' },
  { id: 'SHELL_STATE_NAV', mobileBelow: 768, more: true, second: 'Map' },
  { id: 'SHELL_FEW_DESKTOP_BREAK', mobileBelow: 1280, more: false, second: 'Signals' },
  { id: 'SHELL_INSPECTOR', mobileBelow: 768, more: true, second: 'Hub', inspector: true },
  { id: 'SHELL_LONG_LABELS', mobileBelow: 768, more: true, second: null },
]
// The control fixtures (controls.html) are one page, driven at every width
// with one repository accent per width, then scanned with axe for every
// repository in both themes at a phone and a desktop width.
const controlRepos = ['thehub-pr', 'spiderweb-pr', 'skywatcher-pr', 'moneysweep-pr', 'centinelas-pr', 'aguayluz-pr', 'ovnis-pr']
const controlAxeWidths = [375, 1280]
const axeSource = fs.readFileSync(new URL('../node_modules/axe-core/axe.min.js', import.meta.url), 'utf8')
const viewports = [320,375,768,1280,1440,1920]
const allEngines = { chromium, firefox, webkit }
// Local runs may not have every browser. CI runs all three; GUI_ENGINES
// narrows the set, and GUI_CHROMIUM_EXECUTABLE points at a system Chromium.
const selected = (process.env.GUI_ENGINES || Object.keys(allEngines).join(',')).split(',').map((name) => name.trim()).filter(Boolean)
for (const name of selected) if (!allEngines[name]) throw new Error(`unknown engine in GUI_ENGINES: ${name}`)
const engines = Object.fromEntries(selected.map((name) => [name, allEngines[name]]))
const launchOptions = (engineName) => ({
  headless: true,
  ...(engineName === 'chromium' && process.env.GUI_CHROMIUM_EXECUTABLE ? { executablePath: process.env.GUI_CHROMIUM_EXECUTABLE } : {}),
})
// GUI_SUITES narrows a local run to some suites (baseline, shell, controls,
// reduced-motion). CI runs all of them; the expected cell counts in the
// summary assume that.
const suites = new Set((process.env.GUI_SUITES || 'baseline,shell,controls,reduced-motion').split(',').map((name) => name.trim()))
const results = []
let failed = false

function push(entry) { results.push(entry); if (entry.status === 'FAIL') failed = true }

const verdict = (condition) => (condition ? 'PASS' : 'FAIL')
const visibleCount = (page, selector) => page.evaluate((sel) => [...document.querySelectorAll(sel)].filter((node) => node.getClientRects().length > 0).length, selector)
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)
const focusIs = (page, selector) => page.evaluate((sel) => Boolean(document.activeElement?.matches(sel)), selector)

// One shell fixture at one width. Every value is PASS, FAIL or SKIP; the cell
// fails if any is FAIL. The checks are the shell's contract
// (docs/FEDERATION_GUI_STANDARD.md section 4), exercised in a real browser.
async function runShellChecks(page, fixture, width, engineName) {
  const mobile = width < fixture.mobileBelow
  const checks = {}
  await page.goto(`${BASE_URL}/shell.html?fixture=${fixture.id}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.locator(`[data-fixture-id="${fixture.id}"]`).waitFor({ timeout: 30000 })
  await page.screenshot({ path: path.join(OUT, `${engineName}-${width}-${fixture.id}.png`), fullPage: true })

  checks.no_horizontal_overflow = verdict(await noOverflow(page))

  // The skip link is the first stop, and it lands on main.
  await page.keyboard.press('Tab')
  let skipFocused = await focusIs(page, '.fd-shell__skip')
  if (!skipFocused && engineName === 'webkit') {
    await page.keyboard.press('Alt+Tab')
    skipFocused = await focusIs(page, '.fd-shell__skip')
  }
  checks.skip_link_first = verdict(skipFocused)
  if (skipFocused) await page.keyboard.press('Enter')
  checks.skip_link_reaches_main = verdict(skipFocused && await focusIs(page, '#fd-main'))

  // Exactly one primary navigation is exposed, with exactly one current page.
  checks.one_primary_nav = verdict(await visibleCount(page, 'nav[aria-label="Primary"]') === 1)
  checks.one_current_page = verdict(await visibleCount(page, 'nav[aria-label="Primary"] [aria-current="page"]') === 1)
  checks.sidebar_matches_viewport = verdict((await visibleCount(page, '.fd-shell__nav')) === (mobile ? 0 : 1))
  checks.bottom_bar_matches_viewport = verdict((await visibleCount(page, '.fd-shell__mobile-nav')) === (mobile ? 1 : 0))

  if (mobile) {
    const bar = await page.evaluate(() => [...document.querySelectorAll('.fd-mobile-nav__list > li > *')].map((node) => {
      const box = node.getBoundingClientRect()
      return { width: box.width, height: box.height }
    }))
    checks.bar_at_most_five = verdict(bar.length >= 1 && bar.length <= 5)
    checks.bar_touch_targets = verdict(bar.every((box) => box.width >= 44 && box.height >= 44))
    const more = page.locator('.fd-mobile-nav__more')
    checks.more_entry_matches_registry = verdict((await more.count()) === (fixture.more ? 1 : 0))
    if (fixture.more) {
      const sheet = page.locator('dialog.fd-mobile-nav__sheet')
      await more.click()
      const opened = await sheet.evaluate((node) => node.open && node.matches(':modal'))
      await page.keyboard.press('Escape')
      await page.waitForFunction(() => !document.querySelector('dialog.fd-mobile-nav__sheet').open)
      checks.more_opens_and_escape_closes = verdict(opened)
      checks.more_focus_returns = verdict(await focusIs(page, '.fd-mobile-nav__more'))
      // Choosing an entry closes the sheet and makes it the current page,
      // which the bar reports on "More" because the entry is not on it.
      await more.click()
      const before = await page.locator('#page-title').getAttribute('data-current')
      await sheet.locator('.fd-nav__link').last().click()
      await page.waitForFunction(() => !document.querySelector('dialog.fd-mobile-nav__sheet').open)
      const after = await page.locator('#page-title').getAttribute('data-current')
      checks.sheet_entry_navigates = verdict(after !== before)
      checks.more_marks_overflow_current = verdict(await more.getAttribute('aria-current') === 'page')
      checks.no_horizontal_overflow_after_sheet = verdict(await noOverflow(page))
    }
  } else {
    checks.sidebar_touch_targets = verdict(await page.evaluate(() => [...document.querySelectorAll('.fd-shell__nav .fd-nav__link')].every((node) => node.getBoundingClientRect().height >= 44)))
    if (fixture.second) {
      await page.locator('.fd-shell__nav .fd-nav__link', { hasText: fixture.second }).first().click()
      checks.sidebar_click_moves_current = verdict(
        (await visibleCount(page, 'nav[aria-label="Primary"] [aria-current="page"]')) === 1
        && (await page.locator('.fd-shell__nav [aria-current="page"]').innerText()).includes(fixture.second),
      )
      // focusMainOnNavigate: the new page is announced by moving focus to it.
      checks.focus_moves_to_main_on_navigate = verdict(await focusIs(page, '#fd-main'))
    }
  }

  if (fixture.inspector) {
    const docked = width >= 1280
    const panel = page.locator('dialog.fd-inspector')
    await page.locator('#open-inspector').click()
    const state = await panel.evaluate((node) => ({ open: node.open, modal: node.matches(':modal') }))
    checks.inspector_opens = verdict(state.open)
    checks.inspector_presentation_matches_viewport = verdict(state.modal === !docked)
    checks.no_horizontal_overflow_with_inspector = verdict(await noOverflow(page))
    if (docked) {
      // Docked, it is a side panel: it must not take focus from the opener.
      checks.inspector_docked_keeps_focus = verdict(await focusIs(page, '#open-inspector'))
      await panel.locator('.fd-inspector__close').click()
    } else {
      checks.inspector_modal_traps_focus = verdict(await page.evaluate(() => document.querySelector('dialog.fd-inspector').contains(document.activeElement)))
      await page.keyboard.press('Escape')
    }
    await page.waitForFunction(() => !document.querySelector('dialog.fd-inspector').open)
    checks.inspector_closes = 'PASS'
    checks.inspector_focus_returns = verdict(await focusIs(page, '#open-inspector'))
  }
  return checks
}

// Critical and serious axe findings on the page as it stands. Returned as
// "rule: selector" strings so a failure names the element.
async function blockingAxe(page) {
  if (!(await page.evaluate(() => Boolean(window.axe)))) await page.addScriptTag({ content: axeSource })
  return page.evaluate(async () => {
    const result = await window.axe.run(document, { resultTypes: ['violations'] })
    return result.violations
      .filter((violation) => violation.impact === 'critical' || violation.impact === 'serious')
      .flatMap((violation) => violation.nodes.map((node) => `${violation.id}: ${node.target.join(' ')}`))
  })
}

const activeMenuItem = (page) => page.evaluate(() => document.activeElement?.getAttribute('data-menu-item-id') || null)
const menuOpen = (page, root) => page.evaluate((sel) => Boolean(document.querySelector(`${sel} [role="menu"]`)), root)
const dialogState = (page, selector) => page.evaluate((sel) => {
  const node = document.querySelector(sel)
  return { open: Boolean(node?.open), modal: Boolean(node?.matches(':modal')) }
}, selector)
const waitClosed = (page, selector) => page.waitForFunction((sel) => !document.querySelector(sel)?.open, selector)

// The control primitives at one width, driven from the keyboard. The checks
// are the contracts in packages/react/tests/controls-contracts.test.mjs,
// exercised in a real browser.
async function runControlsChecks(page, width, engineName, repo, theme) {
  const checks = {}
  const notes = {}
  try {
    return await driveControls(page, width, engineName, repo, theme, checks, notes)
  } catch (error) {
    // Say how far it got: a timeout alone does not name the step.
    error.message = `${error.message} (after check: ${Object.keys(checks).at(-1) || 'none'})`
    throw error
  }
}

async function driveControls(page, width, engineName, repo, theme, checks, notes) {
  const mobile = width < 768
  await page.goto(`${BASE_URL}/controls.html?repo=${repo}&theme=${theme}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.locator('[data-fixture-id="CONTROLS"]').waitFor({ timeout: 30000 })
  await page.screenshot({ path: path.join(OUT, `${engineName}-${width}-CONTROLS.png`), fullPage: true })
  checks.no_horizontal_overflow = verdict(await noOverflow(page))

  // A label hidden on a small screen is still the button's name.
  checks.responsive_label_is_the_name = verdict(await page.getByRole('button', { name: 'Board view', exact: true }).count() === 1)
  const labelWidth = await page.locator('#responsive .fd-responsive-label').evaluate((node) => node.getBoundingClientRect().width)
  checks.responsive_label_hidden_matches_viewport = verdict(mobile ? labelWidth <= 1 : labelWidth > 1)

  // A scrolling box with nothing focusable inside is a tab stop; one with
  // nothing to scroll is not.
  await page.waitForFunction(() => document.querySelector('#scroll')?.getAttribute('tabindex') === '0', null, { timeout: 5000 }).catch(() => {})
  checks.scroll_region_is_tab_stop = verdict(await page.locator('#scroll').getAttribute('tabindex') === '0')
  checks.short_region_is_not_tab_stop = verdict(await page.locator('#noscroll').getAttribute('tabindex') === null)
  checks.dataset_grid_is_tab_stop = verdict(await page.locator('.lab-grid .fd-gis-grid').getAttribute('tabindex') === '0')
  await page.locator('#scroll').focus()
  await page.keyboard.press('End')
  await page.waitForFunction(() => document.querySelector('#scroll').scrollTop > 0, null, { timeout: 3000 }).catch(() => {})
  checks.scroll_region_scrolls_from_keyboard = verdict(await page.locator('#scroll').evaluate((node) => node.scrollTop > 0))

  // Menu button: arrows open, move, wrap and skip the disabled action.
  const trigger = page.locator('#menu .fd-menu__trigger')
  await trigger.focus()
  await page.keyboard.press('ArrowDown')
  checks.menu_arrow_down_opens_on_first = verdict(await activeMenuItem(page) === 'rename')
  checks.menu_stays_inside_viewport = verdict(await page.locator('#menu [role="menu"]').evaluate((node) => {
    const box = node.getBoundingClientRect()
    return box.left >= 0 && box.top >= 0 && box.right <= window.innerWidth && box.bottom <= window.innerHeight
  }))
  const walk = []
  for (const key of ['ArrowDown', 'ArrowDown', 'ArrowDown', 'End', 'Home', 'ArrowUp', 'u']) {
    await page.keyboard.press(key)
    walk.push(await activeMenuItem(page))
  }
  notes.menu_walk = walk.join(',')
  checks.menu_keys_move_wrap_and_skip_disabled = verdict(notes.menu_walk === 'unpin,delete,rename,delete,rename,delete,unpin')
  await page.keyboard.press('Escape')
  checks.menu_escape_closes_and_returns_focus = verdict(!(await menuOpen(page, '#menu')) && await focusIs(page, '#menu .fd-menu__trigger'))
  await page.keyboard.press('ArrowUp')
  checks.menu_arrow_up_opens_on_last = verdict(await activeMenuItem(page) === 'delete')
  await page.locator('#page-title').click()
  checks.menu_outside_click_closes = verdict(!(await menuOpen(page, '#menu')))

  // Rename: opened from the menu, validated, and focus comes back.
  const rename = 'dialog.fd-rename-dialog'
  const input = page.locator(`${rename} input`)
  const alertText = () => page.locator(`${rename} [role="alert"]`).innerText().catch(() => '')
  await trigger.focus()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.waitForFunction((sel) => document.querySelector(sel)?.open, rename)
  const opened = await dialogState(page, rename)
  checks.rename_is_a_modal_dialog = verdict(opened.open && opened.modal)
  checks.rename_focuses_the_name_selected = verdict(await page.evaluate((sel) => {
    const field = document.querySelector(`${sel} input`)
    return document.activeElement === field && field.value === 'Budget review' && field.selectionStart === 0 && field.selectionEnd === field.value.length
  }, rename))
  checks.rename_unchanged_cannot_save = verdict(await page.locator(`${rename} button[type="submit"]`).isDisabled())
  await input.fill('   ')
  await page.keyboard.press('Enter')
  checks.rename_rejects_empty = verdict((await alertText()).includes('Enter a name') && (await dialogState(page, rename)).open)
  await input.fill('x'.repeat(41))
  await page.keyboard.press('Enter')
  checks.rename_rejects_too_long = verdict((await alertText()).includes('40') && (await dialogState(page, rename)).open)
  await input.fill('fail')
  await page.keyboard.press('Enter')
  await page.locator(`${rename} [role="alert"]`).waitFor({ timeout: 3000 }).catch(() => {})
  checks.rename_reports_failed_save_and_stays_open = verdict((await alertText()).includes('refused') && (await dialogState(page, rename)).open && await input.inputValue() === 'fail')
  await input.fill('  Budget review 2026  ')
  await page.keyboard.press('Enter')
  await waitClosed(page, rename)
  checks.rename_saves_trimmed_name = verdict(await page.locator('#name').innerText() === 'Budget review 2026')
  checks.rename_focus_returns_to_opener = verdict(await focusIs(page, '#menu .fd-menu__trigger'))
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.waitForFunction((sel) => document.querySelector(sel)?.open, rename)
  await input.fill('Abandoned')
  await page.keyboard.press('Escape')
  await waitClosed(page, rename)
  checks.rename_escape_cancels = verdict(await page.locator('#name').innerText() === 'Budget review 2026' && await focusIs(page, '#menu .fd-menu__trigger'))

  // Dialog: modal, initial focus where asked, Escape in a menu inside it
  // closes only the menu, and focus returns to the opener.
  const dialog = 'dialog.fd-dialog:not(.fd-rename-dialog)'
  await page.locator('#open-dialog').focus()
  await page.keyboard.press('Enter')
  await page.waitForFunction((sel) => document.querySelector(sel)?.open, dialog)
  const shown = await dialogState(page, dialog)
  checks.dialog_is_modal = verdict(shown.open && shown.modal)
  checks.dialog_initial_focus_where_asked = verdict(await page.evaluate(() => document.activeElement?.hasAttribute('data-autofocus')))
  checks.dialog_blocking_axe = verdict((notes.dialog_axe = await blockingAxe(page)).length === 0)
  await page.locator('#menu-in-dialog .fd-menu__trigger').focus()
  await page.keyboard.press('ArrowDown')
  const innerOpened = await menuOpen(page, '#menu-in-dialog')
  await page.keyboard.press('Escape')
  checks.menu_escape_inside_dialog_closes_only_the_menu = verdict(innerOpened && !(await menuOpen(page, '#menu-in-dialog')) && (await dialogState(page, dialog)).open)
  await page.keyboard.press('Escape')
  await waitClosed(page, dialog)
  checks.dialog_escape_returns_focus = verdict(await focusIs(page, '#open-dialog'))

  // Pinned and recent groups.
  checks.one_current_page = verdict(await visibleCount(page, 'nav[aria-label="Primary"] [aria-current="page"]') === 1)
  if (mobile) {
    // Collections never take a bar slot; having entries, they force "More".
    const more = page.locator('.fd-mobile-nav__more')
    checks.collections_force_more = verdict(await more.count() === 1)
    await more.click()
    const sheet = page.locator('dialog.fd-mobile-nav__sheet')
    checks.sheet_holds_pinned_and_recent = verdict(
      await sheet.locator('.fd-nav__group[data-kind="pinned"] .fd-nav__row').count() === 2
      && await sheet.locator('.fd-nav__group[data-kind="recent"]').count() === 2,
    )
    checks.sheet_item_menu_named_after_item = verdict(await sheet.getByRole('button', { name: 'Actions for Budget review 2026', exact: true }).count() === 1)
    await page.keyboard.press('Escape')
    await waitClosed(page, 'dialog.fd-mobile-nav__sheet')
  } else {
    const side = page.locator('.fd-shell__nav')
    const pinned = side.locator('.fd-nav__group[data-kind="pinned"]')
    const recent = side.locator('.fd-nav__group[data-kind="recent"]').first()
    const searches = side.locator('.fd-nav__group[data-kind="recent"]').nth(1)
    checks.pinned_rows_shown = verdict(await pinned.locator('.fd-nav__row').count() === 2)
    checks.item_menu_named_after_item = verdict(await side.getByRole('button', { name: 'Actions for Budget review 2026', exact: true }).count() === 1)
    checks.status_is_part_of_the_link_name = verdict(await side.getByRole('link', { name: /Budget review 2026.*Running/ }).count() === 1)
    checks.item_menu_touch_target = verdict(await pinned.locator('.fd-menu__trigger').first().evaluate((node) => {
      const box = node.getBoundingClientRect()
      return box.width >= 44 && box.height >= 44
    }))
    checks.recent_shows_limit = verdict(await recent.locator('.fd-nav__row').count() === 3)
    const moreButton = recent.locator('.fd-nav__more')
    checks.recent_overflow_is_a_disclosure = verdict(await moreButton.getAttribute('aria-expanded') === 'false' && (await moreButton.innerText()).includes('(4)'))
    await moreButton.focus()
    await page.keyboard.press('Enter')
    checks.recent_overflow_expands = verdict(await recent.locator('.fd-nav__row').count() === 7 && await moreButton.getAttribute('aria-expanded') === 'true')
    // overflow: 'scroll' shows every entry in a box sized to the limit; its
    // entries are links, so the box needs no tab stop of its own.
    checks.scroll_overflow_lists_all = verdict(await searches.locator('.fd-nav__row').count() === 5)
    checks.scroll_overflow_box_is_not_a_tab_stop = verdict(await searches.locator('.fd-scroll-region').getAttribute('tabindex') === null)
    // Opening a pinned entry marks it without creating a second current page.
    await pinned.locator('.fd-nav__link').first().click()
    checks.open_pinned_entry_is_marked = verdict(await visibleCount(page, '.fd-shell__nav [aria-current="true"]') === 1)
    checks.still_one_current_page = verdict(await visibleCount(page, 'nav[aria-label="Primary"] [aria-current="page"]') === 1)
    // An item action reaches the host.
    await pinned.locator('.fd-menu__trigger').nth(1).focus()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    checks.item_action_reaches_host = verdict(await page.locator('#log').getAttribute('data-log') === 'unpin:case-2' && await pinned.locator('.fd-nav__row').count() === 1)
  }
  checks.no_horizontal_overflow_after_use = verdict(await noOverflow(page))
  checks.blocking_axe = verdict((notes.axe = await blockingAxe(page)).length === 0)
  return { checks, notes }
}

for (const [engineName, engine] of Object.entries(engines)) {
  const browser = await engine.launch(launchOptions(engineName))
  try {
    for (const width of suites.has('baseline') ? viewports : []) {
      const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } })
      const page = await context.newPage()
      for (const fixture of fixtures) {
        const pageErrors = []
        page.removeAllListeners('pageerror')
        page.on('pageerror', (err) => pageErrors.push(String(err)))
        try {
          await page.goto(`${BASE_URL}/?fixture=${fixture}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
          await page.locator(`[data-fixture-id="${fixture}"]`).waitFor({ timeout: 30000 })
          const screenshot = `${engineName}-${width}-${fixture}.png`
          await page.screenshot({ path: path.join(OUT, screenshot), fullPage: true })

          await page.locator('body').click({ position: { x: 2, y: 2 } })
          await page.keyboard.press('Tab')
          let keyboardNavigationKey = 'Tab'
          let keyboardTarget = await page.evaluate(() => document.activeElement?.id === 'keyboard-target')
          if (!keyboardTarget && engineName === 'webkit') {
            await page.locator('body').click({ position: { x: 2, y: 2 } })
            await page.keyboard.press('Alt+Tab')
            keyboardNavigationKey = 'Alt+Tab'
            keyboardTarget = await page.evaluate(() => document.activeElement?.id === 'keyboard-target')
          }

          await page.evaluate(() => { document.documentElement.style.zoom = '2' })
          const zoomStress = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }))
          await page.evaluate(() => { document.documentElement.style.zoom = '' })

          push({
            engine: engineName,
            viewport: width,
            fixture,
            status: pageErrors.length === 0 && keyboardTarget ? 'PASS' : 'FAIL',
            page_errors: pageErrors,
            keyboard_only: keyboardTarget ? 'PASS' : 'FAIL',
            keyboard_navigation_key: keyboardNavigationKey,
            css_200_percent_zoom_stress: zoomStress.scrollWidth > 0 ? 'PASS' : 'FAIL',
            native_200_percent_zoom_certified: false,
            screenshot,
          })
        } catch (error) {
          push({ engine: engineName, viewport: width, fixture, status: 'FAIL', error: String(error), page_errors: pageErrors })
        }
      }
      await context.close()
    }

    for (const width of suites.has('shell') ? viewports : []) {
      for (const fixture of shellFixtures) {
        const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } })
        const page = await context.newPage()
        const pageErrors = []
        page.on('pageerror', (err) => pageErrors.push(String(err)))
        try {
          const checks = await runShellChecks(page, fixture, width, engineName)
          const failures = Object.entries(checks).filter(([, value]) => value === 'FAIL').map(([name]) => name)
          push({
            engine: engineName,
            viewport: width,
            fixture: fixture.id,
            suite: 'shell',
            status: pageErrors.length === 0 && failures.length === 0 ? 'PASS' : 'FAIL',
            page_errors: pageErrors,
            failed_checks: failures,
            ...checks,
          })
        } catch (error) {
          push({ engine: engineName, viewport: width, fixture: fixture.id, suite: 'shell', status: 'FAIL', error: String(error), page_errors: pageErrors })
        } finally {
          await context.close()
        }
      }
    }

    for (const [index, width] of suites.has('controls') ? viewports.entries() : []) {
      const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } })
      const page = await context.newPage()
      const pageErrors = []
      page.on('pageerror', (err) => pageErrors.push(String(err)))
      const repo = controlRepos[index % controlRepos.length]
      const theme = index % 2 === 0 ? 'light' : 'dark'
      try {
        const { checks, notes } = await runControlsChecks(page, width, engineName, repo, theme)
        const failures = Object.entries(checks).filter(([, value]) => value === 'FAIL').map(([name]) => name)
        push({
          engine: engineName,
          viewport: width,
          fixture: 'CONTROLS',
          suite: 'controls',
          repo,
          theme,
          status: pageErrors.length === 0 && failures.length === 0 ? 'PASS' : 'FAIL',
          page_errors: pageErrors,
          failed_checks: failures,
          notes,
          ...checks,
        })
      } catch (error) {
        push({ engine: engineName, viewport: width, fixture: 'CONTROLS', suite: 'controls', repo, status: 'FAIL', error: String(error), page_errors: pageErrors })
      } finally {
        await context.close()
      }
    }

    // Every repository accent in both themes: the page at rest, with a menu
    // open and with the rename dialog open.
    for (const width of suites.has('controls') ? controlAxeWidths : []) {
      for (const repo of controlRepos) {
        for (const theme of ['light', 'dark']) {
          const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 } })
          const page = await context.newPage()
          try {
            await page.goto(`${BASE_URL}/controls.html?repo=${repo}&theme=${theme}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
            await page.locator('[data-fixture-id="CONTROLS"]').waitFor({ timeout: 30000 })
            const findings = { rest: await blockingAxe(page) }
            await page.locator('#primary').focus()
            await page.locator('#menu .fd-menu__trigger').focus()
            await page.keyboard.press('ArrowDown')
            findings.menu_open = await blockingAxe(page)
            await page.keyboard.press('Enter')
            await page.waitForFunction(() => document.querySelector('dialog.fd-rename-dialog')?.open)
            await page.locator('dialog.fd-rename-dialog input').fill(' ')
            await page.keyboard.press('Enter')
            findings.rename_open_with_error = await blockingAxe(page)
            const total = Object.values(findings).flat().length
            push({ engine: engineName, viewport: width, fixture: 'CONTROLS', suite: 'controls-axe', repo, theme, status: total === 0 ? 'PASS' : 'FAIL', findings })
          } catch (error) {
            push({ engine: engineName, viewport: width, fixture: 'CONTROLS', suite: 'controls-axe', repo, theme, status: 'FAIL', error: String(error) })
          } finally {
            await context.close()
          }
        }
      }
    }

    for (const fixture of suites.has('reduced-motion') ? [...fixtures, ...shellFixtures.map((entry) => entry.id)] : []) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })
      const page = await context.newPage()
      try {
        await page.goto(`${BASE_URL}/${fixture.startsWith('SHELL_') ? 'shell.html' : ''}?fixture=${fixture}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
        const matches = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
        push({ engine: engineName, viewport: 1280, fixture, mode: 'reduced-motion', status: matches ? 'PASS' : 'FAIL' })
      } catch (error) {
        push({ engine: engineName, viewport: 1280, fixture, mode: 'reduced-motion', status: 'FAIL', error: String(error) })
      } finally {
        await context.close()
      }
    }
  } finally {
    await browser.close()
  }
}

const baseline = results.filter((r) => !r.mode && !r.suite)
const shell = results.filter((r) => r.suite === 'shell')
const reduced = results.filter((r) => r.mode === 'reduced-motion')
const controls = results.filter((r) => r.suite === 'controls')
const controlsAxe = results.filter((r) => r.suite === 'controls-axe')
const summary = {
  schema_version: '1.0',
  fixtures: fixtures.length,
  positive_fixtures: fixtures.filter((x) => x.startsWith('POS_')).length,
  negative_fixtures: fixtures.filter((x) => x.startsWith('NEG_')).length,
  engines: Object.keys(engines),
  viewports,
  expected_baseline_cells: fixtures.length * Object.keys(engines).length * viewports.length,
  observed_baseline_cells: baseline.length,
  shell_fixtures: shellFixtures.length,
  expected_shell_cells: shellFixtures.length * Object.keys(engines).length * viewports.length,
  observed_shell_cells: shell.length,
  shell_cells_passed: shell.filter((r) => r.status === 'PASS').length,
  expected_controls_cells: Object.keys(engines).length * viewports.length,
  observed_controls_cells: controls.length,
  controls_cells_passed: controls.filter((r) => r.status === 'PASS').length,
  expected_controls_axe_cells: Object.keys(engines).length * controlAxeWidths.length * controlRepos.length * 2,
  observed_controls_axe_cells: controlsAxe.length,
  controls_axe_cells_passed: controlsAxe.filter((r) => r.status === 'PASS').length,
  expected_reduced_motion_cells: (fixtures.length + shellFixtures.length) * Object.keys(engines).length,
  observed_reduced_motion_cells: reduced.length,
  keyboard_cells_passed: baseline.filter((r) => r.keyboard_only === 'PASS').length,
  css_zoom_stress_cells_passed: baseline.filter((r) => r.css_200_percent_zoom_stress === 'PASS').length,
  native_200_percent_zoom_certified: false,
  failures: results.filter((r) => r.status === 'FAIL').length,
  results,
}
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2) + '\n')
console.log(JSON.stringify({
  expected_baseline_cells: summary.expected_baseline_cells,
  observed_baseline_cells: summary.observed_baseline_cells,
  expected_shell_cells: summary.expected_shell_cells,
  observed_shell_cells: summary.observed_shell_cells,
  shell_cells_passed: summary.shell_cells_passed,
  expected_controls_cells: summary.expected_controls_cells,
  controls_cells_passed: summary.controls_cells_passed,
  expected_controls_axe_cells: summary.expected_controls_axe_cells,
  controls_axe_cells_passed: summary.controls_axe_cells_passed,
  expected_reduced_motion_cells: summary.expected_reduced_motion_cells,
  observed_reduced_motion_cells: summary.observed_reduced_motion_cells,
  keyboard_cells_passed: summary.keyboard_cells_passed,
  failures: summary.failures,
  native_200_percent_zoom_certified: false,
}, null, 2))
process.exit(failed ? 1 : 0)

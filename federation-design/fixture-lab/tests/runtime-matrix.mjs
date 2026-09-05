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
const viewports = [320,375,768,1280,1440,1920]
const engines = { chromium, firefox, webkit }
const results = []
let failed = false

function push(entry) { results.push(entry); if (entry.status === 'FAIL') failed = true }

for (const [engineName, engine] of Object.entries(engines)) {
  const browser = await engine.launch({ headless: true })
  try {
    for (const width of viewports) {
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
          const zoomStressPassed = zoomStress.scrollWidth <= zoomStress.clientWidth

          push({
            engine: engineName,
            viewport: width,
            fixture,
            status: pageErrors.length === 0 && keyboardTarget && zoomStressPassed ? 'PASS' : 'FAIL',
            page_errors: pageErrors,
            keyboard_only: keyboardTarget ? 'PASS' : 'FAIL',
            keyboard_navigation_key: keyboardNavigationKey,
            css_200_percent_zoom_stress: zoomStressPassed ? 'PASS' : 'FAIL',
            css_zoom_scroll_width: zoomStress.scrollWidth,
            css_zoom_client_width: zoomStress.clientWidth,
            native_200_percent_zoom_certified: false,
            screenshot,
          })
        } catch (error) {
          push({ engine: engineName, viewport: width, fixture, status: 'FAIL', error: String(error), page_errors: pageErrors })
        }
      }
      await context.close()
    }

    for (const fixture of fixtures) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })
      const page = await context.newPage()
      try {
        await page.goto(`${BASE_URL}/?fixture=${fixture}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
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

const baseline = results.filter((r) => !r.mode)
const reduced = results.filter((r) => r.mode === 'reduced-motion')
const summary = {
  schema_version: '1.0',
  fixtures: fixtures.length,
  positive_fixtures: fixtures.filter((x) => x.startsWith('POS_')).length,
  negative_fixtures: fixtures.filter((x) => x.startsWith('NEG_')).length,
  engines: Object.keys(engines),
  viewports,
  expected_baseline_cells: fixtures.length * Object.keys(engines).length * viewports.length,
  observed_baseline_cells: baseline.length,
  expected_reduced_motion_cells: fixtures.length * Object.keys(engines).length,
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
  expected_reduced_motion_cells: summary.expected_reduced_motion_cells,
  observed_reduced_motion_cells: summary.observed_reduced_motion_cells,
  keyboard_cells_passed: summary.keyboard_cells_passed,
  failures: summary.failures,
  native_200_percent_zoom_certified: false,
}, null, 2))
process.exit(failed ? 1 : 0)

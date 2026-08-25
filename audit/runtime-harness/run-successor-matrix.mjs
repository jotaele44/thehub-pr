import fs from 'node:fs'
import path from 'node:path'
import { chromium, firefox, webkit } from 'playwright'

const APP = process.env.GUI_APP
const BASE_URL = process.env.GUI_BASE_URL || 'http://127.0.0.1:5173'
const OUT = path.resolve(process.env.GUI_ARTIFACT_DIR || `artifacts/${APP}`)
fs.mkdirSync(OUT, { recursive: true })

const routesByApp = {
  'thehub-pr': ['/', '/activity', '/programs', '/apps', '/operations', '/cases', '/sources', '/tasks', '/gates', '/integrations', '/exports', '/readiness', '/transition', '/crossover', '/anomaly-overlap', '/control', '/hub', '/project-signs', '/research', '/dictionary', '/manifest', '/spiderweb', '/ovnis', '/aguayluz', '/moneysweep', '/skywatcher', '/centinelas', '/__gui_not_found__'],
  'moneysweep-pr': ['/', '/__gui_not_found__'],
  'aguayluz-pr': ['/', '/map', '/assets', '/alerts', '/outages', '/monitoring', '/cave-karst', '/regulatory', '/regulatory/review', '/environmental-exposure', '/review', '/analytics', '/logs', '/system', '/water-disruption', '/__gui_not_found__'],
  'ovnis-pr': ['/', '/__gui_not_found__'],
  'centinelas-pr': ['/', '/monitor', '/signals', '/matters', '/sources', '/handoff', '/pipeline', '/water-disruption', '/tabla', '/entidades', '/__gui_not_found__'],
}
if (!routesByApp[APP]) throw new Error(`Unsupported GUI_APP: ${APP}`)

const engines = { chromium, firefox, webkit }
const widths = [320, 375, 768, 1280, 1440, 1920]
const results = []
let failed = false
const slug = (route) => route === '/' ? 'root' : route.replace(/^\//, '').replace(/[^a-zA-Z0-9_-]+/g, '-')
const record = (row) => { results.push(row); if (row.status === 'FAIL') failed = true }

async function waitForSettled(page) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(700)
  await page.locator('body').waitFor({ state: 'visible', timeout: 30000 })
}
async function keyboardProbe(page) {
  await page.keyboard.press('Home').catch(() => {})
  const traversed = []
  for (let i = 0; i < 10; i += 1) {
    await page.keyboard.press('Tab')
    const f = await page.evaluate(() => {
      const el = document.activeElement
      if (!el || el === document.body || el === document.documentElement) return null
      return { tag: el.tagName, text: (el.textContent || '').trim().slice(0, 80), ariaLabel: el.getAttribute?.('aria-label') || null, href: el instanceof HTMLAnchorElement ? el.getAttribute('href') : null }
    })
    if (f) traversed.push(f)
  }
  return traversed
}

for (const [engineName, engine] of Object.entries(engines)) {
  const browser = await engine.launch({ headless: true })
  try {
    for (const width of widths) {
      const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, reducedMotion: 'no-preference' })
      try {
        // Each rendered surface owns a fresh Page and error ledger. This prevents
        // asynchronous work (maps, blobs, streams) from one surface from
        // contaminating the next surface after navigation.
        for (const route of routesByApp[APP]) {
          const page = await context.newPage()
          const pageErrors = []
          page.on('pageerror', (e) => pageErrors.push(String(e)))
          try {
            await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded', timeout: 45000 })
            await waitForSettled(page)
            const body = await page.locator('body').innerText()
            const screenshot = `${engineName}-${width}-${slug(route)}.png`
            await page.screenshot({ path: path.join(OUT, screenshot), fullPage: true })
            record({ app: APP, engine: engineName, viewport: width, route, status: body.trim().length > 0 && pageErrors.length === 0 ? 'PASS' : 'FAIL', body_nonempty: body.trim().length > 0, page_errors: [...pageErrors], screenshot })
          } catch (error) {
            record({ app: APP, engine: engineName, viewport: width, route, status: 'FAIL', error: String(error), page_errors: [...pageErrors] })
          } finally { await page.close() }
        }

        const kp = await context.newPage()
        try {
          await kp.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 45000 })
          await waitForSettled(kp)
          const traversed = await keyboardProbe(kp)
          record({ app: APP, engine: engineName, viewport: width, mode: 'keyboard-only', status: traversed.length > 0 ? 'PASS' : 'FAIL', traversed })
        } catch (error) {
          record({ app: APP, engine: engineName, viewport: width, mode: 'keyboard-only', status: 'FAIL', error: String(error) })
        } finally { await kp.close() }
      } finally { await context.close() }
    }

    const reduced = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })
    const rp = await reduced.newPage()
    try {
      await rp.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 45000 })
      await waitForSettled(rp)
      const matches = await rp.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
      record({ app: APP, engine: engineName, viewport: 1280, mode: 'reduced-motion', status: matches ? 'PASS' : 'FAIL' })
    } catch (error) { record({ app: APP, engine: engineName, viewport: 1280, mode: 'reduced-motion', status: 'FAIL', error: String(error) }) }
    finally { await reduced.close() }
  } finally { await browser.close() }
}

const expectedSurfaceCells = routesByApp[APP].length * Object.keys(engines).length * widths.length
const observedSurfaceCells = results.filter(r => r.route).length
const summary = { schema_version: '1.0', app: APP, routes: routesByApp[APP], engines: Object.keys(engines), viewports: widths, expected_surface_cells: expectedSurfaceCells, observed_surface_cells: observedSurfaceCells, keyboard_cells: results.filter(r => r.mode === 'keyboard-only').length, reduced_motion_cells: results.filter(r => r.mode === 'reduced-motion').length, failures: results.filter(r => r.status === 'FAIL').length, native_200_percent_zoom_certified: false, results }
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2) + '\n')
console.log(JSON.stringify({ app: APP, expected_surface_cells: expectedSurfaceCells, observed_surface_cells: observedSurfaceCells, failures: summary.failures }, null, 2))
process.exit(failed || observedSurfaceCells !== expectedSurfaceCells ? 1 : 0)

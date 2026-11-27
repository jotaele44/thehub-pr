// Chromium pass over named UI states of a single-address application.
//
// views_pass.js opens each in-memory view by its tab. Some surfaces appear only
// after a further click: a selection fills an inspector, a phone width hides a
// panel behind a toggle, a run prints a log. A states file lists those, each as
// a short sequence of steps, and this runs the same measures and axe-core
// detail as views_pass.js on each. Each state is recorded as the route
// "/#state:<name>", so rc3_runtime_detail.py and rc4_pilot_compare.py read the
// output unchanged. Records what was observed; decides nothing.
//
// usage: node states_pass.js <repository> <port> <states.json> <axe.min.js> <out dir>
//
// states.json: { "<repository>": { "states": [ { "name": "...", "min_width"?: n,
//   "max_width"?: n, "steps": [ step, ... ] } ] } }
// A step is one of {"click": sel}, {"click_if_visible": sel}, {"fill": [sel, text]},
// {"press": [sel, key]}, {"wait": sel}, where sel is a Playwright selector.
// A state is opened on a fresh page loaded at "/". A step that fails records
// the error for that state and width; no axe result is kept for it.
// BYPASS_CSP=1 lifts a strict script policy for this test context only, and the
// output records that it was lifted.
const playwright = require('playwright');
const fs = require('fs');

const [,, name, port, statesFile, axeFile, outDir] = process.argv;
const states = JSON.parse(fs.readFileSync(statesFile))[name].states;
const axeSource = fs.readFileSync(axeFile, 'utf8');
const WIDTHS = [320, 390, 430, 768, 1280, 1440, 1920];
const DETAIL = ['color-contrast', 'button-name', 'scrollable-region-focusable', 'label-content-name-mismatch'];

async function measure(page) {
  const row = await page.evaluate(() => {
    const d = document.documentElement;
    const unnamed = [...document.querySelectorAll('button, [role=button]')].filter((e) => {
      const r = e.getBoundingClientRect(); if (!r.width || !r.height) return false;
      return !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('title') || (e.textContent || '').trim());
    }).length;
    const small = [...document.querySelectorAll('button, a[href], [role=button], input:not([type=hidden]), select')]
      .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24); }).length;
    return {
      final_path: location.pathname + location.search,
      rendered_text_chars: (document.body.innerText || '').trim().length,
      horizontal_overflow_px: Math.max(0, d.scrollWidth - d.clientWidth),
      controls_under_24px: small, unnamed_buttons: unnamed,
    };
  });
  if (!(await page.evaluate(() => Boolean(window.axe)))) await page.addScriptTag({ content: axeSource });
  const axe = await page.evaluate(async (detailRules) => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    const detail = (v) => v.nodes.slice(0, 80).map((n) => {
      const d = ((n.any || []).find((c) => c.data && c.data.fgColor) || {}).data;
      return Object.assign({ target: n.target.join(' '), html: n.html.slice(0, 200) },
        d ? { fg: d.fgColor, bg: d.bgColor, ratio: d.contrastRatio, expected: d.expectedContrastRatio, font_size: d.fontSize, font_weight: d.fontWeight } : {});
    });
    return { version: window.axe.version, violations: r.violations.map((v) => Object.assign({ id: v.id, impact: v.impact, nodes: v.nodes.length }, detailRules.includes(v.id) ? { detail: detail(v) } : {})) };
  }, DETAIL);
  return { row, axe };
}

async function run(page, step) {
  if (step.click) return page.locator(step.click).first().click({ timeout: 5000 });
  if (step.click_if_visible) {
    const target = page.locator(step.click_if_visible).first();
    if (await target.isVisible()) await target.click({ timeout: 5000 });
    return undefined;
  }
  if (step.fill) return page.locator(step.fill[0]).first().fill(step.fill[1], { timeout: 5000 });
  if (step.press) return page.locator(step.press[0]).first().press(step.press[1], { timeout: 5000 });
  if (step.wait) return page.locator(step.wait).first().waitFor({ timeout: 8000 });
  throw new Error('unknown step ' + JSON.stringify(step));
}

(async () => {
  const browser = await playwright.chromium.launch();
  const out = { repository: name, engine: 'chromium', browser_version: browser.version(), base: 'http://127.0.0.1:' + port, mode: 'named states', axe_version: null, csp_bypassed_for_scan: process.env.BYPASS_CSP === '1', states: states.map((s) => s.name), observations: [] };
  for (const width of WIDTHS) {
    const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, colorScheme: 'dark', bypassCSP: process.env.BYPASS_CSP === '1' });
    for (const state of states) {
      if ((state.min_width && width < state.min_width) || (state.max_width && width > state.max_width)) continue;
      const page = await context.newPage();
      const pageErrors = [];
      page.on('pageerror', (e) => pageErrors.push(String(e).slice(0, 160)));
      const obs = { route: `/#state:${state.name}`, width };
      try {
        const response = await page.goto(out.base + '/', { waitUntil: 'domcontentloaded', timeout: 20000 });
        obs.status = response ? response.status() : null;
        await page.waitForLoadState('networkidle', { timeout: 6000 }).catch(() => {});
        await page.waitForTimeout(400);
        for (const step of state.steps) {
          await run(page, step);
          await page.waitForTimeout(250);
        }
        await page.waitForLoadState('networkidle', { timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(400);
        const { row, axe } = await measure(page);
        out.axe_version = axe.version;
        Object.assign(obs, row, { axe: axe.violations });
      } catch (e) { obs.error = String(e).slice(0, 200); }
      obs.page_errors = pageErrors.slice(0, 2);
      out.observations.push(obs);
      await page.close();
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(`${outDir}/out-${name}.json`, JSON.stringify(out, null, 1));
  console.log(name, 'states', states.length, 'observations', out.observations.length, 'errors', out.observations.filter((o) => o.error).length);
})();

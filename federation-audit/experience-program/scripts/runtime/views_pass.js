// Chromium pass over the in-memory views of a single-address application.
//
// Some applications keep their views in memory and have one address, so a
// route scan sees only the first view. This loads "/", finds the controls that
// switch views (tabs, or the buttons of a workspace list), opens each one and
// runs the same measures and axe-core detail as chromium_pass.js. Each view is
// recorded as the route "/#view:<label>", so rc3_runtime_detail.py and
// rc4_pilot_compare.py read the output unchanged. Records what was observed;
// decides nothing.
//
// usage: node views_pass.js <repository> <port> <axe.min.js> <out dir>
// BYPASS_CSP=1 lifts a strict script policy for this test context only, and
// the output records that it was lifted.
// GUI_ENGINE=chromium|firefox|webkit picks the browser (default chromium, which
// is what every RC1 to RC4 pass used). The output records the engine and its
// version; keep one output directory per engine.
const playwright = require('playwright');
const ENGINE = process.env.GUI_ENGINE || 'chromium';
if (!['chromium', 'firefox', 'webkit'].includes(ENGINE)) throw new Error('GUI_ENGINE must be chromium, firefox or webkit');
const fs = require('fs');

const [,, name, port, axeFile, outDir] = process.argv;
const axeSource = fs.readFileSync(axeFile, 'utf8');
const WIDTHS = [320, 390, 430, 768, 1280, 1440, 1920];
// Controls that switch an in-memory view, in the order they are tried.
const SWITCHERS = ['[role=tablist] [role=tab]', '.workspace-nav button', 'nav button[aria-current], nav button'];
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

(async () => {
  const browser = await playwright[ENGINE].launch();
  const out = { repository: name, engine: ENGINE, browser_version: browser.version(), base: 'http://127.0.0.1:' + port, mode: 'in-memory views', axe_version: null, csp_bypassed_for_scan: process.env.BYPASS_CSP === '1', switcher: null, observations: [] };
  for (const width of WIDTHS) {
    const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, colorScheme: 'dark', bypassCSP: process.env.BYPASS_CSP === '1' });
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(String(e).slice(0, 160)));
    await page.goto(out.base + '/', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForLoadState('networkidle', { timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(500);
    // Find the switcher once per width: on a phone a menu may hide it, so
    // only controls that are visible now are used.
    let selector = null; let labels = [];
    for (const candidate of SWITCHERS) {
      labels = await page.$$eval(candidate, (els) => els.filter((e) => e.getBoundingClientRect().width > 0).map((e) => (e.textContent || '').trim()).filter(Boolean));
      if (labels.length > 1) { selector = candidate; break; }
    }
    out.switcher = out.switcher || selector;
    if (!selector) {
      const { row, axe } = await measure(page);
      out.axe_version = axe.version;
      out.observations.push(Object.assign({ route: '/#view:(only)', width, status: 200, axe: axe.violations, page_errors: pageErrors.slice(0, 2), note: 'no view switcher visible at this width' }, row));
    }
    for (const label of selector ? labels : []) {
      const obs = { route: `/#view:${label}`, width, status: 200 };
      try {
        const target = page.locator(selector, { hasText: label }).first();
        // On a phone the view list can sit off screen behind a collapsed menu,
        // where it still counts as visible. If the click cannot land, open the
        // menu's toggle and try again.
        try {
          await target.click({ timeout: 2500 });
        } catch {
          const toggle = page.locator('button[aria-expanded="false"][aria-label*="navigation" i], button[aria-expanded="false"][aria-label*="menu" i]').first();
          if (!(await toggle.count())) throw new Error('view control not clickable and no menu toggle found');
          await toggle.click({ timeout: 3000 });
          await page.waitForTimeout(300);
          obs.opened_menu_first = true;
          await target.click({ timeout: 5000 });
        }
        await page.waitForLoadState('networkidle', { timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(500);
        const { row, axe } = await measure(page);
        out.axe_version = axe.version;
        Object.assign(obs, row, { axe: axe.violations });
      } catch (e) { obs.error = String(e).slice(0, 200); }
      obs.page_errors = pageErrors.splice(0).slice(0, 2);
      out.observations.push(obs);
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(`${outDir}/out-${name}.json`, JSON.stringify(out, null, 1));
  console.log(name, 'switcher', out.switcher, 'observations', out.observations.length, 'errors', out.observations.filter((o) => o.error).length);
})();

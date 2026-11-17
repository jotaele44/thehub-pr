// Chromium runtime pass for one application: every addressable route at seven
// viewport widths. Records what was observed; decides nothing.
const { chromium } = require('playwright');
const fs = require('fs');
// usage: node chromium_pass.js <repository> <port> <routes.json> <axe.min.js> <out dir>
const [,, name, port, routesFile, axeFile, outDir] = process.argv;
const routes = JSON.parse(fs.readFileSync(routesFile))[name].routes;
const axeSource = fs.readFileSync(axeFile, 'utf8');
const WIDTHS = [320, 390, 430, 768, 1280, 1440, 1920];
(async () => {
  const browser = await chromium.launch();
  const out = { repository: name, base: 'http://127.0.0.1:' + port, axe_version: null, csp_bypassed_for_scan: process.env.BYPASS_CSP === '1', observations: [] };
  for (const width of WIDTHS) {
    // An application with a strict script-src policy refuses the injected axe
    // source. BYPASS_CSP=1 lifts the policy for this test context only, and the
    // output records that it was lifted.
    const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, colorScheme: 'dark', bypassCSP: process.env.BYPASS_CSP === '1' });
    for (const route of routes) {
      const page = await context.newPage();
      const consoleErrors = [], pageErrors = [], failed = [];
      page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 160)); });
      page.on('pageerror', e => pageErrors.push(String(e).slice(0, 160)));
      page.on('response', r => { if (r.status() >= 400 && r.url().startsWith(out.base)) failed.push(r.status() + ' ' + r.request().method() + ' ' + new URL(r.url()).pathname); });
      const row = { route, width };
      try {
        const response = await page.goto(out.base + route, { waitUntil: 'domcontentloaded', timeout: 15000 });
        row.status = response ? response.status() : null;
        await page.waitForLoadState('networkidle', { timeout: 6000 }).catch(() => { row.network_idle = false; });
        await page.waitForTimeout(350);
        Object.assign(row, await page.evaluate(() => {
          const d = document.documentElement, root = document.getElementById('root') || document.body;
          const small = [...document.querySelectorAll('button, a[href], [role=button], input:not([type=hidden]), select')]
            .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24); }).length;
          const unnamed = [...document.querySelectorAll('button, [role=button]')].filter(e => {
            const r = e.getBoundingClientRect(); if (!r.width || !r.height) return false;
            return !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('title') || (e.textContent || '').trim());
          }).length;
          return {
            final_path: location.pathname + location.search,
            rendered_text_chars: (root.innerText || '').trim().length,
            h1: [...document.querySelectorAll('h1')].map(h => h.textContent.trim().slice(0, 60)),
            title: document.title.slice(0, 80),
            horizontal_overflow_px: Math.max(0, d.scrollWidth - d.clientWidth),
            has_main_landmark: !!document.querySelector('main, [role=main]'),
            not_found_text: /page not found|404/i.test((root.innerText || '').slice(0, 400)),
            controls_under_24px: small, unnamed_buttons: unnamed,
          };
        }));
        await page.addScriptTag({ content: axeSource });
        const axe = await page.evaluate(async () => {
          const r = await window.axe.run(document, { resultTypes: ['violations'] });
          // For the rules a fix has to be traced to a component, keep what
          // identifies each failing element: selector, markup and, for contrast,
          // the colours axe measured.
          const DETAIL = ['color-contrast', 'button-name', 'scrollable-region-focusable', 'label-content-name-mismatch'];
          const detail = v => v.nodes.slice(0, 80).map(n => {
            const d = ((n.any || []).find(c => c.data && c.data.fgColor) || {}).data;
            return Object.assign({ target: n.target.join(' '), html: n.html.slice(0, 200) },
              d ? { fg: d.fgColor, bg: d.bgColor, ratio: d.contrastRatio, expected: d.expectedContrastRatio, font_size: d.fontSize, font_weight: d.fontWeight } : {});
          });
          return { version: window.axe.version, violations: r.violations.map(v => Object.assign({ id: v.id, impact: v.impact, nodes: v.nodes.length }, DETAIL.includes(v.id) ? { detail: detail(v) } : {})) };
        });
        out.axe_version = axe.version; row.axe = axe.violations;
      } catch (e) { row.error = String(e).slice(0, 200); }
      row.console_errors = consoleErrors.length; row.console_error_sample = consoleErrors.slice(0, 2);
      row.page_errors = pageErrors.slice(0, 2); row.failed_requests = [...new Set(failed)].slice(0, 6);
      out.observations.push(row);
      await page.close();
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(outDir + '/out-' + name + '.json', JSON.stringify(out, null, 1));
  console.log(name, 'observations', out.observations.length);
})();

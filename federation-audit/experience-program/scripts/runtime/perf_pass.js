// Page-load timing for one application: every addressable route at two
// viewport widths, several cold runs each. Records what was measured; decides
// nothing.
//
// usage: node perf_pass.js <repository> <port> <routes.json> <out dir> <label>
//
// Each run uses a fresh browser context, so nothing is cached between runs.
// Timings are relative to navigation start, in milliseconds. They come from
// the machine the script runs on, over loopback: they compare applications and
// commits with each other and are not what a person sees on their own device.
const { chromium } = require('playwright');
const fs = require('fs');

const [,, name, port, routesFile, outDir, label] = process.argv;
const routes = JSON.parse(fs.readFileSync(routesFile))[name].routes;
const WIDTHS = [390, 1280];
const RUNS = Number(process.env.PERF_RUNS || 3);
const SETTLE_MS = 1200;

(async () => {
  const browser = await chromium.launch();
  const out = {
    repository: name, label, base: 'http://127.0.0.1:' + port, runs_per_cell: RUNS, widths: WIDTHS,
    browser: 'chromium ' + browser.version(), samples: [],
  };
  for (const width of WIDTHS) {
    for (const route of routes) {
      for (let run = 0; run < RUNS; run += 1) {
        const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 900 }, colorScheme: 'dark' });
        const page = await context.newPage();
        // Largest contentful paint and layout shift are only reported to
        // observers, so the observers are installed before any page script.
        await page.addInitScript(() => {
          window.__perf = { lcp: null, cls: 0 };
          try {
            new PerformanceObserver((list) => { for (const entry of list.getEntries()) window.__perf.lcp = entry.startTime; })
              .observe({ type: 'largest-contentful-paint', buffered: true });
            new PerformanceObserver((list) => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__perf.cls += entry.value; })
              .observe({ type: 'layout-shift', buffered: true });
          } catch (error) { window.__perf.unsupported = String(error); }
        });
        const sample = { route, width, run };
        try {
          const response = await page.goto(out.base + route, { waitUntil: 'load', timeout: 30000 });
          sample.status = response ? response.status() : null;
          await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => { sample.network_idle = false; });
          await page.waitForTimeout(SETTLE_MS);
          Object.assign(sample, await page.evaluate(() => {
            const nav = performance.getEntriesByType('navigation')[0];
            const resources = performance.getEntriesByType('resource');
            const round = (value) => (typeof value === 'number' ? Math.round(value * 10) / 10 : null);
            return {
              final_path: location.pathname + location.search,
              ttfb_ms: round(nav.responseStart),
              dom_content_loaded_ms: round(nav.domContentLoadedEventEnd),
              load_ms: round(nav.loadEventEnd),
              lcp_ms: round(window.__perf.lcp),
              cls: Math.round(window.__perf.cls * 10000) / 10000,
              requests: resources.length + 1,
              transferred_bytes: resources.reduce((sum, entry) => sum + (entry.transferSize || 0), nav.transferSize || 0),
              script_bytes: resources.filter((entry) => entry.initiatorType === 'script' || /\.js(\?|$)/.test(entry.name))
                .reduce((sum, entry) => sum + (entry.transferSize || 0), 0),
            };
          }));
        } catch (error) { sample.error = String(error).slice(0, 200); }
        out.samples.push(sample);
        await context.close();
      }
    }
  }
  await browser.close();
  fs.writeFileSync(`${outDir}/perf-${label}.json`, JSON.stringify(out, null, 1));
  console.log(label, 'samples', out.samples.length, 'errors', out.samples.filter((sample) => sample.error).length);
})();

import { test } from '@playwright/test';

const runLive = process.env.GIS_LIVE_PROVIDER_TESTS === '1';
const sources = [
  ['pr-sige-municipios', 'https://sige.pr.gov/server/rest/services/MIPR/LimitesAdministrativos_v10/FeatureServer/0/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-represas', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-aeropuertos', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/17/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-helipuertos', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/18/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-cuencas', 'https://sige.pr.gov/server/rest/services/MIPR/Geologia_v10_N/FeatureServer/0/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-acuiferos', 'https://sige.pr.gov/server/rest/services/MIPR/Geologia_v10_N/FeatureServer/2/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-sumideros', 'https://sige.pr.gov/server/rest/services/MIPR/Geologia_v10_N/FeatureServer/4/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-aaa-pozos', 'https://sige.pr.gov/server/rest/services/MIPR/AAA_v10_N/MapServer/2/query?f=json&returnCountOnly=true&where=1%3D1'],
];

for (const [sourceId, url] of sources) {
  test(`${sourceId} browser CORS observation`, async ({ page }) => {
    test.skip(!runLive, 'live provider observations run only in the dedicated workflow');
    await page.goto('/gis');
    const observation = await page.evaluate(async (target) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10_000);
      try {
        const response = await fetch(target, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
        return { reachable: true, ok: response.ok, status: response.status, body: (await response.text()).slice(0, 256) };
      } catch (error) {
        return { reachable: false, ok: false, status: null, error: String(error) };
      } finally {
        clearTimeout(timeout);
      }
    }, url);
    console.log('GIS_BROWSER_CORS', JSON.stringify({ sourceId, ...observation }));
    // Observation is intentionally non-fatal. Provider data invariants are enforced
    // by liveProviders.test.js; this distinguishes direct browser CORS from the
    // same-origin allowlisted proxy fallback rather than making CORS policy a data failure.
  });
}

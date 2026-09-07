#!/usr/bin/env node
import { chromium } from 'playwright';
import http from 'node:http';

const targets = [
  ['pr-sige-municipios', 'https://sige.pr.gov/server/rest/services/MIPR/LimitesAdministrativos_v10/FeatureServer/0/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-represas', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-aeropuertos', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/17/query?f=json&returnCountOnly=true&where=1%3D1'],
  ['pr-sige-helipuertos', 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/18/query?f=json&returnCountOnly=true&where=1%3D1'],
];

const server = http.createServer((_req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end('<!doctype html><title>GIS CORS certification</title>');
});
await new Promise((resolve) => server.listen(8765, '127.0.0.1', resolve));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto('http://127.0.0.1:8765');
const results = [];
for (const [sourceId, url] of targets) {
  const result = await page.evaluate(async ({ sourceId, url }) => {
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      const text = await response.text();
      return { sourceId, status: response.ok ? 'PASS' : 'FAIL', httpStatus: response.status, bodyPrefix: text.slice(0, 160) };
    } catch (error) {
      return { sourceId, status: 'CORS_OR_NETWORK_BLOCKED', error: String(error) };
    }
  }, { sourceId, url });
  results.push(result);
}
console.log(JSON.stringify({ origin: 'http://127.0.0.1:8765', results }, null, 2));
await browser.close();
server.close();
if (results.some((item) => item.status !== 'PASS')) process.exitCode = 2;

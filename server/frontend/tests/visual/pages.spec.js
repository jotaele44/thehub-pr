import { test, expect } from '@playwright/test';

// Routes chosen to be deterministic: no live charts/timestamps, driven only by
// the (mocked-empty) API so the screenshot reflects the design system —
// headers, nav, tabs, filter bars, tables, empty states, and the auth layout.
const ROUTES = [
  { name: 'login', path: '/login' },
  { name: 'moneysweep', path: '/moneysweep' },
  { name: 'sources', path: '/sources' },
  { name: 'gates', path: '/gates' },
  { name: 'programs', path: '/programs' },
];

test.beforeEach(async ({ page }) => {
  // Freeze time so any relative/absolute timestamps render identically.
  await page.clock.setFixedTime(new Date('2026-01-01T00:00:00Z'));
  // Deterministic API: anonymous mode + empty collections.
  await page.route('**/api/**', (route) => {
    const url = route.request().url();
    const body = url.includes('/apps/public-settings')
      ? { id: 'thehub', public_settings: { requires_auth: false } }
      : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
});

for (const route of ROUTES) {
  test(`${route.name}`, async ({ page }) => {
    await page.goto(route.path, { waitUntil: 'networkidle' });
    // Ensure the self-hosted webfonts are applied before capture.
    await page.evaluate(() => document.fonts.ready);
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot(`${route.name}.png`, { fullPage: true });
  });
}

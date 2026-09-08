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
  // The operations plane without a native manager session. That is what a
  // browser-only visitor actually sees, it is fully deterministic (no run
  // timestamps, no streamed output), and keeping it under visual coverage
  // means a regression in the unavailable path is caught rather than assumed.
  { name: 'operations', path: '/operations' },
];

test.beforeEach(async ({ page }, testInfo) => {
  // Freeze time so any relative/absolute timestamps render identically.
  await page.clock.setFixedTime(new Date('2026-01-01T00:00:00Z'));
  // The /login route renders only when the app reports that auth is required —
  // in diagnostic mode App.jsx redirects it to / rather than offering a sign-in
  // against endpoints the backend does not implement. Report requires_auth=true
  // for that one test so the auth layout stays under visual coverage, and false
  // for the rest so the app shell renders anonymously. Between them the suite
  // now exercises both sides of that gate.
  const requiresAuth = testInfo.title === 'login';
  // Deterministic API: empty collections.
  await page.route('**/api/**', (route) => {
    const url = route.request().url();
    const body = url.includes('/apps/public-settings')
      ? { id: 'thehub', public_settings: { requires_auth: requiresAuth } }
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

test('empty notification viewport does not intercept page controls', async ({ page }) => {
  await page.goto('/sources', { waitUntil: 'networkidle' });
  await page.evaluate(() => {
    const button = document.createElement('button');
    button.textContent = 'Underlying control';
    button.style.cssText = 'position:fixed;bottom:0;right:0;width:200px;height:24px;z-index:90';
    button.onclick = () => { button.textContent = 'Control activated'; };
    document.body.appendChild(button);
  });
  await page.getByRole('button', { name: 'Underlying control' }).click();
  await expect(page.getByRole('button', { name: 'Control activated' })).toBeVisible();
});

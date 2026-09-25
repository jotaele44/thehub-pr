import { test, expect } from '@playwright/test';

// GUI capability parity E2E (see .federation/gui-capabilities.json). Every
// active capability's e2e_routes must be reachable from visible navigation and
// render its primary surface against a deterministic, mocked API.

async function mockApi(page, handlers = {}) {
  await page.route('**/api/**', (route) => {
    const url = route.request().url();
    if (url.includes('/apps/public-settings')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'thehub', public_settings: { requires_auth: false } }) });
    }
    for (const [fragment, body] of Object.entries(handlers)) {
      if (url.includes(fragment)) {
        const status = body && body.__status ? body.__status : 200;
        return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
      }
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
}

test.describe('federation shell', () => {
  test('primary navigation rail is present and marks the active module', async ({ page }) => {
    await mockApi(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    const nav = page.getByRole('navigation', { name: 'Primary' }).first();
    await expect(nav).toBeVisible();
    const active = nav.getByRole('link', { name: 'Sources' });
    await expect(active).toHaveClass(/bg-sidebar-accent/);
  });
});


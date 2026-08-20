import { expect, test } from '@playwright/test';

test('operator settings page surfaces write-token failures', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = request.url();
    if (url.includes('/apps/public-settings')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'thehub', public_settings: { requires_auth: false } }),
      });
    }
    if (url.includes('/notifications/preferences') && request.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          prefs: { all: { channels: [], timing: 'asap' } },
          targets: {},
          domains: [],
          channels: ['push', 'sms'],
          timing: ['asap', 'brief'],
        }),
      });
    }
    if (url.includes('/notifications/preferences') && request.method() === 'PUT') {
      return route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Missing or invalid write token' }),
      });
    }
    if (url.includes('/connectors/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'not_connected' }),
      });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/operator-settings');
  await expect(page).toHaveURL(/\/operator-settings$/);
  await expect(page.getByRole('heading', { name: 'Operator Settings' })).toBeVisible();

  await page.getByRole('button', { name: 'Save preferences' }).click();
  await expect(page.getByRole('alert')).toContainText('Missing or invalid write token');
});

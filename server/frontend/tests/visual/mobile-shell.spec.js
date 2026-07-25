import { test, expect } from '@playwright/test';

const ROUTES = [
  ['activity-root', '/'], ['activity', '/activity'], ['programs', '/programs'],
  ['cases', '/cases'], ['sources', '/sources'], ['tasks', '/tasks'],
  ['gates', '/gates'], ['integrations', '/integrations'], ['exports', '/exports'],
  ['readiness', '/readiness'], ['transition', '/transition'], ['crossover', '/crossover'],
  ['anomaly-overlap', '/anomaly-overlap'], ['control', '/control'], ['hub', '/hub'],
  ['research', '/research'], ['dictionary', '/dictionary'], ['manifest', '/manifest'],
  ['spiderweb', '/spiderweb'], ['ovnis', '/ovnis'], ['aguayluz', '/aguayluz'],
  ['moneysweep', '/moneysweep'], ['skywatcher', '/skywatcher'], ['centinelas', '/centinelas'],
];

async function installDeterministicApi(page) {
  await page.clock.setFixedTime(new Date('2026-01-01T00:00:00Z'));
  await page.route('**/api/**', (route) => {
    const url = route.request().url();
    const body = url.includes('/apps/public-settings')
      ? { id: 'thehub', public_settings: { requires_auth: false } }
      : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test.beforeEach(async ({ page }) => {
  await installDeterministicApi(page);
});

for (const [name, path] of ROUTES) {
  test(`mobile route ${name}`, async ({ page }, testInfo) => {
    await page.goto(path, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);

    const screenshot = await page.screenshot({ fullPage: true, animations: 'disabled' });
    await testInfo.attach(`${name}-${testInfo.project.name}.png`, { body: screenshot, contentType: 'image/png' });

    const main = page.locator('#main-content');
    await expect(main).toBeVisible({ timeout: 15000 });

    const overflow = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
    }));
    expect(overflow.document, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport);
    expect(overflow.body, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport);

    if (testInfo.project.name.startsWith('mobile-')) {
      const mobileNav = page.getByRole('navigation', { name: 'Mobile primary' });
      await expect(mobileNav).toBeVisible();
      const primaryTargets = mobileNav.getByRole('link');
      await expect(primaryTargets).toHaveCount(5);
      for (const target of await primaryTargets.all()) {
        const box = await target.boundingBox();
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
        expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
      }
    }
  });
}

test('mobile navigation, skip link, and focus restoration', async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith('mobile-'), 'Phone-only bottom navigation behavior');
  await page.goto('/programs', { waitUntil: 'networkidle' });

  await page.keyboard.press('Tab');
  const skipLink = page.getByRole('link', { name: 'Skip to main content' });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();

  const menuButton = page.getByRole('button', { name: 'Open navigation menu' });
  const notificationButton = page.getByRole('button', { name: /Notifications:/ });
  const menuBox = await menuButton.boundingBox();
  const notificationBox = await notificationButton.boundingBox();
  expect(menuBox).not.toBeNull();
  expect(notificationBox).not.toBeNull();
  const overlaps = !(
    menuBox.x + menuBox.width <= notificationBox.x ||
    notificationBox.x + notificationBox.width <= menuBox.x ||
    menuBox.y + menuBox.height <= notificationBox.y ||
    notificationBox.y + notificationBox.height <= menuBox.y
  );
  expect(overlaps).toBe(false);

  await menuButton.click();
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  await page.keyboard.press('Escape');

  const activity = page.getByRole('navigation', { name: 'Mobile primary' }).getByRole('link', { name: 'Activity' });
  await activity.evaluate((element) => element.click());
  await expect(page).toHaveURL(/\/$/);
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('main-content');
});

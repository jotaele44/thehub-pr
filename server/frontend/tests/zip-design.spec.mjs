import { test, expect } from 'playwright/test';

// Explicit failure fixtures exercise chrome without reading mutable sources.
// These tests certify UI behavior only; they do not certify backend data.
test.beforeEach(async ({ page }) => {
 await page.route('**/*', async route => {
  const url = new URL(route.request().url());
  if (url.pathname.includes('public-settings')) return route.fulfill({json: {requires_auth: false}});
  if (url.hostname === '127.0.0.1' && url.port === '5419' && !url.pathname.startsWith('/api/')) return route.continue();
  return route.abort('connectionrefused');
 });
});
for (const width of [390, 1440]) {
 test(`archive design renders and stays within ${width}px viewport`, async ({ page }) => {
  await page.setViewportSize({width, height: 900});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('.zip-surface')).toBeVisible();
  await expect.poll(() => page.locator('#root').innerText()).not.toBe('');
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(errors).toEqual([]);
  const css = await page.locator('.zip-surface').evaluate(el => getComputedStyle(el).getPropertyValue('--zip-background'));
  expect(css.trim()).not.toBe('');
 });
}
test('quick navigation retains working routes', async ({page}) => {
 await page.goto('/');await page.getByRole('navigation',{name:'Quick navigation'}).getByRole('link',{name:'Programs',exact:true}).click();
 await expect(page).toHaveURL(/\/programs$/);await expect(page.locator('.zip-surface')).toBeVisible();
});

for (const width of [390, 1440]) {
 test(`header theme control is not covered by notifications at ${width}px`, async ({page}) => {
  await page.setViewportSize({width,height:900}); await page.goto('/');
  const theme=page.locator('header').getByRole('button',{name:/Switch to .* theme/});
  const original=await theme.getAttribute('aria-label');
  await theme.click(); await expect(theme).not.toHaveAttribute('aria-label',original);
  const bell=page.getByRole('button',{name:/Notifications:/});
  const a=await theme.boundingBox(), b=await bell.boundingBox();
  expect(a.x+a.width<=b.x || a.y+a.height<=b.y || b.y+b.height<=a.y).toBe(true);
 });
}

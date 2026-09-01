import { test, expect } from '@playwright/test';

const CASES = [
  {
    name: 'spiderweb-intelligence',
    path: '/spiderweb',
    primary: 'GraphNodes',
    row: { node_id: 'N-1', label: 'Spatial node', node_type: 'Location', municipality: 'San Juan', confidence: 'High' },
    boundedVisible: 1,
  },
  {
    name: 'skywatcher-intelligence',
    path: '/skywatcher',
    primary: 'AirspaceEvents',
    row: { event_id: 'A-1', title: 'Undated airspace event', event_type: 'Aviation', municipality: 'Carolina', confidence: 'High' },
    boundedVisible: 0,
  },
  {
    name: 'aguayluz-intelligence',
    path: '/aguayluz',
    primary: 'InfrastructureAssets',
    row: { asset_id: 'U-1', name: 'Persistent utility asset', asset_type: 'Reservoir', municipality: 'Trujillo Alto', status: 'Active' },
    boundedVisible: 1,
  },
];

for (const fixture of CASES) {
  test(fixture.name, async ({ page }) => {
    await page.clock.setFixedTime(new Date('2026-08-25T02:03:00Z'));
    await page.route('**/api/**', (route) => {
      const url = route.request().url();
      if (url.includes('/apps/public-settings')) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'thehub', public_settings: { requires_auth: false } }) });
      }
      if (url.includes(`/entities/${fixture.primary}`)) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([fixture.row]) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    await page.goto(fixture.path, { waitUntil: 'networkidle' });
    await expect(page.getByRole('tab', { name: 'Workspace' })).toHaveAttribute('data-state', 'active');
    await expect(page.getByLabel('Search')).toBeVisible();
    await expect(page.getByLabel('Category')).toBeVisible();
    await expect(page.getByText('Loaded-row denominator: 1 = 1 visible + 0 excluded.')).toBeVisible();

    await expect(page.locator('[data-forensic-axis="Identity"]')).toHaveAttribute('data-forensic-value', 'UNRESOLVED');
    await expect(page.locator('[data-forensic-axis="Certification"]')).toHaveAttribute('data-forensic-value', 'OPEN');
    await expect(page.locator('[data-forensic-axis="Epistemic"]')).toHaveAttribute('data-forensic-value', 'UNKNOWN');
    await expect(page.getByText('Query recency is not source freshness.')).toBeVisible();

    const controls = page.locator('[data-intelligence-toolbar] input, [data-intelligence-toolbar] select, [data-intelligence-toolbar] button');
    const count = await controls.count();
    expect(count).toBeGreaterThanOrEqual(7);
    for (let index = 0; index < count; index += 1) {
      const box = await controls.nth(index).boundingBox();
      expect(box?.height || 0).toBeGreaterThanOrEqual(44);
    }

    await page.getByRole('button', { name: '24H' }).click();
    await expect(page.getByText(`Loaded-row denominator: 1 = ${fixture.boundedVisible} visible + ${1 - fixture.boundedVisible} excluded.`)).toBeVisible();
  });
}

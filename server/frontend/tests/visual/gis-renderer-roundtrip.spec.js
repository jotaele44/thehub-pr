import { expect, test } from '@playwright/test';

test('GIS 2D→3D→2D renderer round trip preserves canonical switch gate', async ({ page }) => {
  await page.goto('/gis');
  await expect(page.getByTestId('maplibre-renderer')).toBeVisible();
  await expect(page.getByText('Mode: 2d')).toBeVisible();

  await page.getByRole('button', { name: '3D Cesium' }).click();
  await expect(page.getByTestId('cesium-renderer')).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Last 2D↔3D gate: PASS/)).toBeVisible();
  await expect(page.getByText('Mode: 3d')).toBeVisible();

  await page.getByRole('button', { name: '2D MapLibre' }).click();
  await expect(page.getByTestId('maplibre-renderer')).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Last 2D↔3D gate: PASS/)).toBeVisible();
  await expect(page.getByText('Mode: 2d')).toBeVisible();
});

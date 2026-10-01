import { test, expect } from '@playwright/test';
import { OVNIS_YEAR_ONLY_CASE } from '../../src/test/fixtures/evidenceObject.js';

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
    // Below the lg breakpoint the rail collapses into the responsive mobile menu.
    const menu = page.getByRole('button', { name: 'Open navigation menu' });
    if (await menu.isVisible()) await menu.click();
    const nav = page.locator('nav[aria-label="Primary"]:visible').first();
    await expect(nav).toBeVisible();
    const active = nav.getByRole('link', { name: 'Sources' });
    await expect(active).toHaveClass(/bg-sidebar-accent/);
  });
});

test.describe('provenance inspector', () => {
  test('is reachable from a producer workspace record and renders the evidence object', async ({ page }) => {
    const asset = { id: 'ent_1', entity_id: 'ent_1', asset_id: 'ent_1', name: 'Persistent utility asset', asset_type: 'utility_asset', municipality: 'Guayama', _producers: ['aguayluz-pr'] };
    const evidence = { ...OVNIS_YEAR_ONLY_CASE, id: 'evo:entities:ent_1', stream: 'entities', producer_record_id: 'ent_1', producer_repo: 'aguayluz-pr', title: 'Persistent utility asset' };
    await mockApi(page, { '/evidence/Entities/ent_1': evidence, '/entities/InfrastructureAssets': [asset] });

    await page.goto('/aguayluz', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /Persistent utility asset/ }).first().click();
    await page.getByRole('link', { name: 'Open provenance inspector' }).click();

    await expect(page).toHaveURL(/\/evidence\/Entities\/ent_1$/);
    await expect(page.getByRole('heading', { name: 'Provenance inspector' })).toBeVisible();
    await expect(page.locator('[data-evidence-axis="epistemic_class"]')).toHaveAttribute('data-evidence-value', 'CURATED');
    await expect(page.locator('[data-evidence-axis="temporal_precision"]')).toHaveAttribute('data-evidence-value', 'YEAR_ONLY');
    await expect(page.locator('[data-edge-state="DOCUMENTED"]')).toBeVisible();
  });

  test('a record the Hub does not hold is reported, not substituted', async ({ page }) => {
    await mockApi(page, { '/evidence/Entities/missing': { __status: 404, detail: 'Entities/missing not found' } });
    await page.goto('/evidence/Entities/missing', { waitUntil: 'networkidle' });
    await expect(page.getByRole('alert')).toContainText('The Hub holds no Entities record missing');
    await expect(page.locator('[data-evidence-axis]')).toHaveCount(0);
  });
});

test.describe('MoneySweep certified leaderboard consumer', () => {
  test('is discoverable from MoneySweep and preserves certified producer rows', async ({ page }) => {
    const packageHash = 'a'.repeat(64);
    await mockApi(page, {
      '/moneysweep/leaderboards/status': {
        state: 'PASS',
        producerCommit: 'b'.repeat(40),
        rankingContractVersion: 'moneysweep.leaderboard/v1.1',
        ontologyContractVersion: 'moneysweep.financial-category-ontology/v1.1',
        scopeId: 'moneysweep.leaderboard.production-v1',
        categoryCount: 1,
        consumerPackageSha256: packageHash,
      },
      '/moneysweep/leaderboards/top': {
        categoryId: 'debt_issuance',
        metricType: 'DEBT_ISSUED_PAR',
        rows: [
          {
            entityId: 'entity_5204a3d8f84bbfcd',
            entityDisplayName: 'Puerto Rico Sales Tax Financing Corporation',
            entityResolutionState: 'CANONICAL_V1_ENTITY_ID',
            currency: 'USD',
            metricValue: 16314000000,
            rank: 1,
          },
        ],
        consumerState: 'PASS',
        producerCommit: 'b'.repeat(40),
        scopeId: 'moneysweep.leaderboard.production-v1',
        consumerPackageSha256: packageHash,
      },
    });

    await page.goto('/moneysweep', { waitUntil: 'networkidle' });
    await page.getByRole('tab', { name: 'Leaderboards' }).click();

    await expect(page.getByRole('heading', { name: 'Certified Public Debt Issuance' })).toBeVisible();
    await expect(page.getByText('Puerto Rico Sales Tax Financing Corporation')).toBeVisible();
    await expect(page.getByText('entity_5204a3d8f84bbfcd')).toBeVisible();
    await expect(page.getByText('CANONICAL_V1_ENTITY_ID')).toBeVisible();
    await expect(page.getByText(/Package SHA-256:/)).toBeVisible();
  });

  test('shows fail-closed producer status instead of synthetic ranking rows', async ({ page }) => {
    await mockApi(page, {
      '/moneysweep/leaderboards/status': {
        state: 'BLOCKED',
        reason: 'certified MoneySweep leaderboard package is not mounted',
      },
    });

    await page.goto('/moneysweep', { waitUntil: 'networkidle' });
    await page.getByRole('tab', { name: 'Leaderboards' }).click();

    await expect(page.getByRole('heading', { name: 'Financial Leaderboards' })).toBeVisible();
    await expect(page.getByText('BLOCKED')).toBeVisible();
    await expect(page.getByText(/fail-closed until MoneySweep supplies/)).toBeVisible();
    await expect(page.getByRole('table')).toHaveCount(0);
  });
});

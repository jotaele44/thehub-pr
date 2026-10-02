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

const SEARCH_RESPONSE = {
  query: 'laguna cartagena', terms: ['laguna', 'cartagena'], type: 'ALL', type_status: 'OK', query_status: 'OK',
  include_synthetic: false, indexed_records: 42, matched: 2, excluded_synthetic: 1, total: 1, next_cursor: null,
  producers: [
    { producer: 'spiderweb-pr', status: 'AVAILABLE', indexed_records: 12 },
    { producer: 'moneysweep-pr', status: 'NO_DATA', indexed_records: 0 },
  ],
  results: [{
    evidence_id: 'evo:entities:ent_1', stream: 'entities', collection: 'Entities', record_id: 'ent_1', kind: 'ENTITY',
    title: 'Laguna Cartagena', type: 'wetland', producers: ['spiderweb-pr'], synthetic: false,
    declared_epistemic_class: 'CURATED', source_ids: [], evidence_href: '/evidence/Entities/ent_1', entity_href: '/entity/ent_1',
  }],
};

const COMPOSITION = {
  contract: 'federation-entity-composition-v1',
  contract_status: 'CANDIDATE',
  anchor: { ...OVNIS_YEAR_ONLY_CASE, id: 'evo:entities:ent_1', stream: 'entities', producer_record_id: 'ent_1',
            producer_repo: 'spiderweb-pr', canonical_type: 'entity:wetland', title: 'Laguna Cartagena' },
  identity: { identity_state: 'UNRESOLVED', identity_scope: 'PRODUCER_LOCAL', identity_basis: 'no identity adjudication',
              registry_status: 'NOT_CONFIGURED', members: [{ producer: 'spiderweb-pr', collection: 'Entities', record_id: 'ent_1' }] },
  sections: [{ producer: 'spiderweb-pr', status: 'AVAILABLE', relationship_count: 1, linked_record_count: 0 }],
  relationships: [{
    evidence_id: 'evo:correlations:rel_2', collection: 'Correlations', record_id: 'rel_2', relationship_type: 'spatial_proximity',
    direction: 'INBOUND', counterpart: { record_id: 'ent_9', title: null, resolved: false, entity_href: null },
    edge_state: 'CANDIDATE', edge_basis: "hub correlation on weak basis 'location'", producers: ['thehub-pr'],
    synthetic: false, match_basis: 'location', evidence_href: '/evidence/Correlations/rel_2',
  }],
  linked_records: [],
  truncated: { relationships: false, linked_records: false },
  limits: { relationships: 200, linked_records: 200 },
};

async function openPrimaryNav(page) {
  const menu = page.getByRole('button', { name: 'Open navigation menu' });
  if (await menu.isVisible()) await menu.click();
  return page.locator('nav[aria-label="Primary"]:visible').first();
}

test.describe('federated search', () => {
  test('is reachable from navigation and deep-links every result to its provenance', async ({ page }) => {
    await mockApi(page, { '/search': SEARCH_RESPONSE });
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'Search', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Search the Federation' })).toBeVisible();

    await page.getByLabel('Search query').fill('laguna cartagena');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page).toHaveURL(/\/search\?q=laguna\+cartagena$/);
    await expect(page.locator('[data-search-summary]')).toContainText('1 synthetic excluded');
    const result = page.locator('[data-search-result="evo:entities:ent_1"]');
    await expect(result.getByRole('link', { name: 'Provenance' })).toHaveAttribute('href', '/evidence/Entities/ent_1');
    await expect(page.locator('[data-producer-status="NO_DATA"]')).toContainText('moneysweep-pr');
  });

  test('a finding search says no producer emits findings', async ({ page }) => {
    await mockApi(page, { '/search': { ...SEARCH_RESPONSE, type: 'FINDING', type_status: 'NO_PRODUCER_EMITS_FINDINGS', results: [], total: 0, matched: 0, excluded_synthetic: 0 } });
    await page.goto('/search?q=laguna&type=FINDING', { waitUntil: 'networkidle' });
    await expect(page.locator('[data-type-status="NO_PRODUCER_EMITS_FINDINGS"]')).toBeVisible();
    await expect(page.locator('[data-search-result]')).toHaveCount(0);
  });
});

test.describe('command palette', () => {
  test('opens with Ctrl+K and navigates to a page', async ({ page }) => {
    await mockApi(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await page.keyboard.press('Control+k');
    const input = page.getByRole('combobox', { name: 'Command, search or record' });
    await expect(input).toBeFocused();
    await input.fill('control ledgers');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/control$/);
    await expect(input).toHaveCount(0);
  });

  test('jumps the map to typed coordinates through a deep link', async ({ page }) => {
    await mockApi(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await page.keyboard.press('Control+k');
    await page.getByRole('combobox').fill('18.2, -66.5');
    await page.getByRole('option', { name: /Jump the map to 18.2, -66.5/ }).click();
    await expect(page).toHaveURL(/\/gis\?lat=18\.2&lon=-66\.5$/);
    await expect(page.locator('[data-map-deep-link]')).toContainText('Centred on 18.2, -66.5');
  });
});

test.describe('entity page', () => {
  test('is reachable from a search result and never upgrades a proximity edge', async ({ page }) => {
    await mockApi(page, { '/search': SEARCH_RESPONSE, '/entity/ent_1': COMPOSITION });
    await page.goto('/search?q=laguna+cartagena', { waitUntil: 'networkidle' });
    await page.getByRole('link', { name: 'Entity composition' }).click();
    await expect(page).toHaveURL(/\/entity\/ent_1$/);
    await expect(page.getByRole('heading', { name: 'Laguna Cartagena' })).toBeVisible();
    await expect(page.locator('[data-registry-status="NOT_CONFIGURED"]')).toBeVisible();
    await expect(page.locator('[data-edge-state="CANDIDATE"]')).toBeVisible();
    await expect(page.getByText(/Not held by the Hub/)).toBeVisible();
    await expect(page.getByRole('link', { name: 'Full provenance' })).toHaveAttribute('href', '/evidence/Entities/ent_1');
  });

  test('an entity the Hub does not hold is reported, not substituted', async ({ page }) => {
    await mockApi(page, { '/entity/ent_missing': { __status: 404, detail: 'Entities/ent_missing not found' } });
    await page.goto('/entity/ent_missing', { waitUntil: 'networkidle' });
    await expect(page.getByRole('alert')).toContainText('The Hub holds no entity ent_missing');
  });
});

const TIMELINE_EVENT = {
  evidence_id: 'evo:observations:obs_1', observation_id: 'obs_1', entity_id: 'ent_1', case_id: 'PRUAP-0001',
  title: 'Offshore', category: 'USO', environment: 'underwater', date: '1927-10-06', time: null,
  temporal_precision: 'DATE_ONLY', era: '1920s', narrative: 'Shipping barge crew reported a submerged blue light.',
  place: { municipality: null, location_name: 'Offshore' }, evidence_tier: 'T3', source_id: 'src_1',
  source: { source_id: 'src_1', name: 'Dartmouth Alumni Magazine', url: 'https://example.org/article', evidence_href: '/evidence/Sources/src_1' },
  producers: ['ovnis-pr'], synthetic: false, findings: [],
  evidence_href: '/evidence/Observations/obs_1', entity_href: '/entity/ent_1',
};
const TIMELINE_RESPONSE = {
  contract: 'federation-event-timeline-v1', producer: 'ovnis-pr', producer_status: 'AVAILABLE', sort: 'oldest',
  categories: [{ category: 'UAP', count: 1 }, { category: 'USO', count: 1 }], selected_categories: [],
  findings_only: false, include_synthetic: false, loaded_events: 2, excluded_synthetic: 0, matched: 2, undated: 0,
  findings_total: 0, findings_status: 'NO_FINDINGS_RECORDED',
  events: [TIMELINE_EVENT, {
    ...TIMELINE_EVENT, evidence_id: 'evo:observations:obs_2', observation_id: 'obs_2', entity_id: 'ent_2', case_id: null,
    title: 'Cabo Rojo', category: 'UAP', date: '1967', temporal_precision: 'YEAR_ONLY', era: '1960s',
    evidence_href: '/evidence/Observations/obs_2', entity_href: '/entity/ent_2',
  }],
  next_cursor: null,
};

test.describe('event timeline', () => {
  test('is reachable from navigation and keeps each date at its recorded precision', async ({ page }) => {
    await mockApi(page, { '/timeline': TIMELINE_RESPONSE });
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'Timeline', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Event Timeline' })).toBeVisible();
    await expect(page.locator('[data-timeline-summary]')).toContainText("2 events in this Hub's store");
    const yearOnly = page.locator('[data-timeline-event="obs_2"]');
    await expect(yearOnly.locator('time')).toHaveText('1967');
    await expect(yearOnly.locator('[data-temporal-precision]')).toHaveText('year only');
    await expect(page.locator('[data-timeline-event="obs_1"]').getByRole('link', { name: 'Provenance', exact: true }))
      .toHaveAttribute('href', '/evidence/Observations/obs_1');
    await page.getByRole('button', { name: 'Newest first' }).click();
    await expect(page).toHaveURL(/\/timeline\?sort=newest$/);
  });

  test('findings-only mode says no findings are recorded', async ({ page }) => {
    await mockApi(page, { '/timeline': { ...TIMELINE_RESPONSE, findings_only: true, events: [], matched: 0 } });
    await page.goto('/timeline?findings=1', { waitUntil: 'networkidle' });
    await expect(page.locator('[data-findings-status="NO_FINDINGS_RECORDED"]')).toBeVisible();
    await expect(page.locator('[data-timeline-event]')).toHaveCount(0);
  });
});

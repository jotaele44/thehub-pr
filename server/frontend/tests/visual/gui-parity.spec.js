import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
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

  test('switches to the certified ASG plane and preserves source-native accounting', async ({ page }) => {
    const packageHash = 'c'.repeat(64);
    await mockApi(page, {
      '/moneysweep/leaderboards/status': {
        state: 'BLOCKED',
        reason: 'certified debt leaderboard package is not mounted',
      },
      '/moneysweep/asg-leaderboards/status': {
        state: 'PASS',
        producerCommit: 'd'.repeat(40),
        rankingContractVersion: 'moneysweep.leaderboard/v1.1',
        ontologyContractVersion: 'moneysweep.financial-category-ontology/v1.1',
        scopeId: 'moneysweep.leaderboard.asg-emergency-source-native-v1',
        inputRecords: 1431,
        outOfScopeRecords: 1410,
        retainedRecords: 21,
        candidateCount: 10,
        consumerPackageSha256: packageHash,
      },
      '/moneysweep/asg-leaderboards/top': {
        categoryId: 'asg_emergency_purchase_source_native',
        metricType: 'ASG_EMERGENCY_PURCHASE_COST',
        rows: [
          {
            entityId: 'ASG-12345',
            entityDisplayName: 'Proveedor con ID nativo',
            entityResolutionState: 'SOURCE_NATIVE_ID',
            currency: 'USD',
            metricValue: 125000,
            recordCount: 3,
            rank: 1,
          },
        ],
        consumerState: 'PASS',
        producerCommit: 'd'.repeat(40),
        scopeId: 'moneysweep.leaderboard.asg-emergency-source-native-v1',
        scopeBoundary: 'Only purchases with an explicit ASG Licitador ID are ranked.',
        consumerPackageSha256: packageHash,
      },
    });

    await page.goto('/moneysweep', { waitUntil: 'networkidle' });
    await page.getByRole('tab', { name: 'Leaderboards' }).click();
    await page.getByRole('tab', { name: 'ASG emergency purchases' }).click();

    await expect(page.getByRole('heading', { name: 'ASG Emergency Purchases — Source-Native IDs' })).toBeVisible();
    await expect(page.getByText('Proveedor con ID nativo')).toBeVisible();
    await expect(page.getByText('ASG-12345')).toBeVisible();
    await expect(page.getByText('SOURCE_NATIVE_ID')).toBeVisible();
    await expect(page.getByText('3 retained purchases')).toBeVisible();
    await expect(page.getByText(/1431 records = 1410 explicit identity exclusions \+ 21 retained source-native rows/)).toBeVisible();
    await expect(page.getByText(/Package SHA-256:/)).toBeVisible();
  });

  test('renders exact ASG consumer at desktop and iPhone width without overflow or sub-44px tabs', async ({ page }, testInfo) => {
    const packageHash = '6ecdad09a48cdbd4ae1076138a9b5017a5be82608b489871a50ce0d599680337';
    await mockApi(page, {
      '/moneysweep/leaderboards/status': {
        state: 'BLOCKED',
        reason: 'certified debt leaderboard package is not mounted',
      },
      '/moneysweep/asg-leaderboards/status': {
        state: 'PASS',
        producerCommit: 'e963f4258a78c9b30427df7a7e9b4edf83f00692',
        rankingContractVersion: 'moneysweep.leaderboard/v1.1',
        ontologyContractVersion: 'moneysweep.financial-category-ontology/v1.1',
        scopeId: 'moneysweep.leaderboard.asg-emergency-source-native-v1',
        inputRecords: 1431,
        outOfScopeRecords: 1410,
        retainedRecords: 21,
        candidateCount: 10,
        consumerPackageSha256: packageHash,
      },
      '/moneysweep/asg-leaderboards/top': {
        categoryId: 'asg_emergency_purchase_source_native',
        metricType: 'ASG_EMERGENCY_PURCHASE_COST',
        rows: [{
          entityId: 'asg_licitador_id:23388',
          entityDisplayName: 'Sonnell Truck Center LLC',
          entityResolutionState: 'SOURCE_NATIVE_ASG_LICITADOR_ID',
          currency: 'USD',
          metricValue: 1744085,
          recordCount: 1,
          rank: 1,
        }],
        consumerState: 'PASS',
        producerCommit: 'e963f4258a78c9b30427df7a7e9b4edf83f00692',
        scopeId: 'moneysweep.leaderboard.asg-emergency-source-native-v1',
        scopeBoundary: 'Only purchases with an explicit ASG Licitador ID are ranked.',
        consumerPackageSha256: packageHash,
      },
    });

    for (const viewport of [
      { name: 'desktop', width: 1280, height: 800 },
      { name: 'iphone393', width: 393, height: 852 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/moneysweep', { waitUntil: 'networkidle' });
      await page.getByRole('tab', { name: 'Leaderboards' }).click();
      await page.getByRole('tab', { name: 'ASG emergency purchases' }).click();

      await expect(page.getByRole('heading', { name: 'ASG Emergency Purchases — Source-Native IDs' })).toBeVisible();
      await expect(page.getByText('Sonnell Truck Center LLC')).toBeVisible();
      await expect(page.getByText('asg_licitador_id:23388')).toBeVisible();
      await expect(page.getByText('SOURCE_NATIVE_ASG_LICITADOR_ID')).toBeVisible();
      await expect(page.getByText('1 retained purchase')).toBeVisible();
      await expect(page.getByText(/1431 records = 1410 explicit identity exclusions \+ 21 retained source-native rows/)).toBeVisible();
      await expect(page.getByText(new RegExp(packageHash.slice(0, 24)))).toBeVisible();

      const geometry = await page.evaluate(() => {
        const root = document.documentElement;
        const tabs = [...document.querySelectorAll('[role="tab"]')]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
          })
          .map((el) => {
            const r = el.getBoundingClientRect();
            return { label: el.textContent?.trim() || '', width: r.width, height: r.height };
          });
        const intentionalScroller = (el) => {
          let node = el;
          while (node && node !== document.body) {
            const style = getComputedStyle(node);
            if ((style.overflowX === 'auto' || style.overflowX === 'scroll') && node.scrollWidth > node.clientWidth + 1) return true;
            node = node.parentElement;
          }
          return false;
        };
        const offenders = [...document.querySelectorAll('body *')]
          .map((el) => ({ el, rect: el.getBoundingClientRect() }))
          .filter(({ el, rect }) => rect.width > 0 && (rect.right > root.clientWidth + 1 || rect.left < -1) && !intentionalScroller(el))
          .slice(0, 30)
          .map(({ el, rect }) => ({
            tag: el.tagName.toLowerCase(),
            className: typeof el.className === 'string' ? el.className.slice(0, 180) : '',
            text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 100),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
          }));
        return {
          clientWidth: root.clientWidth,
          scrollWidth: root.scrollWidth,
          overflowPx: Math.max(0, root.scrollWidth - root.clientWidth),
          tabs,
          offenders,
        };
      });

      await page.screenshot({
        path: testInfo.outputPath(`moneysweep-asg-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      });

      expect(
        geometry.overflowPx,
        `${viewport.name} document overflow; geometry=${JSON.stringify(geometry)}`,
      ).toBe(0);
      expect(geometry.tabs.length).toBeGreaterThanOrEqual(7);
      for (const tab of geometry.tabs) {
        expect(tab.height, `${viewport.name} tab "${tab.label}" height`).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test('shows the ASG producer blocker without synthesizing ranking rows', async ({ page }) => {
    await mockApi(page, {
      '/moneysweep/leaderboards/status': {
        state: 'BLOCKED',
        reason: 'certified debt leaderboard package is not mounted',
      },
      '/moneysweep/asg-leaderboards/status': {
        state: 'BLOCKED',
        reason: 'certified ASG MoneySweep leaderboard package is not mounted',
      },
    });

    await page.goto('/moneysweep', { waitUntil: 'networkidle' });
    await page.getByRole('tab', { name: 'Leaderboards' }).click();
    await page.getByRole('tab', { name: 'ASG emergency purchases' }).click();

    await expect(page.getByRole('heading', { name: 'ASG Emergency Purchases — Source-Native IDs' })).toBeVisible();
    await expect(page.getByText('BLOCKED')).toBeVisible();
    await expect(page.getByText('certified ASG MoneySweep leaderboard package is not mounted')).toBeVisible();
    await expect(page.getByRole('table')).toHaveCount(0);
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

    await expect(page.getByRole('heading', { name: 'Certified Public Debt Issuance' })).toBeVisible();
    await expect(page.getByText('BLOCKED')).toBeVisible();
    await expect(page.getByText(/fail-closed until TheHub trusts/)).toBeVisible();
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

  test('a finding search says no finding is recorded', async ({ page }) => {
    await mockApi(page, { '/search': { ...SEARCH_RESPONSE, type: 'FINDING', type_status: 'NO_FINDINGS_RECORDED', results: [], total: 0, matched: 0, excluded_synthetic: 0 } });
    await page.goto('/search?q=laguna&type=FINDING', { waitUntil: 'networkidle' });
    await expect(page.locator('[data-type-status="NO_FINDINGS_RECORDED"]')).toBeVisible();
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

const RESEARCH_KINDS = ['topics', 'findings', 'hypotheses', 'contradictions', 'adjudications', 'queue', 'episodes', 'reports'];
const RESEARCH_OVERVIEW = {
  contract: 'federation-research-v1', producer: 'ovnis-pr', producer_status: 'AVAILABLE', include_synthetic: false, topics: [],
  kinds: {
    ...Object.fromEntries(RESEARCH_KINDS.map((k) => [k, { total: 0, kind_status: 'NONE_RECORDED', status_counts: {} }])),
    adjudications: { total: 1, kind_status: 'RECORDED', status_counts: { CANDIDATE: 1 }, computed_candidates: 1, curated_decisions: 0 },
    reports: { total: 1, kind_status: 'RECORDED', status_counts: { NONE: 1 } },
  },
};
const RESEARCH_PAIR = {
  kind: 'adjudications', record_id: 'ADJ-C-1', entity_id: 'ent_p', status: 'CANDIDATE', origin: 'COMPUTED', epistemic_class: 'COMPUTED',
  case_ids: ['PRUAP-0001', 'PRUAP-0002'], producers: ['ovnis-pr'], synthetic: false,
  attributes: { case_a: 'PRUAP-0001', case_b: 'PRUAP-0002', status: 'CANDIDATE', origin: 'COMPUTED',
                signals: { date_relation: 'COMPATIBLE_PRECISION', place_basis: 'MUNICIPALITY', narrative_similarity: 0.3, same_source: false } },
};
const RESEARCH_REPORT = {
  kind: 'reports', record_id: 'RPT-PRUAP-0001', case_ids: ['PRUAP-0001'], attributes: { report: {
    report_id: 'RPT-PRUAP-0001', case_id: 'PRUAP-0001', case: { date_local: '1972', temporal_precision: 'YEAR_ONLY', location_name: 'Aguadilla coast', object_type: 'UAP' },
    evidence_ids: { entity: 'evo:entities:ent_c', observation: 'evo:observations:obs_c', source: 'evo:sources:src_c' },
    linked: { manifestation_candidates: ['ADJ-C-1'] }, unresolved: [{ kind: 'UNADJUDICATED_DUPLICATE_CANDIDATE', detail: 'may record the same event as PRUAP-0002; not yet reviewed', ref: 'ADJ-C-1' }],
    receipt: { run_id: 'run_e2e', report_sha256: 'a'.repeat(64), snapshot_id: `sha256:${'b'.repeat(64)}`, created_at: '2026-10-03T00:00:00Z' } } },
};
const RESEARCH_CASE = {
  contract: 'federation-research-v1',
  case: { case_id: 'PRUAP-0001', entity_id: 'ent_c', title: 'Aguadilla coast', category: 'UAP', date: '1972', time: null,
          temporal_precision: 'YEAR_ONLY', place: { municipality: null, location_name: 'Aguadilla coast' }, evidence_tier: 'T3',
          narrative: 'Lights over the water.', entity_href: '/entity/ent_c', evidence_href: '/evidence/Entities/ent_c' },
  source: null, report_status: 'HELD', report: RESEARCH_REPORT.attributes.report, unresolved: RESEARCH_REPORT.attributes.report.unresolved,
  findings: [], hypotheses: [], contradictions: [], queue: [], episodes: [],
  adjudications: [{ ...RESEARCH_PAIR, reviewed: false, other_case: { case_id: 'PRUAP-0002', held: false } }],
};
function researchPage(kind, records) {
  return { contract: 'federation-research-v1', kind, kind_status: records.length ? 'RECORDED' : 'NONE_RECORDED',
           total: records.length, matched: records.length, records, next_cursor: null };
}
const RESEARCH_HANDLERS = {
  '/research/case/PRUAP-0001': RESEARCH_CASE,
  '/research/records/adjudications': researchPage('adjudications', [RESEARCH_PAIR]),
  '/research/records/reports': researchPage('reports', [RESEARCH_REPORT]),
  '/research/records/': researchPage('topics', []),
  '/research?': RESEARCH_OVERVIEW,
};

test.describe('research hub', () => {
  test('is reachable from navigation, says empty ledgers are empty, and keeps computed pairs as candidates', async ({ page }) => {
    await mockApi(page, RESEARCH_HANDLERS);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'Research', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Research Hub' })).toBeVisible();
    await expect(page.locator('[data-empty-ledger]')).toContainText('No topics are recorded in the OVNIS research ledger yet');
    await page.getByRole('tab', { name: 'Duplicate candidates' }).click();
    await expect(page).toHaveURL(/\/research\?tab=candidates$/);
    const pair = page.locator('[data-research-record="ADJ-C-1"]');
    await expect(pair.locator('[data-record-status="CANDIDATE"]')).toContainText('computed, not reviewed');
    await pair.getByRole('link', { name: 'PRUAP-0001' }).click();
    await expect(page).toHaveURL(/\/research\/case\/PRUAP-0001$/);
    await expect(page.getByRole('heading', { name: 'Case PRUAP-0001' })).toBeVisible();
    await expect(page.locator('[data-case-record] [data-temporal-precision]')).toHaveText('(year only)');
    await expect(page.locator('[data-report-receipt]')).toContainText('run_e2e');
  });

  test('the OVNIS reports workspace deep-links each report to its case', async ({ page }) => {
    await mockApi(page, RESEARCH_HANDLERS);
    await page.goto('/ovnis?tab=reports', { waitUntil: 'networkidle' });
    const row = page.locator('[data-report-row="PRUAP-0001"]');
    await expect(row).toContainText('1972');
    await row.getByRole('link', { name: 'Open report' }).click();
    await expect(page).toHaveURL(/\/research\/case\/PRUAP-0001$/);
  });
});

function spatialFeature(stream, recordId, category, producer, precision, lon, lat, title) {
  const collection = stream === 'alerts' ? 'Alerts' : 'Entities';
  return {
    type: 'Feature', id: `evo:${stream}:${recordId}`, geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { evidence_id: `evo:${stream}:${recordId}`, stream, collection, record_id: recordId, title, category, object_type: null,
      producer, producers: [producer], geometry_precision: precision, geometry_basis: null, municipality: null, synthetic: false,
      evidence_href: `/evidence/${collection}/${recordId}`, entity_href: stream === 'entities' ? `/entity/${recordId}` : null },
  };
}
const SPATIAL_FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', bbox_filter: null, include_synthetic: false,
  loaded: 10, matched: 3, truncated: false, outside_bbox: 0, excluded_synthetic: 1,
  features: [
    spatialFeature('alerts', 'alrt_c', 'CONTAMINATION', 'aguayluz-pr', 'REPRESENTATIVE_POINT', -66.1, 18.4, 'Boil water notice'),
    spatialFeature('entities', 'ent_m', 'mineral_occurrence', 'spiderweb-pr', 'OBSERVED_POINT', -66.5, 18.2, 'Manganese occurrence'),
    spatialFeature('entities', 'ent_s', 'sensor_site', 'skywatcher-pr', 'INTERPRETED_POINT', -65.4, 18.1, 'Receiver site'),
  ],
  categories: [
    { producer: 'aguayluz-pr', stream: 'alerts', category: 'CONTAMINATION', count: 1 },
    { producer: 'skywatcher-pr', stream: 'entities', category: 'sensor_site', count: 1 },
    { producer: 'spiderweb-pr', stream: 'entities', category: 'mineral_occurrence', count: 1 },
  ],
  precision_counts: { INTERPRETED_POINT: 1, OBSERVED_POINT: 1, REPRESENTATIVE_POINT: 1 },
  coordinates_without_point_precision: { 'ovnis-pr': 5 },
  not_drawn: [{ producer: 'ovnis-pr', stream: 'observations', category: 'uap_case', count: 6,
    coordinates_without_point_precision: 5, municipality_recorded: 4, object_type_counts: { Mutilation: 2, UAP: 4 } }],
  area_references: [
    { producer: 'ovnis-pr', stream: 'observations', category: 'uap_case', municipality_as_recorded: 'southwest', count: 2, object_type_counts: { UAP: 2 } },
    { producer: 'ovnis-pr', stream: 'observations', category: 'uap_case', municipality_as_recorded: 'vieques', count: 2, object_type_counts: { Mutilation: 1, UAP: 1 } },
  ],
};
const SPATIAL_INTEL = {
  contract: 'federation-spatial-features-v1', point: { lat: 18.4, lon: -66.1 }, radius_m: 1000, nearby_total: 1,
  nearby: [{ ...SPATIAL_FEATURES.features[0].properties, distance_m: 0, distance_basis: 'distance to a representative point, not to the feature itself' }],
  nearby_truncated: false, category_counts: { CONTAMINATION: 1 }, municipality: null, municipality_area_references: [],
  distance_basis: 'great-circle distance to each mapped point',
};

// TIGERweb municipios 2025 (count gate: 78). Vieques is real-shaped; the rest are
// small offshore squares so the gate and identity checks see a full layer.
function municipioPage() {
  const square = (minLon, minLat, size) => [[[minLon, minLat], [minLon + size, minLat], [minLon + size, minLat + size], [minLon, minLat + size], [minLon, minLat]]];
  const features = [{ type: 'Feature', properties: { OBJECTID: 1, NAME: 'Vieques Municipio', BASENAME: 'Vieques', GEOID: '72147' },
    geometry: { type: 'Polygon', coordinates: square(-65.6, 18.05, 0.15) } }];
  for (let i = 2; i <= 78; i += 1) {
    features.push({ type: 'Feature', properties: { OBJECTID: i, NAME: `Municipio ${i} Municipio`, BASENAME: `Municipio ${i}` },
      geometry: { type: 'Polygon', coordinates: square(-68 + i * 0.01, 17.0, 0.005) } });
  }
  return { type: 'FeatureCollection', features };
}

async function mockMapProviders(page) {
  await page.route(/^https:\/\/(?:a\.basemaps\.cartocdn\.com|tile\.openstreetmap\.org|basemap\.nationalmap\.gov)\//, (route) => route.fulfill({ status: 204 }));
  await page.route('https://tigerweb.geo.census.gov/**', (route) => {
    const body = route.request().url().includes('returnCountOnly') ? { count: 78 } : municipioPage();
    return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(body) });
  });
}

test.describe('property map', () => {
  test('is reachable from the GIS workspace, draws by declared precision and outlines only municipios', async ({ page }) => {
    await mockApi(page, { '/spatial/intel': SPATIAL_INTEL, '/spatial/features': SPATIAL_FEATURES });
    await mockMapProviders(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'GIS Workspace', exact: true }).click();
    await page.getByRole('button', { name: 'Property Map', exact: true }).click();
    await expect(page).toHaveURL(/\/gis\?view=property-map$/);
    await expect(page.locator('[data-property-map-summary]')).toContainText('3 of 10 loaded records drawn · 6 not drawn · 1 synthetic excluded');
    const canvas = page.getByTestId('property-map-canvas');
    await expect(canvas).toHaveAttribute('data-map-ready', 'true', { timeout: 30000 });
    await expect(canvas).toHaveAttribute('data-feature-count', '3');
    // MapLibre's worker must actually draw them (the built app once shipped without it).
    await expect(canvas).toHaveAttribute('data-drawn-count', '3', { timeout: 30000 });
    await expect(page.locator('[data-map-origin]')).toContainText('fitted to Puerto Rico, Vieques and Culebra');

    const area = page.locator('[data-area-references]');
    await expect(area.locator('[data-area-reference-counter]')).toHaveText('2 of 6 record no municipality and are not mapped; 4 record a place value.');
    await area.getByRole('button', { name: 'Load municipio boundaries (TIGERweb 2025)' }).click();
    await expect(area.locator('[data-outlined-municipio="Vieques"]')).toContainText('Vieques: 2 (recorded as vieques)');
    await expect(area.locator('[data-unmatched-values]')).toContainText('“southwest”: 2');
    await expect(page.locator('[data-boundary-provenance]')).toContainText(/Snapshot SHA-256 [0-9a-f]{64}/);

    await page.getByRole('button', { name: /Boil water notice/ }).click();
    await expect(page.locator('[data-selected-precision="REPRESENTATIVE_POINT"]')).toContainText('Representative point');
    await expect(page.locator('[data-intel-total]')).toContainText('1 mapped record within 1.00 km');
    await expect(page.locator('[data-intel-row="evo:alerts:alrt_c"]')).toContainText('not to the feature itself');

    await canvas.click({ position: { x: 40, y: 40 } });
    await expect(page.locator('[data-intel-point]')).toBeVisible();
  });

  test('a map deep link starts Location Intel at the linked point', async ({ page }) => {
    await mockApi(page, { '/spatial/intel': SPATIAL_INTEL, '/spatial/features': SPATIAL_FEATURES });
    await mockMapProviders(page);
    await page.goto('/gis?view=property-map&lat=18.1&lon=-65.4');
    await expect(page.locator('[data-intel-point]')).toHaveText('18.10000, -65.40000 (WGS84)');
    await expect(page.locator('[data-map-origin]')).toContainText('18.1000, -65.4000 · zoom 12.0 from the map link');
    await expect(page.locator('[data-intel-municipio]')).toHaveText('Not determined: the municipio boundary layer is not loaded.');
    await expect(page.locator('[data-intel-total]')).toContainText('1 mapped record within 1.00 km');
  });
});

// Digital Twin: CUDEM tiles are synthesized per requested tile name (bounds from
// the name, like the real NOAA tiles) and served the way NOAA's S3 bucket serves
// them (206 for one byte range, CORS open, Content-Range not exposed), so the
// real reader, terrain provider and elevation readout run without the network.
const TWIN_FEATURES = {
  ...SPATIAL_FEATURES,
  undated: 1,
  time_extent: { start: '2001-02-03T00:00:00.000Z', end: '2019-12-31T00:00:00.000Z' },
  features: [
    { ...SPATIAL_FEATURES.features[0], properties: { ...SPATIAL_FEATURES.features[0].properties, time_start: '2019-10-01T00:00:00.000Z', time_end: '2019-12-31T00:00:00.000Z', temporal_state: 'HISTORICAL' } },
    { ...SPATIAL_FEATURES.features[1], properties: { ...SPATIAL_FEATURES.features[1].properties, time_start: null, time_end: null, temporal_state: 'UNKNOWN' } },
    { ...SPATIAL_FEATURES.features[2], properties: { ...SPATIAL_FEATURES.features[2].properties, time_start: '2001-02-03T00:00:00.000Z', time_end: '2001-02-03T23:59:59.999Z', temporal_state: 'HISTORICAL' } },
  ],
};

// Serves a file the way NOAA's bucket and the PROJ CDN do: 206 for one byte range, CORS open.
function serveRanges(route, file) {
  const range = /^bytes=(\d+)-(\d+)$/.exec(route.request().headers().range || '');
  if (!range) return route.fulfill({ status: 200, contentType: 'image/tiff', headers: { 'Access-Control-Allow-Origin': '*' }, body: file });
  const start = Number(range[1]);
  const end = Math.min(Number(range[2]), file.length - 1);
  return route.fulfill({
    status: 206, contentType: 'image/tiff', body: file.subarray(start, end + 1),
    headers: { 'Access-Control-Allow-Origin': '*', 'Content-Range': `bytes ${start}-${end}/${file.length}` },
  });
}

async function mockCudem(page) {
  const { writeArrayBuffer } = await import('geotiff');
  const { tileBounds } = await import('../../src/gis/cudem.js');
  await page.route('https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/**', (route) => {
    const name = route.request().url().split('/').pop();
    const [west, south, east, north] = tileBounds(name);
    const pixels = 64;
    const values = new Float32Array(pixels * pixels).map((_, index) => 100 + Math.floor(index / pixels) * 10);
    return serveRanges(route, Buffer.from(writeArrayBuffer(values, {
      width: pixels, height: pixels, BitsPerSample: [32], SampleFormat: [3],
      ModelPixelScale: [(east - west) / pixels, (north - south) / pixels, 0],
      ModelTiepoint: [0, 0, 0, west, north, 0], GeographicTypeGeoKey: 4269,
    })));
  });
}

// GEOID18's layout (301 x 361 nodes at 1 arc-minute, longitudes 0-360, PixelIsPoint) holding N = -40 m.
async function mockGeoid(page) {
  const { writeArrayBuffer } = await import('geotiff');
  const file = Buffer.from(writeArrayBuffer(new Float32Array(301 * 361).fill(-40), {
    width: 301, height: 361, BitsPerSample: [32], SampleFormat: [3],
    ModelPixelScale: [1 / 60, 1 / 60, 0], ModelTiepoint: [0, 0, 0, 291, 21, 0],
    GeographicTypeGeoKey: 6318, GTRasterTypeGeoKey: 2,
  }));
  await page.route('https://cdn.proj.org/us_noaa_g2018p0.tif', (route) => serveRanges(route, file));
}

// SIGE's karst layer (sumideros): a count query, then GeoJSON pages, as the registry's acquisition gates expect.
async function mockSige(page) {
  await page.route('https://sige.pr.gov/**', (route) => {
    const body = route.request().url().includes('returnCountOnly')
      ? { count: 1 }
      : {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature', properties: { OBJECTID: 1, NOMBRE: 'Sumidero de prueba' },
          geometry: { type: 'Polygon', coordinates: [[[-66.3, 18.1], [-66.2, 18.1], [-66.2, 18.3], [-66.3, 18.3], [-66.3, 18.1]]] },
        }],
      };
    return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(body) });
  });
}

// Nine records of one category: six inside the study box, three inside the control box.
const AOI_FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', loaded: 9, matched: 9, truncated: false, excluded_synthetic: 0, outside_bbox: 0,
  features: [
    ...Array.from({ length: 6 }, (_, i) => [`s${i}`, -66.55 + i * 0.02]),
    ...Array.from({ length: 3 }, (_, i) => [`c${i}`, -65.95 + i * 0.05]),
  ].map(([id, lon]) => ({
    type: 'Feature', id: `evo:entities:${id}`, geometry: { type: 'Point', coordinates: [lon, 18.2] },
    properties: {
      evidence_id: `evo:entities:${id}`, title: id, category: 'utility_asset', stream: 'entities', producer: 'aguayluz-pr', producers: ['aguayluz-pr'],
      geometry_precision: 'OBSERVED_POINT', geometry_basis: null, municipality: null, object_type: null, synthetic: false,
      evidence_href: `/evidence/Entities/${id}`, entity_href: null, time_start: null, time_end: null, temporal_state: 'UNKNOWN',
    },
  })),
  categories: [{ producer: 'aguayluz-pr', stream: 'entities', category: 'utility_asset', count: 9 }], precision_counts: { OBSERVED_POINT: 9 },
  coordinates_without_point_precision: {}, not_drawn: [], area_references: [], time_extent: null, undated: 9,
  store: { kind: 'bounded-sample', cap_per_stream: 400, streams: { entities: { sampled: 825, actual: 48224, closure_added: 425 } } },
};

test.describe('aoi comparison', () => {
  test('compares a study box with a control box as background, over a stated sample, and refuses overlap', async ({ page }) => {
    test.setTimeout(90000);
    await mockApi(page, { '/spatial/features': AOI_FEATURES });
    await mockMapProviders(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'GIS Workspace', exact: true }).click();
    await page.getByRole('button', { name: 'AOI comparison', exact: true }).click();
    await expect(page).toHaveURL(/\/gis\?view=aoi-comparison$/);
    await expect(page.getByTestId('aoi-map')).toHaveAttribute('data-map-ready', 'true', { timeout: 30000 });
    await expect(page.locator('[data-store-basis]')).toContainText('bounded sample (at most 400 records per stream): entities 825 of 48224');

    await page.getByLabel('Study AOI bounding box').fill('-66.6,18.1,-66.4,18.3');
    await page.getByLabel('Control 1 bounding box').fill('-66.5,18.1,-65.8,18.3');
    await page.getByRole('button', { name: 'Compare' }).click();
    await expect(page.getByRole('alert')).toContainText('overlaps the study AOI');

    await page.getByLabel('Control 1 bounding box').fill('-66.0,18.1,-65.8,18.3');
    await page.getByRole('button', { name: 'Compare' }).click();
    await expect(page.locator('[data-not-a-finding]')).toHaveText('BACKGROUND COMPARISON — not a finding');
    const row = page.locator('[data-comparison-row="aguayluz-pr|entities|utility_asset"]');
    await expect(row.locator('[data-study-count]')).toHaveText('6');
    await expect(row.locator('[data-control-count]')).toHaveText('3');
    await expect(row.locator('[data-ratio]')).toContainText(/^\d+\.\d{2} \(95% CI/);
    await expect(row.locator('[data-p]')).toHaveText(/^\d\.\d{3}$/);
    await expect(page.locator('[data-multiplicity]')).toContainText('not adjusted for multiple comparisons');
    await expect(page.locator('[data-aoi-summary]')).toContainText('spherical polygon area');

    const [receipt] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download receipt (JSON)' }).click()]);
    expect(receipt.suggestedFilename()).toBe('aoi-comparison.json');
    const { readFile } = await import('node:fs/promises');
    const body = JSON.parse(await readFile(await receipt.path(), 'utf8'));
    expect(body).toMatchObject({ contract: 'aoi-comparison-v1', certification: 'NOT_CERTIFIED', store: { sample: true } });
    expect(body.rows[0]).toMatchObject({ study_count: 6, control_count: 3 });
  });
});

test.describe('interpretive layers', () => {
  test('keeps documented and modelled geometry apart and reads a terrain profile with its datum and gaps', async ({ page }) => {
    test.setTimeout(90000);
    await mockApi(page, { '/spatial/features': SPATIAL_FEATURES });
    await mockMapProviders(page);
    await mockCudem(page);
    await mockSige(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'GIS Workspace', exact: true }).click();
    await page.getByRole('button', { name: 'Subsurface & interpretive', exact: true }).click();
    await expect(page).toHaveURL(/\/gis\?view=interpretive-layers$/);
    await expect(page.getByTestId('interpretive-map')).toHaveAttribute('data-map-ready', 'true', { timeout: 30000 });

    const modelled = page.locator('[data-group="modelled"]');
    await expect(modelled).toContainText('MODELLED — not observed geometry');
    await expect(modelled.locator('[data-modelled-count]')).toHaveText('0');
    await expect(modelled).toContainText('No producer exports a modelled or interpretive layer');
    await expect(page.locator('[data-hub-documented]')).toContainText('1 Hub-held documented record');

    const karst = page.locator('[data-layer="pr-sige-sumideros"]');
    await karst.getByRole('button', { name: 'Load Sumideros' }).click();
    await expect(karst.locator('[data-layer-provenance]')).toContainText(/1 feature .* snapshot SHA-256 [0-9a-f]{12}/);

    // West to east across the island and out to sea: CUDEM ends at -65.25, so the east is a gap, not zero.
    await page.getByLabel('Start (lat, lon)').fill('18.2, -66.5');
    await page.getByLabel('End (lat, lon)').fill('18.2, -64.0');
    await page.getByRole('button', { name: 'Draw profile' }).click();
    const stats = page.locator('[data-profile-stats]');
    await expect(stats).toContainText(/100 samples · [1-9]\d* with a CUDEM height · [1-9]\d* without/, { timeout: 30000 });
    await expect(page.locator('[data-profile-datum]')).toContainText('PRVD02');
    await expect(page.locator('svg[data-profile-chart] path')).toHaveAttribute('d', /^M/);
    await expect(page.locator('[data-profile-crossings]')).toContainText('Sumideros');
    await expect(page.locator('[data-profile-subsurface]')).toContainText('No subsurface model supplied');
    const [csv] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download CSV' }).click()]);
    expect(csv.suggestedFilename()).toBe('terrain-profile.csv');
  });
});

test.describe('digital twin', () => {
  test('is reachable from the GIS workspace, binds uniform-datum terrain and keeps panels in step', async ({ page }) => {
    // Cesium (lazy-loaded, software WebGL in CI) plus three other panels exceed the 30 s default.
    test.setTimeout(120000);
    await mockApi(page, { '/spatial/features': TWIN_FEATURES });
    await mockMapProviders(page);
    await mockCudem(page);
    await mockGeoid(page);
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'GIS Workspace', exact: true }).click();
    await page.getByRole('button', { name: 'Digital Twin', exact: true }).click();
    await expect(page).toHaveURL(/\/gis\?view=digital-twin$/);

    const perspective = page.getByTestId('digital-twin-perspective');
    await expect(perspective).toHaveAttribute('data-ready', 'true', { timeout: 30000 });
    await expect(perspective).toHaveAttribute('data-terrain', 'noaa-ncei-cudem-pr-ninth-m9525');
    await expect(perspective).toHaveAttribute('data-geoid', 'applied');
    await expect(page.getByTestId('digital-twin-ortho')).toHaveAttribute('data-map-ready', 'true', { timeout: 30000 });
    await expect(page.getByTestId('digital-twin-ortho')).toHaveAttribute('data-drawn-count', /^[1-9]/, { timeout: 30000 });
    await expect(page.locator('[data-dt-findings-status]')).toContainText('No finding carries geometry');
    await expect(page.locator('[data-dt-live-status]')).toContainText('No producer declares a live cadence');
    await expect(page.locator('[data-dt-terrain-status]')).toContainText('bound (uniform vertical datum)');
    await expect(page.locator('[data-dt-geoid]')).toContainText('GEOID18 applied');

    await page.locator('[data-dt-record="evo:entities:ent_m"]').click();
    await expect(page.locator('[data-dt-elevation]')).toContainText(/m PRVD02 · CUDEM m9525/, { timeout: 30000 });
    // The ellipsoidal height is H + N from the geoid grid read from the CDN (N = -40 m in the mock), with its own datum.
    await expect(page.locator('[data-dt-ellipsoidal]')).toContainText(/Geoid N -40\.0 m \(GEOID18\) → [\d.]+ m NAD83\(2011\) ellipsoidal · H \+ N/);
    await expect(page.locator('[data-dt-terrain-tiles]')).toContainText('ncei19_', { timeout: 30000 });

    await page.getByRole('slider', { name: 'Time' }).fill(String(Date.parse('2005-01-01T00:00:00Z')));
    await expect(page.locator('[data-dt-counts]')).toContainText('2 shown · 1 outside the time window · 1 undated');

    await page.getByRole('button', { name: 'Maximize Perspective' }).click();
    await expect(page).toHaveURL(/\/gis\?view=digital-twin&panel=perspective$/);
    await expect(page.locator('[data-dt-panel="ortho"]')).toBeHidden();
    await page.getByRole('button', { name: 'Restore Perspective' }).click();
    await expect(page.locator('[data-dt-panel="ortho"]')).toBeVisible();

    const [geojson] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export GeoJSON' }).click()]);
    expect(geojson.suggestedFilename()).toBe('digital-twin.geojson');
    const [usd] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export USD' }).click()]);
    expect(usd.suggestedFilename()).toBe('digital-twin.usda');
  });
});

// The frozen reference values (JPL Horizons) and real NOAA SWPC payloads the Sky tests are held to.
const readJson = (relative) => JSON.parse(readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8'));
const SKY_REFERENCE = readJson('../../src/sky/referenceEphemerides.json');
const SWPC_SAMPLES = readJson('../../src/sky/fixtures/swpc-samples.json');

// NOAA SWPC answers cross-origin reads; the sandbox browser cannot reach it, so the real payloads frozen in the
// fixture are served with the same CORS header.
async function mockSwpc(page, { failSolarWind = false } = {}) {
  await page.route('https://services.swpc.noaa.gov/**', (route) => {
    const url = route.request().url();
    const headers = { 'Access-Control-Allow-Origin': '*' };
    if (url.endsWith('noaa-planetary-k-index.json')) return route.fulfill({ status: 200, contentType: 'application/json', headers, body: JSON.stringify(SWPC_SAMPLES.kp.payload) });
    if (url.endsWith('solar-wind-speed.json')) {
      if (failSolarWind) return route.fulfill({ status: 503, contentType: 'text/plain', headers, body: 'down' });
      return route.fulfill({ status: 200, contentType: 'application/json', headers, body: JSON.stringify(SWPC_SAMPLES.solar_wind_speed.payload) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', headers, body: JSON.stringify(SWPC_SAMPLES.mag_field.payload) });
  });
}

test.describe('sky workspace', () => {
  test('is reachable from Skywatcher, reads the sky where Horizons puts it, keeps its state in the link, and says when a product is down', async ({ page }) => {
    test.setTimeout(90000);
    await page.clock.install({ time: new Date('2026-10-18T20:55:00Z') });
    await mockApi(page);
    await mockSwpc(page, { failSolarWind: true });
    await page.goto('/sources', { waitUntil: 'networkidle' });
    await (await openPrimaryNav(page)).getByRole('link', { name: 'Skywatcher-PR', exact: true }).click();
    await page.getByRole('tab', { name: 'Sky', exact: true }).click();
    await expect(page).toHaveURL(/\/skywatcher\?view=sky/);
    await expect(page.locator('[data-sky-default-observer]')).toContainText('does not ask your browser for your location');

    // A fixed instant, so the readout can be held to the frozen Horizons value for it.
    await page.getByLabel('Time (UTC)').fill('2026-10-16T00:30:00Z');
    await page.getByRole('button', { name: 'Set time' }).click();
    await expect(page.locator('[data-sky-time]')).toContainText('2026-10-16T00:30:00Z');
    const horizons = SKY_REFERENCE.horizons.cases.find((c) => c.body === 'Sun' && c.observer === 'San Juan' && c.time === '2026-10-16T00:30:00Z');
    const shown = horizons.airless.alt > -1 ? horizons.refracted.alt : horizons.airless.alt;
    const altitude = Number.parseFloat((await page.locator('[data-sky-sun] [data-testid="altitude"]').innerText()).replace('−', '-'));
    expect(Math.abs(altitude - shown)).toBeLessThan(0.06);
    await expect(page.locator('[data-sky-daylight]')).toContainText(/twilight|Night/);
    await expect(page.locator('[data-sky-conventions]')).toContainText('astronomy-engine 2.1.19');

    // Every one of the seven bodies is drawn or named as below the horizon.
    await expect(page.locator('svg[data-sky-chart]')).toBeVisible();
    const drawn = await page.locator('[data-sky-glyph]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-sky-glyph')));
    const below = await page.locator('[data-sky-below]').innerText();
    for (const body of ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn']) expect(drawn.includes(body) || below.includes(body), body).toBe(true);

    // Space weather: the products that answered are shown with their state; the one that failed is unavailable, not zero.
    const kp = page.locator('[data-sw="kp"]');
    await expect(kp.locator('[data-testid="sw-value"]')).toHaveText('1.67');
    await expect(kp.locator('[data-testid="sw-state"]')).toHaveText('LIVE');
    await expect(page.locator('[data-sw="imf-bz"] [data-testid="sw-value"]')).toHaveText('3');
    const wind = page.locator('[data-sw="solar-wind-speed"]');
    await expect(wind.locator('[data-testid="sw-state"]')).toHaveText('FAILED');
    await expect(wind).toContainText('Unavailable: HTTP 503');
    await expect(wind.locator('[data-testid="sw-value"]')).toHaveCount(0);
    await expect(page.locator('[data-sw-note]')).toContainText('not tied to the time above');

    // The time and the observer live in the link.
    await page.getByRole('button', { name: 'Forward 1 hour' }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('t')).toBe('2026-10-16T01:30:00Z');
    await page.getByLabel('Latitude (°N)').fill('-33.4489');
    await page.getByLabel('Longitude (°E)').fill('-70.6693');
    await page.getByLabel('Elevation (m)').fill('520');
    await page.getByLabel('UTC offset (hours)').fill('-3');
    await page.getByRole('button', { name: 'Apply observer' }).click();
    await expect(page.locator('[data-sky-default-observer]')).toHaveCount(0);
    const link = new URL(page.url());
    expect(link.searchParams.get('view')).toBe('sky');
    expect(link.searchParams.get('lat')).toBe('-33.4489');
    expect(link.searchParams.get('tz')).toBe('-3');
    const before = await page.locator('[data-sky-sun] [data-testid="altitude"]').innerText();
    await page.reload({ waitUntil: 'networkidle' });
    await expect(page.locator('[data-sky-time]')).toContainText('2026-10-16T01:30:00Z');
    await expect(page.locator('[data-sky-sun] [data-testid="altitude"]')).toHaveText(before);
  });

  test('refuses an observer it cannot compute for, in words, with no readout', async ({ page }) => {
    await mockApi(page);
    await mockSwpc(page);
    await page.goto('/skywatcher?view=sky&lat=95&lon=-66&t=2026-10-16T00:30:00Z', { waitUntil: 'networkidle' });
    await expect(page.getByRole('alert').first()).toContainText('Latitude must be between -90 and 90 degrees.');
    await expect(page.locator('[data-sky-sun]')).toHaveCount(0);
  });
});

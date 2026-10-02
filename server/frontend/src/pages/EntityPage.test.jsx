import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import { OVNIS_YEAR_ONLY_CASE } from '@/test/fixtures/evidenceObject';
import EntityPage from './EntityPage';

vi.mock('@/api/federationClient', () => ({ federation: { composition: { get: vi.fn() } } }));

const COMPOSITION = {
  contract: 'federation-entity-composition-v1',
  contract_status: 'CANDIDATE',
  anchor: { ...OVNIS_YEAR_ONLY_CASE, id: 'evo:entities:ent_a', stream: 'entities', producer_record_id: 'ent_a',
            canonical_type: 'entity:wetland', title: 'Laguna Cartagena' },
  identity: { identity_state: 'UNRESOLVED', identity_scope: 'PRODUCER_LOCAL', identity_basis: 'no identity adjudication',
              registry_status: 'NOT_CONFIGURED', members: [{ producer: 'spiderweb-pr', collection: 'Entities', record_id: 'ent_a' }] },
  sections: [
    { producer: 'spiderweb-pr', status: 'AVAILABLE', relationship_count: 1, linked_record_count: 0 },
    { producer: 'moneysweep-pr', status: 'NO_DATA', relationship_count: 0, linked_record_count: 0 },
  ],
  relationships: [
    { evidence_id: 'evo:relationships:rel_1', collection: 'Relationships', record_id: 'rel_1', relationship_type: 'located_in',
      direction: 'OUTBOUND', counterpart: { record_id: 'ent_b', title: 'Lajas', resolved: true, entity_href: '/entity/ent_b' },
      edge_state: 'DOCUMENTED', edge_basis: 'producer-asserted relationship with a bound source', producers: ['spiderweb-pr'],
      synthetic: false, match_basis: null, evidence_href: '/evidence/Relationships/rel_1' },
    { evidence_id: 'evo:correlations:rel_2', collection: 'Correlations', record_id: 'rel_2', relationship_type: 'spatial_proximity',
      direction: 'INBOUND', counterpart: { record_id: 'ent_c', title: null, resolved: false, entity_href: null },
      edge_state: 'CANDIDATE', edge_basis: "hub correlation on weak basis 'location'", producers: ['thehub-pr'],
      synthetic: true, match_basis: 'location', evidence_href: '/evidence/Correlations/rel_2' },
  ],
  linked_records: [],
  truncated: { relationships: false, linked_records: false },
  limits: { relationships: 200, linked_records: 200 },
};

function renderAt(url) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/entity/:id" element={<EntityPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('EntityPage', () => {
  beforeEach(() => {
    federation.composition.get.mockClear();
  });

  it('composes the entity without inferring identity', async () => {
    federation.composition.get.mockResolvedValue(COMPOSITION);
    renderAt('/entity/ent_a');
    expect(await screen.findByRole('heading', { name: 'Laguna Cartagena' })).toBeInTheDocument();
    expect(federation.composition.get).toHaveBeenCalledWith('ent_a');
    expect(screen.getByText(/no registry is connected/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Full provenance' })).toHaveAttribute('href', '/evidence/Entities/ent_a');
  });

  it('shows each edge state and never fabricates an unresolved counterpart', async () => {
    federation.composition.get.mockResolvedValue(COMPOSITION);
    renderAt('/entity/ent_a');
    const table = within(await screen.findByRole('table', { name: /Relationships naming this entity/ }));
    expect(table.getByRole('link', { name: 'Lajas' })).toHaveAttribute('href', '/entity/ent_b');
    expect(table.getByText(/Not held by the Hub/)).toBeInTheDocument();
    expect(document.querySelector('[data-edge-state="CANDIDATE"]')).not.toBeNull();
    expect(document.querySelector('[data-edge-state="DOCUMENTED"]')).not.toBeNull();
    expect(screen.getByText('No data for this entity')).toBeInTheDocument();
  });

  it('reports a missing entity instead of substituting one', async () => {
    federation.composition.get.mockImplementation(() => Promise.reject(Object.assign(new Error('not found'), { status: 404 })));
    renderAt('/entity/ent_missing');
    expect(await screen.findByRole('alert')).toHaveTextContent('The Hub holds no entity ent_missing');
  });

  it('has no axe violations', async () => {
    federation.composition.get.mockResolvedValue(COMPOSITION);
    const { container } = renderAt('/entity/ent_a');
    await screen.findByRole('heading', { name: 'Laguna Cartagena' });
    expect(await axe(container)).toHaveNoViolations();
  });
});

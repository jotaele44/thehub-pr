import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import Search from './Search';

vi.mock('@/api/federationClient', () => ({ federation: { search: { query: vi.fn() } } }));

const PRODUCERS = [
  { producer: 'ovnis-pr', status: 'AVAILABLE', indexed_records: 12 },
  { producer: 'moneysweep-pr', status: 'NO_DATA', indexed_records: 0 },
];

function response(overrides = {}) {
  return {
    query: 'laguna cartagena', terms: ['laguna', 'cartagena'], type: 'ALL', type_status: 'OK', query_status: 'OK',
    include_synthetic: false, indexed_records: 42, matched: 3, excluded_synthetic: 1, total: 2, next_cursor: null,
    producers: PRODUCERS,
    results: [
      { evidence_id: 'evo:entities:e2', stream: 'entities', collection: 'Entities', record_id: 'e2', kind: 'ENTITY',
        title: 'Laguna Cartagena', type: 'wetland', producers: ['spiderweb-pr'], synthetic: false,
        declared_epistemic_class: 'CURATED', source_ids: [], evidence_href: '/evidence/Entities/e2', entity_href: '/entity/e2' },
      { evidence_id: 'evo:observations:o2', stream: 'observations', collection: 'Observations', record_id: 'o2', kind: 'READING',
        title: 'Laguna Cartagena', type: 'adsb_contact', producers: ['skywatcher-pr'], synthetic: false,
        declared_epistemic_class: null, source_ids: [], evidence_href: '/evidence/Observations/o2', entity_href: null },
    ],
    ...overrides,
  };
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname + location.search}</output>;
}

function renderAt(url) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/search" element={<><Search /><Where /></>} /><Route path="*" element={<Where />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Search page', () => {
  beforeEach(() => {
    federation.search.query.mockClear();
  });

  it('reads its state from the URL and renders results with provenance links', async () => {
    federation.search.query.mockResolvedValue(response());
    renderAt('/search?q=laguna+cartagena&type=ALL');
    expect(await screen.findByText('2 results', { exact: false })).toBeInTheDocument();
    expect(federation.search.query).toHaveBeenCalledWith({ q: 'laguna cartagena', type: 'ALL', includeSynthetic: false, cursor: undefined });
    expect(screen.getByText(/1 synthetic excluded/)).toBeInTheDocument();
    expect(screen.getByText(/42 indexed records/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Provenance' })[0]).toHaveAttribute('href', '/evidence/Entities/e2');
    expect(screen.getByRole('link', { name: 'Entity composition' })).toHaveAttribute('href', '/entity/e2');
    expect(screen.getByText(/class not declared by producer/)).toBeInTheDocument();
    expect(screen.getByText('No data in the Hub')).toBeInTheDocument();
  });

  it('writes the query, filter and synthetic toggle back to the URL', async () => {
    federation.search.query.mockResolvedValue(response());
    renderAt('/search');
    fireEvent.change(await screen.findByLabelText('Search query'), { target: { value: 'san germán' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/search?q=san+germ%C3%A1n'));
    fireEvent.click(screen.getByRole('button', { name: 'Sources' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('type=SOURCE'));
    expect(screen.getByRole('button', { name: 'Sources' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByLabelText(/Include synthetic/));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('synthetic=1'));
  });

  it('says no finding is recorded instead of showing an empty result', async () => {
    federation.search.query.mockResolvedValue(response({ type: 'FINDING', type_status: 'NO_FINDINGS_RECORDED', results: [], total: 0, matched: 0, excluded_synthetic: 0 }));
    renderAt('/search?q=laguna&type=finding');
    expect(await screen.findByText(/No findings are recorded in the OVNIS research ledger yet/)).toBeInTheDocument();
  });

  it('shows a finding with the status its producer recorded', async () => {
    federation.search.query.mockResolvedValue(response({ type: 'FINDING', total: 1, matched: 1, excluded_synthetic: 0, results: [
      { evidence_id: 'evo:entities:f1', stream: 'entities', collection: 'Entities', record_id: 'f1', kind: 'FINDING',
        title: 'Two reports cite one newspaper', type: 'finding', producers: ['ovnis-pr'], synthetic: false,
        declared_epistemic_class: 'CURATED', source_ids: [], evidence_href: '/evidence/Entities/f1', entity_href: '/entity/f1',
        finding_status: 'CANDIDATE' },
    ] }));
    renderAt('/search?q=newspaper&type=finding');
    expect(await screen.findByText('Finding status: CANDIDATE')).toBeInTheDocument();
  });

  it('paginates through the URL cursor', async () => {
    federation.search.query.mockResolvedValue(response({ next_cursor: '25' }));
    renderAt('/search?q=laguna');
    fireEvent.click(await screen.findByRole('button', { name: 'Next results' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('cursor=25'));
  });

  it('reports an unavailable search instead of fabricating results', async () => {
    federation.search.query.mockImplementation(() => Promise.reject(new Error('503 Service Unavailable')));
    renderAt('/search?q=laguna');
    expect(await screen.findByRole('alert')).toHaveTextContent('Search is unavailable');
    expect(screen.queryByRole('link', { name: 'Provenance' })).toBeNull();
  });

  it('has no axe violations', async () => {
    federation.search.query.mockResolvedValue(response());
    const { container } = renderAt('/search?q=laguna+cartagena');
    await screen.findByText('2 results', { exact: false });
    expect(await axe(container)).toHaveNoViolations();
  });
});

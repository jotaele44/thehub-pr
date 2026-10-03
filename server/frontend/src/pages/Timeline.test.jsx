import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import Timeline from './Timeline';

vi.mock('@/api/federationClient', () => ({ federation: { timeline: { query: vi.fn() } } }));

const EVENT = {
  evidence_id: 'evo:observations:obs_1', observation_id: 'obs_1', entity_id: 'ent_1', case_id: 'PRUAP-0001',
  title: 'Offshore', category: 'USO', environment: 'underwater', date: '1927-10-06', time: null,
  temporal_precision: 'DATE_ONLY', era: '1920s', narrative: 'Shipping barge crew reported a submerged blue light.',
  place: { municipality: null, location_name: 'Offshore' }, evidence_tier: 'T3', source_id: 'src_1',
  source: { source_id: 'src_1', name: 'Dartmouth Alumni Magazine', url: 'https://example.org/article', evidence_href: '/evidence/Sources/src_1' },
  producers: ['ovnis-pr'], synthetic: false, findings: [],
  evidence_href: '/evidence/Observations/obs_1', entity_href: '/entity/ent_1',
};
const YEAR_ONLY = {
  ...EVENT, evidence_id: 'evo:observations:obs_2', observation_id: 'obs_2', entity_id: 'ent_2', case_id: null,
  title: 'Cabo Rojo', category: 'UAP', date: '1967', temporal_precision: 'YEAR_ONLY', era: '1960s', narrative: null,
  place: { municipality: 'Cabo Rojo', location_name: 'Cabo Rojo' }, source: null,
  evidence_href: '/evidence/Observations/obs_2', entity_href: '/entity/ent_2',
};

function response(overrides = {}) {
  return {
    contract: 'federation-event-timeline-v1', producer: 'ovnis-pr', producer_status: 'AVAILABLE', sort: 'oldest',
    categories: [{ category: 'UAP', count: 1 }, { category: 'USO', count: 1 }], selected_categories: [],
    findings_only: false, include_synthetic: false, loaded_events: 3, excluded_synthetic: 0, matched: 2, undated: 1,
    findings_total: 0, findings_status: 'NO_FINDINGS_RECORDED', events: [EVENT, YEAR_ONLY], next_cursor: null,
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
        <Routes><Route path="/timeline" element={<><Timeline /><Where /></>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Timeline page', () => {
  beforeEach(() => {
    federation.timeline.query.mockReset();
  });

  it('renders events with their recorded precision and never invents a date', async () => {
    federation.timeline.query.mockResolvedValue(response());
    renderAt('/timeline');
    expect(await screen.findByRole('heading', { name: 'Offshore' })).toBeInTheDocument();
    expect(screen.getByText('1967')).toBeInTheDocument();
    expect(document.querySelector('[data-timeline-event="obs_2"] [data-temporal-precision]')).toHaveTextContent('year only');
    expect(screen.getByText('No narrative was exported for this case.')).toBeInTheDocument();
    expect(screen.getByText('Source not held by the Hub')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Source$/ })).toHaveAttribute('href', 'https://example.org/article');
    expect(screen.getAllByRole('link', { name: 'Provenance' })[0]).toHaveAttribute('href', '/evidence/Observations/obs_1');
    expect(screen.getAllByRole('link', { name: 'Case composition' })[0]).toHaveAttribute('href', '/entity/ent_1');
    expect(screen.getByText(/3 events in this Hub's store · 2 match · 1 undated, listed last/)).toBeInTheDocument();
  });

  it('keeps sort, categories and the synthetic toggle in the URL', async () => {
    federation.timeline.query.mockResolvedValue(response());
    renderAt('/timeline');
    fireEvent.click(await screen.findByRole('button', { name: 'Newest first' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('sort=newest'));
    fireEvent.click(screen.getByRole('button', { name: /USO/ }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('category=USO'));
    expect(federation.timeline.query).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'newest', categories: ['USO'] }));
    fireEvent.click(screen.getByLabelText(/Include synthetic/));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('synthetic=1'));
  });

  it('links only an http(s) source URL and shows any other locator as text', async () => {
    const named = { ...EVENT, source: { ...EVENT.source, url: 'Dartmouth Alumni Magazine, 1927' } };
    federation.timeline.query.mockResolvedValue(response({ events: [named] }));
    renderAt('/timeline');
    expect(await screen.findByText('Source locator: Dartmouth Alumni Magazine, 1927')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Source$/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Source provenance' })).toHaveAttribute('href', '/evidence/Sources/src_1');
  });

  it('says no findings are recorded instead of showing an empty result', async () => {
    federation.timeline.query.mockResolvedValue(response({ findings_only: true, events: [], matched: 0 }));
    renderAt('/timeline?findings=1');
    expect(await screen.findByText(/No findings are recorded yet/)).toBeInTheDocument();
    expect(federation.timeline.query).toHaveBeenCalledWith(expect.objectContaining({ findingsOnly: true }));
  });

  it('reports a Hub with no OVNIS events', async () => {
    federation.timeline.query.mockResolvedValue(response({ producer_status: 'NO_DATA', events: [], loaded_events: 0, matched: 0, categories: [] }));
    renderAt('/timeline');
    expect(await screen.findByText(/The Hub holds no OVNIS case events/)).toBeInTheDocument();
  });

  it('reports an unavailable timeline', async () => {
    federation.timeline.query.mockImplementation(() => Promise.reject(new Error('503 Service Unavailable')));
    renderAt('/timeline');
    expect(await screen.findByRole('alert')).toHaveTextContent('The timeline is unavailable');
  });

  it('has no axe violations', async () => {
    federation.timeline.query.mockResolvedValue(response());
    const { container } = renderAt('/timeline');
    await screen.findByRole('heading', { name: 'Offshore' });
    expect(await axe(container)).toHaveNoViolations();
  });
});

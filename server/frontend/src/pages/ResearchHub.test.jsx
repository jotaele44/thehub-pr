import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import ResearchHub from './ResearchHub';

vi.mock('@/api/federationClient', () => ({
  federation: { research: { overview: vi.fn(), records: vi.fn(), caseRecord: vi.fn() } },
}));
vi.mock('@/pages/ResearchAssistant', () => ({ default: () => <p>Research assistant (unchanged)</p> }));

const KINDS = ['topics', 'findings', 'hypotheses', 'contradictions', 'adjudications', 'queue', 'episodes', 'reports'];

function overview(overrides = {}) {
  const kinds = Object.fromEntries(KINDS.map((k) => [k, { total: 0, kind_status: 'NONE_RECORDED', status_counts: {} }]));
  kinds.adjudications = { total: 2, kind_status: 'RECORDED', status_counts: { CANDIDATE: 2 }, computed_candidates: 2, curated_decisions: 0 };
  kinds.reports = { total: 3, kind_status: 'RECORDED', status_counts: { NONE: 3 } };
  return { contract: 'federation-research-v1', producer: 'ovnis-pr', producer_status: 'AVAILABLE', kinds, topics: [], ...overrides };
}

const PAIR = {
  kind: 'adjudications', record_id: 'ADJ-C-1', entity_id: 'ent_p', status: 'CANDIDATE', origin: 'COMPUTED',
  epistemic_class: 'COMPUTED', case_ids: ['PRUAP-0001', 'PRUAP-0002'], producers: ['ovnis-pr'], synthetic: false,
  attributes: { case_a: 'PRUAP-0001', case_b: 'PRUAP-0002', status: 'CANDIDATE', origin: 'COMPUTED',
                signals: { date_relation: 'COMPATIBLE_PRECISION', place_basis: 'MUNICIPALITY', narrative_similarity: 0.42, same_source: true } },
};

function page(kind, records, extra = {}) {
  return { contract: 'federation-research-v1', kind, kind_status: records.length ? 'RECORDED' : 'NONE_RECORDED',
           total: records.length, matched: records.length, records, next_cursor: null, ...extra };
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
        <Routes><Route path="/research" element={<><ResearchHub /><Where /></>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Research Hub', () => {
  beforeEach(() => {
    federation.research.overview.mockReset();
    federation.research.records.mockReset();
    federation.research.overview.mockResolvedValue(overview());
    federation.research.records.mockImplementation((kind) => Promise.resolve(page(kind, kind === 'adjudications' ? [PAIR] : [])));
  });

  it('says an empty ledger is empty instead of showing a result', async () => {
    renderAt('/research');
    expect(await screen.findByText(/No topics are recorded in the OVNIS research ledger yet/)).toBeInTheDocument();
    expect(within(document.querySelector('[data-research-overview]')).getByText('Duplicate candidates').nextSibling).toHaveTextContent('2');
  });

  it('shows a computed pair as an unreviewed candidate with its signals', async () => {
    renderAt('/research?tab=candidates');
    expect(await screen.findByText(/computed, not reviewed/)).toBeInTheDocument();
    expect(screen.getByText(/never decide that two cases are one event/)).toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'PRUAP-0001' })[0]).toHaveAttribute('href', '/research/case/PRUAP-0001');
  });

  it('keeps the tab in the URL and keeps the assistant reachable', async () => {
    renderAt('/research');
    fireEvent.mouseDown(await screen.findByRole('tab', { name: 'Hypotheses' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('tab=hypotheses'));
    expect(await screen.findByText(/No hypotheses are recorded/)).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Assistant' }));
    expect(await screen.findByText('Research assistant (unchanged)')).toBeInTheDocument();
  });

  it('renders topic cards with finding and distinct-source counts and expands to findings', async () => {
    federation.research.overview.mockResolvedValue(overview({
      topics: [{ kind: 'topics', record_id: 'TOPIC-USO', status: 'ACTIVE', attributes: { title: 'Submerged objects', scope: 'USO reports', tags: ['USO'] },
                 finding_count: 1, finding_ids: ['FIND-1'], source_count: 1, source_count_basis: 'distinct cited sources' }],
    }));
    federation.research.records.mockImplementation((kind) => Promise.resolve(page(kind, kind === 'findings' ? [{
      kind: 'findings', record_id: 'FIND-1', status: 'ACCEPTED', case_ids: ['PRUAP-0001'],
      attributes: { statement: 'Both reports cite the same harbour log.', epistemic_class: 'CURATED',
                    source_refs: [{ case_id: 'PRUAP-0001', locator: 'p. 2' }] },
    }] : [])));
    renderAt('/research');
    expect(await screen.findByText('1 finding ·', { exact: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View findings' }));
    expect(await screen.findByText('Both reports cite the same harbour log.')).toBeInTheDocument();
    expect(document.querySelector('[data-finding="FIND-1"] [data-record-status="ACCEPTED"]')).toHaveTextContent(/not an established fact/);
  });

  it('shows the falsification checklist for a hypothesis', async () => {
    federation.research.records.mockImplementation((kind) => Promise.resolve(page(kind, kind === 'hypotheses' ? [{
      kind: 'hypotheses', record_id: 'HYP-1', status: 'OPEN', case_ids: ['PRUAP-0001'],
      attributes: { statement: 'One launch seen from two towns.', falsification: { missing_data: { status: 'PASSED', note: 'logs checked' } } },
    }] : [])));
    renderAt('/research?tab=hypotheses');
    expect(await screen.findByText('One launch seen from two towns.')).toBeInTheDocument();
    expect(document.querySelectorAll('[data-falsification-check]')).toHaveLength(9);
    expect(document.querySelector('[data-falsification-check="missing_data"]')).toHaveTextContent('PASSED');
    expect(document.querySelector('[data-falsification-check="source_dependence"]')).toHaveTextContent('NOT_RUN');
  });

  it('reports an unavailable research API', async () => {
    federation.research.overview.mockImplementation(() => Promise.reject(new Error('503 Service Unavailable')));
    renderAt('/research');
    expect(await screen.findByRole('alert')).toHaveTextContent('The research overview is unavailable');
  });

  it('has no axe violations', async () => {
    const { container } = renderAt('/research?tab=candidates');
    await screen.findByText(/computed, not reviewed/);
    expect(await axe(container)).toHaveNoViolations();
  });
});

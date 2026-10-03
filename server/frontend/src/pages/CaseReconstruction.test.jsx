import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import CaseReconstruction from './CaseReconstruction';
import { ReportsWorkspace, ShowLog } from '@/components/research/OvnisResearchTabs';

vi.mock('@/api/federationClient', () => ({
  federation: { research: { overview: vi.fn(), records: vi.fn(), caseRecord: vi.fn() } },
}));

const CASE = {
  contract: 'federation-research-v1',
  case: { case_id: 'PRUAP-0159', entity_id: 'ent_c', title: 'Aguadilla coast', category: 'UAP', date: '1979',
          time: null, temporal_precision: 'YEAR_ONLY', place: { municipality: null, location_name: 'Aguadilla coast' },
          evidence_tier: 'T3', narrative: 'Lights seen over the water.', entity_href: '/entity/ent_c', evidence_href: '/evidence/Entities/ent_c' },
  source: { source_id: 'src_1', name: 'El Mundo', url: 'Archivo El Mundo', ref: null, evidence_href: '/evidence/Sources/src_1' },
  report_status: 'HELD',
  report: { report_id: 'RPT-PRUAP-0159', case_id: 'PRUAP-0159',
            evidence_ids: { entity: 'evo:entities:ent_c', observation: 'evo:observations:obs_c', source: 'evo:sources:src_1' },
            unresolved: [{ kind: 'RECORD_GAP', detail: 'date recorded only to the year' }],
            receipt: { run_id: 'run_abc', report_sha256: 'f'.repeat(64), snapshot_id: `sha256:${'0'.repeat(64)}`, created_at: '2026-10-03T00:00:00Z' } },
  unresolved: [{ kind: 'RECORD_GAP', detail: 'date recorded only to the year' }],
  findings: [], hypotheses: [], contradictions: [], queue: [], episodes: [],
  adjudications: [
    { record_id: 'ADJ-C-1', status: 'CANDIDATE', origin: 'COMPUTED', reviewed: false,
      attributes: { signals: { date_relation: 'COMPATIBLE_PRECISION', place_basis: 'MUNICIPALITY', narrative_similarity: 0.2, same_source: false } },
      other_case: { case_id: 'PRUAP-0164', held: true, date: '1979-11-30', temporal_precision: 'DATE_ONLY', place: { municipality: 'Aguadilla' }, category: 'UAP' } },
    { record_id: 'ADJ-C-2', status: 'CANDIDATE', origin: 'COMPUTED', reviewed: false, attributes: {},
      other_case: { case_id: 'PRUAP-0404', held: false } },
  ],
};

function renderAt(url, element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/research/case/:caseId" element={<CaseReconstruction />} />
          <Route path="/ovnis" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Case reconstruction', () => {
  beforeEach(() => {
    federation.research.caseRecord.mockReset();
    federation.research.records.mockReset();
  });

  it('shows the case as recorded with its report, receipt and unreviewed candidates', async () => {
    federation.research.caseRecord.mockResolvedValue(CASE);
    renderAt('/research/case/PRUAP-0159');
    expect(await screen.findByText('Lights seen over the water.')).toBeInTheDocument();
    expect(federation.research.caseRecord).toHaveBeenCalledWith('PRUAP-0159');
    expect(document.querySelector('[data-case-record] [data-temporal-precision]')).toHaveTextContent('year only');
    expect(screen.getByText('date recorded only to the year')).toBeInTheDocument();
    expect(screen.getByText('run_abc')).toBeInTheDocument();
    expect(screen.getAllByText(/computed, not reviewed/)).toHaveLength(2);
    expect(screen.getByText(/not held by this Hub/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Open source/ })).not.toBeInTheDocument(); // a name, not a URL
    expect(screen.getByText('No findings name this case.')).toBeInTheDocument();
  });

  it('says when the Hub does not hold the case report', async () => {
    federation.research.caseRecord.mockResolvedValue({ ...CASE, report_status: 'NOT_HELD', report: null, unresolved: [] });
    renderAt('/research/case/PRUAP-0159');
    expect(await screen.findByText(/does not hold the report for this case/)).toBeInTheDocument();
  });

  it('reports a case the Hub does not hold', async () => {
    federation.research.caseRecord.mockImplementation(() => Promise.reject(new Error('404 Not Found')));
    renderAt('/research/case/NOPE');
    expect(await screen.findByRole('alert')).toHaveTextContent('This case cannot be shown');
  });

  it('has no axe violations', async () => {
    federation.research.caseRecord.mockResolvedValue(CASE);
    const { container } = renderAt('/research/case/PRUAP-0159');
    await screen.findByText('Lights seen over the water.');
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('OVNIS reports workspace and show log', () => {
  beforeEach(() => federation.research.records.mockReset());

  it('lists case reports and links each to its case', async () => {
    federation.research.records.mockResolvedValue({
      kind: 'reports', kind_status: 'RECORDED', total: 1, matched: 1, next_cursor: null,
      records: [{ record_id: 'RPT-PRUAP-0006', case_ids: ['PRUAP-0006'], attributes: { report: {
        case_id: 'PRUAP-0006', case: { date_local: '1943-06', temporal_precision: 'MONTH_YEAR', location_name: 'Offshore', object_type: 'USO' },
        unresolved: [{ kind: 'RECORD_GAP', detail: 'municipality not recorded' }], linked: { manifestation_candidates: [] },
        receipt: { report_sha256: 'abcdef1234567890' } } } }],
    });
    renderAt('/ovnis', <ReportsWorkspace />);
    expect(await screen.findByRole('link', { name: 'Open report' })).toHaveAttribute('href', '/research/case/PRUAP-0006');
    expect(screen.getByText(/1 unresolved item/)).toBeInTheDocument();
    expect(federation.research.records).toHaveBeenCalledWith('reports', expect.anything());
  });

  it('says the show log is empty until a curator records an episode', async () => {
    federation.research.records.mockResolvedValue({ kind: 'episodes', kind_status: 'NONE_RECORDED', total: 0, matched: 0, records: [], next_cursor: null });
    renderAt('/ovnis', <ShowLog />);
    expect(await screen.findByText(/No media episodes are recorded/)).toBeInTheDocument();
  });

  it('shows a recorded episode with its primary source', async () => {
    federation.research.records.mockResolvedValue({
      kind: 'episodes', kind_status: 'RECORDED', total: 1, matched: 1, next_cursor: null,
      records: [{ record_id: 'EP-1', case_ids: ['PRUAP-0006'], attributes: { series: 'Example Series', season: 1, episode: 2,
        air_date: '2020-05', title: 'Lights over the bay', primary_source_url: 'https://example.org/ep2' } }],
    });
    renderAt('/ovnis', <ShowLog />);
    expect(await screen.findByText('Lights over the bay')).toBeInTheDocument();
    expect(screen.getByText(/S1 E2/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Primary source' })).toHaveAttribute('href', 'https://example.org/ep2');
  });
});

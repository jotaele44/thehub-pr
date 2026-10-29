import React, { forwardRef, useImperativeHandle } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import { constellationPayload } from '@/test/constellationPayload';
import { DWELL_MS, FLIGHT_MS } from '@/lib/constellation/camera';
import FederationConstellation from './FederationConstellation';

vi.mock('@/api/federationClient', () => ({ federation: { constellation: { get: vi.fn() } } }));

const canvasCalls = { zoomBy: vi.fn(), fit: vi.fn() };

// jsdom has no 2D canvas; the drawing component is replaced by a stand-in that
// exposes the props the page hands it.
vi.mock('@/components/constellation/ConstellationCanvas', () => ({
  default: forwardRef(function CanvasStandIn(props, handle) {
    useImperativeHandle(handle, () => canvasCalls);
    return (
      <>
        <div role="img" aria-label={props.label} data-lens={props.lens} data-stage-index={props.stageIndex} />
        <button type="button" onClick={() => props.onSelect('thehub.fetch')}>pick fetch on canvas</button>
        <button type="button" onClick={() => props.onUserInteract()}>drag canvas</button>
      </>
    );
  }),
}));

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.search}</output>;
}

function renderAt(url = '/constellation') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/constellation" element={<><FederationConstellation /><Where /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const caption = () => document.querySelector('[data-stage-title]');
const where = () => new URLSearchParams(screen.getByTestId('where').textContent);

describe('FederationConstellation', () => {
  beforeEach(() => {
    federation.constellation.get.mockResolvedValue(constellationPayload);
    canvasCalls.zoomBy.mockClear();
    canvasCalls.fit.mockClear();
  });
  afterEach(() => vi.useRealTimers());

  it('opens on the first stage with its caption, legend and tour playing', async () => {
    const { container } = renderAt();
    await waitFor(() => expect(caption()).toHaveTextContent('SIGNAL INTAKE'));
    const subtitle = within(document.querySelector('[data-stage-caption="signal-intake"]')).getByText('Captura de señales · Centinelas');
    expect(subtitle).toHaveAttribute('lang', 'es');
    expect(screen.getByRole('list', { name: 'Edge legend, code lens' })).toHaveTextContent(/CALL.*HANDOFF.*RESULT/);
    expect(screen.getByRole('button', { name: 'Pause' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('img')).toHaveAccessibleName(/code lens\. Stage 1 of 3: SIGNAL INTAKE, 3 nodes in view/);
    expect(screen.getByRole('region', { name: 'Nodes in this stage' })).toHaveTextContent('poll_all');
    expect(screen.getByText('672')).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('flies to the next stage after the flight and dwell', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderAt();
    await waitFor(() => expect(caption()).toHaveTextContent('SIGNAL INTAKE'));
    await act(async () => { vi.advanceTimersByTime(FLIGHT_MS + DWELL_MS + 10); });
    expect(caption()).toHaveTextContent('HUB AGGREGATE');
    expect(where().get('stage')).toBe('hub-aggregate');
  });

  it('switches lens in place and keeps the URL a deep link', async () => {
    renderAt();
    await waitFor(() => expect(caption()).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Content' }));
    expect(screen.getByRole('button', { name: 'Content' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('list', { name: 'Edge legend, content lens' })).toHaveTextContent(/RECORDS.*CORRELATION.*PROJECTION/);
    expect(screen.getByRole('img')).toHaveAttribute('data-lens', 'content');
    expect(where().get('lens')).toBe('content');
    expect(screen.getByRole('region', { name: 'Nodes in this stage' })).toHaveTextContent('intake drops');
  });

  it('steps and jumps between stages', async () => {
    renderAt();
    await waitFor(() => expect(caption()).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Next stage' }));
    expect(caption()).toHaveTextContent('HUB AGGREGATE');
    fireEvent.click(screen.getByRole('button', { name: 'Stage 3 of 3: THE FEDERATION' }));
    expect(caption()).toHaveTextContent('THE FEDERATION');
    expect(screen.getByRole('button', { name: 'Stage 3 of 3: THE FEDERATION' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Previous stage' }));
    expect(caption()).toHaveTextContent('HUB AGGREGATE');
  });

  it('selecting a node pauses the tour and carries it across lenses', async () => {
    renderAt('/constellation?stage=hub-aggregate');
    await waitFor(() => expect(caption()).toHaveTextContent('HUB AGGREGATE'));
    expect(screen.getByRole('button', { name: 'Play tour' })).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole('region', { name: 'Nodes in this stage' })).getByRole('button', { name: /^aggregate/ }));
    const details = document.querySelector('[data-constellation-details="thehub.aggregate"]');
    expect(details).toHaveTextContent('Unions validated rows.');
    expect(within(details).getByText('CALL')).toBeInTheDocument();
    fireEvent.click(within(details).getByRole('button', { name: 'fetch_all' }));
    expect(document.querySelector('[data-constellation-details="thehub.fetch"]')).toBeInTheDocument();
    fireEvent.click(within(document.querySelector('[data-constellation-details]')).getByRole('button', { name: 'aggregate' }));
    fireEvent.click(within(document.querySelector('[data-constellation-details]')).getByRole('button', { name: /observations/ }));
    expect(screen.getByRole('img')).toHaveAttribute('data-lens', 'content');
    const stream = document.querySelector('[data-constellation-details="content:thehub:stream:observations"]');
    expect(stream).toHaveTextContent('572');
    expect(where().get('node')).toBe('content:thehub:stream:observations');
    fireEvent.click(screen.getByRole('button', { name: 'Code' }));
    expect(document.querySelector('[data-constellation-details="thehub.aggregate"]')).toBeInTheDocument();
  });

  it('shows real sample records with provenance links in the content lens', async () => {
    renderAt('/constellation?lens=content&stage=signal-intake&node=content:centinelas:observations');
    await waitFor(() => expect(document.querySelector('[data-constellation-details]')).toBeInTheDocument());
    const sample = document.querySelector('[data-constellation-sample="obs_004a"]');
    expect(sample).toHaveTextContent('Municipio adjudica contrato del acueducto');
    expect(within(sample).getByRole('link', { name: 'Provenance' })).toHaveAttribute('href', '/evidence/Observations/obs_004a');
    expect(screen.getByText(/scripts\/federation_export.py · OBSERVATION · 100 rows/)).toBeInTheDocument();
  });

  it('labels correlation candidates as synthetic', async () => {
    renderAt('/constellation?lens=content&stage=hub-aggregate&node=content:thehub:correlation:alerts');
    await waitFor(() => expect(document.querySelector('[data-constellation-details]')).toBeInTheDocument());
    expect(screen.getByText(/synthetic CANDIDATE derived by the Hub/)).toBeInTheDocument();
  });

  it('pauses when the viewer takes the camera and selects from the canvas', async () => {
    renderAt();
    await waitFor(() => expect(caption()).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'drag canvas' }));
    expect(screen.getByRole('button', { name: 'Play tour' })).toBeInTheDocument();
    expect(document.querySelector('[data-constellation-mode="explore"]')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'pick fetch on canvas' }));
    expect(document.querySelector('[data-constellation-details="thehub.fetch"]')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close details' }));
    expect(document.querySelector('[data-constellation-stage-card]')).toBeInTheDocument();
  });

  it('drives the tour, lens and camera from the keyboard', async () => {
    renderAt();
    await waitFor(() => expect(caption()).toBeInTheDocument());
    const stage = screen.getByRole('region', { name: /Constellation stage/ });
    fireEvent.keyDown(stage, { key: 'ArrowRight' });
    expect(caption()).toHaveTextContent('HUB AGGREGATE');
    fireEvent.keyDown(stage, { key: 'l' });
    expect(screen.getByRole('img')).toHaveAttribute('data-lens', 'content');
    fireEvent.keyDown(stage, { key: ' ' });
    expect(screen.getByRole('button', { name: 'Play tour' })).toBeInTheDocument();
    fireEvent.keyDown(stage, { key: '+' });
    fireEvent.keyDown(stage, { key: 'f' });
    expect(canvasCalls.zoomBy).toHaveBeenCalledWith(1.25);
    expect(canvasCalls.fit).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
    expect(canvasCalls.zoomBy).toHaveBeenCalledWith(0.8);
  });

  it('says so when the Hub store is empty', async () => {
    federation.constellation.get.mockResolvedValue({ ...constellationPayload, store_status: 'EMPTY' });
    renderAt();
    expect(await screen.findByText(/holds no records yet/)).toBeInTheDocument();
  });

  it('reports an unavailable API', async () => {
    federation.constellation.get.mockRejectedValue(new Error('boom'));
    renderAt();
    expect(await screen.findByRole('alert')).toHaveTextContent('The constellation is unavailable: boom');
  });
});

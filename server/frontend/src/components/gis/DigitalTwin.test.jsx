import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import { elevationAt } from '@/gis/cudem';
import DigitalTwin from './DigitalTwin';

vi.mock('@/api/federationClient', () => ({ federation: { spatial: { features: vi.fn() } } }));
vi.mock('@/gis/cudem', async (importOriginal) => ({ ...(await importOriginal()), elevationAt: vi.fn() }));
const seen = {};
// WebGL is not available in jsdom; the stubs expose what each panel is asked to draw.
vi.mock('@/components/gis/DigitalTwinPerspective', () => ({
  default: (props) => {
    seen.perspective = props;
    return (
      <div data-testid="perspective" data-count={props.features.length} data-selected={props.selectedId || ''}>
        <button type="button" onClick={() => props.onTerrainTiles(['ncei19_n18x25_w066x75_2022v2.tif'])}>terrain tiles loaded</button>
        <button type="button" onClick={() => props.onTerrainError(new Error('HTTP 503'))}>terrain failed</button>
        <button type="button" onClick={() => props.onViewChange({ center: [-66.6, 18.17], zoom: 12, bearing: 0 })}>orbit</button>
      </div>
    );
  },
}));
vi.mock('@/components/gis/PropertyMapCanvas', () => ({
  default: (props) => (
    <div data-testid={props.testId} data-count={props.features.length} data-selected={props.selectedId || ''}
      data-center={props.view.center.join(',')} />
  ),
}));

function feature(id, category, precision, lon, lat, title, props = {}) {
  return {
    type: 'Feature', id, geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { evidence_id: id, title, category, producer: 'p', producers: ['p'], geometry_precision: precision,
      geometry_basis: null, municipality: null, object_type: null, synthetic: false, evidence_href: `/evidence/Entities/${id}`,
      entity_href: null, time_start: null, time_end: null, temporal_state: 'UNKNOWN', ...props },
  };
}
const FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', loaded: 3, matched: 3, truncated: false,
  outside_bbox: 0, excluded_synthetic: 0, undated: 1,
  time_extent: { start: '2001-02-03T00:00:00.000Z', end: '2019-12-31T00:00:00.000Z' },
  features: [
    feature('evo:alerts:a', 'CONTAMINATION', 'REPRESENTATIVE_POINT', -66.1, 18.4, 'Boil water notice',
      { time_start: '2019-10-01T00:00:00.000Z', time_end: '2019-12-31T00:00:00.000Z', temporal_state: 'HISTORICAL' }),
    feature('evo:entities:m', 'mineral_occurrence', 'OBSERVED_POINT', -66.59, 18.17, 'Manganese occurrence'),
    feature('evo:entities:s', 'sensor_site', 'INTERPRETED_POINT', -65.4, 18.1, 'Receiver site',
      { time_start: '2001-02-03T00:00:00.000Z', time_end: '2001-02-03T23:59:59.999Z', temporal_state: 'CURRENT' }),
  ],
  categories: [], precision_counts: {}, coordinates_without_point_precision: {}, not_drawn: [], area_references: [],
};

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.search}</output>;
}

// The panels mount before the records arrive; the controls appear with the data.
const loaded = () => screen.findByRole('button', { name: 'Export GeoJSON' });

function renderTwin(url = '/gis?view=digital-twin') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/gis" element={<><DigitalTwin /><Where /></>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Digital Twin', () => {
  beforeEach(() => {
    federation.spatial.features.mockReset();
    federation.spatial.features.mockResolvedValue(FEATURES);
    elevationAt.mockReset();
    elevationAt.mockResolvedValue({ metres: 1322.7, tile: 'ncei19_n18x25_w066x75_2022v2.tif' });
  });
  afterEach(() => vi.useRealTimers());

  it('lays out four synchronized panels and says why the counters are zero', async () => {
    const { container } = renderTwin();
    await loaded();
    expect(screen.getByTestId('perspective')).toHaveAttribute('data-count', '3');
    expect(['perspective', 'ortho', 'overhead', 'details'].map((id) => container.querySelector(`[data-dt-panel="${id}"]`))).not.toContain(null);
    expect(container.querySelector('[data-dt-findings-status]')).toHaveTextContent('No finding carries geometry: the OVNIS findings ledger records none yet.');
    expect(container.querySelector('[data-dt-live-status]')).toHaveTextContent('No live feed; 1 current (inside a declared validity window)');
    expect(container.querySelector('[data-dt-terrain-status]')).toHaveTextContent('bound (uniform vertical datum)');
    expect(container.querySelector('[data-dt-dem-provenance]')).toHaveTextContent('PRVD02, EPSG:6641');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('moves the time cursor and counts what falls outside the window instead of hiding it silently', async () => {
    const { container } = renderTwin();
    await loaded();
    expect(container.querySelector('[data-dt-counts]')).toHaveTextContent('3 shown · 0 outside the time window · 1 undated');
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: String(Date.parse('2005-01-01T00:00:00Z')) } });
    expect(container.querySelector('[data-dt-counts]')).toHaveTextContent('2 shown · 1 outside the time window · 1 undated');
    expect(screen.getByTestId('digital-twin-ortho')).toHaveAttribute('data-count', '2');
    fireEvent.change(screen.getByLabelText('Window'), { target: { value: 'month' } });
    expect(container.querySelector('[data-dt-counts]')).toHaveTextContent('1 shown · 2 outside the time window · 1 undated');
    fireEvent.click(screen.getByLabelText(/Show undated/));
    expect(screen.getByTestId('perspective')).toHaveAttribute('data-count', '0');
  });

  it('plays through time and stops at the end of the extent', async () => {
    renderTwin();
    await loaded();
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: String(Date.parse('2019-12-01T00:00:00Z')) } });
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByRole('button', { name: 'Play' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByText('2019-12-31')).toBeInTheDocument();
  });

  it('selects across panels and reads the selected record\'s CUDEM elevation with its datum', async () => {
    const { container } = renderTwin();
    await loaded();
    fireEvent.click(container.querySelector('[data-dt-record="evo:entities:m"]'));
    expect(screen.getByTestId('perspective')).toHaveAttribute('data-selected', 'evo:entities:m');
    expect(screen.getByTestId('digital-twin-ortho')).toHaveAttribute('data-selected', 'evo:entities:m');
    expect(screen.getByTestId('digital-twin-overhead')).toHaveAttribute('data-selected', 'evo:entities:m');
    await waitFor(() => expect(container.querySelector('[data-dt-elevation]')).toHaveTextContent('1322.7 m PRVD02 · CUDEM m9525 1/9″'));
    expect(elevationAt).toHaveBeenCalledWith(-66.59, 18.17);
  });

  it('does not report a height outside CUDEM coverage', async () => {
    const outside = { ...FEATURES, features: [feature('evo:entities:far', 'x', 'OBSERVED_POINT', -60, 15, 'Far away')] };
    federation.spatial.features.mockResolvedValue(outside);
    const { container } = renderTwin();
    fireEvent.click(await screen.findByRole('button', { name: /Far away/ }));
    expect(container.querySelector('[data-dt-elevation]')).toHaveTextContent('Outside CUDEM coverage (no height reported).');
    expect(elevationAt).not.toHaveBeenCalled();
  });

  it('shares one camera between panels and lists the CUDEM tiles read', async () => {
    const { container } = renderTwin();
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: 'orbit' }));
    expect(screen.getByTestId('digital-twin-ortho')).toHaveAttribute('data-center', '-66.6,18.17');
    expect(screen.getByTestId('digital-twin-overhead')).toHaveAttribute('data-center', '-66.6,18.17');
    fireEvent.click(screen.getByRole('button', { name: 'terrain tiles loaded' }));
    expect(container.querySelector('[data-dt-terrain-tiles]')).toHaveTextContent('ncei19_n18x25_w066x75_2022v2.tif');
    fireEvent.click(screen.getByRole('button', { name: 'terrain failed' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Terrain tiles failed to load; the surface is flat there: HTTP 503');
  });

  it('maximizes a panel through the URL and restores the grid', async () => {
    const { container } = renderTwin();
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: 'Maximize Ortho / top-down' }));
    expect(screen.getByTestId('where')).toHaveTextContent('view=digital-twin&panel=ortho');
    expect(container.querySelector('[data-dt-panel="perspective"]')).toHaveClass('hidden');
    fireEvent.click(screen.getByRole('button', { name: 'Restore Ortho / top-down' }));
    expect(screen.getByTestId('where')).toHaveTextContent('view=digital-twin');
    expect(container.querySelector('[data-dt-panel="perspective"]')).not.toHaveClass('hidden');
  });

  it('live / current only shows exactly the current records', async () => {
    renderTwin();
    await loaded();
    fireEvent.click(screen.getByLabelText(/Live \/ current only/));
    expect(screen.getByTestId('perspective')).toHaveAttribute('data-count', '1');
  });

  it('exports GeoJSON and USD of exactly what is shown, with provenance', async () => {
    const blobs = [];
    URL.createObjectURL = vi.fn((blob) => { blobs.push(blob); return 'blob:x'; });
    URL.revokeObjectURL = vi.fn();
    renderTwin();
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: 'Export GeoJSON' }));
    fireEvent.click(screen.getByRole('button', { name: 'Export USD' }));
    const geojson = JSON.parse(await blobs[0].text());
    expect(geojson.features).toHaveLength(3);
    expect(geojson.federation_export).toMatchObject({ contract: 'federation-spatial-features-v1', certification: 'NOT_CERTIFIED',
      layers: { terrain: 'noaa-ncei-cudem-pr-ninth-m9525' } });
    const usda = await blobs[1].text();
    expect(usda).toContain('def Points "FederationRecords"');
    expect(usda).toContain('int record_count = 3');
  });

  it('says when the Hub cannot return records', async () => {
    federation.spatial.features.mockRejectedValue(new Error('HTTP 500'));
    renderTwin();
    expect(await screen.findByRole('alert')).toHaveTextContent('The Hub could not return spatial features: HTTP 500');
  });
});

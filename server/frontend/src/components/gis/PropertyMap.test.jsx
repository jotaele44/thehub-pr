import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import PropertyMap from './PropertyMap';

vi.mock('@/api/federationClient', () => ({ federation: { spatial: { features: vi.fn(), intel: vi.fn() } } }));
vi.mock('@/gis/acquisitionFacade', () => ({ acquireOnlineSource: vi.fn() }));
// WebGL is not available in jsdom; the stub exposes what the map is asked to draw.
vi.mock('@/components/gis/PropertyMapCanvas', () => ({
  default: (props) => (
    <div data-testid="canvas" data-features={props.features.length} data-outline={props.outline ? props.outline.features.length : 'none'}>
      <button type="button" onClick={() => props.onPickPoint({ lon: -65.4, lat: 18.1 })}>pick a map point</button>
      <button type="button" onClick={() => props.onSelectFeature('evo:alerts:alrt_c')}>click a map marker</button>
    </div>
  ),
}));

function feature(id, category, producer, precision, lon, lat, title) {
  const [, stream, recordId] = id.split(':');
  const collection = stream === 'alerts' ? 'Alerts' : 'Entities';
  return {
    type: 'Feature', id, geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { evidence_id: id, stream, collection, record_id: recordId, title, category, object_type: null, producer,
      producers: [producer], geometry_precision: precision, geometry_basis: null, municipality: null, synthetic: false,
      evidence_href: `/evidence/${collection}/${recordId}`, entity_href: stream === 'entities' ? `/entity/${recordId}` : null },
  };
}

const FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', bbox_filter: null, include_synthetic: false,
  loaded: 10, matched: 3, truncated: false, outside_bbox: 0, excluded_synthetic: 1,
  features: [
    feature('evo:alerts:alrt_c', 'CONTAMINATION', 'aguayluz-pr', 'REPRESENTATIVE_POINT', -66.1, 18.4, 'Boil water notice'),
    feature('evo:entities:ent_m', 'mineral_occurrence', 'spiderweb-pr', 'OBSERVED_POINT', -66.5, 18.2, 'Manganese occurrence'),
    feature('evo:entities:ent_s', 'sensor_site', 'skywatcher-pr', 'INTERPRETED_POINT', -65.4, 18.1, 'Receiver site'),
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

const VIEQUES = { type: 'Feature', properties: { NAME: 'Vieques Municipio', BASENAME: 'Vieques' },
  geometry: { type: 'Polygon', coordinates: [[[-65.6, 18.05], [-65.2, 18.05], [-65.2, 18.2], [-65.6, 18.2], [-65.6, 18.05]]] } };
const BOUNDARY_LAYER = { geojson: { type: 'FeatureCollection', features: [VIEQUES] }, snapshotSha256: 'c'.repeat(64),
  queryReceiptSha256: 'd'.repeat(64), certification: { status: 'PASS' }, manifest: { featureCount: 1 },
  sourceManifest: { retrievalUtc: '2026-10-03T00:00:00Z' } };

function intel({ lat, lon, radiusM, municipality }) {
  return Promise.resolve({
    contract: 'federation-spatial-features-v1', point: { lat, lon }, radius_m: radiusM, nearby_total: 1,
    nearby: [{ ...FEATURES.features[0].properties, distance_m: 0, distance_basis: 'distance to a representative point, not to the feature itself' }],
    nearby_truncated: false, category_counts: { CONTAMINATION: 1 }, municipality: municipality ?? null,
    municipality_area_references: municipality === 'Vieques' ? [FEATURES.area_references[1]] : [],
    distance_basis: 'great-circle distance to each mapped point',
  });
}

function renderMap() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><PropertyMap initialView={{ center: [-66.4, 18.22], zoom: 9 }} /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Property Map', () => {
  beforeEach(() => {
    federation.spatial.features.mockReset();
    federation.spatial.intel.mockReset();
    acquireOnlineSource.mockReset();
    federation.spatial.features.mockResolvedValue(FEATURES);
    federation.spatial.intel.mockImplementation(intel);
  });

  it('accounts for every loaded record and legends precision and category from the data', async () => {
    const { container } = renderMap();
    expect(await screen.findByText(/3 of 10 loaded records drawn · 6 not drawn · 1 synthetic excluded/)).toBeInTheDocument();
    const precision = container.querySelector('[data-uncertainty-legend]');
    expect(within(precision).getByText('Representative point')).toBeInTheDocument();
    expect(precision.querySelector('[data-unplaced-coordinates]')).toHaveTextContent('5 ovnis-pr rows carry coordinates without a declared point precision');
    const categories = container.querySelector('[data-category-legend]');
    expect(within(categories).getAllByRole('checkbox').map((box) => box.parentElement.textContent)).toEqual([
      'CONTAMINATION1 · aguayluz-pr', 'mineral_occurrence1 · spiderweb-pr', 'sensor_site1 · skywatcher-pr']);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('hides a category from the map and the record list', async () => {
    renderMap();
    await screen.findByText('Boil water notice');
    fireEvent.click(screen.getByRole('checkbox', { name: /CONTAMINATION/ }));
    expect(screen.queryByText('Boil water notice')).toBeNull();
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-features', '2');
  });

  it('outlines only exact municipio names and lists regions as recorded', async () => {
    const { container } = renderMap();
    const panel = await waitFor(() => {
      const node = container.querySelector('[data-area-references]');
      expect(node).not.toBeNull();
      return node;
    });
    expect(panel.querySelector('[data-area-reference-counter]')).toHaveTextContent('2 of 6 record no municipality and are not mapped; 4 record a place value.');
    expect(panel.querySelector('[data-boundary-needed]')).toHaveTextContent('Map outlines need the municipio boundary layer.');
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-outline', 'none');

    acquireOnlineSource.mockResolvedValue(BOUNDARY_LAYER);
    fireEvent.click(within(panel).getByRole('button', { name: 'Load municipio boundaries (TIGERweb 2025)' }));
    await waitFor(() => expect(panel.querySelector('[data-outlined-municipio="Vieques"]')).toHaveTextContent('Vieques: 2 (recorded as vieques)'));
    expect(acquireOnlineSource).toHaveBeenCalledWith('census-tigerweb-pr-municipios-2025');
    expect(panel.querySelector('[data-unmatched-values]')).toHaveTextContent('“southwest”: 2');
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-outline', '1');
    expect(container.querySelector('[data-boundary-provenance]')).toHaveTextContent(`Snapshot SHA-256 ${'c'.repeat(64)}`);

    fireEvent.change(within(panel).getByLabelText('Object type (as recorded)'), { target: { value: 'Mutilation' } });
    expect(panel.querySelector('[data-area-reference-counter]')).toHaveTextContent('1 of 2 record no municipality and are not mapped; 1 record a place value.');
    expect(panel.querySelector('[data-outlined-municipio="Vieques"]')).toHaveTextContent('Vieques: 1');
    expect(panel.querySelector('[data-unmatched-values]')).toBeNull();
  });

  it('a boundary layer that fails to load is reported and nothing is outlined', async () => {
    renderMap();
    acquireOnlineSource.mockRejectedValue(new Error('HTTP 502'));
    fireEvent.click(await screen.findByRole('button', { name: 'Load municipio boundaries (TIGERweb 2025)' }));
    expect(await screen.findByText('Boundary layer unavailable: HTTP 502')).toBeInTheDocument();
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-outline', 'none');
  });

  it('selecting a record shows its declared precision and runs Location Intel at its point', async () => {
    const { container } = renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /Boil water notice/ }));
    const selected = container.querySelector('[data-selected-record="evo:alerts:alrt_c"]');
    expect(selected.querySelector('[data-selected-precision]')).toHaveTextContent('Representative point');
    expect(within(selected).getByRole('link', { name: 'Provenance' })).toHaveAttribute('href', '/evidence/Alerts/alrt_c');
    await waitFor(() => expect(federation.spatial.intel).toHaveBeenCalledWith(expect.objectContaining({ lat: 18.4, lon: -66.1, radiusM: 1000 })));
    expect(await screen.findByText(/not to the feature itself/)).toBeInTheDocument();
    expect(container.querySelector('[data-intel-municipio]')).toHaveTextContent('Not determined: the municipio boundary layer is not loaded.');
    expect(screen.getByRole('button', { name: /Boil water notice/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('a map point inside a loaded municipio names it and lists records that name it', async () => {
    acquireOnlineSource.mockResolvedValue(BOUNDARY_LAYER);
    const { container } = renderMap();
    fireEvent.click(await screen.findByRole('button', { name: 'Load municipio boundaries (TIGERweb 2025)' }));
    await screen.findByText(/outlined on 1 municipio/);
    fireEvent.click(screen.getByRole('button', { name: 'pick a map point' }));
    await waitFor(() => expect(container.querySelector('[data-intel-municipio]')).toHaveTextContent('Vieques (TIGERweb municipios 2025, point in polygon)'));
    await waitFor(() => expect(federation.spatial.intel).toHaveBeenCalledWith(expect.objectContaining({ municipality: 'Vieques' })));
    expect(await screen.findByText(/Records that name Vieques/)).toBeInTheDocument();
    expect(container.querySelector('[data-intel-area]')).toHaveTextContent('776 acres');
  });

  it('refuses malformed coordinates and AOIs, and filters by a valid AOI', async () => {
    const { container } = renderMap();
    await screen.findByText('Boil water notice');
    fireEvent.change(screen.getByLabelText('Location (lat, lon)'), { target: { value: 'north coast' } });
    fireEvent.click(screen.getByRole('button', { name: 'Show intel' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a latitude and longitude');
    fireEvent.change(screen.getByLabelText('AOI (minLon,minLat,maxLon,maxLat)'), { target: { value: '-66.3,18.1,-66.6,18.3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(screen.getAllByRole('alert').map((node) => node.textContent)).toContain('The AOI must be minLon,minLat,maxLon,maxLat within WGS84 bounds.');
    fireEvent.change(screen.getByLabelText('AOI (minLon,minLat,maxLon,maxLat)'), { target: { value: '-66.6,18.1,-66.3,18.3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(federation.spatial.features).toHaveBeenLastCalledWith({ includeSynthetic: false, bbox: [-66.6, 18.1, -66.3, 18.3] }));
    expect(container.querySelector('[data-aoi-area]')).toHaveTextContent('acres');
  });

  it('says when the Hub cannot return features', async () => {
    federation.spatial.features.mockRejectedValue(new Error('HTTP 500'));
    renderMap();
    expect(await screen.findByRole('alert')).toHaveTextContent('The Hub could not return spatial features: HTTP 500');
  });
});

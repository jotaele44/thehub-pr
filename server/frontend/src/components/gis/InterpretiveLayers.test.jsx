import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import { elevationAt } from '@/gis/cudem';
import InterpretiveLayers from './InterpretiveLayers';

vi.mock('@/api/federationClient', () => ({ federation: { spatial: { features: vi.fn() } } }));
vi.mock('@/gis/acquisitionFacade', () => ({ acquireOnlineSource: vi.fn() }));
vi.mock('@/gis/cudem', async (importOriginal) => ({ ...(await importOriginal()), elevationAt: vi.fn() }));
const seen = {};
// MapLibre needs WebGL, which jsdom lacks; the stub exposes what the map is asked to draw.
vi.mock('@/components/gis/PropertyMapCanvas', () => ({
  default: (props) => {
    seen.canvas = props;
    return (
      <div data-testid="canvas" data-features={props.features.length} data-outline={props.outline?.features?.length ?? 0}>
        <button type="button" onClick={() => props.onPickPoint({ lon: -66, lat: 18 })}>pick west</button>
        <button type="button" onClick={() => props.onPickPoint({ lon: -65, lat: 18 })}>pick east</button>
      </div>
    );
  },
}));

function feature(id, category, props = {}) {
  return {
    type: 'Feature', id, geometry: { type: 'Point', coordinates: [-66.59, 18.17] },
    properties: {
      evidence_id: id, title: id, category, producer: 'spiderweb-pr', geometry_precision: 'OBSERVED_POINT',
      declared_epistemic_class: 'CURATED', evidence_href: `/evidence/Entities/${id}`, ...props,
    },
  };
}
const FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', loaded: 3, matched: 3, truncated: false,
  features: [feature('evo:entities:m', 'mineral_occurrence'), feature('evo:entities:s', 'sensor_site')],
  categories: [], not_drawn: [], area_references: [], precision_counts: {}, coordinates_without_point_precision: {},
  store: { kind: 'bounded-sample', cap_per_stream: 400, streams: { entities: { sampled: 825, actual: 48224 } } },
};
const square = (west, south, east, north) => ({
  type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
});
const LAYER = {
  geojson: { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { OBJECTID: 1 }, geometry: square(-65.8, 17.9, -65.7, 18.1) }] },
  snapshotSha256: 'a'.repeat(64), queryReceiptSha256: 'b'.repeat(64),
  certification: { status: 'PROVISIONAL_PROVIDER_RUNTIME' }, sourceManifest: { retrievalUtc: '2026-10-07T10:00:00Z' },
  manifest: { featureCount: 1 },
};

function renderView(data = FEATURES) {
  federation.spatial.features.mockResolvedValue(data);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><InterpretiveLayers /></QueryClientProvider>);
}
const group = (container, id) => container.querySelector(`[data-group="${id}"]`);
const loaded = () => screen.findByTestId('canvas');

describe('Subsurface and interpretive layers', () => {
  beforeEach(() => {
    federation.spatial.features.mockReset();
    acquireOnlineSource.mockReset();
    elevationAt.mockReset();
  });

  it('keeps documented and modelled layers apart, and says the modelled group is empty and why', async () => {
    const { container } = renderView();
    await loaded();
    const modelled = group(container, 'modelled');
    expect(modelled).toHaveTextContent('MODELLED — not observed geometry');
    expect(modelled.querySelector('[data-modelled-count]')).toHaveTextContent('0');
    expect(modelled).toHaveTextContent('No producer exports a modelled or interpretive layer');
    expect(modelled).toHaveTextContent('test fixtures and are not shown');
    const documented = group(container, 'documented');
    expect(documented).toHaveTextContent('Sumideros');
    expect(documented).toHaveTextContent('not subsurface geometry');
    expect(documented.querySelector('[data-hub-documented]')).toHaveTextContent('1 Hub-held');
    // The Hub-held counts come from a sampled store, and the view says so.
    expect(container.querySelector('[data-store-basis]')).toHaveTextContent('bounded sample (at most 400 records per stream): entities 825 of 48224');
    // Documented swatch solid, modelled swatch hatched: not the same look.
    expect(documented.querySelector('[data-swatch]')).toHaveAttribute('data-swatch', 'solid');
    expect(modelled.querySelector('[data-swatch]')).toHaveAttribute('data-swatch', 'hatched');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('shows the provider failure verbatim instead of an empty map', async () => {
    acquireOnlineSource.mockRejectedValue(new Error('remote fetch failed 502 Bad Gateway for https://sige.pr.gov/x'));
    const { container } = renderView();
    await loaded();
    fireEvent.click(within(container.querySelector('[data-layer="pr-sige-sumideros"]')).getByRole('button', { name: /Load/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('remote fetch failed 502 Bad Gateway');
    expect(seen.canvas.outline.features).toHaveLength(0);
  });

  it('loads a documented layer through the registry and shows its provenance', async () => {
    acquireOnlineSource.mockResolvedValue(LAYER);
    const { container } = renderView();
    await loaded();
    fireEvent.click(within(container.querySelector('[data-layer="pr-sige-sumideros"]')).getByRole('button', { name: /Load/ }));
    await waitFor(() => expect(seen.canvas.outline.features).toHaveLength(1));
    expect(acquireOnlineSource).toHaveBeenCalledWith('pr-sige-sumideros');
    expect(seen.canvas.outline.features[0].properties.layer).toBe('pr-sige-sumideros');
    const row = container.querySelector('[data-layer="pr-sige-sumideros"]');
    expect(row).toHaveTextContent('1 feature');
    expect(row).toHaveTextContent('PROVISIONAL_PROVIDER_RUNTIME');
    expect(row).toHaveTextContent('a'.repeat(12));
    // Hiding a layer removes it from the map without discarding it.
    fireEvent.click(within(row).getByRole('checkbox'));
    await waitFor(() => expect(seen.canvas.outline.features).toHaveLength(0));
  });

  it('draws a record the producer declared INTERPRETIVE only in the modelled group', async () => {
    const data = {
      ...FEATURES,
      features: [...FEATURES.features, feature('evo:entities:model', 'mineral_occurrence', {
        title: 'Void model', declared_epistemic_class: 'INTERPRETIVE', geometry_precision: 'INTERPRETED_POINT',
      })],
    };
    const { container } = renderView(data);
    await loaded();
    expect(group(container, 'modelled').querySelector('[data-modelled-count]')).toHaveTextContent('1');
    expect(group(container, 'modelled')).toHaveTextContent('Void model');
    expect(group(container, 'documented')).not.toHaveTextContent('Void model');
    const byGroup = Object.fromEntries(seen.canvas.features.map((item) => [item.id, item.properties.group]));
    expect(byGroup).toEqual({ 'evo:entities:m': 'DOCUMENTED', 'evo:entities:model': 'MODELLED' });
  });

  it('reads a terrain profile with its datum, keeps no-data samples as gaps and says nothing is drawn below the surface', async () => {
    elevationAt.mockImplementation(async (lon) => (lon < -65.5 ? { metres: 50 + (lon + 66) * 100, tile: 'ncei19_n18x00_w066x00_2022v2.tif' } : null));
    acquireOnlineSource.mockResolvedValue(LAYER);
    const urls = [];
    URL.createObjectURL = vi.fn((blob) => { urls.push(blob); return 'blob:x'; });
    URL.revokeObjectURL = vi.fn();
    const { container } = renderView();
    await loaded();
    fireEvent.click(within(container.querySelector('[data-layer="pr-sige-sumideros"]')).getByRole('button', { name: /Load/ }));
    await waitFor(() => expect(seen.canvas.outline.features).toHaveLength(1));

    fireEvent.change(screen.getByLabelText('Start (lat, lon)'), { target: { value: '18.0, -66.0' } });
    fireEvent.change(screen.getByLabelText('End (lat, lon)'), { target: { value: '18.0, -65.0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Draw profile' }));
    await waitFor(() => expect(container.querySelector('[data-profile-stats]')).toBeTruthy());

    const stats = container.querySelector('[data-profile-stats]').textContent;
    const [, samples, withHeight, without] = /(\d+) samples · (\d+) with a CUDEM height · (\d+) without/.exec(stats).map(Number);
    expect(samples).toBe(100);
    expect(withHeight + without).toBe(100);
    expect(without).toBeGreaterThan(0); // the sea: gaps, never zeros
    expect(container.querySelector('[data-profile-datum]')).toHaveTextContent('PRVD02');
    expect(container.querySelector('svg[data-profile-chart] path').getAttribute('d')).toMatch(/^M/);
    expect(container.querySelector('[data-profile-subsurface]')).toHaveTextContent('No subsurface model supplied');
    expect(container.querySelector('[data-profile-crossings]')).toHaveTextContent('Sumideros');
    expect(seen.canvas.profile.features[0].geometry.type).toBe('LineString');

    fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }));
    const csv = await urls[0].text();
    expect(csv.split('\n')[0]).toBe('distance_km,longitude,latitude,height_m_PRVD02');
    expect(csv.trim().split('\n')).toHaveLength(101);
    // No-data rows have an empty height, not 0.
    expect(csv.trim().split('\n').some((line) => /,$/.test(line))).toBe(true);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('draws no profile where CUDEM has no value, instead of a flat zero line', async () => {
    elevationAt.mockResolvedValue(null);
    const { container } = renderView();
    await loaded();
    fireEvent.change(screen.getByLabelText('Start (lat, lon)'), { target: { value: '19.5, -60' } });
    fireEvent.change(screen.getByLabelText('End (lat, lon)'), { target: { value: '19.6, -60' } });
    fireEvent.click(screen.getByRole('button', { name: 'Draw profile' }));
    expect(await screen.findByText(/CUDEM has no value along this line/)).toBeInTheDocument();
    expect(container.querySelector('svg[data-profile-chart]')).toBeNull();
  });

  it('refuses coordinates it cannot read, and fills the endpoints from two map clicks', async () => {
    elevationAt.mockResolvedValue({ metres: 10, tile: 't' });
    renderView();
    await loaded();
    fireEvent.change(screen.getByLabelText('Start (lat, lon)'), { target: { value: 'north-ish' } });
    fireEvent.change(screen.getByLabelText('End (lat, lon)'), { target: { value: '18.0, -65.0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Draw profile' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Start is not a "lat, lon" pair');
    expect(elevationAt).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'pick west' }));
    fireEvent.click(screen.getByRole('button', { name: 'pick east' }));
    expect(screen.getByLabelText('Start (lat, lon)')).toHaveValue('18.00000, -66.00000');
    expect(screen.getByLabelText('End (lat, lon)')).toHaveValue('18.00000, -65.00000');
  });

  it('says when the Hub cannot return records', async () => {
    federation.spatial.features.mockRejectedValue(new Error('HTTP 500'));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><InterpretiveLayers /></QueryClientProvider>);
    expect(await screen.findByRole('alert')).toHaveTextContent('The Hub could not return spatial features: HTTP 500');
  });
});

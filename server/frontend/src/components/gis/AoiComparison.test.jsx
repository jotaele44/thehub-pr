import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import AoiComparison from './AoiComparison';

vi.mock('@/api/federationClient', () => ({ federation: { spatial: { features: vi.fn() } } }));
vi.mock('@/gis/acquisitionFacade', () => ({ acquireOnlineSource: vi.fn() }));
const seen = {};
// MapLibre needs WebGL, which jsdom lacks; the stub exposes what the map is asked to draw.
vi.mock('@/components/gis/PropertyMapCanvas', () => ({
  default: (props) => {
    seen.canvas = props;
    return <div data-testid="canvas" data-features={props.features.length} data-outline={props.outline?.features?.length ?? 0} />;
  },
}));

const square = (west, south, east, north) => ({
  type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
});
function feature(id, lon, lat, precision = 'OBSERVED_POINT', category = 'utility_asset') {
  return {
    type: 'Feature', id, geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { evidence_id: id, title: id, category, stream: 'entities', producer: 'aguayluz-pr', geometry_precision: precision },
  };
}
// 6 records in the study box, 2 in the control box, 1 stand-in in the study box, 1 outside both.
const FEATURES = {
  contract: 'federation-spatial-features-v1', type: 'FeatureCollection', loaded: 10, matched: 10, truncated: false,
  features: [
    ...Array.from({ length: 6 }, (_, i) => feature(`s${i}`, -0.9 + i * 0.1, 0.5)),
    feature('stand-in', -0.5, 0.6, 'REPRESENTATIVE_POINT'),
    feature('c0', 1.5, 0.5), feature('c1', 2.5, 0.5), feature('far', 9, 9),
  ],
  categories: [], not_drawn: [], area_references: [], precision_counts: {}, coordinates_without_point_precision: {},
  store: { kind: 'bounded-sample', cap_per_stream: 400, streams: { entities: { sampled: 10, actual: 48224 } } },
};
const BOUNDARIES = {
  geojson: {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { NAME: 'Vieques Municipio', BASENAME: 'Vieques' }, geometry: square(-1, 0, 0, 1) },
      { type: 'Feature', properties: { NAME: 'Culebra Municipio', BASENAME: 'Culebra' }, geometry: square(1, 0, 3, 1) },
    ],
  },
};

function renderView(data = FEATURES) {
  federation.spatial.features.mockResolvedValue(data);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AoiComparison /></QueryClientProvider>);
}
const loaded = () => screen.findByTestId('canvas');
const study = () => screen.getByLabelText('Study AOI bounding box');
const control = () => screen.getByLabelText('Control 1 bounding box');

describe('AOI comparison with negative controls', () => {
  beforeEach(() => {
    federation.spatial.features.mockReset();
    acquireOnlineSource.mockReset();
  });

  it('states up front that the store is a sample and that a result is not a finding', async () => {
    const { container } = renderView();
    await loaded();
    expect(container.querySelector('[data-store-basis]')).toHaveTextContent('The Hub store is a bounded sample (at most 400 records per stream): entities 10 of 48224.');
    expect(container.querySelector('[data-store-basis]')).toHaveTextContent('not Puerto Rico');
    expect(screen.getByText(/says nothing about why/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('compares a study box with a control box per category, with densities, ratio, interval and exact p', async () => {
    const { container } = renderView();
    await loaded();
    fireEvent.change(study(), { target: { value: '-1,0,0,1' } });
    fireEvent.change(control(), { target: { value: '1,0,3,1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(await screen.findByText('BACKGROUND COMPARISON — not a finding')).toBeInTheDocument();
    const row = container.querySelector('[data-comparison-row="aguayluz-pr|entities|utility_asset"]');
    expect(row.querySelector('[data-study-count]')).toHaveTextContent('6');
    expect(row.querySelector('[data-study-stand-ins]')).toHaveTextContent('1 stand-in');
    expect(row.querySelector('[data-control-count]')).toHaveTextContent('2');
    expect(row.querySelector('[data-ratio]')).toHaveTextContent(/^\d+\.\d+ \(95% CI \d+\.\d+–\d+\.\d+\)$/);
    expect(row.querySelector('[data-p]')).toHaveTextContent(/^\d\.\d{3}$/);
    expect(container.querySelector('[data-multiplicity]')).toHaveTextContent('1 comparison was tested; p-values are not adjusted for multiple comparisons.');
    expect(container.querySelector('[data-outside]')).toHaveTextContent('1 record is outside every AOI');
    // Both boxes are drawn for the reader to check, coloured by role.
    expect(seen.canvas.outline.features.map((item) => item.properties.role)).toEqual(['study', 'control']);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('refuses a control that overlaps the study area, and a box it cannot read, with the reason', async () => {
    renderView();
    await loaded();
    fireEvent.change(study(), { target: { value: '-1,0,0,1' } });
    fireEvent.change(control(), { target: { value: '-0.5,0,0.5,1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('overlaps the study AOI');
    fireEvent.change(control(), { target: { value: 'around the corner' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Control 1: The AOI must be minLon,minLat,maxLon,maxLat within WGS84 bounds.'));
    expect(screen.queryByText('BACKGROUND COMPARISON — not a finding')).toBeNull();
  });

  it('reports too few records instead of a ratio', async () => {
    const { container } = renderView({ ...FEATURES, features: [feature('a', -0.5, 0.5), feature('b', 1.5, 0.5)] });
    await loaded();
    fireEvent.change(study(), { target: { value: '-1,0,0,1' } });
    fireEvent.change(control(), { target: { value: '1,0,3,1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    await screen.findByText('BACKGROUND COMPARISON — not a finding');
    expect(container.querySelector('[data-ratio]')).toHaveTextContent('too few records to compare (fewer than 5 combined)');
    expect(container.querySelector('[data-p]')).toHaveTextContent('—');
  });

  it('builds AOIs from municipios by name once the boundary layer is loaded, and adds more controls', async () => {
    acquireOnlineSource.mockResolvedValue(BOUNDARIES);
    const { container } = renderView();
    await loaded();
    expect(screen.getByLabelText('Study AOI kind')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Study AOI kind'), { target: { value: 'municipio' } });
    expect(screen.getByLabelText('Study AOI municipio')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Load municipio boundaries (TIGERweb 2025)' }));
    await waitFor(() => expect(screen.getByLabelText('Study AOI municipio')).not.toBeDisabled());
    expect(acquireOnlineSource).toHaveBeenCalledWith('census-tigerweb-pr-municipios-2025');
    fireEvent.change(screen.getByLabelText('Study AOI municipio'), { target: { value: 'Vieques' } });
    fireEvent.change(screen.getByLabelText('Control 1 kind'), { target: { value: 'municipio' } });
    fireEvent.change(screen.getByLabelText('Control 1 municipio'), { target: { value: 'Culebra' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add control AOI' }));
    expect(screen.getByLabelText('Control 2 bounding box')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove Control 2' }));
    expect(screen.queryByLabelText('Control 2 bounding box')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    await screen.findByText('BACKGROUND COMPARISON — not a finding');
    const aois = container.querySelector('[data-aoi-summary]');
    expect(aois).toHaveTextContent('Vieques');
    expect(aois).toHaveTextContent('Culebra');
    expect(aois).toHaveTextContent('TIGERweb municipios 2025');
    expect(aois).toHaveTextContent('spherical polygon area');
  });

  it('downloads a receipt naming the method, the areas and the sampled store', async () => {
    const blobs = [];
    URL.createObjectURL = vi.fn((blob) => { blobs.push(blob); return 'blob:x'; });
    URL.revokeObjectURL = vi.fn();
    renderView();
    await loaded();
    fireEvent.change(study(), { target: { value: '-1,0,0,1' } });
    fireEvent.change(control(), { target: { value: '1,0,3,1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare' }));
    await screen.findByText('BACKGROUND COMPARISON — not a finding');
    fireEvent.click(screen.getByRole('button', { name: 'Download receipt (JSON)' }));
    const receipt = JSON.parse(await blobs[0].text());
    expect(receipt).toMatchObject({ contract: 'aoi-comparison-v1', certification: 'NOT_CERTIFIED', label: 'BACKGROUND COMPARISON — not a finding' });
    expect(receipt.store.sample).toBe(true);
    expect(receipt.method.synthetic_records).toBe('excluded');
    expect(receipt.rows[0]).toMatchObject({ category: 'utility_asset', study_count: 6, control_count: 2, study_membership_not_determined: 1 });
  });

  it('says when the Hub cannot return records', async () => {
    federation.spatial.features.mockRejectedValue(new Error('HTTP 500'));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><AoiComparison /></QueryClientProvider>);
    expect(await screen.findByRole('alert')).toHaveTextContent('The Hub could not return spatial features: HTTP 500');
    expect(within(document.body).queryByRole('button', { name: 'Compare' })).toBeNull();
  });
});

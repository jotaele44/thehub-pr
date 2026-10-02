import { describe, expect, it } from 'vitest';
import { entityHref, mapViewHref, parseCoordinateQuery, parseMapView, searchHref, validMapView } from './deepLinks';
import { initialMapState } from '@/gis/deepLinkView';
import { createCanonicalMapState } from '@/gis/contracts';

const DEFAULT = createCanonicalMapState({ mode: '2d', view: { center: { lon: -66.4, lat: 18.22 }, groundResolutionM: 1000 } });

describe('deep links', () => {
  it('parses a valid map view and rejects out-of-range or malformed values', () => {
    expect(parseMapView(new URLSearchParams('lat=18.2&lon=-66.5&z=12'))).toEqual({ lat: 18.2, lon: -66.5, z: 12 });
    expect(parseMapView(new URLSearchParams('lat=18.2&lon=-66.5'))).toEqual({ lat: 18.2, lon: -66.5, z: null });
    expect(parseMapView(new URLSearchParams(''))).toBeUndefined();
    for (const qs of ['lat=91&lon=0', 'lat=18&lon=-181', 'lat=abc&lon=1', 'lat=18', 'lat=18&lon=-66&z=40', 'lat=18&lon=-66&z=x']) {
      expect(parseMapView(new URLSearchParams(qs))).toBeNull();
    }
    expect(validMapView({ lat: '', lon: '1' })).toBeNull();
  });

  it('parses typed coordinates, lat first, with an optional zoom', () => {
    expect(parseCoordinateQuery('18.2, -66.5')).toEqual({ lat: 18.2, lon: -66.5, z: null });
    expect(parseCoordinateQuery('18.2 -66.5 z12')).toEqual({ lat: 18.2, lon: -66.5, z: 12 });
    expect(parseCoordinateQuery('laguna cartagena')).toBeNull();
    expect(parseCoordinateQuery('95, 10')).toBeNull();
  });

  it('builds encoded links', () => {
    expect(mapViewHref({ lat: 18.2, lon: -66.5, z: 12 })).toBe('/gis?lat=18.2&lon=-66.5&z=12');
    expect(mapViewHref({ lat: 18.2, lon: -66.5, z: null })).toBe('/gis?lat=18.2&lon=-66.5');
    expect(searchHref('San Germán', 'SOURCE')).toBe('/search?q=San+Germ%C3%A1n&type=SOURCE');
    expect(searchHref('', 'ALL')).toBe('/search');
    expect(entityHref('ent/1')).toBe('/entity/ent%2F1');
  });

  it('centres the map from a valid link and reports, not corrects, an invalid one', () => {
    const linked = initialMapState(new URLSearchParams('lat=18.0&lon=-67.1&z=14'), DEFAULT);
    expect(linked.state.view.center).toEqual({ lon: -67.1, lat: 18.0 });
    expect(linked.state.view.groundResolutionM).toBeLessThan(DEFAULT.view.groundResolutionM);
    expect(linked.notice).toMatch(/Centred on 18, -67.1 at zoom 14/);
    const broken = initialMapState(new URLSearchParams('lat=999&lon=-67.1'), DEFAULT);
    expect(broken.state).toBe(DEFAULT);
    expect(broken.notice).toMatch(/invalid/);
    expect(initialMapState(new URLSearchParams(''), DEFAULT)).toEqual({ state: DEFAULT, notice: null });
  });
});

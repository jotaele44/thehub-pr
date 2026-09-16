import { describe, expect, it, vi } from 'vitest';
import { buildMultiMarkerParityModel, buildSinglePointParityModel, selectOriginalMapRecord } from './sharedMapParity';

describe('shared-map Leaflet→MapLibre parity contract', () => {
  it('preserves numeric-only multi-point filtering, first-valid centering, zoom and scroll behavior', () => {
    const first = { id: 'a', lat: 18.2, lon: -66.4, title: 'A' };
    const second = { id: 'b', lat: 18.3, lon: -66.5, title: 'B' };
    const model = buildMultiMarkerParityModel([
      { id: 'string', lat: '18.1', lon: '-66.3' },
      first,
      { id: 'nan', lat: Number.NaN, lon: -66.2 },
      second,
    ]);
    expect(model.points).toEqual([first, second]);
    expect(model.points[0]).toBe(first);
    expect(model.center).toEqual([-66.4, 18.2]);
    expect(model.zoom).toBe(9);
    expect(model.scrollZoom).toBe(true);
  });

  it('preserves the Puerto Rico fallback center for an empty multi-point set', () => {
    expect(buildMultiMarkerParityModel([]).center).toEqual([-66.4, 18.22]);
  });

  it('preserves single-point zoom/scroll behavior and null suppression', () => {
    expect(buildSinglePointParityModel(null, -66.4, 'X')).toBeNull();
    expect(buildSinglePointParityModel(18.2, -66.4, 'X')).toMatchObject({
      center: [-66.4, 18.2],
      zoom: 10,
      scrollZoom: false,
    });
  });

  it('returns the original selected record object to the callback', () => {
    const point = { id: 'stable-1', lat: 18.2, lon: -66.4 };
    const callback = vi.fn();
    expect(selectOriginalMapRecord(point, callback)).toBe(point);
    expect(callback).toHaveBeenCalledWith(point);
  });
});

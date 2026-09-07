import { describe, expect, it } from 'vitest';
import { normalizeMapPoints } from './MapLibrePointMap';

describe('shared MapLibre point map contracts', () => {
  it('preserves valid record objects without synthesizing identity', () => {
    const a = { id: 'a', lat: 18.2, lon: -66.4, title: 'A' };
    const b = { id: 'b', lat: 18.3, lon: -66.5, title: 'B' };
    const result = normalizeMapPoints([a, { id: 'bad', lat: Number.NaN, lon: -66 }, b]);
    expect(result).toEqual([a, b]);
    expect(result[0]).toBe(a);
    expect(result[1]).toBe(b);
  });

  it('does not coerce string coordinates into geolocated records', () => {
    expect(normalizeMapPoints([{ id: 'x', lat: '18.2', lon: '-66.4' }])).toEqual([]);
  });
});

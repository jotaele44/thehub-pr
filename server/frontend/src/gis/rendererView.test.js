import { describe, expect, it } from 'vitest';
import {
  canonicalViewToCesium,
  canonicalViewToMapLibre,
  cesiumViewToCanonical,
  mapLibreViewToCanonical,
} from './rendererView';

const VIEW = Object.freeze({
  center: Object.freeze({ lon: -66.4, lat: 18.22 }),
  groundResolutionM: 24.75,
  bearing: 27.5,
  requestedPitch: 42,
});

function expectViewClose(actual, expected) {
  expect(actual.center.lon).toBeCloseTo(expected.center.lon, 9);
  expect(actual.center.lat).toBeCloseTo(expected.center.lat, 9);
  expect(actual.groundResolutionM).toBeCloseTo(expected.groundResolutionM, 9);
  expect(actual.bearing).toBeCloseTo(expected.bearing, 9);
  expect(actual.requestedPitch).toBeCloseTo(expected.requestedPitch, 9);
}

describe('renderer canonical view adapters', () => {
  it('round-trips canonical view through MapLibre parameters', () => {
    const encoded = canonicalViewToMapLibre(VIEW);
    expectViewClose(mapLibreViewToCanonical(encoded), VIEW);
  });

  it('round-trips canonical view through Cesium camera parameters', () => {
    const encoded = canonicalViewToCesium(VIEW, 640);
    expectViewClose(cesiumViewToCanonical(encoded, 640), VIEW);
  });

  it('preserves canonical view across 2D→3D→2D mathematical interchange', () => {
    const mapLibre = canonicalViewToMapLibre(VIEW);
    const canonicalAfter2d = mapLibreViewToCanonical(mapLibre);
    const cesium = canonicalViewToCesium(canonicalAfter2d, 640);
    const canonicalAfter3d = cesiumViewToCanonical(cesium, 640);
    const mapLibreAgain = canonicalViewToMapLibre(canonicalAfter3d);
    expectViewClose(mapLibreViewToCanonical(mapLibreAgain), VIEW);
  });

  it('fails closed on non-positive ground resolution', () => {
    expect(() => canonicalViewToMapLibre({ ...VIEW, groundResolutionM: 0 })).toThrow(/groundResolutionM/);
    expect(() => canonicalViewToCesium({ ...VIEW, groundResolutionM: -1 })).toThrow(/groundResolutionM/);
  });
});

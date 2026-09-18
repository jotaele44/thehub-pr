import { describe, expect, it } from 'vitest';
import { IMAGERY_PROVIDER_REGISTRY, IMAGERY_FALLBACK_STATES, getImageryProvider } from './imageryProviderRegistry';

describe('imagery provider registry', () => {
  it('has unique stable provider IDs', () => {
    const ids = IMAGERY_PROVIDER_REGISTRY.map((item) => item.providerId);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('keeps commercial renderers non-authoritative and non-persistent', () => {
    const apple = getImageryProvider('apple-mapkit');
    expect(apple.manifestationType).toBe('RENDER_MANIFESTATION');
    expect(apple.authority).toBe('NONE');
    expect(apple.retention).toMatch(/MUST_NOT_BE_PERSISTED/);
    expect(apple.download).toMatch(/NO_TILE_HARVEST/);

    const esri = getImageryProvider('esri-world-imagery');
    expect(esri.manifestationType).toBe('RENDER_MANIFESTATION');
    expect(esri.authority).toMatch(/NONE/);
    expect(esri.retention).toMatch(/UNRESOLVED/);
  });

  it('does not collapse retained source manifestations into render providers', () => {
    const naip = getImageryProvider('noaa-pr-naip-2021-2023');
    const landsat = getImageryProvider('usgs-landsat-c2l2-sr');
    const sentinel = getImageryProvider('copernicus-sentinel-2-l2a');
    expect([naip, landsat, sentinel].every((item) => item.manifestationType === 'SOURCE_MANIFESTATION')).toBe(true);
    expect(naip.authority).not.toBe('NONE');
  });

  it('contains explicit failover control states', () => {
    expect(IMAGERY_FALLBACK_STATES).toContain('TERMS_BLOCKED');
    expect(IMAGERY_FALLBACK_STATES).toContain('AUTH_BLOCKED');
    expect(IMAGERY_FALLBACK_STATES).toContain('FALLBACK_ACTIVE');
  });
});

import { describe, expect, it } from 'vitest';
import { GEOSPATIAL_PROVIDERS, ONLINE_SOURCE_CATALOG, SOURCE_PROTOCOL_ADAPTERS, getOnlineSourceDefinition, getProvider } from './sourceRegistry';

describe('GIS source registry invariants', () => {
  it('has unique provider and source stable IDs', () => {
    const providerIds = GEOSPATIAL_PROVIDERS.map((item) => item.providerId);
    const sourceIds = ONLINE_SOURCE_CATALOG.map((item) => item.sourceId);
    expect(new Set(providerIds).size).toBe(providerIds.length);
    expect(new Set(sourceIds).size).toBe(sourceIds.length);
  });

  it('binds every source to an existing provider and protocol adapter', () => {
    for (const source of ONLINE_SOURCE_CATALOG) {
      expect(getProvider(source.providerId).providerId).toBe(source.providerId);
      expect(SOURCE_PROTOCOL_ADAPTERS[source.protocol]).toBeTruthy();
      expect(getOnlineSourceDefinition(source.sourceId)).toBe(source);
      expect(['direct', 'direct-or-proxy', 'proxy-required']).toContain(source.transport);
    }
  });

  it('requires protocol-specific identity and query bindings for executable sources', () => {
    for (const source of ONLINE_SOURCE_CATALOG.filter((item) => item.runtimeStatus === 'IMPLEMENTED')) {
      expect(SOURCE_PROTOCOL_ADAPTERS[source.protocol].runtimeStatus).toBe('IMPLEMENTED');
      expect(source.endpoint).toMatch(/^https?:\/\//);
      if (source.protocol === 'arcgis-feature-layer-geojson') {
        expect(source.stableIdField).toBeTruthy();
        expect(source.outputCrs).toBe('EPSG:4326');
      } else if (source.protocol === 'wfs') {
        expect(source.transport).toBe('proxy-required');
        expect(source.typeName).toBeTruthy();
        expect(source.stableIdField).toBeTruthy();
      } else if (source.protocol === 'stac') {
        expect(source.collectionId).toBeTruthy();
      } else if (source.protocol === 'static-stac-item-collection') {
        expect(source.collectionId).toBeTruthy();
      }
    }
  });

  it('binds Census Puerto Rico current-vintage layers to an explicit jurisdiction filter', () => {
    const state = getOnlineSourceDefinition('census-tigerweb-pr-state-2025');
    const municipios = getOnlineSourceDefinition('census-tigerweb-pr-municipios-2025');
    expect(state.endpoint).toMatch(/State_County\/MapServer\/0$/);
    expect(municipios.endpoint).toMatch(/State_County\/MapServer\/1$/);
    expect(state.where).toBe("STATE='72'");
    expect(municipios.where).toBe("STATE='72'");
    expect(state.expectedFeatureCount).toBe(1);
    expect(municipios.expectedFeatureCount).toBe(78);
  });
});

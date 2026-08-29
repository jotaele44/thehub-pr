import { describe, expect, it } from 'vitest';
import {
  GEOSPATIAL_PROVIDERS,
  ONLINE_SOURCE_CATALOG,
  SOURCE_PROTOCOL_ADAPTERS,
  getOnlineSourceDefinition,
  getProvider,
} from './sourceRegistry';

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
    }
  });

  it('does not advertise an implemented source on an open adapter', () => {
    for (const source of ONLINE_SOURCE_CATALOG.filter((item) => item.runtimeStatus === 'IMPLEMENTED')) {
      expect(SOURCE_PROTOCOL_ADAPTERS[source.protocol].runtimeStatus).toBe('IMPLEMENTED');
      expect(source.endpoint).toMatch(/^https:\/\//);
      expect(source.stableIdField).toBeTruthy();
      expect(source.outputCrs).toBe('EPSG:4326');
    }
  });
});

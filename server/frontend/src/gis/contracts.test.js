import { describe, expect, it } from 'vitest';
import { compareRendererEquivalence, createCanonicalMapState, createLayerManifest, switchRenderMode } from './contracts';
import { ingestGeoJSONText } from './ingestGeoJSON';

describe('canonical GIS state', () => {
  const base = {
    mode: '2d',
    view: { center: { lon: -66.4, lat: 18.22 }, groundResolutionM: 25, bearing: 15, requestedPitch: 35, aoi: { id: 'aoi-1' } },
    activeLayerIds: ['layer-1'],
    layerState: { 'layer-1': { visible: true, opacity: 0.8 } },
    selectedFeatureIds: ['feature-1'],
    imagerySelection: { providerId: 'copernicus-cdse', itemId: 'item-1', assetKey: 'visual' },
    terrainSourceId: 'terrain-1',
    time: { instant: '2026-08-29T00:00:00Z' },
    filters: { confidence: 'high' },
    displayCrs: 'EPSG:4326',
    provenanceRefs: ['sha256:abc'],
  };

  it('preserves canonical geographic state across a 2D→3D switch', () => {
    const threeD = switchRenderMode(base, '3d');
    const report = compareRendererEquivalence(base, threeD);
    expect(report.status).toBe('PASS');
    expect(report.pixelEquivalenceClaimed).toBe(false);
    expect(report.intersection).toContain('imagerySelection');
    expect(report.symmetricDifference).toContain('terrainOcclusion');
    expect(report.symmetricDifference).toContain('tileCache');
  });

  it('fails equivalence when a source-visible state changes', () => {
    const changed = createCanonicalMapState({ ...base, selectedFeatureIds: ['feature-2'] });
    const report = compareRendererEquivalence(base, changed);
    expect(report.status).toBe('FAIL');
    expect(report.failures).toContain('selectedFeatureIds');
  });

  it('fails closed on duplicate stable IDs', () => {
    expect(() => createCanonicalMapState({ ...base, activeLayerIds: ['layer-1', 'layer-1'] })).toThrow(/duplicate activeLayerId/);
  });

  it('rejects layer state for an inactive layer', () => {
    expect(() => createCanonicalMapState({ ...base, activeLayerIds: [], layerState: { 'layer-1': { visible: true } } })).toThrow(/inactive layerId/);
  });
});

describe('layer manifest and GeoJSON ingestion', () => {
  it('requires stable source and layer identity', () => {
    expect(() => createLayerManifest({ kind: 'vector' })).toThrow(/layerId/);
  });

  it('preserves raw text while deriving a canonical manifest', async () => {
    const raw = JSON.stringify({
      type: 'FeatureCollection',
      features: [{ type: 'Feature', id: 'p1', properties: { name: 'raw-name' }, geometry: { type: 'Point', coordinates: [-66.1, 18.3, 42] } }],
    });
    const result = await ingestGeoJSONText(raw, { fileName: 'fixture.geojson', layerId: 'layer-fixture', sourceId: 'source-fixture' });
    expect(result.rawText).toBe(raw);
    expect(result.manifest.featureCount).toBe(1);
    expect(result.manifest.geometryTypes).toEqual(['Point']);
    expect(result.manifest.preservesZ).toBe(true);
    expect(result.manifest.transformHistory).toEqual([]);
  });

  it('rejects a non-FeatureCollection instead of guessing', async () => {
    await expect(ingestGeoJSONText('{"type":"Point","coordinates":[0,0]}')).rejects.toThrow(/FeatureCollection/);
  });
});

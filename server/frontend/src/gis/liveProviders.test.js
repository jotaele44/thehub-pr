import { describe, expect, it } from 'vitest';
import { acquireOnlineSource, acquireRasterAsset } from './acquisitionFacade';
import { getOnlineSourceDefinition } from './sourceRegistry';

const runLive = process.env.GIS_LIVE_PROVIDER_TESTS === '1';
const live = runLive ? describe : describe.skip;

async function boundedFetch(url, init = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    return await globalThis.fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

const direct = { fetchImpl: boundedFetch, retrievalUtc: '2026-08-29T22:00:00Z' };

live('live authoritative GIS providers', () => {
  for (const sourceId of [
    'pr-sige-municipios',
    'pr-sige-represas',
    'pr-sige-aeropuertos',
    'pr-sige-helipuertos',
    'pr-sige-cuencas',
    'pr-sige-acuiferos',
    'pr-sige-sumideros',
    'pr-sige-aaa-pozos',
  ]) {
    it(`${sourceId} closes provider denominator and validation gates`, async () => {
      try {
        const result = await acquireOnlineSource(sourceId, direct);
        expect(result.certification.status).toBe('PASS');
        expect(result.manifest.featureCount).toBeGreaterThan(0);
        expect(result.certification.gates).toEqual({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' });
        console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
      } catch (error) {
        const source = getOnlineSourceDefinition(sourceId);
        const message = String(error);
        if (source.certification !== 'PROVISIONAL_PROVIDER_RUNTIME' || !/abort|fetch failed|network|enotfound|econn/i.test(message)) {
          throw error;
        }
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId, certification: source.certification, error: message }));
      }
    }, 45000);
  }

  it('Census current Puerto Rico state layer closes to exactly one feature', async () => {
    const result = await acquireOnlineSource('census-tigerweb-pr-state-2025', direct);
    expect(result.manifest.featureCount).toBe(1);
    expect(result.certification.status).toBe('PASS');
  }, 120000);

  it('Census current Puerto Rico municipios close to exactly 78 county-equivalent features', async () => {
    const result = await acquireOnlineSource('census-tigerweb-pr-municipios-2025', direct);
    expect(result.manifest.featureCount).toBe(78);
    expect(result.certification.status).toBe('PASS');
  }, 120000);

  it('Puerto Rico WFS municipios closes its 78-feature denominator', async () => {
    const result = await acquireOnlineSource('pr-geodata-municipios-2015', direct);
    expect(result.manifest.featureCount).toBe(78);
    expect(result.certification.status).toBe('PASS');
    console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId: result.sourceDefinition.sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
  }, 120000);

  for (const sourceId of ['usgs-landsat-stac-sr', 'copernicus-cdse-sentinel-2-l2a']) {
    it(`${sourceId} exhausts a bounded January 2025 Puerto Rico candidate window`, async () => {
      const result = await acquireOnlineSource(sourceId, { ...direct, bbox: [-67.4, 17.8, -65.2, 18.6], start: '2025-01-01', end: '2025-01-31', maxItems: 1000 });
      expect(result.certification.status).toBe('PASS');
      expect(result.certification.residue).toBeNull();
      expect(result.candidates.length).toBeGreaterThan(0);
      console.log('GIS_LIVE_DISCOVERY', JSON.stringify({ sourceId, candidates: result.candidates.length, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
      if (sourceId === 'usgs-landsat-stac-sr') {
        const candidate = result.candidates.find((item) => Object.values(item.assets || {}).some((asset) => asset?.href && /tiff?/i.test(asset.type || '')));
        if (candidate) {
          const assetEntry = Object.entries(candidate.assets).find(([, asset]) => asset?.href && /tiff?/i.test(asset.type || ''));
          const raster = await acquireRasterAsset(sourceId, candidate, assetEntry[0], { fetchImpl: globalThis.fetch, range: 'bytes=0-65535' });
          expect(raster.certification.gates.rangeRetrieval).toBe('PASS');
          expect(raster.certification.gates.fullAssetByteIdentity).toBe('OPEN');
          console.log('GIS_LIVE_RASTER_RANGE', JSON.stringify({ sourceId, itemId: candidate.itemId, assetKey: assetEntry[0], classification: raster.assetClassification, rangeSha256: raster.snapshotSha256 }));
        }
      }
    }, 120000);
  }

  it('NOAA Puerto Rico NAIP static STAC returns bounded Puerto Rico candidates without assuming TIFF=COG', async () => {
    const result = await acquireOnlineSource('noaa-pr-naip-2021-2023-stac', { ...direct, bbox: [-67.4, 17.8, -65.2, 18.6], start: '2021-01-01', end: '2023-12-31' });
    expect(result.certification.status).toBe('PASS');
    expect(result.candidates.length).toBeGreaterThan(0);
    console.log('GIS_LIVE_DISCOVERY', JSON.stringify({ sourceId: 'noaa-pr-naip-2021-2023-stac', candidates: result.candidates.length, snapshotSha256: result.snapshotSha256 }));
  }, 120000);
});

import { describe, expect, it } from 'vitest';
import { acquireOnlineSource } from './remoteAcquisition';

const runLive = process.env.GIS_LIVE_PROVIDER_TESTS === '1';
const live = runLive ? describe : describe.skip;
const direct = { fetchImpl: globalThis.fetch, retrievalUtc: '2026-08-29T21:00:00Z' };

live('live authoritative GIS providers', () => {
  for (const sourceId of ['pr-sige-municipios', 'pr-sige-represas', 'pr-sige-aeropuertos', 'pr-sige-helipuertos']) {
    it(`${sourceId} closes provider denominator and validation gates`, async () => {
      const result = await acquireOnlineSource(sourceId, direct);
      expect(result.certification.status).toBe('PASS');
      expect(result.manifest.featureCount).toBeGreaterThan(0);
      expect(result.certification.gates).toEqual({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' });
      console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
    }, 120000);
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

  it('Puerto Rico WFS barrios closes its hits denominator', async () => {
    const result = await acquireOnlineSource('pr-geodata-barrios-2015-simpl', direct);
    expect(result.manifest.featureCount).toBeGreaterThan(0);
    expect(result.certification.status).toBe('PASS');
    console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId: result.sourceDefinition.sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256 }));
  }, 120000);

  for (const sourceId of ['usgs-landsat-stac-sr', 'copernicus-cdse-sentinel-2-l2a']) {
    it(`${sourceId} returns a bounded Puerto Rico imagery candidate set`, async () => {
      const result = await acquireOnlineSource(sourceId, { ...direct, bbox: [-67.4, 17.8, -65.2, 18.6], start: '2025-01-01', end: '2025-12-31', maxItems: 100 });
      expect(result.certification.status).toBe('PASS');
      expect(result.candidates.length).toBeGreaterThan(0);
      console.log('GIS_LIVE_DISCOVERY', JSON.stringify({ sourceId, candidates: result.candidates.length, snapshotSha256: result.snapshotSha256 }));
    }, 120000);
  }
});

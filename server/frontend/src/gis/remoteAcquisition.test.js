import { describe, expect, it } from 'vitest';
import { acquireOnlineSource } from './remoteAcquisition';

function response(raw, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'ERROR',
    text: async () => raw,
  };
}

function makeFetch({ count = 2, duplicate = false, shortPage = false } = {}) {
  const firstId = duplicate ? 2 : 1;
  return async (url) => {
    if (url.includes('returnCountOnly=true')) return response(JSON.stringify({ count }));
    const features = [
      { type: 'Feature', properties: { OBJECTID_1: firstId }, geometry: { type: 'Point', coordinates: [-66.8, 18.1] } },
      { type: 'Feature', properties: { OBJECTID_1: 2 }, geometry: { type: 'Point', coordinates: [-66.6, 18.2] } },
    ];
    return response(JSON.stringify({ type: 'FeatureCollection', features: shortPage ? features.slice(0, 1) : features }));
  };
}

describe('remote GIS acquisition', () => {
  it('preserves raw manifestations and produces deterministic query/snapshot hashes', async () => {
    const fetchImpl = makeFetch();
    const first = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-29T20:00:00Z' });
    const second = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-30T20:00:00Z' });

    expect(first.rawResponses).toHaveLength(2);
    expect(first.rawResponses[0]).toBe(JSON.stringify({ count: 2 }));
    expect(first.queryReceiptSha256).toBe(second.queryReceiptSha256);
    expect(first.snapshotSha256).toBe(second.snapshotSha256);
    expect(first.sourceManifest.retrievalUtc).not.toBe(second.sourceManifest.retrievalUtc);
    expect(first.sourceManifest.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
    expect(first.certification.gates).toEqual({
      schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS',
    });
  });

  it('fails closed when the provider count does not close against fetched rows', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: makeFetch({ count: 3, shortPage: true }) })).rejects.toThrow(/count gate failed/);
  });

  it('fails closed on duplicate provider stable IDs', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: makeFetch({ duplicate: true }) })).rejects.toThrow(/identity gate failed/);
  });

  it('does not execute registry-only providers', async () => {
    await expect(acquireOnlineSource('copernicus-cdse-stac', { fetchImpl: makeFetch() })).rejects.toThrow(/registry-only/);
  });
});

import { describe, expect, it } from './testHarnessCompat';
import { acquireOnlineSource, acquireRasterAsset } from './acquisitionFacade';
import { classifyRasterAsset } from './remoteAcquisition';
import { getOnlineSourceDefinition } from './sourceRegistry';
import { toStacInterval } from './stacTime';

function textResponse(raw, status = 200, headers = {}) {
  return { ok: status >= 200 && status < 300, status, statusText: status === 200 ? 'OK' : 'ERROR', text: async () => raw, headers: { get: (name) => headers[name.toLowerCase()] || null } };
}

function binaryResponse(bytes, headers = {}) {
  return { ok: true, status: 206, statusText: 'Partial Content', arrayBuffer: async () => Uint8Array.from(bytes).buffer, headers: { get: (name) => headers[name.toLowerCase()] || null } };
}

function arcgisFetch({ count = 35, fetchedCount = count, duplicate = false, idField = 'OBJECTID_1' } = {}) {
  return async (url) => {
    if (url.includes('returnCountOnly=true')) return textResponse(JSON.stringify({ count }));
    const features = Array.from({ length: fetchedCount }, (_, index) => ({
      type: 'Feature',
      properties: { [idField]: duplicate && index === 1 ? 1 : index + 1 },
      geometry: { type: 'Point', coordinates: [-66.8 + index * 0.001, 18.1 + index * 0.001] },
    }));
    return textResponse(JSON.stringify({ type: 'FeatureCollection', features }));
  };
}

function wfsFetch({ count = 2, duplicate = false } = {}) {
  return async (url) => {
    if (url.includes('resultType=hits')) return textResponse(`<wfs:FeatureCollection numberMatched="${count}"/>`);
    return textResponse(JSON.stringify({ type: 'FeatureCollection', features: [
      { type: 'Feature', properties: { gid: duplicate ? 2 : 1 }, geometry: { type: 'Polygon', coordinates: [[[-66.8, 18.1], [-66.7, 18.1], [-66.7, 18.2], [-66.8, 18.1]]] } },
      { type: 'Feature', properties: { gid: 2 }, geometry: { type: 'Polygon', coordinates: [[[-66.6, 18.2], [-66.5, 18.2], [-66.5, 18.3], [-66.6, 18.2]]] } },
    ] }));
  };
}

function stacFetch(capture = []) {
  return async (url) => {
    capture.push(url);
    return textResponse(JSON.stringify({ type: 'FeatureCollection', features: [
      { type: 'Feature', id: 'item-a', collection: 'landsat-c2l2-sr', bbox: [-67, 18, -66, 18.5], geometry: null, properties: { datetime: '2026-01-15T00:00:00Z', 'proj:epsg': 32620 }, assets: { blue: { href: 'https://landsatlook.usgs.gov/data/item-a-blue.tif', type: 'image/tiff; application=geotiff; profile=cloud-optimized' } } },
    ], links: [] }));
  };
}

describe('remote vector acquisition', () => {
  it('preserves raw manifestations and deterministic query/snapshot hashes', async () => {
    const fetchImpl = arcgisFetch();
    const first = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-29T20:00:00Z' });
    const second = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-30T20:00:00Z' });
    expect(first.rawResponses).toHaveLength(2);
    expect(first.manifest.featureCount).toBe(35);
    expect(first.queryReceiptSha256).toBe(second.queryReceiptSha256);
    expect(first.snapshotSha256).toBe(second.snapshotSha256);
    expect(first.sourceManifest.retrievalUtc).not.toBe(second.sourceManifest.retrievalUtc);
    expect(first.sourceManifest.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
    expect(first.certification.gates).toEqual({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' });
  });

  it('fails closed when provider count does not close', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: arcgisFetch({ fetchedCount: 34 }) })).rejects.toThrow(/count gate failed/);
  });

  it('fails closed on duplicate provider stable IDs', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: arcgisFetch({ duplicate: true }) })).rejects.toThrow(/identity gate failed/);
  });

  it('implements WFS hits denominator + GeoJSON page path on the live-certified municipios layer', async () => {
    const result = await acquireOnlineSource('pr-geodata-municipios-2015', { fetchImpl: wfsFetch() });
    expect(result.manifest.featureCount).toBe(2);
    expect(result.certification.gates.count).toBe('PASS');
    expect(result.queryReceipt.typeName).toBe('pr_geodata:g03_legales_municipios_2015');
  });

  it('fails WFS duplicate identity instead of deduplicating', async () => {
    await expect(acquireOnlineSource('pr-geodata-municipios-2015', { fetchImpl: wfsFetch({ duplicate: true }) })).rejects.toThrow(/identity gate failed/);
  });

  it('does not execute the displaced WFS candidate', async () => {
    await expect(acquireOnlineSource('pr-geodata-barrios-2015-simpl', { fetchImpl: wfsFetch() })).rejects.toThrow(/registry-only/);
  });
});

describe('STAC discovery and raster manifestation identity', () => {
  it('normalizes date-only UI boundaries into RFC3339 before hashing/querying', async () => {
    const urls = [];
    const result = await acquireOnlineSource('usgs-landsat-stac-sr', { fetchImpl: stacFetch(urls), bbox: [-67.4, 17.8, -65.2, 18.6], start: '2026-01-01', end: '2026-12-31' });
    expect(result.certification.status).toBe('PASS');
    expect(result.candidates).toHaveLength(1);
    expect(decodeURIComponent(urls[0])).toContain('datetime=2026-01-01T00:00:00Z/2026-12-31T23:59:59Z');
    expect(result.queryReceipt.start).toBe('2026-01-01T00:00:00Z');
    expect(result.queryReceipt.end).toBe('2026-12-31T23:59:59Z');
  });

  it('normalizes deterministic STAC intervals independently', () => {
    expect(toStacInterval('2025-01-01', '2025-01-31')).toMatchObject({ start: '2025-01-01T00:00:00Z', end: '2025-01-31T23:59:59Z' });
  });

  it('does not promote a NOAA TIFF to COG from extension/name alone', () => {
    const source = getOnlineSourceDefinition('noaa-pr-naip-2021-2023-stac');
    expect(classifyRasterAsset(source, { href: 'https://coastalimagery.blob.core.windows.net/digitalcoast/PR_NAIP_2021_9825/tile.tif', type: 'image/tiff' })).toBe('GEOTIFF_UNVERIFIED_COG');
  });

  it('accepts an authoritative Landsat collection binding as COG evidence', () => {
    const source = getOnlineSourceDefinition('usgs-landsat-stac-sr');
    expect(classifyRasterAsset(source, { href: 'https://landsatlook.usgs.gov/data/tile.tif', type: 'image/tiff' })).toBe('COG_AUTHORITATIVE_BINDING');
  });

  it('keeps range evidence distinct from full-asset byte identity', async () => {
    const candidate = { itemId: 'item-a', collectionId: 'landsat-c2l2-sr', bbox: [-67, 18, -66, 18.5], properties: { 'proj:epsg': 32620 }, assets: { blue: { href: 'https://landsatlook.usgs.gov/data/item-a-blue.tif', type: 'image/tiff' } } };
    const fetchImpl = async () => binaryResponse([73, 73, 42, 0, 8, 0, 0, 0], { 'content-range': 'bytes 0-7/1000000', 'content-type': 'image/tiff' });
    const result = await acquireRasterAsset('usgs-landsat-stac-sr', candidate, 'blue', { fetchImpl, range: 'bytes=0-7' });
    expect(result.assetClassification).toBe('COG_AUTHORITATIVE_BINDING');
    expect(result.certification.status).toBe('PROVISIONAL');
    expect(result.certification.residue).toBe('FULL_ASSET_BYTES_NOT_HASHED');
    expect(result.manifest.byteSha256).toBeNull();
    expect(result.sourceManifest.byteIdentityStatus).toBe('PARTIAL_RANGE_ONLY');
  });
});

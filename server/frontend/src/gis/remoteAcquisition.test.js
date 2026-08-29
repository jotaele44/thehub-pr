import { describe, expect, it } from 'vitest';
import { acquireOnlineSource, acquireRasterAsset, classifyRasterAsset } from './remoteAcquisition';
import { getOnlineSourceDefinition } from './sourceRegistry';

function textResponse(raw, status = 200, headers = {}) {
  return { ok: status >= 200 && status < 300, status, statusText: status === 200 ? 'OK' : 'ERROR', text: async () => raw, headers: { get: (name) => headers[name.toLowerCase()] || null } };
}

function binaryResponse(bytes, headers = {}) {
  return { ok: true, status: 206, statusText: 'Partial Content', arrayBuffer: async () => Uint8Array.from(bytes).buffer, headers: { get: (name) => headers[name.toLowerCase()] || null } };
}

function arcgisFetch({ count = 2, duplicate = false, shortPage = false, idField = 'OBJECTID_1' } = {}) {
  return async (url) => {
    if (url.includes('returnCountOnly=true')) return textResponse(JSON.stringify({ count }));
    const firstId = duplicate ? 2 : 1;
    const features = [
      { type: 'Feature', properties: { [idField]: firstId }, geometry: { type: 'Point', coordinates: [-66.8, 18.1] } },
      { type: 'Feature', properties: { [idField]: 2 }, geometry: { type: 'Point', coordinates: [-66.6, 18.2] } },
    ];
    return textResponse(JSON.stringify({ type: 'FeatureCollection', features: shortPage ? features.slice(0, 1) : features }));
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

function stacFetch() {
  return async () => textResponse(JSON.stringify({ type: 'FeatureCollection', features: [
    { type: 'Feature', id: 'item-a', collection: 'landsat-c2l2alb-sr', bbox: [-67, 18, -66, 18.5], geometry: null, properties: { datetime: '2026-01-15T00:00:00Z', 'proj:epsg': 32620 }, assets: { blue: { href: 'https://landsatlook.usgs.gov/data/item-a-blue.tif', type: 'image/tiff; application=geotiff; profile=cloud-optimized' } } },
  ], links: [] }));
}

describe('remote vector acquisition', () => {
  it('preserves raw manifestations and deterministic query/snapshot hashes', async () => {
    const fetchImpl = arcgisFetch();
    const first = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-29T20:00:00Z' });
    const second = await acquireOnlineSource('pr-sige-represas', { fetchImpl, retrievalUtc: '2026-08-30T20:00:00Z' });
    expect(first.rawResponses).toHaveLength(2);
    expect(first.queryReceiptSha256).toBe(second.queryReceiptSha256);
    expect(first.snapshotSha256).toBe(second.snapshotSha256);
    expect(first.sourceManifest.retrievalUtc).not.toBe(second.sourceManifest.retrievalUtc);
    expect(first.sourceManifest.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
    expect(first.certification.gates).toEqual({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' });
  });

  it('fails closed when provider count does not close', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: arcgisFetch({ count: 3, shortPage: true }) })).rejects.toThrow(/count gate failed/);
  });

  it('fails closed on duplicate provider stable IDs', async () => {
    await expect(acquireOnlineSource('pr-sige-represas', { fetchImpl: arcgisFetch({ duplicate: true }) })).rejects.toThrow(/identity gate failed/);
  });

  it('implements WFS hits denominator + GeoJSON page path', async () => {
    const result = await acquireOnlineSource('pr-geodata-barrios-2015-simpl', { fetchImpl: wfsFetch() });
    expect(result.manifest.featureCount).toBe(2);
    expect(result.certification.gates.count).toBe('PASS');
    expect(result.queryReceipt.typeName).toBe('pr_geodata:g03_legales_barrios_2015_simpl_5m');
  });

  it('fails WFS duplicate identity instead of deduplicating', async () => {
    await expect(acquireOnlineSource('pr-geodata-barrios-2015-simpl', { fetchImpl: wfsFetch({ duplicate: true }) })).rejects.toThrow(/identity gate failed/);
  });
});

describe('STAC discovery and raster manifestation identity', () => {
  it('discovers a bounded STAC item set with deterministic provenance', async () => {
    const result = await acquireOnlineSource('usgs-landsat-stac-sr', { fetchImpl: stacFetch(), bbox: [-67.4, 17.8, -65.2, 18.6], start: '2026-01-01', end: '2026-12-31' });
    expect(result.certification.status).toBe('PASS');
    expect(result.candidates).toHaveLength(1);
    expect(result.candidates[0].itemId).toBe('item-a');
    expect(result.sourceManifest.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
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
    const candidate = { itemId: 'item-a', collectionId: 'landsat-c2l2alb-sr', bbox: [-67, 18, -66, 18.5], properties: { 'proj:epsg': 32620 }, assets: { blue: { href: 'https://landsatlook.usgs.gov/data/item-a-blue.tif', type: 'image/tiff' } } };
    const fetchImpl = async () => binaryResponse([73, 73, 42, 0, 8, 0, 0, 0], { 'content-range': 'bytes 0-7/1000000', 'content-type': 'image/tiff' });
    const result = await acquireRasterAsset('usgs-landsat-stac-sr', candidate, 'blue', { fetchImpl, range: 'bytes=0-7' });
    expect(result.assetClassification).toBe('COG_AUTHORITATIVE_BINDING');
    expect(result.certification.status).toBe('PROVISIONAL');
    expect(result.certification.residue).toBe('FULL_ASSET_BYTES_NOT_HASHED');
    expect(result.manifest.byteSha256).toBeNull();
    expect(result.sourceManifest.byteIdentityStatus).toBe('PARTIAL_RANGE_ONLY');
  });
});

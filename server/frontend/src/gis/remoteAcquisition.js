import { createLayerManifest } from './contracts';
import { ingestGeoJSONText } from './ingestGeoJSON';
import { frameRawTexts, sha256Bytes, sha256StableJson, sha256Text } from './integrity';
import { fetchSourceRange, fetchSourceText } from './transport';
import { createSourceManifest, getOnlineSourceDefinition, SOURCE_PROTOCOL_ADAPTERS } from './sourceRegistry';

function buildUrl(endpoint, params) {
  const url = new URL(endpoint);
  Object.entries(params)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .sort(([left], [right]) => left.localeCompare(right))
    .forEach(([key, value]) => url.searchParams.set(key, String(value)));
  return url.toString();
}

function parseJson(rawText, label) {
  try { return JSON.parse(rawText); } catch (error) { throw new Error(`${label} returned invalid JSON: ${error.message}`); }
}

function assertFeatureCollection(value, label) {
  if (!value || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) throw new Error(`${label} is not a GeoJSON FeatureCollection`);
}

function geometryTypes(features) {
  return [...new Set(features.map((feature) => feature?.geometry?.type).filter(Boolean))].sort();
}

function assertGeometryGate(features, expectedGeometryTypes = []) {
  const observed = geometryTypes(features);
  const unexpected = observed.filter((type) => !expectedGeometryTypes.includes(type));
  if (expectedGeometryTypes.length && unexpected.length) throw new Error(`geometry gate failed; unexpected geometry types: ${unexpected.join(', ')}`);
  return observed;
}

function walkPositions(value, visit) {
  if (!Array.isArray(value)) return;
  if (value.length >= 2 && value.every((item) => typeof item === 'number')) { visit(value); return; }
  for (const item of value) walkPositions(item, visit);
}

function assertWgs84Coordinates(features) {
  for (let featureIndex = 0; featureIndex < features.length; featureIndex += 1) {
    const geometry = features[featureIndex]?.geometry;
    if (!geometry?.coordinates) continue;
    walkPositions(geometry.coordinates, (position) => {
      const [lon, lat] = position;
      if (!Number.isFinite(lon) || !Number.isFinite(lat) || lon < -180 || lon > 180 || lat < -90 || lat > 90) throw new Error(`CRS gate failed at feature ${featureIndex}: coordinate is not bounded WGS84 lon/lat`);
    });
  }
}

function stableFeatureId(feature, stableIdField) {
  const properties = feature?.properties || {};
  return properties[stableIdField] ?? properties[stableIdField?.toLowerCase?.()] ?? properties[stableIdField?.toUpperCase?.()] ?? feature?.id ?? null;
}

function assertStableIdentity(features, stableIdField) {
  if (!stableIdField) throw new Error('identity gate requires a stableIdField');
  const seen = new Set();
  for (let index = 0; index < features.length; index += 1) {
    const value = stableFeatureId(features[index], stableIdField);
    if (value === null || value === undefined || String(value).trim() === '') throw new Error(`identity gate failed; feature ${index} missing ${stableIdField}`);
    const id = String(value);
    if (seen.has(id)) throw new Error(`identity gate failed; duplicate ${stableIdField}: ${id}`);
    seen.add(id);
  }
  return seen.size;
}

function vectorCertification(source, count, observedGeometryTypes, pageCount) {
  return Object.freeze({
    status: 'PASS',
    scope: Object.freeze({ providerId: source.providerId, sourceId: source.sourceId, protocol: source.protocol, fetchedFeatureCount: count, fetchedPageCount: pageCount, outputCrs: source.outputCrs }),
    gates: Object.freeze({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' }),
    observedGeometryTypes: Object.freeze(observedGeometryTypes),
    providerRuntimeCertification: source.certification,
  });
}

async function finalizeVector(source, rawResponses, queryReceipt, features, observedGeometryTypes, retrievalUtc) {
  const snapshotSha256 = await sha256Text(frameRawTexts(rawResponses));
  const queryReceiptSha256 = await sha256StableJson(queryReceipt);
  if (!snapshotSha256 || !queryReceiptSha256) throw new Error('provenance hash gate failed');
  const normalizedGeojsonText = JSON.stringify({ type: 'FeatureCollection', features });
  const layer = await ingestGeoJSONText(normalizedGeojsonText, {
    sourceId: `remote:${source.sourceId}:snapshot:${snapshotSha256}`,
    layerId: `layer:${source.sourceId}:snapshot:${snapshotSha256}`,
    fileName: source.label,
    nativeCrs: 'RFC7946/WGS84', displayCrs: source.outputCrs || 'EPSG:4326',
    sourceManifestation: 'remote-query-normalized-geojson',
    transformHistory: source.sourceNativeCrs && source.sourceNativeCrs !== source.outputCrs ? [`provider transform ${source.sourceNativeCrs} → ${source.outputCrs}`] : [],
    provenance: { providerId: source.providerId, registrySourceId: source.sourceId, queryReceiptSha256, sourceSnapshotSha256: snapshotSha256, sourceNativeCrs: source.sourceNativeCrs || null, canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY', retrievalUtc },
    validationStatus: 'PASS',
  });
  const sourceManifest = createSourceManifest({ sourceId: source.sourceId, providerId: source.providerId, sourceClass: source.protocol, hrefManifestation: source.endpoint, crs: source.outputCrs || 'EPSG:4326', sourceNativeCrs: source.sourceNativeCrs || null, retrievalUtc, queryReceiptSha256, snapshotSha256, normalizedSha256: layer.manifest.byteSha256, canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
  return { layer, sourceManifest, snapshotSha256, queryReceiptSha256, normalizedGeojsonText, observedGeometryTypes };
}

async function acquireArcGisFeatureLayer(source, options) {
  if (!globalThis.crypto?.subtle) throw new Error('online acquisition requires Web Crypto SHA-256');
  const where = options.where || source.where || '1=1';
  const outFields = options.outFields || '*';
  const pageSize = Number(source.pageSize || 1000);
  if (!Number.isInteger(pageSize) || pageSize <= 0) throw new Error('source pageSize must be a positive integer');
  const countUrl = buildUrl(`${source.endpoint.replace(/\/$/, '')}/query`, { f: 'json', returnCountOnly: true, where });
  const { rawText: rawCount } = await fetchSourceText(source, countUrl, options);
  const expectedCount = Number(parseJson(rawCount, 'count query').count);
  if (!Number.isInteger(expectedCount) || expectedCount < 0) throw new Error('count gate failed; provider did not return a non-negative integer count');
  if (source.expectedFeatureCount !== undefined && expectedCount !== source.expectedFeatureCount) throw new Error(`count gate failed; registry expected ${source.expectedFeatureCount}, provider reported ${expectedCount}`);
  const rawPages = []; const pageUrls = []; const features = [];
  for (let resultOffset = 0; resultOffset < expectedCount; resultOffset += pageSize) {
    const pageUrl = buildUrl(`${source.endpoint.replace(/\/$/, '')}/query`, { f: 'geojson', orderByFields: `${source.stableIdField} ASC`, outFields, outSR: 4326, resultOffset, resultRecordCount: pageSize, returnGeometry: true, where });
    const { rawText } = await fetchSourceText(source, pageUrl, options);
    const page = parseJson(rawText, `page at offset ${resultOffset}`); assertFeatureCollection(page, `page at offset ${resultOffset}`);
    rawPages.push(rawText); pageUrls.push(pageUrl); features.push(...page.features);
  }
  if (features.length !== expectedCount) throw new Error(`count gate failed; provider count=${expectedCount}, fetched=${features.length}`);
  const observedGeometryTypes = assertGeometryGate(features, source.expectedGeometryTypes || []); assertWgs84Coordinates(features); assertStableIdentity(features, source.stableIdField);
  const queryReceipt = Object.freeze({ schemaVersion: '2.0.0', providerId: source.providerId, sourceId: source.sourceId, protocol: source.protocol, countUrl, pageUrls: Object.freeze(pageUrls), where, outFields, requestedOutputCrs: source.outputCrs, sourceNativeCrs: source.sourceNativeCrs, stableIdField: source.stableIdField, pageSize });
  const retrievalUtc = options.retrievalUtc || new Date().toISOString();
  const finalized = await finalizeVector(source, [rawCount, ...rawPages], queryReceipt, features, observedGeometryTypes, retrievalUtc);
  return Object.freeze({ acquisitionMethod: 'online', sourceDefinition: source, rawResponses: Object.freeze([rawCount, ...rawPages]), normalizedGeojsonText: finalized.normalizedGeojsonText, geojson: finalized.layer.geojson, manifest: finalized.layer.manifest, sourceManifest: finalized.sourceManifest, queryReceipt, queryReceiptSha256: finalized.queryReceiptSha256, snapshotSha256: finalized.snapshotSha256, certification: vectorCertification(source, expectedCount, observedGeometryTypes, rawPages.length) });
}

function parseWfsMatched(rawText) {
  const match = rawText.match(/\b(?:numberMatched|numberOfFeatures)=["'](\d+)["']/i);
  if (!match) throw new Error('count gate failed; WFS hits response has no numeric numberMatched/numberOfFeatures');
  return Number(match[1]);
}

async function acquireWfs(source, options) {
  const pageSize = Number(source.pageSize || 1000);
  const hitsUrl = buildUrl(source.endpoint, { service: 'WFS', version: '2.0.0', request: 'GetFeature', typeNames: source.typeName, resultType: 'hits' });
  const { rawText: rawHits } = await fetchSourceText(source, hitsUrl, { ...options, accept: 'application/xml,text/xml' });
  const expectedCount = parseWfsMatched(rawHits);
  if (source.expectedFeatureCount !== undefined && expectedCount !== source.expectedFeatureCount) throw new Error(`count gate failed; registry expected ${source.expectedFeatureCount}, provider reported ${expectedCount}`);
  const rawPages = []; const pageUrls = []; const features = [];
  for (let startIndex = 0; startIndex < expectedCount; startIndex += pageSize) {
    const pageUrl = buildUrl(source.endpoint, { service: 'WFS', version: '2.0.0', request: 'GetFeature', typeNames: source.typeName, outputFormat: 'application/json', srsName: 'EPSG:4326', count: pageSize, startIndex, sortBy: source.stableIdField });
    const { rawText } = await fetchSourceText(source, pageUrl, options);
    const page = parseJson(rawText, `WFS page at ${startIndex}`); assertFeatureCollection(page, `WFS page at ${startIndex}`);
    rawPages.push(rawText); pageUrls.push(pageUrl); features.push(...page.features);
  }
  if (features.length !== expectedCount) throw new Error(`count gate failed; WFS matched=${expectedCount}, fetched=${features.length}`);
  const observedGeometryTypes = assertGeometryGate(features, source.expectedGeometryTypes || []); assertWgs84Coordinates(features); assertStableIdentity(features, source.stableIdField);
  const queryReceipt = Object.freeze({ schemaVersion: '2.0.0', providerId: source.providerId, sourceId: source.sourceId, protocol: 'wfs', hitsUrl, pageUrls: Object.freeze(pageUrls), typeName: source.typeName, requestedOutputCrs: source.outputCrs, stableIdField: source.stableIdField, pageSize });
  const retrievalUtc = options.retrievalUtc || new Date().toISOString();
  const finalized = await finalizeVector(source, [rawHits, ...rawPages], queryReceipt, features, observedGeometryTypes, retrievalUtc);
  return Object.freeze({ acquisitionMethod: 'online', sourceDefinition: source, rawResponses: Object.freeze([rawHits, ...rawPages]), geojson: finalized.layer.geojson, manifest: finalized.layer.manifest, sourceManifest: finalized.sourceManifest, queryReceipt, queryReceiptSha256: finalized.queryReceiptSha256, snapshotSha256: finalized.snapshotSha256, certification: vectorCertification(source, expectedCount, observedGeometryTypes, rawPages.length) });
}

function bboxIntersects(a, b) { return Array.isArray(a) && a.length >= 4 && a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]; }
function datetimeInRange(value, start, end) { if (!value) return true; const t = Date.parse(value); return (!start || t >= Date.parse(start)) && (!end || t <= Date.parse(end)); }
function stacCandidates(features) {
  return features.map((item) => Object.freeze({ itemId: String(item.id), collectionId: item.collection || null, datetime: item.properties?.datetime || item.properties?.start_datetime || null, bbox: item.bbox || null, geometry: item.geometry || null, properties: Object.freeze({ ...(item.properties || {}) }), assets: Object.freeze({ ...(item.assets || {}) }), rawItem: item }));
}

async function discoverStacApi(source, options) {
  const bbox = options.bbox || [-67.4, 17.8, -65.2, 18.6]; const start = options.start || null; const end = options.end || null; const limit = Number(options.pageSize || 100); const maxItems = Number(options.maxItems || 1000);
  const datetime = start || end ? `${start || '..'}/${end || '..'}` : null;
  let nextUrl = buildUrl(`${source.endpoint.replace(/\/$/, '')}/search`, { collections: source.collectionId, bbox: bbox.join(','), datetime, limit });
  const rawResponses = []; const requestUrls = []; const items = []; let residue = false;
  while (nextUrl && items.length < maxItems) {
    requestUrls.push(nextUrl); const { rawText } = await fetchSourceText(source, nextUrl, options); rawResponses.push(rawText);
    const page = parseJson(rawText, 'STAC search'); assertFeatureCollection(page, 'STAC search');
    for (const item of page.features) { if (!item?.id) throw new Error('STAC identity gate failed; item missing id'); items.push(item); if (items.length >= maxItems) break; }
    const next = (page.links || []).find((link) => link.rel === 'next' && link.href); nextUrl = next?.href || null;
    if (items.length >= maxItems && nextUrl) residue = true;
  }
  const ids = items.map((item) => String(item.id)); if (new Set(ids).size !== ids.length) throw new Error('STAC identity gate failed; duplicate item id');
  const queryReceipt = Object.freeze({ schemaVersion: '2.0.0', providerId: source.providerId, sourceId: source.sourceId, protocol: 'stac', collectionId: source.collectionId, bbox: Object.freeze([...bbox]), start, end, limit, maxItems, requestUrls: Object.freeze(requestUrls) });
  return finalizeDiscovery(source, rawResponses, queryReceipt, items, residue, options.retrievalUtc);
}

async function discoverStaticStac(source, options) {
  const bbox = options.bbox || [-67.4, 17.8, -65.2, 18.6]; const start = options.start || null; const end = options.end || null;
  const { rawText } = await fetchSourceText(source, source.endpoint, options); const payload = parseJson(rawText, 'static STAC item collection'); assertFeatureCollection(payload, 'static STAC item collection');
  const filtered = payload.features.filter((item) => (!item.bbox || bboxIntersects(item.bbox, bbox)) && datetimeInRange(item.properties?.datetime || item.properties?.start_datetime, start, end));
  const ids = filtered.map((item) => String(item.id)); if (ids.some((id) => !id || id === 'undefined') || new Set(ids).size !== ids.length) throw new Error('STAC identity gate failed; missing or duplicate item id');
  const queryReceipt = Object.freeze({ schemaVersion: '2.0.0', providerId: source.providerId, sourceId: source.sourceId, protocol: 'static-stac-item-collection', endpoint: source.endpoint, collectionId: source.collectionId, bbox: Object.freeze([...bbox]), start, end });
  return finalizeDiscovery(source, [rawText], queryReceipt, filtered, false, options.retrievalUtc);
}

async function finalizeDiscovery(source, rawResponses, queryReceipt, items, residue, retrievalUtcInput) {
  const snapshotSha256 = await sha256Text(frameRawTexts(rawResponses)); const queryReceiptSha256 = await sha256StableJson(queryReceipt); if (!snapshotSha256 || !queryReceiptSha256) throw new Error('STAC provenance hash gate failed');
  const retrievalUtc = retrievalUtcInput || new Date().toISOString(); const candidates = Object.freeze(stacCandidates(items));
  const sourceManifest = createSourceManifest({ sourceId: source.sourceId, providerId: source.providerId, sourceClass: source.protocol, collectionId: source.collectionId, hrefManifestation: source.endpoint, retrievalUtc, queryReceiptSha256, snapshotSha256, canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
  return Object.freeze({ acquisitionMethod: 'online-discovery', sourceDefinition: source, rawResponses: Object.freeze(rawResponses), candidates, sourceManifest, queryReceipt, queryReceiptSha256, snapshotSha256, certification: Object.freeze({ status: residue ? 'OPEN' : 'PASS', residue: residue ? 'MAX_ITEMS_TRUNCATION' : null, gates: Object.freeze({ schema: 'PASS', identity: 'PASS', provenance: 'PASS', count: residue ? 'OPEN' : 'PASS' }), candidateCount: candidates.length }) });
}

export function classifyRasterAsset(source, asset = {}) {
  const mediaType = String(asset.type || '').toLowerCase(); const roles = (asset.roles || []).map((role) => String(role).toLowerCase());
  if (source.assetFormatBinding === 'COG_BY_AUTHORITATIVE_COLLECTION') return 'COG_AUTHORITATIVE_BINDING';
  if (mediaType.includes('cloud-optimized') || mediaType.includes('profile=cloud-optimized') || roles.includes('cog')) return 'COG_EXPLICIT_METADATA';
  if (mediaType.includes('tiff') || /\.tiff?(?:$|\?)/i.test(asset.href || '')) return 'GEOTIFF_UNVERIFIED_COG';
  return 'UNKNOWN_RASTER';
}

export async function acquireRasterAsset(sourceId, candidate, assetKey, options = {}) {
  const source = getOnlineSourceDefinition(sourceId); const asset = candidate?.assets?.[assetKey]; if (!asset?.href) throw new Error('raster asset requires a candidate asset href');
  const classification = classifyRasterAsset(source, asset); const range = await fetchSourceRange(source, asset.href, options.range || 'bytes=0-65535', options); const rangeSha256 = await sha256Bytes(range.bytes); if (!rangeSha256) throw new Error('raster range SHA-256 unavailable');
  const receipt = Object.freeze({ schemaVersion: '2.0.0', providerId: source.providerId, sourceId, collectionId: candidate.collectionId || source.collectionId || null, itemId: candidate.itemId, assetKey, hrefManifestation: asset.href, requestedRange: range.requestedRange, classification }); const queryReceiptSha256 = await sha256StableJson(receipt);
  const manifest = createLayerManifest({ layerId: `raster:${sourceId}:${candidate.itemId}:${assetKey}:${rangeSha256}`, sourceId: `asset:${sourceId}:${candidate.itemId}:${assetKey}`, titleRaw: `${source.label} · ${candidate.itemId} · ${assetKey}`, kind: 'raster', rawFormat: classification.startsWith('COG_') ? 'COG' : classification.startsWith('GEOTIFF') ? 'GeoTIFF' : 'unknown', nativeCrs: candidate.properties?.['proj:epsg'] ? `EPSG:${candidate.properties['proj:epsg']}` : null, displayCrs: 'EPSG:4326', bbox: candidate.bbox || null, byteSha256: null, transformHistory: [], provenance: { providerId: source.providerId, collectionId: candidate.collectionId || source.collectionId || null, itemId: candidate.itemId, assetKey, hrefManifestation: asset.href, queryReceiptSha256, rangeSha256, byteIdentityStatus: 'PARTIAL_RANGE_ONLY', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' }, validationStatus: 'PROVISIONAL' });
  const sourceManifest = createSourceManifest({ sourceId, providerId: source.providerId, sourceClass: 'raster-asset-range', collectionId: candidate.collectionId || source.collectionId, itemId: candidate.itemId, assetKey, hrefManifestation: asset.href, bbox: candidate.bbox, crs: manifest.nativeCrs, retrievalUtc: options.retrievalUtc || new Date().toISOString(), queryReceiptSha256, snapshotSha256: rangeSha256, byteIdentityStatus: 'PARTIAL_RANGE_ONLY', canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY' });
  return Object.freeze({ acquisitionMethod: 'online-raster-range', sourceDefinition: source, manifest, sourceManifest, queryReceipt: receipt, queryReceiptSha256, snapshotSha256: rangeSha256, assetClassification: classification, rangeEvidence: range, certification: Object.freeze({ status: 'PROVISIONAL', gates: Object.freeze({ provenance: 'PASS', assetIdentity: 'PASS', rangeRetrieval: 'PASS', fullAssetByteIdentity: 'OPEN' }), residue: 'FULL_ASSET_BYTES_NOT_HASHED' }) });
}

export async function acquireOnlineSource(sourceId, options = {}) {
  const source = getOnlineSourceDefinition(sourceId); const adapter = SOURCE_PROTOCOL_ADAPTERS[source.protocol];
  if (!adapter) throw new Error(`no protocol adapter registered for ${source.protocol}`);
  if (source.runtimeStatus !== 'IMPLEMENTED' || adapter.runtimeStatus !== 'IMPLEMENTED') throw new Error(`source ${sourceId} is registry-only; runtime path remains ${source.runtimeStatus}`);
  if (source.protocol === 'arcgis-feature-layer-geojson') return acquireArcGisFeatureLayer(source, options);
  if (source.protocol === 'wfs') return acquireWfs(source, options);
  if (source.protocol === 'stac') return discoverStacApi(source, options);
  if (source.protocol === 'static-stac-item-collection') return discoverStaticStac(source, options);
  throw new Error(`protocol adapter ${source.protocol} is not implemented`);
}

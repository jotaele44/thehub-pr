import { ingestGeoJSONText } from './ingestGeoJSON';
import { frameRawTexts, sha256StableJson, sha256Text } from './integrity';
import { createSourceManifest, getOnlineSourceDefinition, SOURCE_PROTOCOL_ADAPTERS } from './sourceRegistry';

function buildUrl(endpoint, params) {
  const url = new URL(`${endpoint.replace(/\/$/, '')}/query`);
  Object.entries(params)
    .sort(([left], [right]) => left.localeCompare(right))
    .forEach(([key, value]) => url.searchParams.set(key, String(value)));
  return url.toString();
}

function makeResponseError(url, response, rawText) {
  const detail = rawText ? `: ${rawText.slice(0, 240)}` : '';
  return new Error(`remote fetch failed ${response.status || 'UNKNOWN'} ${response.statusText || ''} for ${url}${detail}`);
}

async function fetchRawText(fetchImpl, url) {
  const response = await fetchImpl(url, { headers: { Accept: 'application/json, application/geo+json' } });
  const rawText = await response.text();
  if (!response.ok) throw makeResponseError(url, response, rawText);
  return rawText;
}

function parseJson(rawText, label) {
  try {
    return JSON.parse(rawText);
  } catch (error) {
    throw new Error(`${label} returned invalid JSON: ${error.message}`);
  }
}

function assertFeatureCollection(value, label) {
  if (!value || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) {
    throw new Error(`${label} is not a GeoJSON FeatureCollection`);
  }
}

function geometryTypes(features) {
  return [...new Set(features.map((feature) => feature?.geometry?.type).filter(Boolean))].sort();
}

function assertGeometryGate(features, expectedGeometryTypes = []) {
  const observed = geometryTypes(features);
  const unexpected = observed.filter((type) => !expectedGeometryTypes.includes(type));
  if (expectedGeometryTypes.length && unexpected.length) {
    throw new Error(`geometry gate failed; unexpected geometry types: ${unexpected.join(', ')}`);
  }
  return observed;
}

function walkPositions(value, visit) {
  if (!Array.isArray(value)) return;
  if (value.length >= 2 && value.every((item) => typeof item === 'number')) {
    visit(value);
    return;
  }
  for (const item of value) walkPositions(item, visit);
}

function assertWgs84Coordinates(features) {
  for (let featureIndex = 0; featureIndex < features.length; featureIndex += 1) {
    const geometry = features[featureIndex]?.geometry;
    if (!geometry?.coordinates) continue;
    walkPositions(geometry.coordinates, (position) => {
      const [lon, lat] = position;
      if (!Number.isFinite(lon) || !Number.isFinite(lat) || lon < -180 || lon > 180 || lat < -90 || lat > 90) {
        throw new Error(`CRS gate failed at feature ${featureIndex}: coordinate is not bounded WGS84 lon/lat`);
      }
    });
  }
}

function assertStableIdentity(features, stableIdField) {
  if (!stableIdField) throw new Error('identity gate requires a stableIdField');
  const seen = new Set();
  for (let index = 0; index < features.length; index += 1) {
    const value = features[index]?.properties?.[stableIdField];
    if (value === null || value === undefined || String(value).trim() === '') {
      throw new Error(`identity gate failed; feature ${index} missing ${stableIdField}`);
    }
    const id = String(value);
    if (seen.has(id)) throw new Error(`identity gate failed; duplicate ${stableIdField}: ${id}`);
    seen.add(id);
  }
  return seen.size;
}

function certificationReport(source, count, observedGeometryTypes, pageCount) {
  return Object.freeze({
    status: 'PASS',
    scope: Object.freeze({
      providerId: source.providerId,
      sourceId: source.sourceId,
      protocol: source.protocol,
      fetchedFeatureCount: count,
      fetchedPageCount: pageCount,
      outputCrs: source.outputCrs,
    }),
    gates: Object.freeze({
      schema: 'PASS',
      count: 'PASS',
      geometry: 'PASS',
      crs: 'PASS',
      identity: 'PASS',
      provenance: 'PASS',
    }),
    observedGeometryTypes: Object.freeze(observedGeometryTypes),
    providerRuntimeCertification: source.certification,
  });
}

async function acquireArcGisFeatureLayer(source, options) {
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  if (typeof fetchImpl !== 'function') throw new Error('online acquisition requires fetch');
  if (!globalThis.crypto?.subtle) throw new Error('online acquisition requires Web Crypto SHA-256');

  const where = options.where || '1=1';
  const outFields = options.outFields || '*';
  const pageSize = Number(source.pageSize || 1000);
  if (!Number.isInteger(pageSize) || pageSize <= 0) throw new Error('source pageSize must be a positive integer');

  const countUrl = buildUrl(source.endpoint, { f: 'json', returnCountOnly: true, where });
  const rawCount = await fetchRawText(fetchImpl, countUrl);
  const countPayload = parseJson(rawCount, 'count query');
  const expectedCount = Number(countPayload.count);
  if (!Number.isInteger(expectedCount) || expectedCount < 0) throw new Error('count gate failed; provider did not return a non-negative integer count');
  if (source.expectedFeatureCount !== undefined && expectedCount !== source.expectedFeatureCount) {
    throw new Error(`count gate failed; registry expected ${source.expectedFeatureCount}, provider reported ${expectedCount}`);
  }

  const rawPages = [];
  const pageUrls = [];
  const features = [];
  for (let resultOffset = 0; resultOffset < expectedCount; resultOffset += pageSize) {
    const pageUrl = buildUrl(source.endpoint, {
      f: 'geojson',
      orderByFields: `${source.stableIdField} ASC`,
      outFields,
      outSR: 4326,
      resultOffset,
      resultRecordCount: pageSize,
      returnGeometry: true,
      where,
    });
    const rawPage = await fetchRawText(fetchImpl, pageUrl);
    const page = parseJson(rawPage, `page at offset ${resultOffset}`);
    assertFeatureCollection(page, `page at offset ${resultOffset}`);
    rawPages.push(rawPage);
    pageUrls.push(pageUrl);
    features.push(...page.features);
  }

  if (features.length !== expectedCount) {
    throw new Error(`count gate failed; provider count=${expectedCount}, fetched=${features.length}`);
  }

  const observedGeometryTypes = assertGeometryGate(features, source.expectedGeometryTypes || []);
  assertWgs84Coordinates(features);
  assertStableIdentity(features, source.stableIdField);

  const mergedGeojson = { type: 'FeatureCollection', features };
  const normalizedGeojsonText = JSON.stringify(mergedGeojson);
  const rawResponses = Object.freeze([rawCount, ...rawPages]);
  const snapshotSha256 = await sha256Text(frameRawTexts(rawResponses));
  if (!snapshotSha256) throw new Error('snapshot hash gate failed');

  const queryReceipt = Object.freeze({
    schemaVersion: '1.0.0',
    providerId: source.providerId,
    sourceId: source.sourceId,
    protocol: source.protocol,
    countUrl,
    pageUrls: Object.freeze(pageUrls),
    where,
    outFields,
    requestedOutputCrs: source.outputCrs,
    sourceNativeCrs: source.sourceNativeCrs,
    stableIdField: source.stableIdField,
    pageSize,
  });
  const queryReceiptSha256 = await sha256StableJson(queryReceipt);
  if (!queryReceiptSha256) throw new Error('query receipt hash gate failed');

  const retrievalUtc = options.retrievalUtc || new Date().toISOString();
  const sourceManifest = createSourceManifest({
    sourceId: source.sourceId,
    providerId: source.providerId,
    sourceClass: source.protocol,
    hrefManifestation: source.endpoint,
    crs: source.outputCrs,
    sourceNativeCrs: source.sourceNativeCrs,
    retrievalUtc,
    queryReceiptSha256,
    snapshotSha256,
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
  });

  const layer = await ingestGeoJSONText(normalizedGeojsonText, {
    sourceId: `remote:${source.sourceId}:snapshot:${snapshotSha256}`,
    layerId: `layer:${source.sourceId}:snapshot:${snapshotSha256}`,
    fileName: source.label,
    nativeCrs: 'RFC7946/WGS84',
    displayCrs: source.outputCrs,
    sourceManifestation: 'remote-query-normalized-geojson',
    transformHistory: source.sourceNativeCrs === source.outputCrs ? [] : [`provider outSR transform ${source.sourceNativeCrs} → ${source.outputCrs}`],
    provenance: {
      providerId: source.providerId,
      registrySourceId: source.sourceId,
      queryReceiptSha256,
      sourceSnapshotSha256: snapshotSha256,
      sourceNativeCrs: source.sourceNativeCrs,
      canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
      retrievalUtc,
    },
    validationStatus: 'PASS',
  });

  return Object.freeze({
    acquisitionMethod: 'online',
    sourceDefinition: source,
    rawResponses,
    normalizedGeojsonText,
    geojson: layer.geojson,
    manifest: layer.manifest,
    sourceManifest,
    queryReceipt,
    queryReceiptSha256,
    snapshotSha256,
    certification: certificationReport(source, expectedCount, observedGeometryTypes, rawPages.length),
  });
}

export async function acquireOnlineSource(sourceId, options = {}) {
  const source = getOnlineSourceDefinition(sourceId);
  const adapter = SOURCE_PROTOCOL_ADAPTERS[source.protocol];
  if (!adapter) throw new Error(`no protocol adapter registered for ${source.protocol}`);
  if (source.runtimeStatus !== 'IMPLEMENTED' || adapter.runtimeStatus !== 'IMPLEMENTED') {
    throw new Error(`source ${sourceId} is registry-only; runtime path remains ${source.runtimeStatus}`);
  }
  if (source.protocol === 'arcgis-feature-layer-geojson') return acquireArcGisFeatureLayer(source, options);
  throw new Error(`protocol adapter ${source.protocol} is not implemented`);
}

import { createLayerManifest } from './contracts';
import { sha256Text } from './integrity';

function geometryTypeSet(geojson) {
  const types = new Set();
  for (const feature of geojson.features || []) {
    if (feature?.geometry?.type) types.add(feature.geometry.type);
  }
  return [...types].sort();
}

function coordinateDimensions(value, state = { z: false, m: false }) {
  if (!Array.isArray(value)) return state;
  if (value.length && value.every((item) => typeof item === 'number')) {
    if (value.length >= 3) state.z = true;
    if (value.length >= 4) state.m = true;
    return state;
  }
  for (const item of value) coordinateDimensions(item, state);
  return state;
}

function validateFeatureCollection(value) {
  if (!value || value.type !== 'FeatureCollection' || !Array.isArray(value.features)) {
    throw new Error('GeoJSON ingestion requires a FeatureCollection');
  }
  for (let index = 0; index < value.features.length; index += 1) {
    const feature = value.features[index];
    if (!feature || feature.type !== 'Feature') throw new Error(`features[${index}] is not a GeoJSON Feature`);
    if (feature.geometry !== null && (!feature.geometry || typeof feature.geometry.type !== 'string')) {
      throw new Error(`features[${index}].geometry is invalid`);
    }
  }
  return value;
}

export async function ingestGeoJSONText(rawText, options = {}) {
  if (typeof rawText !== 'string') throw new Error('raw GeoJSON must be a string');
  let parsed;
  try {
    parsed = JSON.parse(rawText);
  } catch (error) {
    throw new Error(`invalid JSON: ${error.message}`);
  }
  const geojson = validateFeatureCollection(parsed);
  const dimensions = { z: false, m: false };
  for (const feature of geojson.features) {
    if (feature.geometry?.coordinates) coordinateDimensions(feature.geometry.coordinates, dimensions);
  }
  const byteSha256 = await sha256Text(rawText);
  if (!byteSha256 && (!options.sourceId || !options.layerId)) {
    throw new Error('Web Crypto SHA-256 unavailable; explicit stable sourceId and layerId are required');
  }
  const sourceId = options.sourceId || `upload:${byteSha256}`;
  const layerId = options.layerId || `layer:${byteSha256}`;
  const ingestionUtc = options.ingestionUtc || new Date().toISOString();

  const manifest = createLayerManifest({
    layerId,
    sourceId,
    titleRaw: options.fileName || 'Uploaded GeoJSON',
    kind: 'vector',
    rawFormat: 'GeoJSON',
    nativeCrs: options.nativeCrs || 'RFC7946/WGS84',
    displayCrs: options.displayCrs || 'EPSG:4326',
    geometryTypes: geometryTypeSet(geojson),
    preservesZ: dimensions.z,
    preservesM: dimensions.m,
    byteSha256,
    featureCount: geojson.features.length,
    transformHistory: options.transformHistory || [],
    provenance: {
      sourceManifestation: options.sourceManifestation || 'local-upload',
      fileNameRaw: options.fileName || null,
      ingestionUtc,
      ...(options.provenance || {}),
    },
    validationStatus: options.validationStatus || (byteSha256 ? 'PASS' : 'PROVISIONAL'),
  });

  return Object.freeze({ rawText, geojson, manifest });
}

export async function ingestGeoJSONFile(file) {
  if (!file || typeof file.text !== 'function') throw new Error('a readable File is required');
  return ingestGeoJSONText(await file.text(), { fileName: file.name });
}

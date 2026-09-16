export const GIS_SCHEMA_VERSION = '1.0.0';

export const RENDER_MODES = Object.freeze(['2d', '3d']);
export const LAYER_KINDS = Object.freeze(['vector', 'raster', 'terrain', '3d-tiles', 'tile']);

const CANONICAL_EQUIVALENCE_FIELDS = Object.freeze([
  'view.center',
  'view.groundResolutionM',
  'view.bearing',
  'view.aoi',
  'activeLayerIds',
  'layerState',
  'selectedFeatureIds',
  'imagerySelection',
  'terrainSourceId',
  'time',
  'filters',
  'displayCrs',
  'provenanceRefs',
]);

const RENDERER_LOCAL_FIELDS = Object.freeze({
  '2d': ['tileCache', 'symbolCollisionState', 'screenPixelState'],
  '3d': ['atmosphere', 'globeLighting', 'terrainOcclusion', 'tilesetLodState'],
});

function assertFinite(value, label) {
  if (!Number.isFinite(value)) throw new Error(`${label} must be finite`);
  return value;
}

function assertStableId(value, label) {
  if (value === null || value === undefined || String(value).trim() === '') {
    throw new Error(`${label} requires a non-empty stable identifier`);
  }
  return String(value);
}

function uniqueStableIds(values, label) {
  const result = [];
  const seen = new Set();
  for (const value of values || []) {
    const id = assertStableId(value, label);
    if (seen.has(id)) throw new Error(`duplicate ${label}: ${id}`);
    seen.add(id);
    result.push(id);
  }
  return result;
}

function normalizeCenter(center = {}) {
  const lon = assertFinite(Number(center.lon), 'view.center.lon');
  const lat = assertFinite(Number(center.lat), 'view.center.lat');
  if (lon < -180 || lon > 180) throw new Error('view.center.lon outside [-180, 180]');
  if (lat < -90 || lat > 90) throw new Error('view.center.lat outside [-90, 90]');
  return { lon, lat };
}

export function createCanonicalMapState(input = {}) {
  const mode = input.mode || '2d';
  if (!RENDER_MODES.includes(mode)) throw new Error(`unsupported render mode: ${mode}`);

  const view = input.view || {};
  const groundResolutionM = assertFinite(Number(view.groundResolutionM ?? 1000), 'view.groundResolutionM');
  if (groundResolutionM <= 0) throw new Error('view.groundResolutionM must be > 0');

  const bearing = assertFinite(Number(view.bearing ?? 0), 'view.bearing');
  const activeLayerIds = uniqueStableIds(input.activeLayerIds, 'activeLayerId');
  const selectedFeatureIds = uniqueStableIds(input.selectedFeatureIds, 'selectedFeatureId');

  const layerState = { ...(input.layerState || {}) };
  for (const layerId of Object.keys(layerState)) {
    if (!activeLayerIds.includes(layerId)) {
      throw new Error(`layerState references inactive layerId: ${layerId}`);
    }
  }

  return Object.freeze({
    schemaVersion: GIS_SCHEMA_VERSION,
    mode,
    view: Object.freeze({
      center: Object.freeze(normalizeCenter(view.center || { lon: -66.4, lat: 18.22 })),
      groundResolutionM,
      bearing,
      requestedPitch: assertFinite(Number(view.requestedPitch ?? 0), 'view.requestedPitch'),
      aoi: view.aoi ?? null,
    }),
    activeLayerIds: Object.freeze(activeLayerIds),
    layerState: Object.freeze(layerState),
    selectedFeatureIds: Object.freeze(selectedFeatureIds),
    imagerySelection: input.imagerySelection ?? null,
    terrainSourceId: input.terrainSourceId ?? null,
    time: Object.freeze({ ...(input.time || {}) }),
    filters: Object.freeze({ ...(input.filters || {}) }),
    displayCrs: input.displayCrs || 'EPSG:4326',
    provenanceRefs: Object.freeze(uniqueStableIds(input.provenanceRefs, 'provenanceRef')),
  });
}

export function createLayerManifest(input = {}) {
  const layerId = assertStableId(input.layerId, 'layerId');
  const sourceId = assertStableId(input.sourceId, 'sourceId');
  if (!LAYER_KINDS.includes(input.kind)) throw new Error(`unsupported layer kind: ${input.kind}`);

  return Object.freeze({
    schemaVersion: GIS_SCHEMA_VERSION,
    layerId,
    sourceId,
    titleRaw: String(input.titleRaw ?? ''),
    titleNormalized: input.titleNormalized ?? null,
    kind: input.kind,
    rawFormat: String(input.rawFormat ?? 'unknown'),
    nativeCrs: input.nativeCrs ?? null,
    displayCrs: input.displayCrs || 'EPSG:4326',
    geometryTypes: Object.freeze([...(input.geometryTypes || [])]),
    preservesZ: Boolean(input.preservesZ),
    preservesM: Boolean(input.preservesM),
    temporalExtent: input.temporalExtent ?? null,
    byteSha256: input.byteSha256 ?? null,
    featureCount: input.featureCount ?? null,
    bbox: input.bbox ?? null,
    transformHistory: Object.freeze([...(input.transformHistory || [])]),
    provenance: Object.freeze({ ...(input.provenance || {}) }),
    validationStatus: input.validationStatus || 'PROVISIONAL',
  });
}

export function compareRendererEquivalence(stateAInput, stateBInput, options = {}) {
  const a = createCanonicalMapState(stateAInput);
  const b = createCanonicalMapState(stateBInput);
  const tolerance = {
    centerDegrees: options.centerDegrees ?? 1e-7,
    groundResolutionM: options.groundResolutionM ?? 0.01,
    bearingDegrees: options.bearingDegrees ?? 1e-6,
  };

  const failures = [];
  const close = (x, y, maxDelta) => Math.abs(x - y) <= maxDelta;
  if (!close(a.view.center.lon, b.view.center.lon, tolerance.centerDegrees) ||
      !close(a.view.center.lat, b.view.center.lat, tolerance.centerDegrees)) failures.push('view.center');
  if (!close(a.view.groundResolutionM, b.view.groundResolutionM, tolerance.groundResolutionM)) failures.push('view.groundResolutionM');
  if (!close(a.view.bearing, b.view.bearing, tolerance.bearingDegrees)) failures.push('view.bearing');

  const exactFields = [
    ['view.aoi', a.view.aoi, b.view.aoi],
    ['activeLayerIds', a.activeLayerIds, b.activeLayerIds],
    ['layerState', a.layerState, b.layerState],
    ['selectedFeatureIds', a.selectedFeatureIds, b.selectedFeatureIds],
    ['imagerySelection', a.imagerySelection, b.imagerySelection],
    ['terrainSourceId', a.terrainSourceId, b.terrainSourceId],
    ['time', a.time, b.time],
    ['filters', a.filters, b.filters],
    ['displayCrs', a.displayCrs, b.displayCrs],
    ['provenanceRefs', a.provenanceRefs, b.provenanceRefs],
  ];
  for (const [name, left, right] of exactFields) {
    if (JSON.stringify(left) !== JSON.stringify(right)) failures.push(name);
  }

  const aOnly = RENDERER_LOCAL_FIELDS[a.mode] || [];
  const bOnly = RENDERER_LOCAL_FIELDS[b.mode] || [];
  const intersection = [...CANONICAL_EQUIVALENCE_FIELDS];
  const symmetricDifference = [...new Set([...aOnly, ...bOnly])].filter((field) => !(aOnly.includes(field) && bOnly.includes(field)));
  const union = [...new Set([...intersection, ...aOnly, ...bOnly])];

  return Object.freeze({
    status: failures.length === 0 ? 'PASS' : 'FAIL',
    failures: Object.freeze(failures),
    intersection: Object.freeze(intersection),
    aOnly: Object.freeze([...aOnly]),
    bOnly: Object.freeze([...bOnly]),
    union: Object.freeze(union),
    symmetricDifference: Object.freeze(symmetricDifference),
    pixelEquivalenceClaimed: false,
  });
}

export function switchRenderMode(stateInput, mode) {
  const state = createCanonicalMapState(stateInput);
  return createCanonicalMapState({ ...state, mode });
}

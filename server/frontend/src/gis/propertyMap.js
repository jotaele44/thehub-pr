// Property Map helpers (Phase 5, P5-A): pure functions over the spatial
// features contract (federation-spatial-features-v1, server/backend/spatial_api.py)
// and the TIGERweb municipio boundary layer the GIS workspace already acquires.
//
// Rules this module enforces, not just documents:
// * a point is styled by the precision its producer declared; a representative
//   point is drawn hollow and labelled, never as an observed point;
// * category colours are assigned from the categories the store holds, in
//   sorted order, so symbology comes from Federation data;
// * a recorded municipality value is joined to a boundary only on an exact name
//   match after accent, case and "Municipio" folding. Anything else (a region,
//   "Barceloneta/Arecibo", "Puerto Rico") is listed as recorded, never split,
//   geocoded or guessed.

export const SPATIAL_CONTRACT = 'federation-spatial-features-v1';
export const MUNICIPIO_BOUNDARY_SOURCE_ID = 'census-tigerweb-pr-municipios-2025';
export const EARTH_RADIUS_M = 6371008.8;
const SQUARE_METRES_PER_ACRE = 4046.8564224;

export const PRECISION_STYLES = Object.freeze({
  OBSERVED_POINT: Object.freeze({
    label: 'Observed point', marker: 'solid',
    description: 'The producer recorded this position as observed or authoritative.',
  }),
  INTERPRETED_POINT: Object.freeze({
    label: 'Interpreted point', marker: 'ringed',
    description: 'A position the producer derived (geocoded, inferred or linked to an asset), not observed directly.',
  }),
  REPRESENTATIVE_POINT: Object.freeze({
    label: 'Representative point', marker: 'hollow',
    description: 'A stand-in position, such as a municipio centroid. The record is not located at this point.',
  }),
  AREA_REFERENCE: Object.freeze({
    label: 'Area reference', marker: 'outline',
    description: 'The record names an area (a municipio). The area is outlined; no point is placed inside it.',
  }),
});

export function precisionStyle(precision) {
  return PRECISION_STYLES[precision] || null;
}

// Okabe-Ito first (colour-blind safe), then a distinct qualitative tail. Colour
// is never the only carrier of meaning: every category is also named in the
// legend, the record list and the details panel.
export const CATEGORY_PALETTE = Object.freeze([
  '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#999999',
  '#8DD3C7', '#BEBADA', '#FB8072', '#80B1D3', '#FDB462', '#B3DE69', '#FCCDE5', '#BC80BD',
]);
const FALLBACK_COLOR = '#9ca3af';

export function categoryColors(categories = []) {
  const names = [...new Set(categories.map((entry) => (typeof entry === 'string' ? entry : entry?.category)).filter(Boolean))].sort();
  return Object.fromEntries(names.map((name, index) => [name, CATEGORY_PALETTE[index % CATEGORY_PALETTE.length]]));
}

function categoryColorExpression(colors) {
  const pairs = Object.entries(colors).flat();
  return pairs.length ? ['match', ['get', 'category'], ...pairs, FALLBACK_COLOR] : FALLBACK_COLOR;
}

// MapLibre circle paint: solid observed, ringed interpreted, hollow representative.
export function featurePaint(colors) {
  const color = categoryColorExpression(colors);
  const byPrecision = (observed, interpreted, representative) => (
    ['match', ['get', 'geometry_precision'], 'OBSERVED_POINT', observed, 'INTERPRETED_POINT', interpreted, representative]
  );
  return {
    'circle-radius': byPrecision(5, 6, 7),
    'circle-color': color,
    'circle-opacity': byPrecision(0.95, 0.55, 0),
    'circle-stroke-width': byPrecision(1, 3, 2),
    'circle-stroke-color': byPrecision('#ffffff', '#ffffff', color),
  };
}

export function featureCollection(features = []) {
  return { type: 'FeatureCollection', features };
}

export function visibleFeatures(features = [], hiddenCategories = new Set()) {
  return features.filter((item) => !hiddenCategories.has(item.properties?.category));
}

export function foldPlaceName(text) {
  return String(text ?? '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/ municipio$/, '');
}

export function boundaryName(properties = {}) {
  return properties?.BASENAME || properties?.NAME || properties?.name || null;
}

function ringContains(ring, x, y) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygonContains(rings, x, y) {
  if (!rings?.length || !ringContains(rings[0], x, y)) return false;
  return !rings.slice(1).some((hole) => ringContains(hole, x, y));
}

export function geometryContains(geometry, lon, lat) {
  if (geometry?.type === 'Polygon') return polygonContains(geometry.coordinates, lon, lat);
  if (geometry?.type === 'MultiPolygon') return geometry.coordinates.some((rings) => polygonContains(rings, lon, lat));
  return false;
}

// The municipio whose boundary contains the point, or null. Null is reported
// as "not determined", never as a nearest municipio.
export function municipalityAt(boundaries, lon, lat) {
  const hit = (boundaries?.features || []).find((item) => geometryContains(item.geometry, lon, lat));
  return hit ? boundaryName(hit.properties) : null;
}

// Group area references by (producer, stream, category) so cases and their
// observations, or two producers, are never summed together.
export function areaReferenceGroups(references = []) {
  const groups = new Map();
  for (const ref of references) {
    const key = `${ref.producer}|${ref.stream}|${ref.category}`;
    if (!groups.has(key)) groups.set(key, { key, producer: ref.producer, stream: ref.stream, category: ref.category, references: [] });
    groups.get(key).references.push(ref);
  }
  return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key));
}

export function objectTypesOf(references = []) {
  return [...new Set(references.flatMap((ref) => Object.keys(ref.object_type_counts || {})))].sort();
}

function referenceCount(ref, objectType) {
  return objectType ? (ref.object_type_counts?.[objectType] || 0) : ref.count;
}

// Join recorded municipality values to boundary features by folded name. With
// no boundary layer every value is unmatched and the outline is empty.
export function joinAreaReferences(references = [], boundaries = null, { objectType = null } = {}) {
  const index = new Map();
  for (const item of boundaries?.features || []) {
    const name = boundaryName(item.properties);
    if (!name) continue;
    for (const candidate of [item.properties?.BASENAME, item.properties?.NAME, item.properties?.name]) {
      if (candidate) index.set(foldPlaceName(candidate), { name, feature: item });
    }
  }
  const matched = new Map();
  const unmatched = [];
  for (const ref of references) {
    const count = referenceCount(ref, objectType);
    if (!count) continue;
    const hit = boundaries ? index.get(foldPlaceName(ref.municipality_as_recorded)) : undefined;
    if (!hit) {
      unmatched.push({ value: ref.municipality_as_recorded, count });
      continue;
    }
    const entry = matched.get(hit.name) || { name: hit.name, count: 0, recordedAs: [], feature: hit.feature };
    entry.count += count;
    entry.recordedAs.push(ref.municipality_as_recorded);
    matched.set(hit.name, entry);
  }
  const rows = [...matched.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  return {
    matched: rows.map(({ feature, ...rest }) => rest),
    unmatched: unmatched.sort((a, b) => b.count - a.count || a.value.localeCompare(b.value)),
    matchedTotal: rows.reduce((sum, row) => sum + row.count, 0),
    unmatchedTotal: unmatched.reduce((sum, row) => sum + row.count, 0),
    outline: featureCollection(rows.map((row) => ({
      type: 'Feature',
      geometry: row.feature.geometry,
      properties: { municipio: row.name, reference_count: row.count, geometry_precision: 'AREA_REFERENCE' },
    }))),
  };
}

const toRadians = (degrees) => (degrees * Math.PI) / 180;

export function bboxAreaM2([minLon, minLat, maxLon, maxLat]) {
  return EARTH_RADIUS_M ** 2 * toRadians(maxLon - minLon) * Math.abs(Math.sin(toRadians(maxLat)) - Math.sin(toRadians(minLat)));
}

// Spherical cap: the exact area of a geodesic circle on the reference sphere.
export function circleAreaM2(radiusM) {
  return 2 * Math.PI * EARTH_RADIUS_M ** 2 * (1 - Math.cos(radiusM / EARTH_RADIUS_M));
}

export function describeArea(squareMetres) {
  return {
    squareMetres,
    hectares: squareMetres / 10000,
    acres: squareMetres / SQUARE_METRES_PER_ACRE,
    squareKilometres: squareMetres / 1e6,
  };
}

export function formatArea(squareMetres) {
  const area = describeArea(squareMetres);
  const format = (value) => value.toLocaleString('en-US', { maximumFractionDigits: value >= 100 ? 0 : 2 });
  return `${format(area.acres)} acres · ${format(area.hectares)} ha · ${format(area.squareKilometres)} km²`;
}

// "minLon,minLat,maxLon,maxLat" -> [numbers]; throws on anything else (same rule as the API).
export function parseBboxText(text) {
  const values = String(text || '').split(',').map((value) => Number(value.trim()));
  const [minLon, minLat, maxLon, maxLat] = values;
  if (values.length !== 4 || values.some((value) => !Number.isFinite(value))
      || !(minLon >= -180 && minLon < maxLon && maxLon <= 180 && minLat >= -90 && minLat < maxLat && maxLat <= 90)) {
    throw new Error('The AOI must be minLon,minLat,maxLon,maxLat within WGS84 bounds.');
  }
  return values;
}

// A closed ring approximating the geodesic circle, for drawing the intel radius.
export function circlePolygon(lon, lat, radiusM, steps = 64) {
  const angular = radiusM / EARTH_RADIUS_M;
  const phi = toRadians(lat);
  const lambda = toRadians(lon);
  const ring = [];
  for (let i = 0; i <= steps; i += 1) {
    const bearing = (2 * Math.PI * i) / steps;
    const phi2 = Math.asin(Math.sin(phi) * Math.cos(angular) + Math.cos(phi) * Math.sin(angular) * Math.cos(bearing));
    const lambda2 = lambda + Math.atan2(Math.sin(bearing) * Math.sin(angular) * Math.cos(phi),
      Math.cos(angular) - Math.sin(phi) * Math.sin(phi2));
    ring.push([(lambda2 * 180) / Math.PI, (phi2 * 180) / Math.PI]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: { radius_m: radiusM } };
}

// What the layer provenance inspector shows for an acquired boundary layer.
export function boundaryProvenance(layer, source, provider) {
  if (!layer) return null;
  return {
    provider: provider?.label || source?.providerId || null,
    authority: provider?.authority || null,
    sourceId: source?.sourceId || null,
    registryCertification: source?.certification || null,
    acquisitionStatus: layer.certification?.status || null,
    snapshotSha256: layer.snapshotSha256 || null,
    queryReceiptSha256: layer.queryReceiptSha256 || null,
    retrievedAt: layer.sourceManifest?.retrievalUtc || null,
    featureCount: layer.manifest?.featureCount ?? layer.geojson?.features?.length ?? null,
    crs: source?.outputCrs || null,
  };
}

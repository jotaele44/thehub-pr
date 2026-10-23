// Digital Twin helpers (Phase 5, P5-B): pure functions over the spatial
// features contract (federation-spatial-features-v1). Time comes from each
// record's own span (time_start/time_end, computed by the Hub at the precision
// the producer declared); undated records are counted, never placed in time.
// Counters say what they count and why a zero is a zero.
import { SPATIAL_CONTRACT } from './propertyMap';

export const DIGITAL_TWIN_PANELS = Object.freeze([
  Object.freeze({ id: 'perspective', label: 'Perspective' }),
  Object.freeze({ id: 'ortho', label: 'Ortho / top-down' }),
  Object.freeze({ id: 'overhead', label: 'Overhead imagery' }),
  Object.freeze({ id: 'details', label: 'Details' }),
]);
export const TIME_WINDOWS = Object.freeze([
  Object.freeze({ id: 'cumulative', label: 'Everything up to the cursor', days: null }),
  Object.freeze({ id: 'year', label: 'One year before the cursor', days: 365 }),
  Object.freeze({ id: 'month', label: '30 days before the cursor', days: 30 }),
]);
const DAY_MS = 86_400_000;
const EARTH_RADIUS_M = 6371008.8;

export function panelFrom(searchParams) {
  const value = searchParams.get('panel');
  return DIGITAL_TWIN_PANELS.some((panel) => panel.id === value) ? value : null;
}

export function timeBounds(extent) {
  if (!extent?.start || !extent?.end) return null;
  return { start: Date.parse(extent.start), end: Date.parse(extent.end) };
}

// [from, to] in epoch ms for a cursor and window choice; null means no time filter.
export function timeWindow(cursor, windowId, bounds) {
  if (!bounds || !Number.isFinite(cursor)) return null;
  const choice = TIME_WINDOWS.find((item) => item.id === windowId) || TIME_WINDOWS[0];
  return [choice.days ? cursor - choice.days * DAY_MS : bounds.start, cursor];
}

// true / false for a dated record, null for an undated one.
export function activeIn(properties, window) {
  if (!properties?.time_start) return null;
  if (!window) return true;
  const start = Date.parse(properties.time_start);
  const end = Date.parse(properties.time_end || properties.time_start);
  return start <= window[1] && end >= window[0];
}

export function filterByTime(features, window, { showUndated = true } = {}) {
  const visible = [];
  let undated = 0;
  let outside = 0;
  for (const item of features) {
    const active = activeIn(item.properties, window);
    if (active === null) {
      undated += 1;
      if (showUndated) visible.push(item);
    } else if (active) {
      visible.push(item);
    } else {
      outside += 1;
    }
  }
  return { visible, undated, outside };
}

// Findings are the OVNIS research records exported as entity_type "finding".
export function findingFeatures(features) {
  return features.filter((item) => item.properties?.category === 'finding');
}

// LIVE needs a declared cadence (hub.epistemic.temporal_state_at); CURRENT is
// inside a declared validity window. Neither is guessed from recency.
export function liveCounts(features) {
  const counts = { LIVE: 0, CURRENT: 0 };
  for (const item of features) {
    const state = item.properties?.temporal_state;
    if (state in counts) counts[state] += 1;
  }
  return counts;
}

export function liveStatement(counts) {
  if (counts.LIVE) return `${counts.LIVE} live (a declared cadence, observed within it)`;
  if (counts.CURRENT) return `No live feed; ${counts.CURRENT} current (inside a declared validity window)`;
  return 'No producer declares a live cadence, and no mapped record is inside a current validity window.';
}

export function findingStatement(count) {
  return count
    ? `${count} finding${count === 1 ? '' : 's'} with declared geometry`
    : 'No finding carries geometry: the OVNIS findings ledger records none yet.';
}

function exportContext({ generatedAt, window, filters, counts, layers }) {
  return {
    contract: SPATIAL_CONTRACT,
    generated_at: generatedAt,
    time_window: window ? { from: new Date(window[0]).toISOString(), to: new Date(window[1]).toISOString() } : null,
    filters,
    counts,
    layers,
    certification: 'NOT_CERTIFIED',
  };
}

// GeoJSON of the visible records, each keeping its evidence links, with the
// export's own provenance in a top-level member.
export function geojsonExport(features, context) {
  return {
    type: 'FeatureCollection',
    federation_export: exportContext(context),
    features: features.map((item) => ({ type: 'Feature', id: item.id, geometry: item.geometry, properties: item.properties })),
  };
}

export function localMetres(lon, lat, origin) {
  const toRad = Math.PI / 180;
  return [
    (lon - origin.lon) * toRad * EARTH_RADIUS_M * Math.cos(origin.lat * toRad),
    (lat - origin.lat) * toRad * EARTH_RADIUS_M,
  ];
}

function usdString(value) {
  return `"${String(value ?? '').replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, ' ')}"`;
}

function usdNumber(value) {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : '0';
}

const WIDTHS = { OBSERVED_POINT: 10, INTERPRETED_POINT: 12, REPRESENTATIVE_POINT: 14 };

// USD (usda text) of the visible records: one Points prim at local east/north
// metres about the origin, z = 0 (terrain heights are not exported), with each
// record's evidence id, category, producer and declared precision as primvars.
export function usdaExport(features, { origin, ...context }) {
  const meta = exportContext(context);
  const points = features.map((item) => {
    const [x, y] = localMetres(item.geometry.coordinates[0], item.geometry.coordinates[1], origin);
    return `(${usdNumber(x)}, ${usdNumber(y)}, 0)`;
  });
  const primvar = (name, values) => `    string[] primvars:${name} = [${values.map(usdString).join(', ')}] (\n        interpolation = "vertex"\n    )`;
  const props = features.map((item) => item.properties);
  const layerData = [
    `string federation_contract = ${usdString(meta.contract)}`,
    `string generated_at = ${usdString(meta.generated_at)}`,
    `string certification = ${usdString(meta.certification)}`,
    `string horizontal_frame = ${usdString('local east/north metres about the origin (equirectangular approximation)')}`,
    `double origin_lon = ${usdNumber(origin.lon)}`,
    `double origin_lat = ${usdNumber(origin.lat)}`,
    `string vertical = ${usdString('none: z = 0; terrain heights are not exported')}`,
    `string time_window = ${usdString(meta.time_window ? `${meta.time_window.from}/${meta.time_window.to}` : 'none')}`,
    `int record_count = ${features.length}`,
  ];
  return [
    '#usda 1.0',
    '(',
    '    defaultPrim = "FederationRecords"',
    `    doc = ${usdString('TheHub Digital Twin export of Hub-held records. Not certified; provenance per record is in primvars:evidence_id.')}`,
    '    metersPerUnit = 1',
    '    upAxis = "Z"',
    '    customLayerData = {',
    ...layerData.map((line) => `        ${line}`),
    '    }',
    ')',
    '',
    'def Points "FederationRecords"',
    '{',
    `    point3f[] points = [${points.join(', ')}]`,
    `    float[] widths = [${props.map((p) => WIDTHS[p.geometry_precision] || 10).join(', ')}] (\n        interpolation = "vertex"\n    )`,
    primvar('evidence_id', props.map((p) => p.evidence_id)),
    primvar('category', props.map((p) => p.category)),
    primvar('producer', props.map((p) => p.producer)),
    primvar('geometry_precision', props.map((p) => p.geometry_precision)),
    '}',
    '',
  ].join('\n');
}

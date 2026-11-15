// Subsurface separation (TWIN-075/076/077/146, FDX-024; directive §11): "a model
// must never visually masquerade as observed underground geometry". This module
// keeps two groups apart and is pure:
//
//  - DOCUMENTED: what a source documents (SIGE karst, aquifer and watershed
//    outlines, loaded through the registry; Hub-held USGS mineral occurrences).
//    These are surface geometry as published, never a subsurface model.
//  - MODELLED: only records whose producer declared the INTERPRETIVE class. No
//    producer exports one today, so the group is empty and says why.
//
// It also builds a terrain profile along a line from CUDEM heights (one datum,
// gaps kept as gaps) and finds where the line crosses a loaded documented layer.
import { EARTH_RADIUS_M, featurePaint, geometryContains } from './propertyMap';

export const MODELLED_CLASS = 'INTERPRETIVE';
export const MODELLED_LABEL = 'MODELLED — not observed geometry';
export const PROFILE_MIN_SAMPLES = 2;
export const PROFILE_MAX_SAMPLES = 200;

export const DOCUMENTED_LAYERS = Object.freeze([
  Object.freeze({ sourceId: 'pr-sige-sumideros', role: 'Karst sinkholes as outlined by SIGE: surface outlines, not subsurface geometry.' }),
  Object.freeze({ sourceId: 'pr-sige-acuiferos', role: 'Aquifer extents as mapped by SIGE: map extents, not subsurface geometry.' }),
  Object.freeze({ sourceId: 'pr-sige-cuencas', role: 'Watersheds (surface hydrography) as mapped by SIGE.' }),
]);

// Hub record categories that document geology (USGS OFR 98-038 metallic occurrences).
export const DOCUMENTED_HUB_CATEGORIES = Object.freeze(['mineral_occurrence']);

export const GROUP_STYLES = Object.freeze({
  documented: Object.freeze({
    id: 'documented', label: 'Documented', swatch: 'solid', color: '#14b8a6',
    note: 'A source documents this geometry (surface outlines and recorded occurrences).',
  }),
  modelled: Object.freeze({
    id: 'modelled', label: MODELLED_LABEL, swatch: 'hatched', color: '#c084fc',
    note: 'A producer interpreted or modelled this. It was not observed.',
  }),
});

// 'modelled' when the producer declared the INTERPRETIVE class (whatever the
// category), 'documented' for a documented-geology category, else null.
export function groupOf(item) {
  const properties = item?.properties || {};
  if (properties.declared_epistemic_class === MODELLED_CLASS) return 'modelled';
  if (DOCUMENTED_HUB_CATEGORIES.includes(properties.category)) return 'documented';
  return null;
}

// Hub features split by group, each tagged for the map; the rest are counted.
export function splitHubFeatures(features = []) {
  const split = { documented: [], modelled: [], other: 0 };
  for (const item of features) {
    const group = groupOf(item);
    if (!group) {
      split.other += 1;
    } else {
      split[group].push({ ...item, properties: { ...item.properties, group: group.toUpperCase() } });
    }
  }
  return split;
}

// MapLibre circle paint for the Hub points: the precision styling of the
// Property Map, except that every property is switched on the group, so a
// modelled point is a violet ring and cannot inherit a documented style.
export function interpretivePaint(colors) {
  const modelled = {
    'circle-radius': 10,
    'circle-color': 'rgba(0,0,0,0)',
    'circle-opacity': 1,
    'circle-stroke-width': 3,
    'circle-stroke-color': GROUP_STYLES.modelled.color,
  };
  return Object.fromEntries(Object.entries(featurePaint(colors)).map(([property, base]) => [
    property, ['case', ['==', ['get', 'group'], 'MODELLED'], modelled[property], base],
  ]));
}

export function modelledStatement(count) {
  if (!count) {
    return 'No producer exports a modelled or interpretive layer: no record in the Hub store declares the INTERPRETIVE class. '
      + 'Spiderweb\'s committed subsurface models are test fixtures and are not shown.';
  }
  return `${count} record${count === 1 ? '' : 's'} declared INTERPRETIVE by their producer. Each is modelled, never observed geometry.`;
}

// ── Terrain profile ──────────────────────────────────────────────────────────

export function haversineKm([lon1, lat1], [lon2, lat2]) {
  const toRad = Math.PI / 180;
  const dLat = (lat2 - lat1) * toRad;
  const dLon = (lon2 - lon1) * toRad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2;
  return (2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))) / 1000;
}

function unitVector([lon, lat]) {
  const toRad = Math.PI / 180;
  return [Math.cos(lat * toRad) * Math.cos(lon * toRad), Math.cos(lat * toRad) * Math.sin(lon * toRad), Math.sin(lat * toRad)];
}

// `count` points along the great circle from a to b (both included), each with its distance from a.
export function profileSamples(a, b, count = 100) {
  const n = Math.min(PROFILE_MAX_SAMPLES, Math.max(PROFILE_MIN_SAMPLES, Math.round(count)));
  const total = haversineKm(a, b);
  const angle = total * 1000 / EARTH_RADIUS_M;
  const [x1, y1, z1] = unitVector(a);
  const [x2, y2, z2] = unitVector(b);
  const toDeg = 180 / Math.PI;
  return Array.from({ length: n }, (_, index) => {
    const fraction = index / (n - 1);
    if (angle === 0) return { lon: a[0], lat: a[1], km: 0 };
    if (index === 0) return { lon: a[0], lat: a[1], km: 0 };
    if (index === n - 1) return { lon: b[0], lat: b[1], km: total };
    const wa = Math.sin((1 - fraction) * angle) / Math.sin(angle);
    const wb = Math.sin(fraction * angle) / Math.sin(angle);
    const x = wa * x1 + wb * x2;
    const y = wa * y1 + wb * y2;
    const z = wa * z1 + wb * z2;
    return { lon: Math.atan2(y, x) * toDeg, lat: Math.atan2(z, Math.hypot(x, y)) * toDeg, km: fraction * total };
  });
}

// Heights are on one named datum; a sample with no value stays null (a gap).
export function buildProfile(samples, heights, datum) {
  if (!datum) throw new Error('a profile needs a declared vertical datum');
  return Object.freeze({
    datum,
    totalKm: samples.length ? samples[samples.length - 1].km : 0,
    samples: samples.map((sample, index) => ({ ...sample, metres: Number.isFinite(heights[index]) ? heights[index] : null })),
  });
}

export function profileStats(profile) {
  const values = profile.samples.map((sample) => sample.metres).filter((value) => value !== null);
  if (!values.length) return null;
  return { min: Math.min(...values), max: Math.max(...values), withHeight: values.length, gaps: profile.samples.length - values.length };
}

export function profileCsv(profile) {
  const lines = [`distance_km,longitude,latitude,height_m_${profile.datum}`];
  for (const sample of profile.samples) {
    lines.push([sample.km, sample.lon, sample.lat, sample.metres === null ? '' : sample.metres].join(','));
  }
  return `${lines.join('\n')}\n`;
}

// SVG path of the profile (x: distance, y: height, north-up), broken at every gap.
export function profilePath(profile, { width = 640, height = 200, pad = 8 } = {}) {
  const stats = profileStats(profile);
  if (!stats) return { path: '', ...stats };
  const span = stats.max - stats.min || 1;
  const x = (km) => pad + (profile.totalKm ? (km / profile.totalKm) * (width - 2 * pad) : 0);
  const y = (metres) => pad + (1 - (metres - stats.min) / span) * (height - 2 * pad);
  let path = '';
  let open = false;
  for (const sample of profile.samples) {
    if (sample.metres === null) {
      open = false;
    } else {
      path += `${open ? 'L' : 'M'}${x(sample.km).toFixed(1)},${y(sample.metres).toFixed(1)}`;
      open = true;
    }
  }
  return { path, ...stats };
}

// Where the line crosses a loaded documented layer, as intervals between samples.
// The extent is to the sample resolution: it names the first and last sample inside.
export function crossings(profile, layers = []) {
  const found = [];
  for (const layer of layers) {
    let run = null;
    const close = () => {
      if (run) found.push({ layerId: layer.id, label: layer.label, startKm: run.start, endKm: run.end, samples: run.count });
      run = null;
    };
    for (const sample of profile.samples) {
      const inside = (layer.features || []).some((item) => geometryContains(item.geometry, sample.lon, sample.lat));
      if (!inside) close();
      else if (run) { run.end = sample.km; run.count += 1; } else run = { start: sample.km, end: sample.km, count: 1 };
    }
    close();
  }
  return found;
}

// Aircraft tracks supplied by the user (FDX-036/037, TWIN-117): a CSV or GeoJSON file of timestamped positions, parsed
// without guessing. Nothing here is fetched (the Hub does not proxy a live aircraft feed, by decision, and OpenSky's
// CORS is locked to its own origin), and nothing is stored: the tracks live in memory for the check.
//
// What is declared, never assumed: the source, the altitude reference (ellipsoid, mean sea level or barometric) and
// its unit, and, where the reference needs it, the geoid separation or the altitude uncertainty. A row without an
// altitude is rejected, not read as ground level (MISSING DATA is not ZERO). A callsign is a label carried from the
// file, not an identification of an airframe, and a track is not an identity.
//
// Track quality mirrors the vocabulary of the Skywatcher flight corpus (`track_quality`: continuous, gapped,
// sparse_evidence, single_point, with `gap_count`) and its eligibility rule (at least two valid spatial observations,
// `flight_corpus_v4.trajectory_eligibility.minimum_valid_spatial_observations`). Skywatcher assigns its quality from
// the source and the point count; the gap rule below is this workspace's own declared policy, recorded in every result,
// and is a statement about coverage, never about whether a flight is unusual.
import { geodeticToEcef } from './geometry.js';

export const AIRCRAFT_TRACK_CONTRACT = 'sky-aircraft-track-v1';
export const TRACK_QUALITY = Object.freeze(['continuous', 'gapped', 'sparse_evidence', 'single_point']);
export const TRACK_POLICY = Object.freeze({
  // Mirrors Skywatcher: flight_corpus_v4.trajectory_eligibility.minimum_valid_spatial_observations.
  minimumValidObservations: 2,
  // This workspace's own rule: an interval between reports longer than this is a gap and is never interpolated across.
  gapSeconds: 30,
  // Faster than this between two reports is not a plausible aircraft: the segment is treated as a gap, not trusted.
  maxPlausibleSpeedMetresPerSecond: 1000,
  note: 'Policy, not physics: the gap length and the speed bound are this workspace\'s declared choices. Skywatcher assigns track_quality from the source and the point count, not from gaps.',
});

export const MAX_ROWS = 50000;
export const MAX_FILE_CHARACTERS = 8 * 1024 * 1024;
const MAX_LISTED = 50;
const FEET = 0.3048;
const ALTITUDE_REFERENCES = ['ELLIPSOID', 'MSL', 'BAROMETRIC'];

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

// ---- declaration --------------------------------------------------------------------------------------------------

export function validateDeclaration(input) {
  const d = input ?? {};
  const notes = [];
  if (typeof d.source !== 'string' || !d.source.trim()) throw new RangeError('Say where the tracks came from (the source): a track of unknown origin cannot be weighed.');
  if (!ALTITUDE_REFERENCES.includes(d.altitudeReference)) throw new RangeError(`Declare the altitude reference: one of ${ALTITUDE_REFERENCES.join(', ')}. Heights are not guessed.`);
  if (d.altitudeUnits !== 'm' && d.altitudeUnits !== 'ft') throw new RangeError('Declare the altitude unit: m or ft.');
  let geoidSeparationMetres = 0;
  if (d.altitudeReference === 'MSL') {
    if (!finite(d.geoidSeparationMetres) || d.geoidSeparationMetres < -120 || d.geoidSeparationMetres > 100) {
      throw new RangeError('Altitude above mean sea level needs the geoid separation at the place, in metres (between -120 and 100; about -43 m at San Juan), to reach the ellipsoid. It is not guessed.');
    }
    geoidSeparationMetres = d.geoidSeparationMetres;
    notes.push(`Heights above mean sea level were moved to the WGS84 ellipsoid with the geoid separation given (${geoidSeparationMetres} m).`);
  } else if (d.altitudeReference === 'BAROMETRIC') {
    if (!finite(d.altitudeUncertaintyMetres) || d.altitudeUncertaintyMetres <= 0) {
      throw new RangeError('A barometric (pressure) altitude is not a geometric height; declare how far it may be from one (altitudeUncertaintyMetres, more than 0). It is not assumed accurate.');
    }
    if (d.geoidSeparationMetres !== undefined) {
      if (!finite(d.geoidSeparationMetres) || d.geoidSeparationMetres < -120 || d.geoidSeparationMetres > 100) throw new RangeError('The geoid separation must be a number between -120 and 100 metres.');
      geoidSeparationMetres = d.geoidSeparationMetres;
    }
    notes.push('Barometric altitudes are used as heights as given, with the declared uncertainty; a pressure altitude is not a height above the ellipsoid.');
  } else if (d.geoidSeparationMetres !== undefined) {
    notes.push('A geoid separation was given but the heights are already above the ellipsoid, so it was not applied.');
  }
  for (const key of ['altitudeUncertaintyMetres', 'horizontalUncertaintyMetres']) {
    if (d[key] !== undefined && (!finite(d[key]) || d[key] < 0 || d[key] > 100000)) throw new RangeError(`${key} must be a number of metres from 0 to 100000.`);
  }
  let clockOffsetSeconds = 0;
  if (d.clockOffsetSeconds !== undefined) {
    if (!finite(d.clockOffsetSeconds) || Math.abs(d.clockOffsetSeconds) > 86400) throw new RangeError('The clock offset must be a number of seconds within a day (the amount to add to this source\'s times to reach UTC).');
    clockOffsetSeconds = d.clockOffsetSeconds;
    notes.push(`This source's clock was declared to be ${clockOffsetSeconds} s from UTC; every time was shifted by that amount.`);
  } else {
    notes.push('No clock offset was declared for this source; its times are taken as UTC as written.');
  }
  const timeFormat = d.timeFormat ?? 'ISO';
  if (timeFormat !== 'ISO' && timeFormat !== 'EPOCH_SECONDS') throw new RangeError('The time format must be ISO (with a UTC designator or offset) or EPOCH_SECONDS.');
  const policy = { ...TRACK_POLICY };
  if (d.gapSeconds !== undefined) {
    if (!finite(d.gapSeconds) || d.gapSeconds <= 0 || d.gapSeconds > 3600) throw new RangeError('The gap length must be from more than 0 to 3600 seconds.');
    policy.gapSeconds = d.gapSeconds;
    notes.push(`The gap length was set to ${d.gapSeconds} s instead of the default ${TRACK_POLICY.gapSeconds} s.`);
  }
  return Object.freeze({
    source: d.source.trim(), altitudeReference: d.altitudeReference, altitudeUnits: d.altitudeUnits, geoidSeparationMetres,
    altitudeUncertaintyMetres: d.altitudeUncertaintyMetres ?? null, horizontalUncertaintyMetres: d.horizontalUncertaintyMetres ?? null,
    clockOffsetSeconds, clockOffsetDeclared: d.clockOffsetSeconds !== undefined, timeFormat, policy: Object.freeze(policy), notes: Object.freeze(notes),
  });
}

// ---- time ---------------------------------------------------------------------------------------------------------

const ISO = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(\.\d{1,6})?)?(Z|[+-]\d{2}:?\d{2})$/i;

// A timestamp with an explicit zone, read strictly: a time without a zone, an impossible date or free text is refused.
export function parseInstant(value, format = 'ISO') {
  if (format === 'EPOCH_SECONDS') {
    const n = typeof value === 'number' ? value : Number(String(value).trim());
    if (!finite(n) || String(value).trim() === '') return { error: 'the epoch time is not a number' };
    if (n > 1e11) return { error: 'the epoch time looks like milliseconds, not seconds' };
    if (n < 1e9 || n > 4e9) return { error: 'the epoch time is outside 2001 to 2096' };
    return { ms: Math.round(n * 1000) };
  }
  if (typeof value !== 'string') return { error: 'the time is not text' };
  const m = ISO.exec(value.trim());
  if (!m) return { error: 'the time is not ISO 8601 with a UTC designator (Z) or an offset' };
  const [, y, mo, d, h, mi, s = '0', frac = '', zone] = m;
  const year = Number(y); const month = Number(mo); const day = Number(d); const hour = Number(h); const minute = Number(mi); const second = Number(s);
  if (month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return { error: 'the date or time is not a real one' };
  const base = Date.UTC(year, month - 1, day, hour, minute, second);
  const check = new Date(base);
  if (check.getUTCDate() !== day || check.getUTCMonth() !== month - 1) return { error: 'the date is not a real one' };
  let offsetMs = 0;
  if (zone.toUpperCase() !== 'Z') {
    const sign = zone[0] === '-' ? -1 : 1;
    const digits = zone.slice(1).replace(':', '');
    const oh = Number(digits.slice(0, 2)); const om = Number(digits.slice(2, 4));
    if (oh > 14 || om > 59) return { error: 'the UTC offset is not a real one' };
    offsetMs = sign * (oh * 3600 + om * 60) * 1000;
  }
  return { ms: base - offsetMs + (frac ? Math.round(Number(`0${frac}`) * 1000) : 0) };
}

// ---- rows to observations -----------------------------------------------------------------------------------------

function toObservation(row, declaration) {
  const time = parseInstant(row.time, declaration.timeFormat);
  if (time.error) return { reason: time.error };
  const lat = typeof row.lat === 'number' ? row.lat : (String(row.lat ?? '').trim() === '' ? NaN : Number(row.lat));
  const lon = typeof row.lon === 'number' ? row.lon : (String(row.lon ?? '').trim() === '' ? NaN : Number(row.lon));
  if (!finite(lat) || lat < -90 || lat > 90) return { reason: 'the latitude is missing or not between -90 and 90' };
  if (!finite(lon) || lon < -180 || lon > 180) return { reason: 'the longitude is missing or not between -180 and 180' };
  const raw = typeof row.altitude === 'number' ? row.altitude : (String(row.altitude ?? '').trim() === '' ? NaN : Number(row.altitude));
  if (!finite(raw)) return { reason: 'the altitude is missing (it is not assumed to be ground level)' };
  const metres = declaration.altitudeUnits === 'ft' ? raw * FEET : raw;
  const height = metres + declaration.geoidSeparationMetres;
  if (height < -500 || height > 100000) return { reason: 'the altitude is outside -500 to 100000 m once converted' };
  return { observation: { ms: time.ms + declaration.clockOffsetSeconds * 1000, lat, lon, height, rawAltitude: raw } };
}

// ---- quality ------------------------------------------------------------------------------------------------------

// Sorted, de-duplicated observations to the track's quality: eligibility, gaps and the Skywatcher-vocabulary class.
export function assessTrack(observations, policy = TRACK_POLICY) {
  const n = observations.length;
  const gaps = [];
  const intervals = [];
  for (let i = 1; i < n; i += 1) {
    const a = observations[i - 1];
    const b = observations[i];
    const seconds = (b.ms - a.ms) / 1000;
    intervals.push(seconds);
    const metres = Math.hypot(b.ecef.x - a.ecef.x, b.ecef.y - a.ecef.y, b.ecef.z - a.ecef.z);
    const speed = metres / seconds;
    if (seconds > policy.gapSeconds) gaps.push({ from: new Date(a.ms).toISOString(), to: new Date(b.ms).toISOString(), seconds, reason: 'LONG_INTERVAL' });
    else if (speed > policy.maxPlausibleSpeedMetresPerSecond) gaps.push({ from: new Date(a.ms).toISOString(), to: new Date(b.ms).toISOString(), seconds, reason: 'IMPLAUSIBLE_SPEED', speedMetresPerSecond: speed });
  }
  const sorted = [...intervals].sort((x, y) => x - y);
  const median = sorted.length === 0 ? null : (sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2);
  const eligible = n >= policy.minimumValidObservations;
  let quality = null;
  if (n === 1) quality = 'single_point';
  else if (n >= 2) quality = gaps.length === 0 ? 'continuous' : (gaps.length * 2 > intervals.length ? 'sparse_evidence' : 'gapped');
  return Object.freeze({
    validObservations: n, eligible, track_quality: quality, gap_count: gaps.length,
    gaps: Object.freeze(gaps.slice(0, MAX_LISTED)), gapsListed: Math.min(gaps.length, MAX_LISTED),
    medianIntervalSeconds: median, maxIntervalSeconds: sorted.length ? sorted[sorted.length - 1] : null,
    spanStart: n ? new Date(observations[0].ms).toISOString() : null, spanEnd: n ? new Date(observations[n - 1].ms).toISOString() : null,
    reason: eligible ? null : (n === 0 ? 'NO_VALID_OBSERVATIONS' : 'FEWER_THAN_TWO_VALID_OBSERVATIONS'),
  });
}

function buildTrack(id, label, rawRows, declaration, rejected) {
  const accepted = [];
  for (const { row, index } of rawRows) {
    const r = toObservation(row, declaration);
    if (r.reason) { rejected.push({ index, track: id, reason: r.reason }); continue; }
    accepted.push({ ...r.observation, index });
  }
  accepted.sort((a, b) => a.ms - b.ms); // stable: reports at one instant keep their file order
  const observations = [];
  for (const o of accepted) {
    const last = observations[observations.length - 1];
    if (last && last.ms === o.ms) { rejected.push({ index: o.index, track: id, reason: 'a second report at the same instant' }); continue; }
    observations.push({ ...o, ecef: geodeticToEcef({ lat: o.lat, lon: o.lon, height: o.height }) });
  }
  return Object.freeze({ id, label, observations: Object.freeze(observations), quality: assessTrack(observations, declaration.policy) });
}

function finish(declaration, tracks, rejected, rowCount, format) {
  const listed = rejected.slice(0, MAX_LISTED);
  return Object.freeze({
    contract: AIRCRAFT_TRACK_CONTRACT, format, declaration, rows: rowCount, tracks: Object.freeze(tracks),
    rejected: Object.freeze({ count: rejected.length, listed: Object.freeze(listed), listedCount: listed.length }),
    notes: Object.freeze([
      ...declaration.notes,
      'A callsign or identifier in a file is a label the file carries, not an identification of an airframe, an operator or an intent.',
      'Rows that could not be read are counted and listed, never dropped silently, and a missing altitude is rejected rather than read as ground level.',
    ]),
    limits: Object.freeze([
      `These are the ${tracks.length} track${tracks.length === 1 ? '' : 's'} in the file: not all air traffic. An aircraft that is not in the file (not broadcasting, not received, or not supplied) is not excluded by this check.`,
      'Positions between two reports are filled in by a straight line only when the interval is within the gap length; nothing is extrapolated before the first report or after the last.',
    ]),
  });
}

// ---- CSV ----------------------------------------------------------------------------------------------------------

// RFC 4180 style: quoted fields, doubled quotes, commas, CRLF or LF. A leading byte-order mark is dropped.
function csvRows(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  const src = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  for (let i = 0; i < src.length; i += 1) {
    const c = src[i];
    if (quoted) {
      if (c === '"') { if (src[i + 1] === '"') { field += '"'; i += 1; } else quoted = false; } else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; } else if (c === '\n' || c === '\r') {
      if (c === '\r' && src[i + 1] === '\n') i += 1;
      row.push(field); field = '';
      if (row.some((x) => x.trim() !== '')) rows.push(row);
      row = [];
    } else field += c;
  }
  if (quoted) throw new RangeError('The CSV has a quoted field that never closes.');
  row.push(field);
  if (row.some((x) => x.trim() !== '')) rows.push(row);
  return rows;
}

const CSV_HEADER = ['time', 'lat', 'lon', 'altitude'];

export function parseTrackCsv(text, declarationInput) {
  const declaration = validateDeclaration(declarationInput);
  if (typeof text !== 'string' || !text.trim()) throw new RangeError('The CSV is empty.');
  if (text.length > MAX_FILE_CHARACTERS) throw new RangeError(`The file is larger than ${MAX_FILE_CHARACTERS / 1048576} MB, which this check does not take.`);
  const all = csvRows(text);
  const header = all[0].map((h) => h.trim().toLowerCase());
  for (const need of CSV_HEADER) {
    if (!header.includes(need)) throw new RangeError(`The CSV needs a header row with the columns ${CSV_HEADER.join(', ')} (and optionally id, callsign); "${need}" is missing.`);
  }
  const body = all.slice(1);
  if (body.length === 0) throw new RangeError('The CSV has a header and no rows.');
  if (body.length > MAX_ROWS) throw new RangeError(`The CSV has ${body.length} rows; this check takes at most ${MAX_ROWS}.`);
  const col = (name) => header.indexOf(name);
  const groups = new Map();
  const labels = new Map();
  body.forEach((cells, i) => {
    const get = (name) => (col(name) >= 0 ? cells[col(name)] : undefined);
    const id = (get('id') ?? '').trim() || 'track-1';
    if (!groups.has(id)) groups.set(id, []);
    const callsign = (get('callsign') ?? '').trim();
    if (callsign && !labels.has(id)) labels.set(id, callsign);
    groups.get(id).push({ index: i + 2, row: { time: get('time'), lat: get('lat'), lon: get('lon'), altitude: get('altitude') } });
  });
  const rejected = [];
  const tracks = [...groups].map(([id, rows]) => buildTrack(id, labels.get(id) ?? null, rows, declaration, rejected));
  return finish(declaration, tracks, rejected, body.length, 'CSV');
}

// ---- GeoJSON ------------------------------------------------------------------------------------------------------

// A FeatureCollection (or one Feature) of Point features each with properties.time, and/or LineString features with
// properties.times, an array parallel to the coordinates. Coordinates are [longitude, latitude, altitude]; GeoJSON
// leaves the altitude's reference open, which is why the declaration is required.
export function parseTrackGeoJson(input, declarationInput) {
  const declaration = validateDeclaration(declarationInput);
  let doc = input;
  if (typeof input === 'string') {
    if (input.length > MAX_FILE_CHARACTERS) throw new RangeError(`The file is larger than ${MAX_FILE_CHARACTERS / 1048576} MB, which this check does not take.`);
    try { doc = JSON.parse(input); } catch { throw new RangeError('The GeoJSON is not valid JSON.'); }
  }
  const features = doc?.type === 'FeatureCollection' ? doc.features : (doc?.type === 'Feature' ? [doc] : null);
  if (!Array.isArray(features)) throw new RangeError('The GeoJSON must be a FeatureCollection or a Feature.');
  const groups = new Map();
  const labels = new Map();
  let rowCount = 0;
  let unnamed = 0;
  const rejected = [];
  features.forEach((feature, fi) => {
    const props = feature?.properties ?? {};
    const geometry = feature?.geometry;
    let id = typeof props.id === 'string' && props.id.trim() ? props.id.trim() : (typeof feature?.id === 'string' ? feature.id : null);
    const callsign = typeof props.callsign === 'string' ? props.callsign.trim() : '';
    const add = (rows) => {
      if (id === null) { unnamed += 1; id = unnamed === 1 && features.length === 1 ? 'track-1' : `feature-${fi + 1}`; }
      if (!groups.has(id)) groups.set(id, []);
      groups.get(id).push(...rows);
      if (callsign && !labels.has(id)) labels.set(id, callsign);
    };
    if (geometry?.type === 'Point' && Array.isArray(geometry.coordinates)) {
      rowCount += 1;
      const [lon, lat, altitude] = geometry.coordinates;
      add([{ index: fi + 1, row: { time: props.time, lat, lon, altitude } }]);
    } else if (geometry?.type === 'LineString' && Array.isArray(geometry.coordinates)) {
      const times = props.times;
      if (!Array.isArray(times) || times.length !== geometry.coordinates.length) {
        rowCount += geometry.coordinates.length;
        rejected.push({ index: fi + 1, track: id ?? `feature-${fi + 1}`, reason: `a LineString needs properties.times with one time per coordinate (${geometry.coordinates.length}); the whole line was set aside` });
        return;
      }
      rowCount += geometry.coordinates.length;
      add(geometry.coordinates.map(([lon, lat, altitude], ci) => ({ index: `${fi + 1}.${ci + 1}`, row: { time: times[ci], lat, lon, altitude } })));
    } else {
      rowCount += 1;
      rejected.push({ index: fi + 1, track: id ?? `feature-${fi + 1}`, reason: `a ${geometry?.type ?? 'missing'} geometry is not a Point or a LineString` });
    }
  });
  if (rowCount > MAX_ROWS) throw new RangeError(`The GeoJSON has ${rowCount} positions; this check takes at most ${MAX_ROWS}.`);
  if (groups.size === 0 && rejected.length === 0) throw new RangeError('The GeoJSON holds no positions.');
  const tracks = [...groups].map(([id, rows]) => buildTrack(id, labels.get(id) ?? null, rows, declaration, rejected));
  return finish(declaration, tracks, rejected, rowCount, 'GeoJSON');
}

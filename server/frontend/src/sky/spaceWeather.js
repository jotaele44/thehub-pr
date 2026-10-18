// Space weather for the Sky workspace (TWIN-029..033, 106, 109): the planetary K-index, the solar-wind speed and
// the IMF Bz, read directly from NOAA SWPC in the browser (the three products answer cross-origin reads, T1
// 2026-10-15). Nothing is stored and no producer is called.
//
// What the data is, as measured: Kp is a 3-hourly series over about a week whose time tags carry no "Z" (they are
// UTC); the two "summary" products are one-row, whole-number readings (the provider rounds them). The older
// /products/solar-wind/* files no longer exist, and the 1-minute /json/rtsw/* series mixes sources and is
// newest-first, so it is not used here. A product that cannot be read is FAILED with its reason, never zero.

export const SWPC_PROVIDER = 'NOAA SWPC (Space Weather Prediction Center)';
const SWPC_BASE = 'https://services.swpc.noaa.gov/products/';
export const SWPC_ENDPOINTS = Object.freeze({
  kp: `${SWPC_BASE}noaa-planetary-k-index.json`,
  solarWindSpeed: `${SWPC_BASE}summary/solar-wind-speed.json`,
  magField: `${SWPC_BASE}summary/solar-wind-mag-field.json`,
});

// Policy, not physics: how old a reading may be and still be called LIVE. A Kp row is stamped with the start of
// its 3-hour interval, so it stays current for that interval plus a quarter hour for the late update; the summary
// products are one-minute products.
export const KP_LIVE_MINUTES = 195;
export const SUMMARY_LIVE_MINUTES = 15;
const FUTURE_SKEW_MINUTES = 5;
const DEFAULT_TIMEOUT_MS = 10000;

// SWPC time tags: "2026-10-18T18:00:00" (Kp, UTC with no designator) or "2026-10-18T20:53:00Z".
function parseTag(tag) {
  if (typeof tag !== 'string') return null;
  const text = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(tag) ? `${tag}Z` : tag;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);

export function parseKp(payload) {
  if (!Array.isArray(payload)) throw new TypeError('Kp payload is not a list of rows.');
  const points = [];
  for (const row of payload) {
    const time = parseTag(row?.time_tag);
    const kp = row?.Kp;
    if (time && isNumber(kp) && kp >= 0 && kp <= 9) {
      points.push({ time, kp, aRunning: isNumber(row.a_running) ? row.a_running : null, stationCount: isNumber(row.station_count) ? row.station_count : null });
    }
  }
  if (!points.length) throw new Error('Kp payload had no usable rows.');
  points.sort((a, b) => a.time - b.time);
  const latest = points[points.length - 1];
  return { points, latest, spanDays: (latest.time - points[0].time) / 86400e3, dropped: payload.length - points.length };
}

function latestRow(payload, what) {
  if (!Array.isArray(payload)) throw new TypeError(`${what} payload is not a list of readings.`);
  if (!payload.length) throw new Error(`${what} payload had no reading.`);
  const rows = payload.map((row) => ({ row, time: parseTag(row?.time_tag) })).filter((item) => item.time);
  if (!rows.length) throw new Error(`${what} reading has no valid time.`);
  return rows.reduce((latest, item) => (item.time > latest.time ? item : latest));
}

export function parseWindSpeed(payload) {
  const { row, time } = latestRow(payload, 'Solar wind');
  if (!isNumber(row.proton_speed) || row.proton_speed < 0) throw new Error('Solar wind speed is missing or not a number.');
  return { speed: row.proton_speed, time };
}

export function parseMagField(payload) {
  const { row, time } = latestRow(payload, 'IMF');
  if (!isNumber(row.bz_gsm)) throw new Error('IMF Bz is missing or not a number.');
  return { bz: row.bz_gsm, bt: isNumber(row.bt) ? row.bt : null, time };
}

// Southward Bz (negative) is the geoeffective direction.
export function imfDirection(bz) {
  if (bz > 0) return 'northward';
  if (bz < 0) return 'southward';
  return 'zero';
}

// NOAA geomagnetic storm scale: G1 at Kp 5 up to G5 at Kp 9, by whole Kp (5- is 4.67, below G1).
export function geomagneticScale(kp) {
  const whole = Math.floor(kp + 1e-9);
  return whole >= 5 ? `G${Math.min(5, whole - 4)}` : null;
}

export function freshness(observedAt, now, liveMinutes) {
  const ageMinutes = Math.round((now.getTime() - observedAt.getTime()) / 60000);
  if (ageMinutes < -FUTURE_SKEW_MINUTES) {
    return { state: 'STALE', ageMinutes, note: 'The reading is timestamped in the future: check this clock or the provider.' };
  }
  return { state: ageMinutes <= liveMinutes ? 'LIVE' : 'STALE', ageMinutes: Math.max(0, ageMinutes) };
}

async function fetchJson(url, fetchImpl, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error(`Timed out after ${timeoutMs} ms`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

const failed = (id, label, url, reason) => ({
  id, label, state: 'FAILED', value: null, observedAt: null, ageMinutes: null,
  error: reason?.message || String(reason), source: { provider: SWPC_PROVIDER, url },
});

function settle(id, label, url, outcome, build) {
  if (outcome.status === 'rejected') return failed(id, label, url, outcome.reason);
  try {
    return build(outcome.value);
  } catch (error) {
    return failed(id, label, url, error);
  }
}

// All three products, independently: one that fails does not hide the others.
export async function loadSpaceWeather({ fetchImpl = globalThis.fetch?.bind(globalThis), now = new Date(), timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  if (!fetchImpl) throw new Error('No fetch implementation is available.');
  const [kpOutcome, windOutcome, magOutcome] = await Promise.allSettled([
    fetchJson(SWPC_ENDPOINTS.kp, fetchImpl, timeoutMs),
    fetchJson(SWPC_ENDPOINTS.solarWindSpeed, fetchImpl, timeoutMs),
    fetchJson(SWPC_ENDPOINTS.magField, fetchImpl, timeoutMs),
  ]);
  const source = (url) => ({ provider: SWPC_PROVIDER, url });
  const kp = settle('kp', 'Planetary K-index (Kp)', SWPC_ENDPOINTS.kp, kpOutcome, (payload) => {
    const parsed = parseKp(payload);
    return {
      id: 'kp', label: 'Planetary K-index (Kp)', value: parsed.latest.kp, unit: 'Kp', observedAt: parsed.latest.time,
      ...freshness(parsed.latest.time, now, KP_LIVE_MINUTES),
      scale: geomagneticScale(parsed.latest.kp), stationCount: parsed.latest.stationCount,
      series: parsed.points, spanDays: parsed.spanDays, dropped: parsed.dropped,
      note: 'The value for the 3-hour interval that starts at the time shown, from the number of stations shown.',
      source: source(SWPC_ENDPOINTS.kp),
    };
  });
  const solarWind = settle('solar-wind-speed', 'Solar wind speed', SWPC_ENDPOINTS.solarWindSpeed, windOutcome, (payload) => {
    const parsed = parseWindSpeed(payload);
    return {
      id: 'solar-wind-speed', label: 'Solar wind speed', value: parsed.speed, unit: 'km/s', precision: 'whole km/s (rounded by the provider)',
      observedAt: parsed.time, ...freshness(parsed.time, now, SUMMARY_LIVE_MINUTES), source: source(SWPC_ENDPOINTS.solarWindSpeed),
    };
  });
  const imf = settle('imf-bz', 'IMF Bz (GSM)', SWPC_ENDPOINTS.magField, magOutcome, (payload) => {
    const parsed = parseMagField(payload);
    return {
      id: 'imf-bz', label: 'IMF Bz (GSM)', value: parsed.bz, bz: parsed.bz, bt: parsed.bt, unit: 'nT', direction: imfDirection(parsed.bz),
      precision: 'whole nT (rounded by the provider)', observedAt: parsed.time, ...freshness(parsed.time, now, SUMMARY_LIVE_MINUTES),
      source: source(SWPC_ENDPOINTS.magField),
    };
  });
  return { kp, solarWind, imf, retrievedAt: now };
}

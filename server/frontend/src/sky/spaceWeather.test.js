import { describe, expect, it, vi } from 'vitest';
import samples from './fixtures/swpc-samples.json';
import {
  KP_LIVE_MINUTES, SUMMARY_LIVE_MINUTES, SWPC_ENDPOINTS, freshness, geomagneticScale, imfDirection, loadSpaceWeather,
  parseKp, parseMagField, parseWindSpeed,
} from './spaceWeather';

// The payloads in swpc-samples.json are real NOAA SWPC responses captured 2026-10-18: Kp is 3-hourly with
// time tags that carry no "Z" (UTC all the same), and the two summary products are whole-number, one-row arrays.
const NOW = new Date('2026-10-18T20:55:00Z');

describe('Kp', () => {
  it('reads the real 3-hourly series in time order, treating the unmarked time tags as UTC', () => {
    const kp = parseKp(samples.kp.payload);
    expect(kp.points).toHaveLength(63);
    expect(kp.points[0].time.toISOString()).toBe('2026-10-11T00:00:00.000Z');
    expect(kp.latest.time.toISOString()).toBe('2026-10-18T18:00:00.000Z');
    expect(kp.latest.kp).toBeCloseTo(1.67, 2);
    expect(kp.latest.stationCount).toBe(8);
    expect(kp.points.every((p, i) => i === 0 || p.time > kp.points[i - 1].time)).toBe(true);
    // The span is what the data holds (7.75 days from first to last interval start), not a number from a label.
    expect(kp.spanDays).toBeCloseTo(7.75, 2);
    expect(kp.dropped).toBe(0);
  });

  it('sorts a series that arrives out of order', () => {
    const shuffled = [...samples.kp.payload].reverse();
    expect(parseKp(shuffled).points[0].time.toISOString()).toBe('2026-10-11T00:00:00.000Z');
  });

  it('drops malformed rows and says how many, rather than reading them as zero', () => {
    const rows = [
      { time_tag: '2026-10-18T12:00:00', Kp: 2.33, a_running: 9, station_count: 8 },
      { time_tag: '2026-10-18T15:00:00', Kp: 'n/a', a_running: 9, station_count: 8 },
      { time_tag: 'not a time', Kp: 3, a_running: 9, station_count: 8 },
      { time_tag: '2026-10-18T18:00:00', Kp: 12, a_running: 9, station_count: 8 },
      { Kp: 1 },
      { time_tag: '2026-10-18T21:00:00', Kp: 1.67, a_running: 6, station_count: 8 },
    ];
    const kp = parseKp(rows);
    expect(kp.points.map((p) => p.kp)).toEqual([2.33, 1.67]);
    expect(kp.dropped).toBe(4);
  });

  it('refuses a payload with no usable row, and one that is not a list', () => {
    expect(() => parseKp([])).toThrow(/no usable/i);
    expect(() => parseKp([{ Kp: 'x', time_tag: 'y' }])).toThrow(/no usable/i);
    expect(() => parseKp({ error: 'gone' })).toThrow(/list/i);
  });

  it('maps Kp to the NOAA geomagnetic storm scale by whole Kp, with 5- below G1 and 9- still G4', () => {
    expect(geomagneticScale(4.67)).toBeNull();
    expect(geomagneticScale(5)).toBe('G1');
    expect(geomagneticScale(5.67)).toBe('G1');
    expect(geomagneticScale(6)).toBe('G2');
    expect(geomagneticScale(7.33)).toBe('G3');
    expect(geomagneticScale(8.67)).toBe('G4');
    expect(geomagneticScale(9)).toBe('G5');
    expect(geomagneticScale(0)).toBeNull();
  });
});

describe('solar wind speed and IMF Bz summaries', () => {
  it('reads the real whole-number summaries, with their UTC time', () => {
    const wind = parseWindSpeed(samples.solar_wind_speed.payload);
    expect(wind).toMatchObject({ speed: 411 });
    expect(wind.time.toISOString()).toBe('2026-10-18T20:53:00.000Z');
    const mag = parseMagField(samples.mag_field.payload);
    expect(mag).toMatchObject({ bt: 5, bz: 3 });
    expect(mag.time.toISOString()).toBe('2026-10-18T20:53:00.000Z');
  });

  it('refuses a missing, non-finite or non-list reading instead of showing zero', () => {
    expect(() => parseWindSpeed([])).toThrow(/no reading/i);
    expect(() => parseWindSpeed([{ proton_speed: null, time_tag: '2026-10-18T20:53:00Z' }])).toThrow(/speed/i);
    expect(() => parseWindSpeed({ proton_speed: 400 })).toThrow(/list/i);
    expect(() => parseMagField([{ bt: 5, bz_gsm: 'x', time_tag: '2026-10-18T20:53:00Z' }])).toThrow(/Bz/i);
    expect(() => parseMagField([{ bt: 5, bz_gsm: 1, time_tag: 'later' }])).toThrow(/time/i);
  });

  it('says which way Bz points: southward is the geoeffective direction', () => {
    expect(imfDirection(3)).toBe('northward');
    expect(imfDirection(-5)).toBe('southward');
    expect(imfDirection(0)).toBe('zero');
  });
});

describe('freshness', () => {
  it('is LIVE through the current 3-hour Kp interval and a late update, and STALE after', () => {
    const interval = new Date('2026-10-18T18:00:00Z');
    expect(freshness(interval, new Date('2026-10-18T20:55:00Z'), KP_LIVE_MINUTES).state).toBe('LIVE');
    expect(freshness(interval, new Date('2026-10-18T21:10:00Z'), KP_LIVE_MINUTES).state).toBe('LIVE');
    expect(freshness(interval, new Date('2026-10-18T21:16:00Z'), KP_LIVE_MINUTES).state).toBe('STALE');
  });

  it('is LIVE for a one-minute product within a quarter of an hour, and STALE with its age after', () => {
    const reading = new Date('2026-10-18T20:53:00Z');
    expect(freshness(reading, NOW, SUMMARY_LIVE_MINUTES)).toMatchObject({ state: 'LIVE', ageMinutes: 2 });
    expect(freshness(reading, new Date('2026-10-18T21:30:00Z'), SUMMARY_LIVE_MINUTES)).toMatchObject({ state: 'STALE', ageMinutes: 37 });
  });

  it('never calls a reading from the future LIVE without saying so', () => {
    const future = freshness(new Date('2026-10-18T21:30:00Z'), NOW, SUMMARY_LIVE_MINUTES);
    expect(future.state).toBe('STALE');
    expect(future.note).toMatch(/future|clock/i);
  });
});

describe('loadSpaceWeather', () => {
  const respond = (payload) => ({ ok: true, status: 200, json: async () => payload });
  const routes = {
    [SWPC_ENDPOINTS.kp]: () => respond(samples.kp.payload),
    [SWPC_ENDPOINTS.solarWindSpeed]: () => respond(samples.solar_wind_speed.payload),
    [SWPC_ENDPOINTS.magField]: () => respond(samples.mag_field.payload),
  };
  const fetchWith = (overrides = {}) => vi.fn(async (url) => ({ ...routes, ...overrides })[url]());

  it('reads the three products, each with its value, unit, time, age, state and source', async () => {
    const fetchImpl = fetchWith();
    const result = await loadSpaceWeather({ fetchImpl, now: NOW });
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(result.kp).toMatchObject({ state: 'LIVE', value: 1.67, scale: null, stationCount: 8 });
    expect(result.kp.series).toHaveLength(63);
    expect(result.solarWind).toMatchObject({ state: 'LIVE', value: 411, unit: 'km/s' });
    expect(result.solarWind.precision).toMatch(/whole/i);
    expect(result.imf).toMatchObject({ state: 'LIVE', bz: 3, bt: 5, direction: 'northward', unit: 'nT' });
    for (const item of [result.kp, result.solarWind, result.imf]) {
      expect(item.source.provider).toMatch(/SWPC/);
      expect(item.source.url).toMatch(/^https:\/\/services\.swpc\.noaa\.gov\//);
      expect(item.observedAt).toBeInstanceOf(Date);
    }
    expect(result.retrievedAt.toISOString()).toBe(NOW.toISOString());
  });

  it('keeps the products independent: one failing does not hide the others, and a failure has no value', async () => {
    const fetchImpl = fetchWith({ [SWPC_ENDPOINTS.solarWindSpeed]: () => ({ ok: false, status: 503, json: async () => ({}) }) });
    const result = await loadSpaceWeather({ fetchImpl, now: NOW });
    expect(result.solarWind).toMatchObject({ state: 'FAILED', value: null, observedAt: null });
    expect(result.solarWind.error).toMatch(/503/);
    expect(result.kp.state).toBe('LIVE');
    expect(result.imf.state).toBe('LIVE');
  });

  it('reports a network failure, bad JSON and an unusable payload as FAILED, never as zero', async () => {
    const result = await loadSpaceWeather({
      fetchImpl: fetchWith({
        [SWPC_ENDPOINTS.kp]: () => { throw new TypeError('Failed to fetch'); },
        [SWPC_ENDPOINTS.solarWindSpeed]: () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected token <'); } }),
        [SWPC_ENDPOINTS.magField]: () => respond([]),
      }),
      now: NOW,
    });
    for (const item of [result.kp, result.solarWind, result.imf]) {
      expect(item.state).toBe('FAILED');
      expect(item.value).toBeNull();
      expect(item.error).toBeTruthy();
    }
    expect(result.kp.error).toMatch(/Failed to fetch/);
    expect(result.solarWind.error).toMatch(/Unexpected token/);
  });

  it('marks old readings STALE and still shows them with their age', async () => {
    const result = await loadSpaceWeather({ fetchImpl: fetchWith(), now: new Date('2026-10-18T23:00:00Z') });
    expect(result.solarWind).toMatchObject({ state: 'STALE', value: 411 });
    expect(result.solarWind.ageMinutes).toBe(127);
    expect(result.kp.state).toBe('STALE');
  });

  it('aborts a request that hangs, and says so', async () => {
    vi.useFakeTimers();
    try {
      const hanging = vi.fn((url, init) => new Promise((resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')));
      }));
      const pending = loadSpaceWeather({ fetchImpl: hanging, now: NOW, timeoutMs: 5000 });
      await vi.advanceTimersByTimeAsync(5001);
      const result = await pending;
      expect(result.kp.state).toBe('FAILED');
      expect(result.kp.error).toMatch(/abort|time/i);
    } finally {
      vi.useRealTimers();
    }
  });
});

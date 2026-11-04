import { createHash } from 'node:crypto';
import { describe, expect, it, vi } from 'vitest';
import elementsText from './fixtures/satellite-elements.json?raw';
import { ELEMENT_SOURCE, loadSatelliteElements } from './satelliteElements';
import { SATELLITES, gpUrl } from './satellites';

const elements = JSON.parse(elementsText);
const issRecord = elements.items.ISS.payload[0];
const hubbleRecord = elements.items.HST.payload[0];
const stationRecord = elements.items.CSS.payload[0];
const NOW = new Date('2026-11-04T08:00:00Z');

// All three are real CelesTrak records (see the fixture's provenance). A synthetic variant, with another catalogue
// number and name, is used only where a test needs an answer that is wrong.
const variant = (noradId, name, change = {}) => ({ ...issRecord, NORAD_CAT_ID: noradId, OBJECT_NAME: name, ...change });
const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const routes = (overrides = {}) => ({
  [gpUrl(25544)]: () => ok([issRecord]),
  [gpUrl(20580)]: () => ok([hubbleRecord]),
  [gpUrl(48274)]: () => ok([stationRecord]),
  ...overrides,
});
const fetchWith = (overrides) => vi.fn(async (url) => routes(overrides)[url]());

describe('loadSatelliteElements', () => {
  it('asks CelesTrak exactly once per satellite, for that catalogue number, and keeps the identity and epoch', async () => {
    const fetchImpl = fetchWith();
    const result = await loadSatelliteElements({ fetchImpl, now: NOW });
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(fetchImpl.mock.calls.map(([url]) => url).sort()).toEqual(SATELLITES.map((s) => gpUrl(s.noradId)).sort());
    expect(result).toMatchObject({ requested: 3, loaded: 3 });
    const iss = result.items.find((item) => item.id === 'ISS');
    expect(iss).toMatchObject({ state: 'LOADED', noradId: 25544, name: 'ISS (ZARYA)', error: null });
    expect(iss.epoch.toISOString()).toBe(`${issRecord.EPOCH.slice(0, 23)}Z`);
    expect(iss.element.noradId).toBe(25544);
    // The record as CelesTrak sent it is kept, unchanged, beside the parsed element set.
    expect(iss.record).toEqual(issRecord);
    expect(iss.url).toBe('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=json');
    expect(iss.ageAtRetrieval.days).toBeCloseTo((NOW - iss.epoch) / 86400e3, 9);
    expect(result.source).toBe(ELEMENT_SOURCE);
    expect(result.retrievedAt).toBe(NOW);
  });

  it('sends nothing but a plain GET with an Accept header: no credentials, no token, nothing in the address', async () => {
    const fetchImpl = fetchWith();
    await loadSatelliteElements({ fetchImpl, now: NOW });
    for (const [url, init] of fetchImpl.mock.calls) {
      expect(url).toMatch(/^https:\/\/celestrak\.org\/NORAD\/elements\/gp\.php\?CATNR=\d+&FORMAT=json$/);
      expect(Object.keys(init).sort()).toEqual(['headers', 'signal']);
      expect(init.headers).toEqual({ accept: 'application/json' });
      expect(init.method).toBeUndefined();
      expect(init.credentials).toBeUndefined();
    }
  });

  it('does not retry: a failure is one request and a reason', async () => {
    const fetchImpl = fetchWith({ [gpUrl(20580)]: () => ({ ok: false, status: 503, json: async () => ({}) }) });
    await loadSatelliteElements({ fetchImpl, now: NOW });
    expect(fetchImpl.mock.calls.filter(([url]) => url === gpUrl(20580))).toHaveLength(1);
  });

  it('keeps the satellites independent: one that fails does not hide the others, and has no element set', async () => {
    const fetchImpl = fetchWith({ [gpUrl(20580)]: () => ({ ok: false, status: 503, json: async () => ({}) }) });
    const result = await loadSatelliteElements({ fetchImpl, now: NOW });
    expect(result).toMatchObject({ requested: 3, loaded: 2 });
    const hubble = result.items.find((item) => item.id === 'HST');
    expect(hubble).toMatchObject({ state: 'FAILED', element: null, record: null, name: null, epoch: null, ageAtRetrieval: null });
    expect(hubble.error).toMatch(/HTTP 503/);
    expect(result.items.filter((item) => item.state === 'LOADED').map((item) => item.id).sort()).toEqual(['CSS', 'ISS']);
  });

  it('reports a network failure, a reset connection and an answer that is not JSON as FAILED, never as an empty or default element', async () => {
    const result = await loadSatelliteElements({
      fetchImpl: fetchWith({
        [gpUrl(25544)]: () => { throw new TypeError('Failed to fetch'); },
        [gpUrl(20580)]: () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected token <'); } }),
        [gpUrl(48274)]: () => { throw new TypeError('NetworkError when attempting to fetch resource.'); },
      }),
      now: NOW,
    });
    expect(result.loaded).toBe(0);
    expect(result.items.map((item) => item.state)).toEqual(['FAILED', 'FAILED', 'FAILED']);
    expect(result.items[0].error).toMatch(/Failed to fetch/);
    expect(result.items[1].error).toMatch(/not JSON/);
    expect(result.items.every((item) => item.element === null)).toBe(true);
  });

  it('refuses an answer that is empty, is for another object, or holds several', async () => {
    const result = await loadSatelliteElements({
      fetchImpl: fetchWith({
        [gpUrl(25544)]: () => ok([]),
        [gpUrl(20580)]: () => ok([variant(99999, 'SOMETHING ELSE')]),
        [gpUrl(48274)]: () => ok([variant(48274, 'CSS (TIANHE)'), variant(48274, 'CSS (TIANHE) AGAIN')]),
      }),
      now: NOW,
    });
    expect(result.items.map((item) => item.state)).toEqual(['FAILED', 'FAILED', 'FAILED']);
    expect(result.items[0].error).toMatch(/no object/);
    expect(result.items[1].error).toMatch(/0 objects/);
    expect(result.items[2].error).toMatch(/2 objects/);
    expect(ok({ error: 'rate limited' }).ok).toBe(true);
    const notAList = await loadSatelliteElements({ fetchImpl: fetchWith({ [gpUrl(25544)]: () => ok({ error: 'rate limited' }) }), now: NOW, satellites: [SATELLITES[0]] });
    expect(notAList.items[0]).toMatchObject({ state: 'FAILED', element: null });
  });

  it('refuses an element set SGP4 cannot use, with the reason', async () => {
    const result = await loadSatelliteElements({
      fetchImpl: fetchWith({ [gpUrl(25544)]: () => ok([{ ...issRecord, ECCENTRICITY: 1.2 }]) }),
      now: NOW, satellites: [SATELLITES[0]],
    });
    expect(result.items[0]).toMatchObject({ state: 'FAILED', element: null });
    expect(result.items[0].error).toMatch(/ECCENTRICITY/);
  });

  it('gives up on a request that hangs, and says how long it waited', async () => {
    vi.useFakeTimers();
    try {
      const hanging = vi.fn((url, init) => new Promise((resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')));
      }));
      const pending = loadSatelliteElements({ fetchImpl: hanging, now: NOW, timeoutMs: 5000, satellites: [SATELLITES[0]] });
      await vi.advanceTimersByTimeAsync(5001);
      const result = await pending;
      expect(result.items[0]).toMatchObject({ state: 'FAILED', element: null });
      expect(result.items[0].error).toBe('No answer from CelesTrak within 5 seconds');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('the frozen element fixture', () => {
  it('holds real records for the three objects, each the object its key names, with the hash of what it holds', () => {
    expect(Object.keys(elements.items)).toEqual(['ISS', 'HST', 'CSS']);
    const expected = { ISS: 25544, HST: 20580, CSS: 48274 };
    for (const [key, item] of Object.entries(elements.items)) {
      expect(item.payload, key).toHaveLength(1);
      expect(item.payload[0].NORAD_CAT_ID, key).toBe(expected[key]);
      expect(item.url, key).toBe(gpUrl(expected[key]));
      expect(item.retrieved_utc, key).toMatch(/^2026-11-0[34]T\d{2}:\d{2}:\d{2}Z$/);
      // Hubble's and the station's are the records as the loader read them, hashed as JSON text; the ISS's is the raw response.
      if (item.record_sha256) expect(createHash('sha256').update(JSON.stringify(item.payload[0])).digest('hex'), key).toBe(item.record_sha256);
      else expect(item.response_sha256, key).toMatch(/^[0-9a-f]{64}$/);
    }
  });
});

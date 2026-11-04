import { describe, expect, it, vi } from 'vitest';
import elementsText from './fixtures/satellite-elements.json?raw';
import { loadSatelliteElements } from './satelliteElements';
import { SATELLITES, gpUrl } from './satellites';
import { chartSatellites, passTrack, satelliteSnapshot, upcomingPasses } from './satelliteView';

const elements = JSON.parse(elementsText);
const issRecord = elements.items.ISS.payload[0];
const SAN_JUAN = { lat: 18.4663, lon: -66.1057, elevation: 0, tzHours: -4, isDefault: true };
const NOW = new Date('2026-11-03T08:00:00Z');
const AT = new Date('2026-11-04T09:30:00Z');
const ok = (body) => ({ ok: true, status: 200, json: async () => body });

async function loadedWith(failures = {}) {
  const fetchImpl = vi.fn(async (url) => {
    if (failures[url]) return failures[url];
    const id = Number(url.match(/CATNR=(\d+)/)[1]);
    return ok([{ ...issRecord, NORAD_CAT_ID: id, OBJECT_NAME: id === 25544 ? 'ISS (ZARYA)' : `OBJECT ${id}` }]);
  });
  return loadSatelliteElements({ fetchImpl, now: NOW });
}

describe('satellite snapshot', () => {
  it('places every loaded satellite for the observer and instant, with its element age', async () => {
    const snapshot = satelliteSnapshot(await loadedWith(), SAN_JUAN, AT);
    expect(snapshot).toMatchObject({ requested: 3, loaded: 3 });
    for (const item of snapshot.items) {
      expect(item.state).toBe('LOADED');
      expect(item.look.azimuth).toBeGreaterThanOrEqual(0);
      expect(item.look.azimuth).toBeLessThan(360);
      expect(['ABOVE_HORIZON', 'BELOW_HORIZON']).toContain(item.position);
      expect(item.position === 'ABOVE_HORIZON').toBe(item.look.elevation >= 0);
      expect(item.age.state).toBe('NORMAL');
    }
    expect(snapshot.items.map((item) => item.id)).toEqual(SATELLITES.map((s) => s.id));
  });

  it('keeps a satellite whose elements did not load in the list as FAILED, with the reason and no position', async () => {
    const snapshot = satelliteSnapshot(await loadedWith({ [gpUrl(20580)]: { ok: false, status: 503, json: async () => ({}) } }), SAN_JUAN, AT);
    expect(snapshot).toMatchObject({ requested: 3, loaded: 2 });
    const hubble = snapshot.items.find((item) => item.id === 'HST');
    expect(hubble).toMatchObject({ state: 'FAILED', look: null, element: null, age: null, position: 'NO_ELEMENTS' });
    expect(hubble.error).toMatch(/HTTP 503/);
    expect(chartSatellites(snapshot).map((s) => s.body)).not.toContain('HST');
  });

  it('says so, with no position, when the elements are too far from the instant', async () => {
    const snapshot = satelliteSnapshot(await loadedWith(), SAN_JUAN, new Date('2026-12-25T00:00:00Z'));
    for (const item of snapshot.items) {
      expect(item).toMatchObject({ state: 'LOADED', look: null, position: 'NO_ANSWER' });
      expect(item.age.state).toBe('REFUSED');
      expect(item.lookError).toMatch(/14 days/);
    }
    expect(chartSatellites(snapshot)).toEqual([]);
  });

  it('gives the chart the lit state and position of each satellite that has one', async () => {
    const snapshot = satelliteSnapshot(await loadedWith(), SAN_JUAN, AT);
    const forChart = chartSatellites(snapshot);
    expect(forChart).toHaveLength(3);
    for (const sat of forChart) {
      const item = snapshot.items.find((i) => i.id === sat.body);
      expect(sat).toMatchObject({ kind: 'satellite', label: sat.body, azimuth: item.look.azimuth, altitude: item.look.elevation, sunlit: item.look.sunlit });
      expect(sat.aboveHorizon).toBe(item.look.elevation >= 0);
    }
  });
});

describe('upcoming passes and their track', () => {
  it('lists the passes in the next 24 hours for a loaded satellite, and gives a track for one', async () => {
    const snapshot = satelliteSnapshot(await loadedWith(), SAN_JUAN, AT);
    const iss = snapshot.items.find((item) => item.id === 'ISS');
    const passes = upcomingPasses(iss, SAN_JUAN, AT);
    expect(passes.ok).toBe(true);
    expect(passes.passes.length).toBeGreaterThan(1);
    expect(passes.window.end - passes.window.start).toBe(24 * 3600e3);
    const track = passTrack(iss, SAN_JUAN, passes.passes[0]);
    expect(track.ok).toBe(true);
    expect(track.points.length).toBeGreaterThan(5);
  });

  it('gives no passes, with the reason, for a satellite whose elements did not load or are too old', async () => {
    const snapshot = satelliteSnapshot(await loadedWith({ [gpUrl(48274)]: { ok: false, status: 502, json: async () => ({}) } }), SAN_JUAN, AT);
    const failed = upcomingPasses(snapshot.items.find((item) => item.id === 'CSS'), SAN_JUAN, AT);
    expect(failed).toMatchObject({ ok: false, reason: 'NO_ELEMENTS' });
    expect(failed.message).toMatch(/HTTP 502/);
    const old = upcomingPasses(snapshot.items.find((item) => item.id === 'ISS'), SAN_JUAN, new Date('2026-12-25T00:00:00Z'));
    expect(old).toMatchObject({ ok: false, reason: 'ELEMENTS_TOO_OLD' });
  });

  it('says why when the window or the minimum elevation is not one the finder accepts, instead of throwing', async () => {
    const iss = satelliteSnapshot(await loadedWith(), SAN_JUAN, AT).items.find((item) => item.id === 'ISS');
    expect(upcomingPasses(iss, SAN_JUAN, AT, { minElevation: 95 })).toMatchObject({ ok: false, reason: 'INVALID_INPUT' });
    expect(upcomingPasses(iss, SAN_JUAN, AT, { hours: 0 }).message).toMatch(/Hours must be/);
  });
});

import { describe, expect, it, vi } from 'vitest';
import elementsText from '../fixtures/satellite-elements.json?raw';
import reference from '../fixtures/satelliteReference.json';
import { loadSatelliteElements } from '../satelliteElements';
import { VISIBLE_LABEL, gpUrl } from '../satellites';
import { enuToAzEl, unitVector } from './geometry';
import { parseObservation } from './observation';
import { apparentElevation } from './refraction';
import { checkSatellites } from './satelliteExclusion';

const frozen = JSON.parse(elementsText).items;
const sanJuan = reference.satellites.ISS.observers['San Juan'];
const OBSERVER = { lat: 18.4663, lon: -66.1057, height: 0 };
const NOW = new Date('2026-11-04T08:00:00Z');
const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const answers = { [gpUrl(25544)]: frozen.ISS.payload, [gpUrl(20580)]: frozen.HST.payload, [gpUrl(48274)]: frozen.CSS.payload };

async function loaded(failures = {}) {
  const fetchImpl = vi.fn(async (url) => failures[url] ?? ok(answers[url]));
  return loadSatelliteElements({ fetchImpl, now: NOW });
}
const aimAt = (look, { time = look.time, uncertainty = 0, tolerance = 0.5, extra = {} } = {}) => parseObservation({
  time, timeUncertaintySeconds: uncertainty, observer: OBSERVER,
  direction: { azimuth: look.azimuth, elevation: apparentElevation(look.elevation), azimuthReference: 'TRUE', toleranceDegrees: tolerance }, ...extra,
});
// The independent reference's look at the ISS when it is high, lit and the sky is dark; and one in the Earth's shadow.
const lit = sanJuan.looks.find((l) => l.sunlit && l.elevation > 20);
const shadow = sanJuan.looks[1];
const iso = (ms) => new Date(ms).toISOString();

describe('checkSatellites: the station in the sight line', () => {
  it('finds the ISS where the independent reference puts it, and says what lit it and what the sky was', async () => {
    const result = await checkSatellites(aimAt(lit), await loaded());
    expect(result.candidates).toHaveLength(1);
    const iss = result.candidates[0];
    expect(iss).toMatchObject({ id: 'ISS', noradId: 25544, status: 'CHECKED', candidate: true, aboveHorizonAtClosest: true, sunlitAtClosest: true, observerDark: true, visibleCandidate: true });
    expect(iss.visibleLabel).toBe(VISIBLE_LABEL);
    // within the 0.03 degrees the two implementations differ by (azimuth 0.026, elevation 0.003)
    expect(iss.minSeparationDegrees).toBeLessThan(0.05);
    expect(Math.abs(iss.rangeKmAtClosest - lit.range_km)).toBeLessThan(0.3);
    expect(Math.abs(Date.parse(iss.minSeparationAt) - Date.parse(lit.time))).toBeLessThan(2000);
    expect(iss.elements.confidence).toBe('NORMAL');
  });

  it('is a candidate in the Earth\'s shadow too, geometrically, and says it was not lit, so it is not a visible-pass candidate', async () => {
    const result = await checkSatellites(aimAt(shadow), await loaded());
    const iss = result.candidates.find((c) => c.id === 'ISS');
    expect(iss).toMatchObject({ candidate: true, sunlitAtClosest: false, visibleCandidate: false });
    expect(iss.visibleLabel).toMatch(/Not a visible-pass candidate/);
  });

  it('counts a satellite that crosses the sight line during the uncertainty, and not one that does not', async () => {
    const earlier = iso(Date.parse(lit.time) - 40000);
    const exact = await checkSatellites(aimAt(lit, { time: earlier }), await loaded());
    expect(exact.candidates.find((c) => c.id === 'ISS')).toBeUndefined();
    const widened = await checkSatellites(aimAt(lit, { time: earlier, uncertainty: 60 }), await loaded());
    const iss = widened.candidates.find((c) => c.id === 'ISS');
    expect(iss).toBeTruthy();
    expect(Date.parse(iss.firstInside)).toBeLessThanOrEqual(Date.parse(lit.time) + 1000);
    expect(Date.parse(iss.lastInside)).toBeGreaterThanOrEqual(Date.parse(lit.time) - 1000);
    expect(Date.parse(iss.lastInside) - Date.parse(iss.firstInside)).toBeLessThan(5000);
  });

  it('meets a satellite only when a moving sight line passes through it, and says when', async () => {
    // A sight line that sweeps 10 degrees of sky in 60 seconds and is at the reference position of the ISS at the
    // middle of that minute (the two end directions are symmetric about it, so the great-circle midpoint is exactly it).
    // The ISS crosses the sky at about 0.36 degrees a second here, so it is inside the 0.5 degree tolerance for a second or
    // two only: the interval says the sight line met it then and not before or after.
    const t0 = Date.parse(lit.time);
    const centre = unitVector(lit.azimuth, apparentElevation(lit.elevation));
    const radians = (lit.azimuth * Math.PI) / 180;
    const along = { e: Math.cos(radians), n: -Math.sin(radians), u: 0 };
    const half = (5 * Math.PI) / 180;
    const direction = (sign) => {
      const v = { e: centre.e * Math.cos(half) + sign * along.e * Math.sin(half), n: centre.n * Math.cos(half) + sign * along.n * Math.sin(half), u: centre.u * Math.cos(half) + sign * along.u * Math.sin(half) };
      return enuToAzEl(v);
    };
    const start = direction(1);
    const end = direction(-1);
    const observation = parseObservation({
      time: iso(t0 - 30000), timeUncertaintySeconds: 0, observer: OBSERVER,
      direction: { azimuth: start.azimuth, elevation: start.elevation, azimuthReference: 'TRUE', toleranceDegrees: 0.5 },
      motion: { endAzimuth: end.azimuth, endElevation: end.elevation, endTime: iso(t0 + 30000) },
    });
    const result = await checkSatellites(observation, await loaded());
    const iss = result.candidates.find((c) => c.id === 'ISS');
    expect(iss).toBeTruthy();
    expect(Math.abs(Date.parse(iss.minSeparationAt) - t0)).toBeLessThan(2000);
    expect(Date.parse(iss.firstInside)).toBeGreaterThan(t0 - 3000);
    expect(Date.parse(iss.lastInside)).toBeLessThan(t0 + 3000);
    // The same sweep half a minute late is somewhere the ISS is not.
    const late = parseObservation({
      time: iso(t0 + 30000), timeUncertaintySeconds: 0, observer: OBSERVER,
      direction: { azimuth: start.azimuth, elevation: start.elevation, azimuthReference: 'TRUE', toleranceDegrees: 0.5 },
      motion: { endAzimuth: end.azimuth, endElevation: end.elevation, endTime: iso(t0 + 90000) },
    });
    expect((await checkSatellites(late, await loaded())).candidates.find((c) => c.id === 'ISS')).toBeUndefined();
  });

  it('does not count a satellite below a known terrain horizon, and says the terrain was the reason', async () => {
    const result = await checkSatellites(aimAt(lit), await loaded(), { horizon: { elevationAt: () => 35 } });
    expect(result.candidates).toHaveLength(0);
    const iss = result.items.find((i) => i.id === 'ISS');
    expect(iss).toMatchObject({ status: 'CHECKED', candidate: false, insideSomeTime: true, terrainAtClosest: 'OBSTRUCTED' });
  });
});

describe('checkSatellites: the denominator', () => {
  it('lists an object whose elements did not load as NOT_CHECKED with the reason, and counts it out of the checked ones', async () => {
    const result = await checkSatellites(aimAt(lit), await loaded({ [gpUrl(20580)]: { ok: false, status: 503, json: async () => ({}) } }));
    expect(result.denominator).toEqual({ checked: 2, requested: 3, names: ['ISS', 'HST', 'CSS'], notAllSatellites: true });
    const hubble = result.items.find((i) => i.id === 'HST');
    expect(hubble).toMatchObject({ status: 'NOT_CHECKED', reason: 'ELEMENTS_NOT_LOADED' });
    expect(hubble.message).toMatch(/HTTP 503/);
    expect(hubble.minSeparationDegrees).toBeUndefined();
    expect(result.limits.join(' ')).toMatch(/2 could be checked/);
  });

  it('refuses a past observation: elements far from the time are not checked, with the reason, and no object is called ruled out', async () => {
    const result = await checkSatellites(aimAt(lit, { time: '2026-12-25T00:00:00Z' }), await loaded());
    expect(result.denominator.checked).toBe(0);
    expect(result.candidates).toHaveLength(0);
    for (const item of result.items) {
      expect(item).toMatchObject({ status: 'NOT_CHECKED', reason: 'ELEMENTS_TOO_OLD' });
      expect(item.message).toMatch(/past observation needs element sets from its own time/);
      expect(item.message).toMatch(/14 days/);
    }
  });

  it('says it is not all satellites, and that a satellite in the sight line is a coincidence', async () => {
    const result = await checkSatellites(aimAt(lit), await loaded());
    expect(result.denominator.notAllSatellites).toBe(true);
    expect(result.limits.join(' ')).toMatch(/not all satellites/);
    expect(result.limits.join(' ')).toMatch(/not an identification/);
    expect(result.limits.join(' ')).toMatch(/Brightness is not estimated/);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.items[0])).toBe(true);
  });

  it('reports a pointing at empty sky as checked and not a candidate, with how close the nearest object came', async () => {
    const result = await checkSatellites(aimAt({ azimuth: 270, elevation: 70, time: lit.time }, { tolerance: 1 }), await loaded());
    expect(result.denominator.checked).toBe(3);
    expect(result.candidates).toHaveLength(0);
    for (const item of result.items) expect(item.minSeparationDegrees).toBeGreaterThan(1);
  });
});

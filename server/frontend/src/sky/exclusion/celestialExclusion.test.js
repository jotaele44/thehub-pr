import { describe, expect, it } from 'vitest';
import { bodyPosition, skyState } from '../astronomy';
import { checkCelestial, samplingPlan } from './celestialExclusion';
import { parseObservation } from './observation';
import { STARS, starPosition } from './stars';

const PLACE = { lat: 18.4663, lon: -66.1057, elevation: 0 };
const OBSERVER = { lat: PLACE.lat, lon: PLACE.lon, height: 0 };
const BASE = Date.parse('2026-11-04T00:00:00Z');
const iso = (ms) => new Date(ms).toISOString();
const observe = (azimuth, elevation, extra = {}, time = '2026-11-04T23:30:00Z', toleranceDegrees = 1) => parseObservation({
  time, timeUncertaintySeconds: 0, observer: OBSERVER, direction: { azimuth, elevation, azimuthReference: 'TRUE', toleranceDegrees }, ...extra,
});

// The first hour of 2026-11-04 (UTC) at which a predicate on the sky holds: scenarios are found in the sky, not assumed.
function hourWhen(predicate) {
  for (let h = 0; h < 24; h += 1) {
    const ms = BASE + h * 3600e3;
    const found = predicate(ms);
    if (found) return { ms, found };
  }
  throw new Error('no such hour');
}

describe('checkCelestial: a planet or the Sun in the sight line', () => {
  it('finds the brightest planet that is up when the sight line points at it, and nothing else of the planets', () => {
    const { ms, found: planet } = hourWhen((t) => skyState({ time: iso(t), ...PLACE }).planets.filter((p) => p.altitude > 10).sort((a, b) => a.magnitude - b.magnitude)[0]);
    const result = checkCelestial(observe(planet.azimuth, planet.altitude, {}, iso(ms)));
    const hit = result.candidates.find((c) => c.name === planet.body);
    expect(hit, planet.body).toBeTruthy();
    expect(hit.kind).toBe('planet');
    expect(hit.minSeparationDegrees).toBeLessThan(0.05);
    expect(hit.candidate).toBe(true);
    expect(hit.aboveHorizonAtClosest).toBe(true);
    expect(hit.magnitude).toBe(planet.magnitude);
    expect(result.candidates.filter((c) => c.kind === 'planet')).toHaveLength(1);
    expect(result.candidates[0].minSeparationDegrees).toBeLessThanOrEqual(result.candidates[result.candidates.length - 1].minSeparationDegrees);
  });

  it('finds the Sun at midday, with the day called daylight', () => {
    const sun = bodyPosition('Sun', '2026-11-04T16:00:00Z', PLACE);
    const result = checkCelestial(observe(sun.azimuth, sun.altitude, {}, '2026-11-04T16:00:00Z', 2));
    const hit = result.candidates.find((c) => c.name === 'Sun');
    expect(hit).toMatchObject({ kind: 'sun', candidate: true, magnitude: -26.74 });
    expect(result.daylight.label).toBe('Daylight');
  });

  it('does not count a body below the horizon, though it is in the direction: the Sun at night, below a sight line pointed under the horizon', () => {
    const night = '2026-11-04T04:00:00Z';
    const sun = bodyPosition('Sun', night, PLACE);
    expect(sun.altitude).toBeLessThan(-20);
    const result = checkCelestial(observe(sun.azimuth, sun.altitude, {}, night, 3));
    const hit = [...result.candidates, ...result.nearest].find((c) => c.name === 'Sun');
    expect(hit.insideSomeTime).toBe(true);
    expect(hit.candidate).toBe(false);
    expect(hit.aboveHorizonAtClosest).toBe(false);
    expect(result.candidates.find((c) => c.name === 'Sun')).toBeUndefined();
  });
});

describe('checkCelestial: a star in the sight line', () => {
  it('finds a bright star when the sight line points at it, and it is the closest thing', () => {
    const sirius = STARS.find((s) => s.name === 'Sirius');
    const { ms, found } = hourWhen((t) => { const p = starPosition(sirius, iso(t), PLACE); return p.altitude > 25 ? p : null; });
    const result = checkCelestial(observe(found.azimuth, found.altitude, {}, iso(ms), 0.5));
    expect(result.candidates[0]).toMatchObject({ kind: 'star', name: 'Sirius', hip: 32349, candidate: true });
    expect(result.candidates[0].minSeparationDegrees).toBeLessThan(0.05);
    expect(result.candidates[0].magnitude).toBeCloseTo(-1.44, 2);
  });

  it('follows a star across the sky with a moving sight line', () => {
    const arcturus = STARS.find((s) => s.name === 'Arcturus');
    const { ms } = hourWhen((t) => starPosition(arcturus, iso(t), PLACE).altitude > 25 && starPosition(arcturus, iso(t + 120e3), PLACE).altitude > 25);
    const a = starPosition(arcturus, iso(ms), PLACE);
    const b = starPosition(arcturus, iso(ms + 120e3), PLACE);
    const result = checkCelestial(observe(a.azimuth, a.altitude, { motion: { endAzimuth: b.azimuth, endElevation: b.altitude, endTime: iso(ms + 120e3) } }, iso(ms), 0.2));
    const hit = result.candidates.find((c) => c.name === 'Arcturus');
    expect(hit.insideFraction).toBeGreaterThan(0.95);
  });

  it('is empty, with the checked set stated, when the sight line points at empty sky', () => {
    // search a grid of directions for one with nothing of the 295 checked within 4 degrees
    let found = null;
    for (let az = 0; az < 360 && !found; az += 20) {
      for (let el = 30; el <= 80 && !found; el += 10) {
        const r = checkCelestial(observe(az, el, {}, '2026-11-04T23:30:00Z', 4));
        if (r.candidates.length === 0) found = r;
      }
    }
    expect(found).toBeTruthy();
    expect(found.checked).toEqual({ sun: 1, moon: 1, planets: 5, stars: 288, starLimitMagnitude: 3.5, notAllStars: true });
    expect(found.nearest).toHaveLength(5);
    expect(found.nearest[0].minSeparationDegrees).toBeGreaterThan(4);
    expect(found.limits.join(' ')).toMatch(/Not every star/);
    expect(found.limits.join(' ')).toMatch(/not an identification|not evidence/i);
  });
});

describe('checkCelestial: the time window', () => {
  it('counts a body that arrives during the uncertainty, and not one that does not', () => {
    const { ms, found } = hourWhen((t) => { const s = skyState({ time: iso(t + 300e3), ...PLACE }).planets.filter((p) => p.altitude > 10).sort((a, b) => a.magnitude - b.magnitude)[0]; return s; });
    const later = bodyPosition(found.body, iso(ms + 300e3), PLACE);
    const exact = checkCelestial(observe(later.azimuth, later.altitude, {}, iso(ms), 0.4));
    expect(exact.candidates.find((c) => c.name === found.body)).toBeUndefined();
    const widened = checkCelestial(parseObservation({
      time: iso(ms), timeUncertaintySeconds: 360, observer: OBSERVER, direction: { azimuth: later.azimuth, elevation: later.altitude, azimuthReference: 'TRUE', toleranceDegrees: 0.4 },
    }));
    const hit = widened.candidates.find((c) => c.name === found.body);
    expect(hit).toBeTruthy();
    expect(hit.insideFraction).toBeGreaterThan(0);
    expect(hit.insideFraction).toBeLessThan(0.6);
    expect(Date.parse(hit.firstInside)).toBeGreaterThan(ms);
  });

  it('says how it sampled: the step, the number of samples and the angular resolution that implies', () => {
    const o = parseObservation({ time: '2026-11-04T23:30:00Z', timeUncertaintySeconds: 120, observer: OBSERVER, direction: { azimuth: 90, elevation: 40, azimuthReference: 'TRUE', toleranceDegrees: 2 } });
    const plan = samplingPlan(o);
    expect(plan.stepSeconds).toBeGreaterThan(1);
    expect(plan.stepSeconds).toBeLessThanOrEqual(60);
    expect(plan.resolutionDegrees).toBeLessThanOrEqual(0.0201);
    expect(plan.instants[0]).toBe(o.window.start.getTime());
    expect(plan.instants[plan.instants.length - 1]).toBe(o.window.end.getTime());
    const result = checkCelestial(o);
    expect(result.sampling).toEqual({ stepSeconds: plan.stepSeconds, samples: plan.samples, resolutionDegrees: plan.resolutionDegrees });
  });

  it('samples a moving sight line more finely, and caps a long window, saying the resolution that costs', () => {
    const moving = parseObservation({
      time: '2026-11-04T23:30:00Z', timeUncertaintySeconds: 0, observer: OBSERVER, direction: { azimuth: 90, elevation: 40, azimuthReference: 'TRUE', toleranceDegrees: 2 },
      motion: { endAzimuth: 120, endElevation: 40, endTime: '2026-11-04T23:30:30Z' },
    });
    const still = parseObservation({ time: '2026-11-04T23:30:00Z', timeUncertaintySeconds: 15, observer: OBSERVER, direction: { azimuth: 90, elevation: 40, azimuthReference: 'TRUE', toleranceDegrees: 2 } });
    expect(samplingPlan(moving).stepSeconds).toBeLessThan(samplingPlan(still).stepSeconds);
    const long = parseObservation({ time: '2026-11-04T23:30:00Z', timeUncertaintySeconds: 10800, observer: OBSERVER, direction: { azimuth: 90, elevation: 40, azimuthReference: 'TRUE', toleranceDegrees: 2 } });
    const plan = samplingPlan(long);
    expect(plan.samples).toBeLessThanOrEqual(401);
    expect(plan.resolutionDegrees).toBeGreaterThan(0.02);
  });
});

describe('checkCelestial: a camera\'s field of view and the terrain horizon', () => {
  it('uses the field of view: a planet 20 degrees off the axis is in a 60 degree view and not in a 30 degree one', () => {
    const { ms, found } = hourWhen((t) => skyState({ time: iso(t), ...PLACE }).planets.filter((p) => p.altitude > 20 && p.altitude < 60).sort((a, b) => a.magnitude - b.magnitude)[0]);
    const cam = (h) => parseObservation({
      time: iso(ms), timeUncertaintySeconds: 0, observer: OBSERVER,
      direction: { azimuth: found.azimuth - 20 / Math.cos((found.altitude * Math.PI) / 180), elevation: found.altitude, azimuthReference: 'TRUE', frustum: { horizontalFovDegrees: h, verticalFovDegrees: h } },
    });
    expect(checkCelestial(cam(60)).candidates.some((c) => c.name === found.body)).toBe(true);
    expect(checkCelestial(cam(30)).candidates.some((c) => c.name === found.body)).toBe(false);
  });

  it('does not count a body below a known terrain horizon, counts one above it, and says when the terrain is not known', () => {
    const { ms, found } = hourWhen((t) => skyState({ time: iso(t), ...PLACE }).planets.filter((p) => p.altitude > 12 && p.altitude < 40).sort((a, b) => a.magnitude - b.magnitude)[0]);
    const o = observe(found.azimuth, found.altitude, {}, iso(ms), 1);
    const blocked = checkCelestial(o, { horizon: { elevationAt: () => found.altitude + 5 } });
    expect(blocked.candidates.find((c) => c.name === found.body)).toBeUndefined();
    const hidden = [...blocked.candidates, ...blocked.nearest].find((c) => c.name === found.body);
    if (hidden) expect(hidden.terrainAtClosest).toBe('OBSTRUCTED');
    const clear = checkCelestial(o, { horizon: { elevationAt: () => found.altitude - 5 } });
    expect(clear.candidates.find((c) => c.name === found.body)).toMatchObject({ terrainAtClosest: 'CLEAR', candidate: true });
    const unknown = checkCelestial(o, { horizon: { elevationAt: () => null } });
    expect(unknown.candidates.find((c) => c.name === found.body)).toMatchObject({ terrainAtClosest: 'UNKNOWN', candidate: true });
    expect(checkCelestial(o).candidates.find((c) => c.name === found.body).terrainAtClosest).toBe('NOT_CHECKED');
  });
});

describe('checkCelestial: the result', () => {
  it('is frozen, names its contract and states its conventions and limits', () => {
    const r = checkCelestial(observe(0, 80));
    expect(Object.isFrozen(r)).toBe(true);
    expect(Object.isFrozen(r.candidates)).toBe(true);
    expect(r.contract).toBe('sky-celestial-exclusion-v1');
    expect(r.conventions.join(' ')).toMatch(/no proper motion, parallax or aberration/);
    expect(r.sightlineAtTime).toEqual({ azimuth: 0, elevation: 80 });
  });
});

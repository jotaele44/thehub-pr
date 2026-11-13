import { describe, expect, it } from 'vitest';
import { angularSeparation } from './geometry';
import {
  MAX_WINDOW_SECONDS, OBSERVATION_CONTRACT, matchDirection, parseObservation, sightlineAt, windowSamples,
} from './observation';

const near = (value, expected, digits = 6) => expect(value).toBeCloseTo(expected, digits);
const base = () => ({
  time: '2026-11-04T01:30:00Z',
  timeUncertaintySeconds: 120,
  observer: { lat: 18.4663, lon: -66.1057, height: 5 },
  direction: { azimuth: 90, elevation: 30, azimuthReference: 'TRUE', toleranceDegrees: 5 },
});
const parse = (change = {}) => parseObservation({ ...base(), ...change });

describe('parseObservation', () => {
  it('reads a sight line with its observer, time and window, and says what it is', () => {
    const o = parse();
    expect(o.contract).toBe(OBSERVATION_CONTRACT);
    expect(o.time.toISOString()).toBe('2026-11-04T01:30:00.000Z');
    expect(o.timeUncertaintySeconds).toBe(120);
    expect(o.window.start.toISOString()).toBe('2026-11-04T01:28:00.000Z');
    expect(o.window.end.toISOString()).toBe('2026-11-04T01:32:00.000Z');
    expect(o.observer).toEqual({ lat: 18.4663, lon: -66.1057, height: 5 });
    expect(o.direction).toMatchObject({ azimuth: 90, elevation: 30, toleranceDegrees: 5, frustum: null, azimuthReference: 'TRUE', azimuthAsGiven: 90 });
    expect(o.motion).toBeNull();
    expect(o.notes).toEqual([]);
    expect(Object.isFrozen(o)).toBe(true);
    expect(Object.isFrozen(o.direction)).toBe(true);
  });

  it('does not change what it is given', () => {
    const input = base();
    const copy = JSON.parse(JSON.stringify(input));
    parseObservation(input);
    expect(input).toEqual(copy);
  });

  it('says in its notes what was not declared, instead of silently assuming it', () => {
    const o = parseObservation({ time: '2026-11-04T01:30:00Z', observer: { lat: 18, lon: -66 }, direction: { azimuth: 10, elevation: 10, azimuthReference: 'TRUE', toleranceDegrees: 3 } });
    expect(o.timeUncertaintySeconds).toBe(0);
    expect(o.timeUncertaintyDeclared).toBe(false);
    expect(o.observer.height).toBe(0);
    expect(o.notes.join(' ')).toMatch(/uncertainty was not declared/i);
    expect(o.notes.join(' ')).toMatch(/height was not declared/i);
  });

  it('refuses a time with no zone, which would be read in the viewer\'s own zone, and a time that is not a time', () => {
    expect(() => parse({ time: '2026-11-04T01:30:00' })).toThrow(/UTC designator/);
    expect(() => parse({ time: 'last night' })).toThrow(/not a valid instant/);
    expect(() => parse({ time: undefined })).toThrow();
  });

  it('refuses an observer that cannot exist and a time uncertainty that is negative, not a number or a day or more', () => {
    expect(() => parse({ observer: { lat: 95, lon: 0 } })).toThrow(/Latitude/);
    expect(() => parse({ timeUncertaintySeconds: -1 })).toThrow(/uncertainty/i);
    expect(() => parse({ timeUncertaintySeconds: 'a minute' })).toThrow(/uncertainty/i);
    expect(() => parse({ timeUncertaintySeconds: 90000 })).toThrow(/uncertainty/i);
  });

  it('refuses a direction without a declared azimuth reference, and converts a magnetic bearing only with a stated declination', () => {
    expect(() => parse({ direction: { azimuth: 90, elevation: 30, toleranceDegrees: 5 } })).toThrow(/azimuth reference/i);
    expect(() => parse({ direction: { azimuth: 90, elevation: 30, azimuthReference: 'GRID', toleranceDegrees: 5 } })).toThrow(/azimuth reference/i);
    expect(() => parse({ direction: { azimuth: 100, elevation: 30, azimuthReference: 'MAGNETIC', toleranceDegrees: 5 } })).toThrow(/declination/i);
    const o = parse({ direction: { azimuth: 100, elevation: 30, azimuthReference: 'MAGNETIC', magneticDeclinationDegrees: -10, toleranceDegrees: 5 } });
    near(o.direction.azimuth, 90, 9);
    expect(o.direction.azimuthAsGiven).toBe(100);
    expect(o.direction.magneticDeclinationDegrees).toBe(-10);
    expect(o.notes.join(' ')).toMatch(/magnetic/i);
    // A true bearing needs no declination, and one given with it is not applied.
    expect(parse({ direction: { azimuth: 100, elevation: 30, azimuthReference: 'TRUE', magneticDeclinationDegrees: -10, toleranceDegrees: 5 } }).direction.azimuth).toBe(100);
    expect(() => parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'MAGNETIC', magneticDeclinationDegrees: 120, toleranceDegrees: 5 } })).toThrow(/declination/i);
  });

  it('wraps an azimuth into [0, 360) and refuses an elevation outside -90 to 90', () => {
    expect(parse({ direction: { azimuth: -10, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 5 } }).direction.azimuth).toBe(350);
    expect(parse({ direction: { azimuth: 725, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 5 } }).direction.azimuth).toBe(5);
    expect(() => parse({ direction: { azimuth: 0, elevation: 91, azimuthReference: 'TRUE', toleranceDegrees: 5 } })).toThrow(/elevation/i);
    expect(() => parse({ direction: { azimuth: 'east', elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 5 } })).toThrow(/azimuth/i);
  });

  it('needs either a tolerance or a field of view, never both and never neither', () => {
    expect(() => parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'TRUE' } })).toThrow(/tolerance or a field of view/i);
    expect(() => parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'TRUE', toleranceDegrees: 5, frustum: { horizontalFovDegrees: 60, verticalFovDegrees: 40 } } })).toThrow(/not both/i);
    expect(() => parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'TRUE', toleranceDegrees: 0 } })).toThrow(/tolerance/i);
    expect(() => parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'TRUE', toleranceDegrees: 91 } })).toThrow(/tolerance/i);
    const o = parse({ direction: { azimuth: 1, elevation: 1, azimuthReference: 'TRUE', frustum: { horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 5 } } });
    expect(o.direction.toleranceDegrees).toBeNull();
    expect(o.direction.frustum).toEqual({ horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 5 });
  });
});

describe('a moving sight line', () => {
  const moving = () => parse({
    timeUncertaintySeconds: 0,
    direction: { azimuth: 90, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 4 },
    motion: { endAzimuth: 180, endElevation: 0, endTime: '2026-11-04T01:30:40Z' },
  });

  it('runs from the direction at the time to the end direction at the end time, and widens the window to cover both', () => {
    const o = parse({
      timeUncertaintySeconds: 30,
      direction: { azimuth: 90, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 4 },
      motion: { endAzimuth: 180, endElevation: 0, endTime: '2026-11-04T01:31:00Z' },
    });
    expect(o.window.start.toISOString()).toBe('2026-11-04T01:29:30.000Z');
    expect(o.window.end.toISOString()).toBe('2026-11-04T01:31:30.000Z');
    expect(o.motion.durationSeconds).toBe(60);
  });

  it('is on the great circle between the two directions, in proportion to the time, and holds the ends outside it', () => {
    const o = moving();
    const t0 = o.time.getTime();
    const t1 = o.motion.endTime.getTime();
    const middle = sightlineAt(o, (t0 + t1) / 2);
    near(middle.azimuth, 135, 6); near(middle.elevation, 0, 6);
    const quarter = sightlineAt(o, t0 + (t1 - t0) / 4);
    near(angularSeparation(quarter.azimuth, quarter.elevation, 90, 0), 22.5, 6);
    expect(sightlineAt(o, t0 - 60000)).toMatchObject({ azimuth: 90, elevation: 0 });
    near(sightlineAt(o, t1 + 60000).azimuth, 180, 6);
  });

  it('refuses an end that is not after the start, an end direction without a time, and a window longer than the engines work over', () => {
    const dir = { azimuth: 90, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 4 };
    expect(() => parse({ direction: dir, motion: { endAzimuth: 180, endElevation: 0, endTime: '2026-11-04T01:30:00Z' } })).toThrow(/after/i);
    expect(() => parse({ direction: dir, motion: { endAzimuth: 180, endElevation: 0 } })).toThrow(/time/i);
    expect(() => parse({ direction: dir, motion: { endAzimuth: 180, endElevation: 99, endTime: '2026-11-04T01:31:00Z' } })).toThrow(/elevation/i);
    expect(MAX_WINDOW_SECONDS).toBe(6 * 3600);
    expect(() => parse({ direction: dir, motion: { endAzimuth: 180, endElevation: 0, endTime: '2026-11-04T09:30:00Z' } })).toThrow(/window/i);
  });
});

describe('matchDirection', () => {
  it('is inside a tolerance cone when within it, with the separation and the margin', () => {
    const o = parse();
    const t = o.time.getTime();
    expect(matchDirection(o, 90, 30, t)).toMatchObject({ inside: true });
    near(matchDirection(o, 90, 30, t).separationDegrees, 0, 9);
    const inside = matchDirection(o, 90, 33, t);
    expect(inside.inside).toBe(true);
    near(inside.separationDegrees, 3, 6); near(inside.marginDegrees, -2, 6);
    const outside = matchDirection(o, 90, 37, t);
    expect(outside.inside).toBe(false);
    near(outside.separationDegrees, 7, 6); near(outside.marginDegrees, 2, 6);
  });

  it('uses the field of view when there is one, and is not inside for a direction behind the camera', () => {
    const o = parse({ direction: { azimuth: 90, elevation: 0, azimuthReference: 'TRUE', frustum: { horizontalFovDegrees: 40, verticalFovDegrees: 20 } } });
    const t = o.time.getTime();
    expect(matchDirection(o, 90, 0, t).inside).toBe(true);
    expect(matchDirection(o, 109, 0, t).inside).toBe(true);
    expect(matchDirection(o, 111, 0, t).inside).toBe(false);
    expect(matchDirection(o, 90, 9, t).inside).toBe(true);
    expect(matchDirection(o, 90, 11, t).inside).toBe(false);
    expect(matchDirection(o, 270, 0, t)).toMatchObject({ inside: false });
    expect(matchDirection(o, 109, 0, t).separationDegrees).toBeGreaterThan(18);
  });

  it('follows a moving sight line', () => {
    const o = parse({
      timeUncertaintySeconds: 0,
      direction: { azimuth: 90, elevation: 0, azimuthReference: 'TRUE', toleranceDegrees: 4 },
      motion: { endAzimuth: 180, endElevation: 0, endTime: '2026-11-04T01:31:00Z' },
    });
    const middle = (o.time.getTime() + o.motion.endTime.getTime()) / 2;
    expect(matchDirection(o, 135, 0, middle).inside).toBe(true);
    expect(matchDirection(o, 90, 0, middle).inside).toBe(false);
  });
});

describe('windowSamples', () => {
  it('covers the whole window, both ends included, at no more than the step', () => {
    const o = parse();
    const samples = windowSamples(o, 30);
    expect(samples[0]).toBe(o.window.start.getTime());
    expect(samples[samples.length - 1]).toBe(o.window.end.getTime());
    expect(samples).toHaveLength(9);
    for (let i = 1; i < samples.length; i += 1) expect(samples[i] - samples[i - 1]).toBeLessThanOrEqual(30000);
  });

  it('is a single instant when there is no window, and refuses a step that is not positive', () => {
    const o = parse({ timeUncertaintySeconds: 0 });
    expect(windowSamples(o, 30)).toEqual([o.time.getTime()]);
    expect(() => windowSamples(o, 0)).toThrow(/step/i);
  });
});

import { describe, expect, it } from 'vitest';
import reference from './fixtures/aircraftReference.json';
import { aircraftLookAt, checkAircraft, earthDipDegrees } from './aircraftExclusion';
import { parseTrackCsv } from './aircraftTracks';
import { angularSeparation } from './geometry';
import { matchDirection, parseObservation } from './observation';

const DECLARED = { source: 'synthetic tracks of the reference fixture', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
const EPOCH = Date.parse(reference.generated_by.epoch);
const seconds = (s) => EPOCH + s * 1000;
const csvOf = (track) => ['time,lat,lon,altitude', ...track.rows.map((r) => `${r.time},${r.lat},${r.lon},${r.altitude_m}`)].join('\n');
const parsedTracks = (declaration = DECLARED) => parseTrackCsv(
  ['time,lat,lon,altitude,id', ...Object.values(reference.tracks).flatMap((t) => t.rows.map((r) => `${r.time},${r.lat},${r.lon},${r.altitude_m},${t.id}`))].join('\n'),
  declaration,
);
const observationOf = (s, extra = {}) => parseObservation({
  time: s.time, timeUncertaintySeconds: s.uncertainty_s, observer: reference.observer,
  direction: { azimuth: s.azimuth, elevation: s.elevation, azimuthReference: 'TRUE', toleranceDegrees: s.tolerance_deg }, ...extra,
});
const scenario = (name) => reference.scenarios.find((s) => s.name === name);
const itemOf = (result, id) => result.items.find((i) => i.id === id);

describe('aircraftLookAt against the independent reference', () => {
  const parsed = parsedTracks();
  const trackA = parsed.tracks.find((t) => t.id === 'A');

  it('puts every checked report where Skyfield does (a 3000 m aircraft 15 to 45 km away)', () => {
    expect(reference.looks.reports.length).toBeGreaterThanOrEqual(12);
    let worst = 0;
    let worstRange = 0;
    for (const ref of reference.looks.reports) {
      const look = aircraftLookAt(reference.observer, trackA, Date.parse(ref.time));
      expect(look.state).toBe('OBSERVED');
      worst = Math.max(worst, angularSeparation(look.azimuth, look.elevation, ref.azimuth, ref.elevation));
      worstRange = Math.max(worstRange, Math.abs(look.rangeM - ref.range_m));
    }
    // measured 9e-12 degrees and 1.5e-9 m
    expect(worst).toBeLessThan(1e-9);
    expect(worstRange).toBeLessThan(1e-6);
  });

  it('puts every position between two reports where Skyfield does for a straight line between them, and calls it INTERPOLATED', () => {
    expect(reference.looks.between.length).toBeGreaterThanOrEqual(12);
    let worst = 0;
    for (const ref of reference.looks.between) {
      const look = aircraftLookAt(reference.observer, trackA, Date.parse(ref.time));
      expect(look.state).toBe('INTERPOLATED');
      worst = Math.max(worst, angularSeparation(look.azimuth, look.elevation, ref.azimuth, ref.elevation));
      expect(Math.abs(look.rangeM - ref.range_m)).toBeLessThan(1e-6);
    }
    expect(worst).toBeLessThan(1e-9);
  });

  it('never extrapolates: before the first report and after the last are OUTSIDE_TRACK, and a long gap is a GAP', () => {
    expect(aircraftLookAt(reference.observer, trackA, seconds(-0.001)).state).toBe('OUTSIDE_TRACK');
    expect(aircraftLookAt(reference.observer, trackA, seconds(600.001)).state).toBe('OUTSIDE_TRACK');
    const trackB = parsed.tracks.find((t) => t.id === 'B');
    expect(aircraftLookAt(reference.observer, trackB, seconds(145)).state).toBe('GAP');
    expect(aircraftLookAt(reference.observer, trackB, seconds(100)).state).toBe('OBSERVED');
    expect(aircraftLookAt(reference.observer, trackB, seconds(190)).state).toBe('OBSERVED');
    expect(aircraftLookAt(reference.observer, trackB, seconds(99)).state).toBe('INTERPOLATED');
  });
});

describe('checkAircraft against the independent reference', () => {
  const parsed = parsedTracks();

  it('finds the pass through a sight line, with the closest approach and the moments it entered and left, to a few milliseconds', () => {
    const s = scenario('A pass through the sight line');
    const result = checkAircraft(observationOf(s), parsed);
    const a = itemOf(result, 'A');
    expect(a).toMatchObject({ status: 'CHECKED', candidate: true, aboveHorizonAtClosest: true, terrainAtClosest: 'NOT_CHECKED' });
    expect(Math.abs(a.minSeparationDegrees - s.expected.min_separation_deg)).toBeLessThan(2e-6); // the reference's own 1 ms grid resolves a minimum to about 6e-7 degrees
    expect(Math.abs(Date.parse(a.closestAt) - seconds(s.expected.closest_s))).toBeLessThan(5);
    expect(Math.abs(Date.parse(a.firstInside) - seconds(s.expected.inside_s[0]))).toBeLessThan(3);
    expect(Math.abs(Date.parse(a.lastInside) - seconds(s.expected.inside_s[1]))).toBeLessThan(3);
    expect(Math.abs(a.rangeKmAtClosest * 1000 - s.expected.range_m)).toBeLessThan(5);
    expect(result.candidates.map((c) => c.id)).toEqual(['A']);
  });

  it('says a pass that only crosses between two reports rests on interpolation, and one a report is inside rests on the report', () => {
    const between = checkAircraft(observationOf(scenario('A sight line on an interpolated position')), parsed);
    const s3 = scenario('A sight line on an interpolated position');
    const a = itemOf(between, 'A');
    expect(a).toMatchObject({ candidate: true, basis: 'INTERPOLATED', closestState: 'INTERPOLATED' });
    expect(Math.abs(a.minSeparationDegrees - s3.expected.min_separation_deg)).toBeLessThan(2e-6); // the reference's own 1 ms grid resolves a minimum to about 6e-7 degrees
    expect(Math.abs(Date.parse(a.firstInside) - seconds(s3.expected.inside_s[0]))).toBeLessThan(3);
    expect(Math.abs(Date.parse(a.lastInside) - seconds(s3.expected.inside_s[1]))).toBeLessThan(3);

    const s5 = scenario('B window across the edge of a gap');
    const b = itemOf(checkAircraft(observationOf(s5), parsed), 'B');
    expect(b).toMatchObject({ candidate: true, basis: 'OBSERVED' });
  });

  it('does not call a miss a hit, and reports how near it came', () => {
    const s = scenario('A sight line away from the pass');
    const result = checkAircraft(observationOf(s), parsed);
    const a = itemOf(result, 'A');
    expect(a).toMatchObject({ status: 'CHECKED', candidate: false, insideSomeTime: false, basis: null, firstInside: null, lastInside: null });
    expect(Math.abs(a.minSeparationDegrees - s.expected.min_separation_deg)).toBeLessThan(2e-6); // the reference's own 1 ms grid resolves a minimum to about 6e-7 degrees
    expect(result.candidates).toHaveLength(0);
  });

  it('does not fill a gap: a window wholly inside one is NOT_CHECKED with the reason, and is not called empty sky', () => {
    const s = scenario('B window inside a gap');
    const result = checkAircraft(observationOf(s), parsed);
    const b = itemOf(result, 'B');
    expect(b).toMatchObject({ status: 'NOT_CHECKED', reason: s.expected.reason });
    expect(b.message).toMatch(/fills in|not filled in/);
    expect(b.message).toMatch(/says nothing about the window/);
    expect(result.denominator).toMatchObject({ tracks: 2, checked: 1, notChecked: 1, notAllAircraft: true });
  });

  it('counts coverage the way the reference counts it: what is interpolated, what is a gap, what is outside the track', () => {
    const gap = itemOf(checkAircraft(observationOf(scenario('B window across the edge of a gap')), parsed), 'B');
    expect(gap.coverage).toEqual(scenario('B window across the edge of a gap').expected.coverage);
    const before = itemOf(checkAircraft(observationOf(scenario('A window starts before the track')), parsed), 'A');
    expect(before.coverage).toEqual(scenario('A window starts before the track').expected.coverage);
    expect(before.quality).toMatchObject({ track_quality: 'continuous', gap_count: 0, validObservations: 121 });
    expect(itemOf(checkAircraft(observationOf(scenario('B window across the edge of a gap')), parsed), 'B').quality).toMatchObject({ track_quality: 'gapped', gap_count: 1 });
  });
});

describe('checkAircraft: what the data does not cover', () => {
  const parsed = parsedTracks();
  const base = { time: '2026-11-04T12:02:04Z', timeUncertaintySeconds: 0, observer: reference.observer, direction: { azimuth: 0, elevation: 11.4, azimuthReference: 'TRUE', toleranceDegrees: 1 } };

  it('says "no data in the window" for a track that ends before the observation, and that is not the same as no aircraft', () => {
    const late = checkAircraft(parseObservation({ ...base, time: '2026-11-04T13:00:00Z' }), parsed);
    for (const id of ['A', 'B']) {
      expect(itemOf(late, id)).toMatchObject({ status: 'NOT_CHECKED', reason: 'NO_DATA_IN_WINDOW' });
      expect(itemOf(late, id).message).toMatch(/No data is not the same as no aircraft/);
    }
    expect(late.denominator).toMatchObject({ checked: 0, notChecked: 2 });
    expect(late.candidates).toHaveLength(0);
  });

  it('does not compare a track with one valid report, and says why', () => {
    const single = parseTrackCsv('time,lat,lon,altitude\n2026-11-04T12:02:04Z,18.6,-66.1,3000', DECLARED);
    const item = itemOf(checkAircraft(parseObservation(base), single), 'track-1');
    expect(item).toMatchObject({ status: 'NOT_CHECKED', reason: 'NOT_ELIGIBLE' });
    expect(item.message).toMatch(/at least 2 are needed/);
    expect(item.quality.track_quality).toBe('single_point');
  });

  it('answers a window of one instant with no uncertainty, and covers it only when a report or a filled-in stretch is there', () => {
    const at = (iso) => itemOf(checkAircraft(parseObservation({ ...base, time: iso }), parsed), 'A');
    expect(at('2026-11-04T12:02:04.000Z').coverage).toMatchObject({ state: 'COVERED', windowSeconds: 0, reportsInWindow: 0 });
    expect(at('2026-11-04T12:02:05.000Z').coverage).toMatchObject({ state: 'COVERED', reportsInWindow: 1 });
    expect(at('2026-11-04T11:59:59.000Z')).toMatchObject({ status: 'NOT_CHECKED', reason: 'NO_DATA_IN_WINDOW' });
  });
});

describe('checkAircraft: the line of sight and what is declared', () => {
  const parsed = parsedTracks();
  const s1 = scenario('A pass through the sight line');
  const s2 = scenario('A sight line away from the pass');

  it('does not count an aircraft below a known terrain horizon, and says the terrain was the reason', () => {
    const result = checkAircraft(observationOf(s1), parsed, { horizon: { elevationAt: () => 20 } });
    expect(result.candidates).toHaveLength(0);
    expect(itemOf(result, 'A')).toMatchObject({ status: 'CHECKED', candidate: false, insideSomeTime: true, aboveHorizonAtClosest: false, terrainAtClosest: 'OBSTRUCTED' });
    const clear = checkAircraft(observationOf(s1), parsed, { horizon: { elevationAt: () => 2 } });
    expect(itemOf(clear, 'A')).toMatchObject({ candidate: true, terrainAtClosest: 'CLEAR' });
    const unknown = checkAircraft(observationOf(s1), parsed, { horizon: { elevationAt: () => null } });
    expect(itemOf(unknown, 'A')).toMatchObject({ candidate: true, terrainAtClosest: 'UNKNOWN' });
  });

  it('does not count an aircraft beyond the Earth\'s curvature, even in the direction of the sight line', () => {
    // 400 km east of San Juan at 1000 m: its elevation is about -1.7 degrees, below the sea-level horizon
    const far = parseTrackCsv(['time,lat,lon,altitude', '2026-11-04T12:00:00Z,18.4663,-62.4,1000', '2026-11-04T12:00:10Z,18.4663,-62.39,1000'].join('\n'), DECLARED);
    const track = far.tracks[0];
    const look = aircraftLookAt({ lat: 18.4663, lon: -66.1057, height: 0 }, track, Date.parse('2026-11-04T12:00:05Z'), far.declaration.policy);
    expect(look.elevation).toBeLessThan(-1);
    const observation = parseObservation({ time: '2026-11-04T12:00:05Z', observer: { lat: 18.4663, lon: -66.1057, height: 0 }, direction: { azimuth: look.azimuth, elevation: look.elevation, azimuthReference: 'TRUE', toleranceDegrees: 0.5 } });
    const item = itemOf(checkAircraft(observation, far), 'track-1');
    expect(item).toMatchObject({ status: 'CHECKED', insideSomeTime: true, candidate: false, aboveHorizonAtClosest: false });
    // the same direction from a hill whose horizon dips lower: the aircraft is then in view
    expect(earthDipDegrees(0)).toBe(0);
    expect(earthDipDegrees(1000)).toBeCloseTo(1.0, 0);
    const hill = parseObservation({ time: '2026-11-04T12:00:05Z', observer: { lat: 18.4663, lon: -66.1057, height: 1000 }, direction: { azimuth: look.azimuth, elevation: look.elevation, azimuthReference: 'TRUE', toleranceDegrees: 3 } });
    expect(itemOf(checkAircraft(hill, far), 'track-1').insideSomeTime).toBe(true);
  });

  it('lists an aircraft that missed the sight line but could be inside it given the position uncertainty declared, and not when none was', () => {
    const declared = parsedTracks({ ...DECLARED, horizontalUncertaintyMetres: 500, altitudeUncertaintyMetres: 100 });
    const withUncertainty = checkAircraft(observationOf(s2), declared);
    const a = itemOf(withUncertainty, 'A');
    expect(a.candidate).toBe(false);
    expect(a.angularUncertaintyDegrees).toBeGreaterThan(1.5);
    expect(a.possibleWithinUncertainty).toBe(true);
    expect(withUncertainty.possible.map((p) => p.id)).toEqual(['A']);
    const without = itemOf(checkAircraft(observationOf(s2), parsed), 'A');
    expect(without.angularUncertaintyDegrees).toBeNull();
    expect(without.possibleWithinUncertainty).toBe(false);
  });

  it('follows a moving sight line and meets the aircraft only when the sight line is where it is', () => {
    const s = scenario('A pass through the sight line');
    const t0 = seconds(s.expected.closest_s);
    const aim = (ms) => aircraftLookAt(reference.observer, parsed.tracks.find((t) => t.id === 'A'), ms);
    const from = aim(t0 - 20000);
    const to = aim(t0 + 20000);
    // a sight line that follows the aircraft's own track: it is on it at the end points but not in between (the track curves on the sky)
    const follows = parseObservation({
      time: new Date(t0 - 20000).toISOString(), observer: reference.observer,
      direction: { azimuth: from.azimuth, elevation: from.elevation, azimuthReference: 'TRUE', toleranceDegrees: 0.3 },
      motion: { endAzimuth: to.azimuth, endElevation: to.elevation, endTime: new Date(t0 + 20000).toISOString() },
    });
    const a = itemOf(checkAircraft(follows, parsed), 'A');
    expect(a.candidate).toBe(true);
    expect(Date.parse(a.firstInside)).toBeLessThan(t0 - 19000);
    // the same sweep a minute early meets nothing
    const early = parseObservation({
      time: new Date(t0 - 80000).toISOString(), observer: reference.observer,
      direction: { azimuth: from.azimuth, elevation: from.elevation, azimuthReference: 'TRUE', toleranceDegrees: 0.3 },
      motion: { endAzimuth: to.azimuth, endElevation: to.elevation, endTime: new Date(t0 - 40000).toISOString() },
    });
    expect(itemOf(checkAircraft(early, parsed), 'A').candidate).toBe(false);
  });

  it('agrees with a brute-force 1 ms scan for a camera field of view, whatever the engine\'s own search does', () => {
    const track = parsed.tracks.find((t) => t.id === 'A');
    const centre = aircraftLookAt(reference.observer, track, seconds(124));
    const observation = parseObservation({
      time: new Date(seconds(124)).toISOString(), timeUncertaintySeconds: 15, observer: reference.observer,
      direction: { azimuth: centre.azimuth + 6, elevation: centre.elevation - 2, azimuthReference: 'TRUE', frustum: { horizontalFovDegrees: 12, verticalFovDegrees: 8, rollDegrees: 0 } },
    });
    const a = itemOf(checkAircraft(observation, parsed), 'A');
    let first = null;
    let last = null;
    for (let ms = seconds(109); ms <= seconds(139); ms += 1) {
      const look = aircraftLookAt(reference.observer, track, ms);
      if (look.state === 'OUTSIDE_TRACK') continue;
      if (matchDirection(observation, look.azimuth, look.elevation, ms).inside) { first = first ?? ms; last = ms; }
    }
    expect(first).not.toBeNull();
    expect(a.candidate).toBe(true);
    expect(Math.abs(Date.parse(a.firstInside) - first)).toBeLessThan(5);
    expect(Math.abs(Date.parse(a.lastInside) - last)).toBeLessThan(5);
  });
});

describe('checkAircraft: what it states', () => {
  it('states the denominator, the conventions and the limits, and treats a callsign as a label', () => {
    const parsed = parsedTracks({ ...DECLARED, altitudeReference: 'BAROMETRIC', altitudeUncertaintyMetres: 120 });
    const result = checkAircraft(observationOf(scenario('A pass through the sight line')), parsed);
    expect(result.contract).toBe('sky-aircraft-exclusion-v1');
    expect(result.source).toMatchObject({ declared: DECLARED.source, altitudeReference: 'BAROMETRIC', clockOffsetDeclared: false });
    expect(result.policy).toMatchObject({ gapSeconds: 30, minimumValidObservations: 2 });
    const text = [...result.limits, ...result.conventions].join(' ');
    expect(text).toMatch(/not all air traffic/);
    expect(text).toMatch(/geometric coincidence, not an identification and not evidence of intent/);
    expect(text).toMatch(/callsign is a label the file carries/i);
    expect(text).toMatch(/nothing is extrapolated/);
    expect(text).toMatch(/pressure altitude is not a geometric height/);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.items[0])).toBe(true);
  });

  it('works over a six-hour window of one-second reports in a few seconds', () => {
    const rows = ['time,lat,lon,altitude'];
    for (let i = 0; i <= 21600; i += 1) rows.push(`${new Date(EPOCH + i * 1000).toISOString()},18.6,${-66.6 + i * 0.00002},3000`);
    const big = parseTrackCsv(rows.join('\n'), DECLARED);
    const observation = parseObservation({
      time: new Date(EPOCH + 10800000).toISOString(), timeUncertaintySeconds: 10800, observer: reference.observer,
      direction: { azimuth: 0, elevation: 11, azimuthReference: 'TRUE', toleranceDegrees: 1 },
    });
    const started = Date.now();
    const a = itemOf(checkAircraft(observation, big), 'track-1');
    expect(Date.now() - started).toBeLessThan(15000);
    expect(a.coverage).toMatchObject({ state: 'COVERED', reportsInWindow: 21601 });
  });
});

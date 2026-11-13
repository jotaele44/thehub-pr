import { describe, expect, it } from 'vitest';
import {
  AIRCRAFT_TRACK_CONTRACT, MAX_ROWS, TRACK_POLICY, TRACK_QUALITY, assessTrack, parseInstant, parseTrackCsv, parseTrackGeoJson, validateDeclaration,
} from './aircraftTracks';

const DECLARED = { source: 'unit-test file', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
const row = (time, lat, lon, altitude, extra = '') => `${time},${lat},${lon},${altitude}${extra}`;
const csv = (...rows) => ['time,lat,lon,altitude', ...rows].join('\n');
const at = (seconds) => new Date(Date.UTC(2026, 10, 4, 12, 0, seconds)).toISOString();

describe('the declaration', () => {
  it('requires a source, an altitude reference and a unit, and guesses none of them', () => {
    expect(() => validateDeclaration({})).toThrow(/where the tracks came from/);
    expect(() => validateDeclaration({ source: 'x' })).toThrow(/altitude reference/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'GPS' })).toThrow(/altitude reference/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'ELLIPSOID' })).toThrow(/altitude unit/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'ELLIPSOID', altitudeUnits: 'km' })).toThrow(/altitude unit/);
  });

  it('needs the geoid separation for a height above mean sea level and an uncertainty for a barometric altitude', () => {
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'MSL', altitudeUnits: 'm' })).toThrow(/geoid separation/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'MSL', altitudeUnits: 'm', geoidSeparationMetres: 500 })).toThrow(/geoid separation/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'BAROMETRIC', altitudeUnits: 'ft' })).toThrow(/barometric \(pressure\) altitude is not a geometric height/);
    expect(() => validateDeclaration({ source: 'x', altitudeReference: 'BAROMETRIC', altitudeUnits: 'ft', altitudeUncertaintyMetres: 0 })).toThrow(/more than 0/);
    const baro = validateDeclaration({ source: 'x', altitudeReference: 'BAROMETRIC', altitudeUnits: 'ft', altitudeUncertaintyMetres: 150 });
    expect(baro.notes.join(' ')).toMatch(/not a height above the ellipsoid/);
  });

  it('records an undeclared clock as UTC as written, and a declared one as a shift', () => {
    expect(validateDeclaration(DECLARED).clockOffsetDeclared).toBe(false);
    expect(validateDeclaration(DECLARED).notes.join(' ')).toMatch(/No clock offset was declared/);
    const shifted = validateDeclaration({ ...DECLARED, clockOffsetSeconds: -2.5 });
    expect(shifted).toMatchObject({ clockOffsetSeconds: -2.5, clockOffsetDeclared: true });
    expect(() => validateDeclaration({ ...DECLARED, clockOffsetSeconds: 90000 })).toThrow(/within a day/);
    expect(() => validateDeclaration({ ...DECLARED, horizontalUncertaintyMetres: -1 })).toThrow(/horizontalUncertaintyMetres/);
  });
});

describe('timestamps', () => {
  it('reads ISO 8601 with a zone and nothing else', () => {
    expect(parseInstant('2026-11-04T12:00:00Z').ms).toBe(Date.UTC(2026, 10, 4, 12));
    expect(parseInstant('2026-11-04T12:00:00.250Z').ms).toBe(Date.UTC(2026, 10, 4, 12, 0, 0, 250));
    expect(parseInstant('2026-11-04 14:00:00+02:00').ms).toBe(Date.UTC(2026, 10, 4, 12));
    expect(parseInstant('2026-11-04T07:30-04:30').ms).toBe(Date.UTC(2026, 10, 4, 12));
    for (const bad of ['2026-11-04T12:00:00', 'Nov 4 2026 12:00', '2026-02-31T12:00:00Z', '2026-13-01T12:00:00Z', '2026-11-04T25:00:00Z', '12:00:00Z', '']) {
      expect(parseInstant(bad).error, bad).toBeTruthy();
    }
    expect(parseInstant(1789000000).error).toMatch(/not text/);
  });

  it('reads epoch seconds only when told to, and refuses milliseconds', () => {
    expect(parseInstant('1793448000', 'EPOCH_SECONDS').ms).toBe(1793448000000);
    expect(parseInstant(1793448000.5, 'EPOCH_SECONDS').ms).toBe(1793448000500);
    expect(parseInstant('1793448000000', 'EPOCH_SECONDS').error).toMatch(/milliseconds/);
    expect(parseInstant('12', 'EPOCH_SECONDS').error).toMatch(/outside 2001 to 2096/);
    expect(parseInstant('abc', 'EPOCH_SECONDS').error).toBeTruthy();
  });
});

describe('parseTrackCsv', () => {
  it('reads a track, converts feet and a geoid separation to a height above the ellipsoid, and shifts a declared clock', () => {
    const text = csv(row(at(0), 18.5, -66.2, 10000), row(at(10), 18.5, -66.19, 10000));
    const parsed = parseTrackCsv(text, { ...DECLARED, altitudeReference: 'MSL', altitudeUnits: 'ft', geoidSeparationMetres: -43.1, clockOffsetSeconds: 2 });
    expect(parsed.contract).toBe(AIRCRAFT_TRACK_CONTRACT);
    const [track] = parsed.tracks;
    expect(track.id).toBe('track-1');
    expect(track.observations[0].height).toBeCloseTo(3048 - 43.1, 6);
    expect(track.observations[0].ms).toBe(Date.UTC(2026, 10, 4, 12, 0, 2));
    expect(parsed.notes.join(' ')).toMatch(/geoid separation given \(-43.1 m\)/);
  });

  it('groups rows by id, labels a track by its callsign without treating it as an identity, and handles quotes, CRLF and a byte-order mark', () => {
    const text = `﻿Time,Lat,Lon,Altitude,ID,Callsign\r\n${at(0)},18.5,-66.2,3000,a,"LOVE, AIR 1"\r\n${at(5)},18.5,-66.19,3000,a,\r\n${at(0)},18.4,-66.1,2000,b,\r\n${at(5)},18.4,-66.09,2000,b,\r\n`;
    const parsed = parseTrackCsv(text, DECLARED);
    expect(parsed.tracks.map((t) => t.id)).toEqual(['a', 'b']);
    expect(parsed.tracks[0].label).toBe('LOVE, AIR 1');
    expect(parsed.tracks[1].label).toBeNull();
    expect(parsed.notes.join(' ')).toMatch(/callsign or identifier in a file is a label/);
  });

  it('counts and lists every row it could not read, with the reason, and never reads a missing altitude as ground level', () => {
    const text = csv(
      row(at(0), 18.5, -66.2, 3000), row(at(5), 18.5, -66.19, ''), row(at(10), 91, -66.18, 3000), row(at(15), 18.5, -66.17, 3000),
      row('2026-11-04T12:00:20', 18.5, -66.16, 3000), row(at(15), 18.6, -66.17, 3000), row(at(25), 18.5, -66.14, 3000),
    );
    const parsed = parseTrackCsv(text, DECLARED);
    expect(parsed.rows).toBe(7);
    expect(parsed.tracks[0].observations).toHaveLength(3);
    expect(parsed.rejected.count).toBe(4);
    const reasons = parsed.rejected.listed.map((r) => r.reason).join(' | ');
    expect(reasons).toMatch(/altitude is missing \(it is not assumed to be ground level\)/);
    expect(reasons).toMatch(/latitude is missing or not between -90 and 90/);
    expect(reasons).toMatch(/UTC designator/);
    expect(reasons).toMatch(/second report at the same instant/);
    // the file's row numbers, counting the header as row 1
    expect(parsed.rejected.listed.map((r) => r.index)).toEqual([3, 4, 6, 7]);
  });

  it('sorts reports that arrive out of order', () => {
    const parsed = parseTrackCsv(csv(row(at(10), 18.5, -66.19, 3000), row(at(0), 18.5, -66.2, 3000)), DECLARED);
    expect(parsed.tracks[0].observations.map((o) => o.ms)).toEqual([Date.UTC(2026, 10, 4, 12), Date.UTC(2026, 10, 4, 12, 0, 10)]);
  });

  it('refuses a file that is empty, has no header columns, or is too large, and says what it needs', () => {
    expect(() => parseTrackCsv('', DECLARED)).toThrow(/empty/);
    expect(() => parseTrackCsv('time,lat,lon\n1,2,3', DECLARED)).toThrow(/"altitude" is missing/);
    expect(() => parseTrackCsv('time,lat,lon,altitude', DECLARED)).toThrow(/no rows/);
    expect(() => parseTrackCsv(`time,lat,lon,altitude\n"${at(0)}`, DECLARED)).toThrow(/never closes/);
    expect(() => parseTrackCsv(csv(...Array.from({ length: MAX_ROWS + 1 }, (_, i) => row(at(i), 18.5, -66.2, 3000))), DECLARED)).toThrow(/at most 50000/);
    expect(() => parseTrackCsv(csv(row(at(0), 18.5, -66.2, 3000)), { source: 'x' })).toThrow(/altitude reference/);
  });

  it('says plainly what the file is not: all air traffic', () => {
    const parsed = parseTrackCsv(csv(row(at(0), 18.5, -66.2, 3000), row(at(5), 18.5, -66.19, 3000)), DECLARED);
    expect(parsed.limits.join(' ')).toMatch(/not all air traffic/);
    expect(parsed.limits.join(' ')).toMatch(/nothing is extrapolated/);
    expect(Object.isFrozen(parsed)).toBe(true);
    expect(Object.isFrozen(parsed.tracks[0])).toBe(true);
  });
});

describe('track quality, in the Skywatcher vocabulary', () => {
  const build = (seconds, { lonStep = 0.00001 } = {}) => {
    const parsed = parseTrackCsv(csv(...seconds.map((s, i) => row(at(s), 18.5, -66.2 + i * lonStep, 3000))), DECLARED);
    return parsed.tracks[0].quality;
  };

  it('uses exactly the four classes of the Skywatcher flight session schema and its two-observation rule', () => {
    expect(TRACK_QUALITY).toEqual(['continuous', 'gapped', 'sparse_evidence', 'single_point']);
    expect(TRACK_POLICY.minimumValidObservations).toBe(2);
    expect(TRACK_POLICY.note).toMatch(/Policy, not physics/);
  });

  it('is single_point and not eligible with one valid report, and not eligible with none', () => {
    expect(build([0])).toMatchObject({ validObservations: 1, eligible: false, track_quality: 'single_point', gap_count: 0, reason: 'FEWER_THAN_TWO_VALID_OBSERVATIONS' });
    const none = parseTrackCsv(csv(row(at(0), 18.5, -66.2, '')), DECLARED).tracks[0].quality;
    expect(none).toMatchObject({ validObservations: 0, eligible: false, track_quality: null, reason: 'NO_VALID_OBSERVATIONS' });
  });

  it('is continuous when every interval is within the gap length', () => {
    expect(build([0, 10, 20, 30, 40])).toMatchObject({ eligible: true, track_quality: 'continuous', gap_count: 0, medianIntervalSeconds: 10, maxIntervalSeconds: 10 });
  });

  it('is gapped, with the gap counted and listed, when some intervals are longer than the gap length', () => {
    const q = build([0, 10, 20, 120, 130, 140]);
    expect(q).toMatchObject({ eligible: true, track_quality: 'gapped', gap_count: 1, maxIntervalSeconds: 100 });
    expect(q.gaps[0]).toMatchObject({ seconds: 100, reason: 'LONG_INTERVAL', from: at(20), to: at(120) });
  });

  it('is sparse_evidence when most intervals are gaps', () => {
    expect(build([0, 100, 200, 300])).toMatchObject({ track_quality: 'sparse_evidence', gap_count: 3, medianIntervalSeconds: 100 });
  });

  it('treats a jump faster than any aircraft as a gap, not as a position to trust', () => {
    // 1 degree of longitude (about 105 km) in 10 s is 10 km/s
    const q = build([0, 10, 20], { lonStep: 1 });
    expect(q.gap_count).toBe(2);
    expect(q.gaps[0]).toMatchObject({ reason: 'IMPLAUSIBLE_SPEED' });
    expect(q.gaps[0].speedMetresPerSecond).toBeGreaterThan(10000);
  });

  it('takes a gap length the user declared, and records that it did', () => {
    const parsed = parseTrackCsv(csv(...[0, 10, 20, 60, 70].map((s, i) => row(at(s), 18.5, -66.2 + i * 0.00001, 3000))), { ...DECLARED, gapSeconds: 60 });
    expect(parsed.tracks[0].quality).toMatchObject({ track_quality: 'continuous', gap_count: 0 });
    expect(parsed.declaration.policy.gapSeconds).toBe(60);
    expect(parsed.notes.join(' ')).toMatch(/gap length was set to 60 s instead of the default 30 s/);
    expect(() => validateDeclaration({ ...DECLARED, gapSeconds: 0 })).toThrow(/gap length/);
  });

  it('assessTrack works on its own for an empty list', () => {
    expect(assessTrack([])).toMatchObject({ validObservations: 0, eligible: false, track_quality: null, spanStart: null });
  });
});

describe('parseTrackGeoJson', () => {
  const point = (time, lon, lat, alt, props = {}) => ({ type: 'Feature', properties: { time, ...props }, geometry: { type: 'Point', coordinates: [lon, lat, alt] } });

  it('reads Point features with a time, grouped by id, with the callsign as a label', () => {
    const doc = { type: 'FeatureCollection', features: [point(at(0), -66.2, 18.5, 3000, { id: 'a', callsign: 'AB1' }), point(at(5), -66.19, 18.5, 3000, { id: 'a' }), point(at(0), -66.1, 18.4, 2000, { id: 'b' })] };
    const parsed = parseTrackGeoJson(doc, DECLARED);
    expect(parsed.format).toBe('GeoJSON');
    expect(parsed.tracks.map((t) => [t.id, t.label, t.observations.length])).toEqual([['a', 'AB1', 2], ['b', null, 1]]);
    expect(parsed.tracks[1].quality.track_quality).toBe('single_point');
  });

  it('reads a LineString whose properties.times has one time per coordinate, and sets aside one that does not', () => {
    const good = { type: 'Feature', properties: { id: 'l', times: [at(0), at(5), at(10)] }, geometry: { type: 'LineString', coordinates: [[-66.2, 18.5, 3000], [-66.19, 18.5, 3000], [-66.18, 18.5, 3000]] } };
    const bad = { type: 'Feature', properties: { id: 'm', times: [at(0)] }, geometry: { type: 'LineString', coordinates: [[-66.2, 18.5, 3000], [-66.19, 18.5, 3000]] } };
    const parsed = parseTrackGeoJson(JSON.stringify({ type: 'FeatureCollection', features: [good, bad] }), DECLARED);
    expect(parsed.tracks).toHaveLength(1);
    expect(parsed.tracks[0].quality.track_quality).toBe('continuous');
    expect(parsed.rejected.count).toBe(1);
    expect(parsed.rejected.listed[0].reason).toMatch(/needs properties.times with one time per coordinate \(2\)/);
  });

  it('rejects other geometries and an altitude-less coordinate by reason, and refuses what is not GeoJSON', () => {
    const doc = { type: 'FeatureCollection', features: [point(at(0), -66.2, 18.5, 3000), point(at(5), -66.19, 18.5, undefined), { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [] } }] };
    const parsed = parseTrackGeoJson(doc, DECLARED);
    expect(parsed.rejected.count).toBe(2);
    const reasons = parsed.rejected.listed.map((r) => r.reason).join(' | ');
    expect(reasons).toMatch(/Polygon geometry is not a Point or a LineString/);
    expect(reasons).toMatch(/altitude is missing/);
    expect(() => parseTrackGeoJson('not json', DECLARED)).toThrow(/not valid JSON/);
    expect(() => parseTrackGeoJson({ type: 'Polygon' }, DECLARED)).toThrow(/FeatureCollection or a Feature/);
    expect(() => parseTrackGeoJson({ type: 'FeatureCollection', features: [] }, DECLARED)).toThrow(/no positions/);
  });
});

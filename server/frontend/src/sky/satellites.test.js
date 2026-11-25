import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { GeoVector, MakeTime } from 'astronomy-engine';
import { sgp4, twoline2satrec } from 'satellite.js';
import elementsText from './fixtures/satellite-elements.json?raw';
import reference from './fixtures/satelliteReference.json';
import valladoCases from './fixtures/vallado/SGP4-VER.TLE?raw';
import valladoOutput from './fixtures/vallado/tcppver.out?raw';
import valladoProvenance from './fixtures/vallado/PROVENANCE.json';
import {
  ELEMENT_POLICY, EARTH_SHADOW_RADIUS_KM, SATELLITES, VISIBLE_LABEL, elementAge, findPasses, gpUrl, lookAt, parseGp,
  shadowState, skyTrack, stateAt, sunVectorKm,
} from './satellites';

const elements = JSON.parse(elementsText);
const SAN_JUAN = { lat: 18.4663, lon: -66.1057, elevation: 0 };
const DAY = 86400e3;
const hypot3 = (a, b) => Math.hypot(a.x - b[0], a.y - b[1], a.z - b[2]);
const angleDifference = (a, b) => Math.abs((((a - b) % 360) + 540) % 360 - 180);
const sha256 = (text) => createHash('sha256').update(text, 'utf8').digest('hex');

const iss = () => parseGp(elements.items.ISS.payload[0]);
const recordWith = (change) => ({ ...elements.items.ISS.payload[0], ...change });
const without = (key) => { const copy = { ...elements.items.ISS.payload[0] }; delete copy[key]; return copy; };

// Vallado's verification set: TEME position (km) and velocity (km/s) from his C++ SGP4 at stated minutes after the epoch.
function readVallado() {
  const references = new Map();
  let current = null;
  for (const line of valladoOutput.split(/\r?\n/)) {
    const header = line.match(/^\s*(\d+)\s+xx\s*$/);
    if (header) { current = Number(header[1]); references.set(current, []); continue; }
    const fields = line.trim().split(/\s+/).map(Number);
    if (current !== null && fields.length >= 7 && fields.slice(0, 7).every(Number.isFinite)) references.get(current).push(fields.slice(0, 7));
  }
  const lines = valladoCases.split(/\r?\n/);
  const cases = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (!lines[i].startsWith('1 ')) continue;
    const satnum = Number(lines[i].slice(2, 7));
    cases.push({ satnum, satrec: twoline2satrec(lines[i].slice(0, 69), lines[i + 1].slice(0, 69)), rows: references.get(satnum) ?? [] });
  }
  return cases;
}

describe('SGP4 against Vallado\'s verification set (AIAA 2006-6753)', () => {
  const cases = readVallado();

  it('uses the files whose checksums are recorded', () => {
    expect(sha256(valladoCases)).toBe(valladoProvenance.files['SGP4-VER.TLE'].sha256);
    expect(sha256(valladoOutput)).toBe(valladoProvenance.files['tcppver.out'].sha256);
  });

  it('reproduces Vallado\'s reference states for every case where SGP4 gives one, to a tenth of a millimetre', () => {
    // Measured when this was written: largest difference 1.2e-7 km in position and 8.5e-10 km/s in velocity over
    // 710 reference states. The tolerances leave an order of magnitude and stay far below anything an observer sees.
    let compared = 0;
    let largestPosition = 0;
    let largestVelocity = 0;
    const refused = [];
    for (const { satnum, satrec, rows } of cases) {
      for (const [minutes, x, y, z, vx, vy, vz] of rows) {
        const state = sgp4(satrec, minutes);
        if (!state || !state.position) { refused.push(satnum); continue; }
        largestPosition = Math.max(largestPosition, Math.hypot(state.position.x - x, state.position.y - y, state.position.z - z));
        largestVelocity = Math.max(largestVelocity, Math.hypot(state.velocity.x - vx, state.velocity.y - vy, state.velocity.z - vz));
        compared += 1;
      }
    }
    expect(cases).toHaveLength(33);
    expect(compared).toBeGreaterThanOrEqual(700);
    expect(largestPosition).toBeLessThan(1e-6);
    expect(largestVelocity).toBeLessThan(1e-8);
    // The one case the library refuses is Vallado's deliberately degenerate orbit (error code 3), not a silent skip.
    expect([...new Set(refused)]).toEqual([33334]);
  });

  it('never shows a state when SGP4 reports an error: the wrapper fails closed with the code', () => {
    const degenerate = cases.find((c) => c.satnum === 33334);
    const epoch = new Date((degenerate.satrec.jdsatepoch - 2440587.5) * DAY);
    const result = stateAt({ satrec: degenerate.satrec, epoch }, epoch);
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('SGP4_ERROR');
    expect(result.code).toBe(3);
    expect(result.positionKm).toBeUndefined();
  });
});

describe('parsing a CelesTrak GP record', () => {
  it('reads the real ISS element set and keeps its identity and epoch', () => {
    const element = iss();
    expect(element.noradId).toBe(25544);
    expect(element.name).toBe('ISS (ZARYA)');
    expect(element.objectId).toBe('1998-067A');
    // CelesTrak's EPOCH carries no zone; it is UTC.
    expect(element.epoch.toISOString()).toBe(`${elements.items.ISS.payload[0].EPOCH.slice(0, 23)}Z`);
    expect(element.periodMinutes).toBeCloseTo(1440 / elements.items.ISS.payload[0].MEAN_MOTION, 9);
  });

  it('accepts numbers sent as strings, as other OMM sources send them, with the same result', () => {
    const record = elements.items.ISS.payload[0];
    const asStrings = Object.fromEntries(Object.entries(record).map(([key, value]) => [key, typeof value === 'number' ? String(value) : value]));
    const a = iss();
    const b = parseGp(asStrings);
    expect(b.epoch.getTime()).toBe(a.epoch.getTime());
    const t = new Date(a.epoch.getTime() + 3600e3);
    expect(stateAt(b, t).positionKm).toEqual(stateAt(a, t).positionKm);
  });

  it('refuses a record that is missing a field, rather than defaulting it', () => {
    for (const key of ['MEAN_MOTION', 'ECCENTRICITY', 'INCLINATION', 'RA_OF_ASC_NODE', 'ARG_OF_PERICENTER', 'MEAN_ANOMALY', 'BSTAR', 'NORAD_CAT_ID', 'MEAN_MOTION_DOT', 'MEAN_MOTION_DDOT']) {
      expect(() => parseGp(without(key)), key).toThrow(new RegExp(key));
    }
    expect(() => parseGp(without('EPOCH'))).toThrow(/EPOCH/);
    expect(() => parseGp(without('OBJECT_NAME'))).toThrow(/OBJECT_NAME/);
  });

  it('refuses values no orbit has, and element sets that are not SGP4', () => {
    expect(() => parseGp(recordWith({ ECCENTRICITY: 1 }))).toThrow(/ECCENTRICITY/);
    expect(() => parseGp(recordWith({ ECCENTRICITY: -0.1 }))).toThrow(/ECCENTRICITY/);
    expect(() => parseGp(recordWith({ INCLINATION: 181 }))).toThrow(/INCLINATION/);
    expect(() => parseGp(recordWith({ RA_OF_ASC_NODE: 360 }))).toThrow(/RA_OF_ASC_NODE/);
    expect(() => parseGp(recordWith({ MEAN_MOTION: 0 }))).toThrow(/MEAN_MOTION/);
    expect(() => parseGp(recordWith({ MEAN_MOTION: 25 }))).toThrow(/MEAN_MOTION/);
    expect(() => parseGp(recordWith({ MEAN_MOTION: 'fast' }))).toThrow(/MEAN_MOTION/);
    expect(() => parseGp(recordWith({ MEAN_ELEMENT_THEORY: 'SGP4-XP' }))).toThrow(/SGP4/);
    expect(() => parseGp(recordWith({ EPHEMERIS_TYPE: 2 }))).toThrow(/EPHEMERIS_TYPE/);
    expect(() => parseGp(recordWith({ NORAD_CAT_ID: 25544.5 }))).toThrow(/NORAD_CAT_ID/);
    expect(() => parseGp(null)).toThrow(/object/);
    expect(() => parseGp([elements.items.ISS.payload[0]])).toThrow(/object/);
  });

  it('refuses an epoch it cannot read as an instant', () => {
    expect(() => parseGp(recordWith({ EPOCH: 'yesterday' }))).toThrow(/EPOCH/);
    expect(() => parseGp(recordWith({ EPOCH: '2026-13-45T25:61:61' }))).toThrow(/EPOCH/);
    expect(() => parseGp(recordWith({ EPOCH: 20261102 }))).toThrow(/EPOCH/);
  });

  it('builds the CelesTrak request address for a catalogue number, with nothing else in it', () => {
    expect(gpUrl(25544)).toBe('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=json');
    expect(SATELLITES.map((s) => s.noradId)).toEqual([25544, 20580, 48274]);
  });
});

describe('the element-age policy', () => {
  const element = () => iss();
  const at = (days) => new Date(element().epoch.getTime() + days * DAY);

  it('steps confidence by distance from the epoch, before or after, and refuses beyond the limit', () => {
    const e = element();
    expect(elementAge(e, at(0)).state).toBe('NORMAL');
    expect(elementAge(e, at(3)).state).toBe('NORMAL');
    expect(elementAge(e, at(3.01)).state).toBe('LOWER');
    expect(elementAge(e, at(7)).state).toBe('LOWER');
    expect(elementAge(e, at(7.01)).state).toBe('LOW');
    expect(elementAge(e, at(14)).state).toBe('LOW');
    expect(elementAge(e, at(14.01)).state).toBe('REFUSED');
    expect(elementAge(e, at(-3)).state).toBe('NORMAL');
    expect(elementAge(e, at(-14.01)).state).toBe('REFUSED');
    expect(ELEMENT_POLICY.kind).toBe('policy');
  });

  it('refuses to give a state beyond the limit, and says why', () => {
    const result = stateAt(element(), at(20));
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('ELEMENTS_TOO_OLD');
    expect(result.message).toMatch(/14 days/);
    expect(stateAt(element(), at(-20)).ok).toBe(false);
    expect(stateAt(element(), at(13)).ok).toBe(true);
  });
});

describe('physical sense of the propagated ISS', () => {
  it('stays on the orbit its own elements describe over one revolution', () => {
    const e = iss();
    const record = elements.items.ISS.payload[0];
    const n = (record.MEAN_MOTION * 2 * Math.PI) / 86400;
    const a = (398600.4418 / (n * n)) ** (1 / 3);
    const start = e.epoch.getTime() + 3600e3;
    let latitudeMax = 0;
    let radiusMin = Infinity;
    let radiusMax = 0;
    let worstSpeed = 0;
    for (let s = 0; s <= e.periodMinutes * 60; s += 30) {
      const look = lookAt(e, new Date(start + s * 1000), SAN_JUAN);
      const state = stateAt(e, new Date(start + s * 1000));
      const r = Math.hypot(state.positionKm.x, state.positionKm.y, state.positionKm.z);
      const v = Math.hypot(state.velocityKmS.x, state.velocityKmS.y, state.velocityKmS.z);
      latitudeMax = Math.max(latitudeMax, Math.abs(look.subpoint.latitude));
      radiusMin = Math.min(radiusMin, r);
      radiusMax = Math.max(radiusMax, r);
      worstSpeed = Math.max(worstSpeed, Math.abs(v - Math.sqrt(398600.4418 * (2 / r - 1 / a))));
    }
    // Kepler's third law from the mean motion gives the radius to within the J2 short-period terms (about 20 km).
    expect(radiusMin).toBeGreaterThan(a * (1 - record.ECCENTRICITY) - 25);
    expect(radiusMax).toBeLessThan(a * (1 + record.ECCENTRICITY) + 25);
    expect(worstSpeed).toBeLessThan(0.1);
    // The ground track reaches the inclination and no further (geodetic latitude runs up to 0.2 degree past geocentric).
    expect(latitudeMax).toBeLessThan(record.INCLINATION + 0.25);
    expect(latitudeMax).toBeGreaterThan(record.INCLINATION - 0.5);
  });

  it('is directly overhead for an observer under the sub-satellite point, and below the horizon on the far side', () => {
    const e = iss();
    const t = new Date(e.epoch.getTime() + 5 * 3600e3);
    const sub = lookAt(e, t, SAN_JUAN).subpoint;
    const under = lookAt(e, t, { lat: sub.latitude, lon: sub.longitude, elevation: 0 });
    expect(under.elevation).toBeGreaterThan(89.9);
    expect(Math.abs(under.rangeKm - sub.heightKm)).toBeLessThan(1);
    const opposite = lookAt(e, t, { lat: -sub.latitude, lon: sub.longitude > 0 ? sub.longitude - 180 : sub.longitude + 180, elevation: 0 });
    expect(opposite.elevation).toBeLessThan(-60);
  });
});

describe('the Earth\'s shadow', () => {
  const sunAlongX = { x: 149597870.7, y: 0, z: 0 };

  it('puts a satellite behind the Earth inside the cylinder in shadow and outside it in sunlight', () => {
    expect(shadowState({ x: -7000, y: 0, z: 0 }, sunAlongX).sunlit).toBe(false);
    expect(shadowState({ x: -7000, y: EARTH_SHADOW_RADIUS_KM - 1, z: 0 }, sunAlongX).sunlit).toBe(false);
    expect(shadowState({ x: -7000, y: 0, z: EARTH_SHADOW_RADIUS_KM - 1 }, sunAlongX).sunlit).toBe(false);
    expect(shadowState({ x: -7000, y: EARTH_SHADOW_RADIUS_KM + 1, z: 0 }, sunAlongX).sunlit).toBe(true);
    expect(shadowState({ x: -42164, y: 0, z: 0 }, sunAlongX).sunlit).toBe(false);
  });

  it('keeps a satellite on the Sun\'s side of the Earth in sunlight, whatever its offset', () => {
    expect(shadowState({ x: 7000, y: 0, z: 0 }, sunAlongX).sunlit).toBe(true);
    expect(shadowState({ x: 1, y: 100, z: 0 }, sunAlongX).sunlit).toBe(true);
    expect(shadowState({ x: 0, y: 0, z: 7000 }, sunAlongX).sunlit).toBe(true);
  });

  it('does not depend on how the axes are oriented', () => {
    const rotate = ({ x, y, z }) => ({ x: -y, y: z, z: -x });
    const cases = [[-7000, 0, 0], [-7000, 6000, 1000], [-7000, 6400, 0], [3000, 5000, -2000]];
    for (const [x, y, z] of cases) {
      expect(shadowState(rotate({ x, y, z }), rotate(sunAlongX)).sunlit).toBe(shadowState({ x, y, z }, sunAlongX).sunlit);
    }
  });

  it('takes the Sun at the equator of date, about 0.37 degree from J2000 after 26.8 years of precession', () => {
    const instant = new Date('2026-11-03T12:00:00Z');
    const of = sunVectorKm(instant);
    const j2000 = GeoVector('Sun', MakeTime(instant), true);
    const cosine = (of.x * j2000.x + of.y * j2000.y + of.z * j2000.z) / (Math.hypot(of.x, of.y, of.z) * Math.hypot(j2000.x, j2000.y, j2000.z));
    const degrees = (Math.acos(Math.min(1, cosine)) * 180) / Math.PI;
    expect(degrees).toBeGreaterThan(0.35);
    expect(degrees).toBeLessThan(0.4);
    expect(Math.hypot(of.x, of.y, of.z) / 149597870.7).toBeCloseTo(0.992, 2);
  });
});

describe('held to an independent implementation (Rhodes\' sgp4 and Skyfield with JPL DE421)', () => {
  // Measured when the reference was frozen (ISS, San Juan and Sydney, 48 hours from a day after the epoch):
  //   states                 : 0.2 m
  //   look angles            : azimuth 0.026 degree, elevation 0.0033 degree, range 0.04 km, sunlit state equal in all 45
  //   AOS, TCA and LOS       : 0.13 s;  greatest elevation 0.003 degree;  Sun altitude 0.000 degree
  //   azimuth at culmination : up to 0.48 degree, on a near-zenith pass, where azimuth changes fastest
  //   shadow entries / exits : all 124 found within 0.13 s;  lit time per pass within one 5-second sample
  // The tolerances below leave a margin over each and are what a change to the code must stay inside.
  const satellites = Object.entries(reference.satellites);

  it('was built from the element fixture in the repository', () => {
    expect(reference.generated_by.elements_fixture_sha256).toBe(sha256(elementsText));
    expect(satellites.length).toBeGreaterThanOrEqual(1);
  });

  for (const [key, sat] of satellites) {
    describe(`${key} (NORAD ${sat.noradId})`, () => {
      const element = () => parseGp(elements.items[key].payload[0]);

      it('gives the same TEME states as the independent SGP4, to 5 metres', () => {
        for (const s of sat.states) {
          const state = stateAt(element(), new Date(s.time));
          expect(state.ok).toBe(true);
          expect(hypot3(state.positionKm, s.r_km)).toBeLessThan(0.005);
          expect(hypot3(state.velocityKmS, s.v_kms)).toBeLessThan(1e-5);
        }
      });

      for (const [place, observer] of Object.entries(sat.observers)) {
        const spot = { lat: observer.lat, lon: observer.lon, elevation: observer.elevation_m };

        it(`${place}: gives the same look angles and sunlit state`, () => {
          expect(observer.looks.length).toBeGreaterThan(0);
          for (const l of observer.looks) {
            const look = lookAt(element(), new Date(l.time), spot);
            expect(angleDifference(look.azimuth, l.azimuth)).toBeLessThan(0.1);
            expect(Math.abs(look.elevation - l.elevation)).toBeLessThan(0.02);
            expect(Math.abs(look.rangeKm - l.range_km)).toBeLessThan(0.2);
            expect(look.sunlit).toBe(l.sunlit);
          }
        });

        it(`${place}: finds the same passes, to a second`, () => {
          const hours = (new Date(observer.window.end) - new Date(observer.window.start)) / 3600e3;
          const found = findPasses(element(), spot, new Date(observer.window.start), { hours, minElevation: 10 });
          expect(found.ok).toBe(true);
          expect(observer.passes.length).toBeGreaterThan(0);
          const matched = new Set();
          for (const expected of observer.passes) {
            const pass = found.passes.find((p) => Math.abs(p.tca - new Date(expected.tca)) < 60e3);
            expect(pass, `a pass near ${expected.tca}`).toBeDefined();
            matched.add(pass);
            expect(Math.abs(pass.aos - new Date(expected.aos))).toBeLessThan(1000);
            expect(Math.abs(pass.tca - new Date(expected.tca))).toBeLessThan(1000);
            expect(Math.abs(pass.los - new Date(expected.los))).toBeLessThan(1000);
            expect(Math.abs(pass.maxElevation - expected.max_elevation)).toBeLessThan(0.02);
            expect(angleDifference(pass.aosAzimuth, expected.aos_azimuth)).toBeLessThan(0.1);
            expect(angleDifference(pass.losAzimuth, expected.los_azimuth)).toBeLessThan(0.1);
            expect(angleDifference(pass.tcaAzimuth, expected.tca_azimuth)).toBeLessThan(1);
            expect(Math.abs(pass.rangeAtCulminationKm - expected.range_km_at_tca)).toBeLessThan(0.2);
            expect(Math.abs(pass.sunAltitudeAtCulmination - expected.sun_altitude_at_tca)).toBeLessThan(0.02);
            expect(Math.abs(pass.sunlitSeconds - expected.sunlit_seconds)).toBeLessThanOrEqual(10);
          }
          // Anything else found must be a pass cut by the edge of the window, which the reference leaves out.
          const windowStart = new Date(observer.window.start);
          const windowEnd = new Date(observer.window.end);
          for (const pass of found.passes.filter((p) => !matched.has(p))) {
            expect(pass.aos < windowStart || pass.los > windowEnd).toBe(true);
          }
        });

        it(`${place}: finds every entry into and exit from the Earth's shadow within a second`, () => {
          expect(observer.shadow_transitions.length).toBeGreaterThan(20);
          const e = element();
          const sunlitAt = (ms) => shadowState(stateAt(e, new Date(ms)).positionKm, sunVectorKm(new Date(ms))).sunlit;
          for (const transition of observer.shadow_transitions) {
            const t = new Date(transition.time).getTime();
            expect(sunlitAt(t - 20000)).toBe(!transition.sunlit_after);
            expect(sunlitAt(t + 20000)).toBe(transition.sunlit_after);
            let low = t - 20000;
            let high = t + 20000;
            for (let i = 0; i < 40 && high - low > 10; i += 1) {
              const middle = (low + high) / 2;
              if (sunlitAt(middle) === sunlitAt(low)) low = middle; else high = middle;
            }
            expect(Math.abs((low + high) / 2 - t)).toBeLessThan(1000);
          }
        });
      }
    });
  }
});

describe('finding passes', () => {
  const element = () => iss();
  const start = () => new Date(element().epoch.getTime() + DAY);

  it('returns ordered passes whose rise, culmination and set are consistent', () => {
    const found = findPasses(element(), SAN_JUAN, start(), { hours: 48, minElevation: 10 });
    expect(found.ok).toBe(true);
    expect(found.passes.length).toBeGreaterThan(3);
    for (let i = 0; i < found.passes.length; i += 1) {
      const p = found.passes[i];
      expect(p.aos < p.tca && p.tca < p.los).toBe(true);
      expect(p.maxElevation).toBeGreaterThanOrEqual(10);
      expect(p.durationSeconds).toBeGreaterThan(30);
      expect(p.durationSeconds).toBeLessThan(15 * 60);
      expect(lookAt(element(), p.aos, SAN_JUAN).elevation).toBeCloseTo(10, 1);
      expect(lookAt(element(), p.los, SAN_JUAN).elevation).toBeCloseTo(10, 1);
      if (i > 0) expect(p.aos > found.passes[i - 1].los).toBe(true);
    }
  });

  it('is deterministic', () => {
    const a = findPasses(element(), SAN_JUAN, start(), { hours: 24 });
    const b = findPasses(element(), SAN_JUAN, start(), { hours: 24 });
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });

  it('includes a pass already under way at the start of the window, with its true rise', () => {
    const first = findPasses(element(), SAN_JUAN, start(), { hours: 24 }).passes[0];
    const middle = new Date((first.aos.getTime() + first.los.getTime()) / 2);
    const found = findPasses(element(), SAN_JUAN, middle, { hours: 6 });
    const same = found.passes.find((p) => Math.abs(p.tca - first.tca) < 1000);
    expect(same).toBeDefined();
    expect(Math.abs(same.aos - first.aos)).toBeLessThan(1000);
    expect(same.aos < middle).toBe(true);
  });

  it('calls a pass a visible-pass candidate only when it is lit, above the minimum and the sky is dark, and says why not otherwise', () => {
    const found = findPasses(element(), SAN_JUAN, start(), { hours: 72 });
    const candidates = found.passes.filter((p) => p.visibility.candidate);
    const others = found.passes.filter((p) => !p.visibility.candidate);
    expect(candidates.length).toBeGreaterThan(0);
    expect(others.length).toBeGreaterThan(0);
    for (const p of candidates) {
      expect(p.visibility.label).toBe(VISIBLE_LABEL);
      expect(p.visibility.label).toMatch(/brightness not estimated/);
      expect(p.sunlitSeconds).toBeGreaterThan(0);
      expect(p.visibility.from >= p.aos && p.visibility.to <= p.los).toBe(true);
      const look = lookAt(element(), p.visibility.from, SAN_JUAN);
      expect(look.sunlit).toBe(true);
      expect(look.elevation).toBeGreaterThanOrEqual(10 - 0.01);
    }
    for (const p of others) {
      expect(p.visibility.reason).toMatch(/shadow|too bright|only while/);
      expect(p.visibility.from).toBeNull();
      if (p.sunlitSeconds === 0) expect(p.visibility.reason).toMatch(/shadow/);
      if (p.sunAltitudeAtCulmination > 0) expect(p.visibility.candidate).toBe(false);
    }
  });

  it('refuses the whole search, with the reason, when the elements are too far from the window', () => {
    const e = element();
    const far = findPasses(e, SAN_JUAN, new Date(e.epoch.getTime() + 20 * DAY), { hours: 24 });
    expect(far.ok).toBe(false);
    expect(far.reason).toBe('ELEMENTS_TOO_OLD');
    expect(findPasses(e, SAN_JUAN, new Date(e.epoch.getTime() + 10 * DAY), { hours: 24 }).ok).toBe(true);
    // The far end of the window counts too.
    expect(findPasses(e, SAN_JUAN, new Date(e.epoch.getTime() + 13.5 * DAY), { hours: 24 }).ok).toBe(false);
  });

  it('checks its inputs instead of guessing', () => {
    const e = element();
    expect(() => findPasses(e, SAN_JUAN, start(), { hours: 0 })).toThrow(/Hours/);
    expect(() => findPasses(e, SAN_JUAN, start(), { hours: 100 })).toThrow(/Hours/);
    expect(() => findPasses(e, SAN_JUAN, start(), { minElevation: -1 })).toThrow(/elevation/);
    expect(() => findPasses(e, SAN_JUAN, start(), { minElevation: 81 })).toThrow(/elevation/);
    expect(() => findPasses(e, SAN_JUAN, start(), { stepSeconds: 1 })).toThrow(/Step/);
    expect(() => findPasses(e, { lat: 95, lon: 0 }, start())).toThrow(/Latitude/);
    expect(() => findPasses(e, SAN_JUAN, 'tomorrow')).toThrow(/valid instant/);
    expect(() => findPasses(e, SAN_JUAN, '2026-11-03T12:00')).toThrow(/UTC designator/);
  });

  it('draws a track above the horizon only', () => {
    const e = element();
    const pass = findPasses(e, SAN_JUAN, start(), { hours: 24 }).passes[0];
    const track = skyTrack(e, SAN_JUAN, new Date(pass.aos.getTime() - 120e3), new Date(pass.los.getTime() + 120e3), 15);
    expect(track.ok).toBe(true);
    expect(track.points.length).toBeGreaterThan(10);
    expect(track.points.every((p) => p.altitude >= 0 && p.azimuth >= 0 && p.azimuth < 360)).toBe(true);
    expect(() => skyTrack(e, SAN_JUAN, pass.los, pass.aos)).toThrow(/interval/);
    const refused = skyTrack(e, SAN_JUAN, new Date(e.epoch.getTime() + 30 * DAY), new Date(e.epoch.getTime() + 30 * DAY + 600e3));
    expect(refused.ok).toBe(false);
  });
});

// A pass that clears the minimum elevation for only a few seconds can fall between two samples of the search. These use the
// independent reference's own maximum elevation for every ISS pass over San Juan (not this module's), asking for a minimum
// just below it, and just above it.
describe('passes that only just clear the minimum elevation', () => {
  const sanJuan = reference.satellites.ISS.observers['San Juan'];
  const passes = sanJuan.passes.map((pass, index) => ({ index, ...pass }));
  const hourAround = (pass) => new Date(Date.parse(pass.aos) - 30 * 60e3);

  // The reference and this module agree on a pass's peak to 0.003 degrees (measured), so 0.005 below the reference's peak is
  // still below this module's.
  const cases = passes.flatMap((pass) => [0.02, 0.01, 0.005].map((below) => ({ ...pass, below })));
  it.each(cases)('finds pass $index when the minimum elevation is $below degrees below its peak', (pass) => {
    const minElevation = pass.max_elevation - pass.below;
    const result = findPasses(iss(), SAN_JUAN, hourAround(pass), { hours: 1, minElevation });
    const hit = result.passes.find((p) => Math.abs(p.tca - new Date(pass.tca)) < 5000);
    expect(hit, `peak ${pass.max_elevation.toFixed(3)} degrees`).toBeTruthy();
    expect(hit.maxElevation).toBeGreaterThanOrEqual(minElevation);
    expect(hit.aos < hit.tca && hit.tca < hit.los).toBe(true);
    expect(hit.durationSeconds).toBeLessThan(30);
  });

  it.each(passes)('finds no pass near pass $index when the minimum elevation is 0.05 degrees above its peak', (pass) => {
    const result = findPasses(iss(), SAN_JUAN, hourAround(pass), { hours: 1, minElevation: pass.max_elevation + 0.05 });
    expect(result.passes.filter((p) => Math.abs(p.tca - new Date(pass.tca)) < 120000)).toHaveLength(0);
  });

  it('keeps the same rise, culmination and set for a pass the old sampling already found', () => {
    const pass = passes[0];
    const wide = findPasses(iss(), SAN_JUAN, hourAround(pass), { hours: 1, minElevation: 10 }).passes.find((p) => Math.abs(p.tca - new Date(pass.tca)) < 5000);
    expect(Math.abs(wide.aos - new Date(pass.aos))).toBeLessThan(1000);
    expect(Math.abs(wide.los - new Date(pass.los))).toBeLessThan(1000);
  });
});

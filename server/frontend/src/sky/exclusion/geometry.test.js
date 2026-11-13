import { describe, expect, it } from 'vitest';
import reference from './fixtures/geometryReference.json';
import {
  WGS84, angularSeparation, ecefToEnu, ecefToGeodetic, enuToAzEl, geodeticToEcef, lookTo, normalizeAzimuth, pointAt, unitVector, validateObserver,
} from './geometry';

const SAN_JUAN = { lat: 18.4663, lon: -66.1057, height: 5 };
const near = (value, expected, digits = 6) => expect(value).toBeCloseTo(expected, digits);
// Difference between two azimuths the short way round the compass.
const circular = (a, b) => Math.abs(((a - b + 540) % 360) - 180);

describe('angularSeparation', () => {
  it('is zero for the same direction and 90 degrees between the cardinal points on the horizon', () => {
    near(angularSeparation(123, 45, 123, 45), 0);
    near(angularSeparation(0, 0, 90, 0), 90);
    near(angularSeparation(0, 0, 180, 0), 180);
    near(angularSeparation(10, 90, 200, 0), 90);
  });

  it('goes the short way round the compass', () => {
    near(angularSeparation(359.9, 0, 0.1, 0), 0.2, 9);
    near(angularSeparation(1, 0, 359, 0), 2, 9);
  });

  it('agrees with the spherical law of cosines, and is not fooled by tiny separations', () => {
    const cosine = (a1, e1, a2, e2) => Math.acos(Math.sin((e1 * Math.PI) / 180) * Math.sin((e2 * Math.PI) / 180)
      + Math.cos((e1 * Math.PI) / 180) * Math.cos((e2 * Math.PI) / 180) * Math.cos(((a1 - a2) * Math.PI) / 180)) * (180 / Math.PI);
    near(angularSeparation(30, 60, 40, 55), cosine(30, 60, 40, 55), 9);
    near(angularSeparation(200, -10, 120, 33), cosine(200, -10, 120, 33), 9);
    // One arc-second apart: acos of nearly 1 loses it, atan2 of cross and dot does not.
    near(angularSeparation(10, 40, 10, 40 + 1 / 3600), 1 / 3600, 12);
  });

  it('refuses coordinates that are not numbers', () => {
    expect(() => angularSeparation(Number.NaN, 0, 0, 0)).toThrow(RangeError);
    expect(() => angularSeparation(0, 0, 0, undefined)).toThrow(RangeError);
  });
});

describe('normalizeAzimuth and unitVector', () => {
  it('keeps azimuth in [0, 360)', () => {
    expect(normalizeAzimuth(-0.5)).toBeCloseTo(359.5, 12);
    expect(normalizeAzimuth(360)).toBe(0);
    expect(normalizeAzimuth(725)).toBe(5);
  });

  it('points east for azimuth 90, north for 0 and up for elevation 90, as unit vectors', () => {
    const east = unitVector(90, 0);
    near(east.e, 1); near(east.n, 0); near(east.u, 0);
    const north = unitVector(0, 0);
    near(north.n, 1);
    near(unitVector(77, 90).u, 1);
    const v = unitVector(33, 21);
    near(Math.hypot(v.e, v.n, v.u), 1, 12);
  });
});

describe('WGS84 conversions', () => {
  it('puts the equator and the pole where the ellipsoid says', () => {
    const equator = geodeticToEcef({ lat: 0, lon: 0, height: 0 });
    near(equator.x, WGS84.a, 6); near(equator.y, 0, 6); near(equator.z, 0, 6);
    const pole = geodeticToEcef({ lat: 90, lon: 0, height: 0 });
    near(pole.z, WGS84.b, 6);
    near(WGS84.b, 6356752.314245, 5);
  });

  it('round-trips geodetic to ECEF and back to well under a millimetre, including near the poles', () => {
    for (const p of [SAN_JUAN, { lat: -33.8688, lon: 151.2093, height: 20 }, { lat: 89.9, lon: 12, height: 9000 }, { lat: -89.99, lon: -170, height: -50 }, { lat: 0, lon: 180, height: 15000 }]) {
      const back = ecefToGeodetic(geodeticToEcef(p));
      near(back.lat, p.lat, 9); near(back.height, p.height, 4);
      near(Math.cos((back.lon * Math.PI) / 180), Math.cos((p.lon * Math.PI) / 180), 9);
    }
  });
});

describe('look angles from a ground observer', () => {
  it('sees a point directly above at elevation 90 and at its height', () => {
    const look = lookTo(SAN_JUAN, { ...SAN_JUAN, height: SAN_JUAN.height + 1000 });
    near(look.elevation, 90, 6); near(look.range, 1000, 6);
  });

  it('sees a point one kilometre north on the same height just below the horizontal, by the curvature of the Earth', () => {
    const lat = SAN_JUAN.lat + 1000 / 110574;
    const look = lookTo(SAN_JUAN, { lat, lon: SAN_JUAN.lon, height: SAN_JUAN.height });
    expect(circular(look.azimuth, 0)).toBeLessThan(1e-6);
    // elevation is about -d/(2R): 1 km is 7.8e-5 rad = 0.0045 degrees below the local horizontal
    expect(look.elevation).toBeLessThan(0);
    expect(Math.abs(look.elevation + 0.0045)).toBeLessThan(0.0004);
  });

  it('puts a point on the same parallel just off east, by exactly the convergence of the meridians', () => {
    // On a sphere a parallel is not a great circle: the azimuth to a point d(lambda) east on the same parallel is
    // 90 degrees minus d(lambda) * sin(latitude) / 2 to first order (0.00158 degrees for 0.01 degrees at 18.47 N).
    const dLambda = 0.01;
    const convergence = (dLambda * Math.sin((SAN_JUAN.lat * Math.PI) / 180)) / 2;
    near(lookTo(SAN_JUAN, { lat: SAN_JUAN.lat, lon: SAN_JUAN.lon + dLambda, height: 5 }).azimuth, 90 - convergence, 5);
    near(lookTo(SAN_JUAN, { lat: SAN_JUAN.lat, lon: SAN_JUAN.lon - dLambda, height: 5 }).azimuth, 270 + convergence, 5);
  });

  it('inverts: a point placed along a direction is seen along that direction', () => {
    for (const [azimuth, elevation, range] of [[0, 5, 12000], [137.5, 33, 800], [271, -2, 60000], [359.99, 60, 25000]]) {
      const target = pointAt(SAN_JUAN, azimuth, elevation, range);
      const look = lookTo(SAN_JUAN, target);
      near(look.azimuth, azimuth, 6); near(look.elevation, elevation, 6); near(look.range, range, 3);
    }
  });

  it('reads ECEF and ENU consistently', () => {
    const target = { lat: 18.6, lon: -65.9, height: 3000 };
    const direct = lookTo(SAN_JUAN, target);
    const viaEnu = enuToAzEl(ecefToEnu(geodeticToEcef(target), SAN_JUAN));
    near(direct.azimuth, viaEnu.azimuth, 12); near(direct.range, viaEnu.range, 6);
  });

  it('refuses a target at the observer, where no direction exists', () => {
    expect(() => lookTo(SAN_JUAN, SAN_JUAN)).toThrow(RangeError);
  });
});

describe('held to an independent implementation (Skyfield\'s WGS84 model)', () => {
  it('gives the same azimuth, elevation and range for every reference case, observer to target', () => {
    expect(reference.cases.length).toBe(40);
    let worstAzimuth = 0; let worstElevation = 0; let worstRange = 0;
    for (const c of reference.cases) {
      const look = lookTo(c.observer, c.target);
      const dAz = Math.abs(((look.azimuth - c.azimuth + 540) % 360) - 180);
      worstAzimuth = Math.max(worstAzimuth, dAz);
      worstElevation = Math.max(worstElevation, Math.abs(look.elevation - c.elevation));
      worstRange = Math.max(worstRange, Math.abs(look.range - c.range_m));
    }
    // Measured when the reference was frozen: 9e-13 degrees, 7e-12 degrees and 3e-9 m (both are the same WGS84 geometry,
    // so the difference is floating-point rounding). The tolerances leave about two orders of magnitude.
    expect(worstAzimuth).toBeLessThan(1e-9);
    expect(worstElevation).toBeLessThan(1e-9);
    expect(worstRange).toBeLessThan(1e-6);
  });
});

describe('validateObserver', () => {
  it('accepts a real place and returns a frozen copy', () => {
    const o = validateObserver({ lat: 18.4663, lon: -66.1057, height: 5 });
    expect(Object.isFrozen(o)).toBe(true);
    expect(o).toEqual({ lat: 18.4663, lon: -66.1057, height: 5 });
  });

  it('refuses a latitude or longitude out of range, a missing coordinate and a height that is not a number', () => {
    expect(() => validateObserver({ lat: 91, lon: 0, height: 0 })).toThrow(/Latitude/);
    expect(() => validateObserver({ lat: 0, lon: 181, height: 0 })).toThrow(/Longitude/);
    expect(() => validateObserver({ lat: 0, height: 0 })).toThrow(/Longitude/);
    expect(() => validateObserver({ lat: 0, lon: 0, height: 'high' })).toThrow(/height/i);
    expect(() => validateObserver({ lat: 0, lon: 0, height: 20000 })).toThrow(/height/i);
  });
});

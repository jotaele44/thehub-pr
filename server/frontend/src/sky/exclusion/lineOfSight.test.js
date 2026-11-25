import { describe, expect, it } from 'vitest';
import {
  DEFAULT_REFRACTION_K, EARTH_RADIUS_M, computeHorizon, destination, elevationAngle, radiusOfCurvature,
} from './horizon';
import { lineOfSight, LINE_OF_SIGHT_CONTRACT } from './lineOfSight';
import { functionTerrain } from './terrain';

const A = { lon: -66.1057, lat: 18.4663 };
const DEG = 180 / Math.PI;
const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 111320 * Math.cos((A.lat * Math.PI) / 180);
const polar = (lon, lat) => {
  const e = (lon - A.lon) * M_PER_DEG_LON;
  const n = (lat - A.lat) * M_PER_DEG_LAT;
  return { r: Math.hypot(e, n), az: ((Math.atan2(e, n) * DEG) + 360) % 360 };
};
const terrainOf = (f) => functionTerrain({ heightAt: f, datum: 'TEST', label: 'synthetic' });
const SEA = terrainOf(() => 0);
const RADIUS_EAST = radiusOfCurvature(A.lat, 90);
const R_EFF_EAST = RADIUS_EAST / (1 - DEFAULT_REFRACTION_K);
// a point `metres` due east of A, at a height above the datum
const eastOf = (metres, heightMetres) => ({ ...destination(A.lon, A.lat, 90, metres, RADIUS_EAST), heightMetres });

describe('over the sea, against its closed form', () => {
  // two eyes at 10 m see each other while the distance is below the sum of their horizon distances, 2 sqrt(2 R_eff h)
  const critical = 2 * Math.sqrt(2 * R_EFF_EAST * 10);

  it('sees across the sea up to the sum of the two horizon distances and not beyond', () => {
    expect(critical).toBeGreaterThan(20000);
    expect(critical).toBeLessThan(30000);
    const clear = lineOfSight(SEA, { ...A, heightMetres: 10 }, eastOf(critical * 0.97, 10));
    expect(clear.state).toBe('CLEAR');
    expect(clear.minClearanceMetres).toBeGreaterThan(0);
    expect(clear.minClearanceMetres).toBeLessThan(1);
    const blocked = lineOfSight(SEA, { ...A, heightMetres: 10 }, eastOf(critical * 1.03, 10));
    expect(blocked.state).toBe('OBSTRUCTED');
    expect(blocked.blockedAt.terrainMetres).toBe(0);
    expect(blocked.blockedAt.clearanceMetres).toBeLessThan(0);
    // the curve of the sea rises into the line half-way along
    expect(blocked.blockedAt.distanceMetres).toBeGreaterThan(blocked.distanceMetres * 0.4);
    expect(blocked.blockedAt.distanceMetres).toBeLessThan(blocked.distanceMetres * 0.6);
  });

  it('puts the threshold where the closed form puts it, to a fraction of a percent', () => {
    const at = (factor) => lineOfSight(SEA, { ...A, heightMetres: 10 }, eastOf(critical * factor, 10), { stepMetres: 25 }).state;
    expect(at(0.995)).toBe('CLEAR');
    expect(at(1.005)).toBe('OBSTRUCTED');
  });

  it('is the same looking back as looking out, and a higher eye sees further', () => {
    const there = eastOf(critical * 1.03, 10);
    expect(lineOfSight(SEA, there, { ...A, heightMetres: 10 }).state).toBe('OBSTRUCTED');
    expect(lineOfSight(SEA, { ...A, heightMetres: 30 }, there).state).toBe('CLEAR');
  });
});

describe('over a ridge', () => {
  // 20 km of sea with a thin ridge half-way: the line from 10 m to 10 m has the bulge d(D-d)/(2 R_eff) = 6.8 m under it
  const D = 20000;
  const ridge = (height) => terrainOf((lon, lat) => {
    const { r, az } = polar(lon, lat);
    return Math.abs(r - D / 2) < 100 && az > 80 && az < 100 ? height : 0;
  });
  const bulge = (D * D) / (8 * R_EFF_EAST);

  it('is blocked by a ridge higher than the line over the curve, and not by one lower', () => {
    expect(bulge).toBeGreaterThan(6.5);
    expect(bulge).toBeLessThan(7);
    const clear = lineOfSight(ridge(10 - bulge - 1), { ...A, heightMetres: 10 }, eastOf(D, 10));
    expect(clear.state).toBe('CLEAR');
    expect(clear.minClearanceMetres).toBeGreaterThan(0.5);
    expect(clear.minClearanceMetres).toBeLessThan(1.6);
    const blocked = lineOfSight(ridge(10 - bulge + 1), { ...A, heightMetres: 10 }, eastOf(D, 10));
    expect(blocked.state).toBe('OBSTRUCTED');
    expect(Math.abs(blocked.blockedAt.distanceMetres - D / 2)).toBeLessThan(200);
    expect(blocked.blockedAt.terrainMetres).toBeCloseTo(10 - bulge + 1, 6);
  });

  it('is not fooled by a ridge off the line', () => {
    const offLine = terrainOf((lon, lat) => {
      const { r, az } = polar(lon, lat);
      return Math.abs(r - D / 2) < 100 && az > 20 && az < 40 ? 500 : 0;
    });
    expect(lineOfSight(offLine, { ...A, heightMetres: 10 }, eastOf(D, 10)).state).toBe('CLEAR');
  });
});

describe('missing data is not clear ground', () => {
  const D = 20000;
  const holeBetween = terrainOf((lon, lat) => {
    const { r, az } = polar(lon, lat);
    return Math.abs(r - D / 2) < 500 && az > 80 && az < 100 ? null : 0;
  });

  it('is UNKNOWN when nothing blocked the line but some of it was over no data', () => {
    const result = lineOfSight(holeBetween, { ...A, heightMetres: 500 }, eastOf(D, 500));
    expect(result.state).toBe('UNKNOWN');
    expect(result.samplesWithoutData).toBeGreaterThan(5);
    expect(Math.abs(result.firstMissingDistanceMetres - (D / 2 - 500))).toBeLessThan(200);
    expect(result.limits.join(' ')).toMatch(/not clear/);
  });

  it('is OBSTRUCTED when ground that is there blocks the line, whatever is missing elsewhere', () => {
    const both = terrainOf((lon, lat) => {
      const { r, az } = polar(lon, lat);
      if (az > 80 && az < 100 && Math.abs(r - D / 2) < 500) return null;
      return az > 80 && az < 100 && Math.abs(r - D / 4) < 100 ? 900 : 0;
    });
    expect(lineOfSight(both, { ...A, heightMetres: 500 }, eastOf(D, 500)).state).toBe('OBSTRUCTED');
  });
});

describe('refusals and statements', () => {
  it('needs both ends with a datum height, and a sensible refraction and step', () => {
    expect(() => lineOfSight(SEA, { lon: 1, lat: 1 }, { lon: 1, lat: 1, heightMetres: 1 })).toThrow(/first point needs/);
    expect(() => lineOfSight(SEA, { ...A, heightMetres: 1 }, { lon: 1, lat: 1 })).toThrow(/second point needs/);
    expect(() => lineOfSight(SEA, { ...A, heightMetres: 1 }, eastOf(1000, 1), { refractionK: 0.9 })).toThrow(/refraction coefficient/);
    expect(() => lineOfSight(SEA, { ...A, heightMetres: 1 }, eastOf(1000, 1), { stepMetres: 1 })).toThrow(/at least 5 metres/);
  });

  it('records what it did and what it leaves out', () => {
    const r = lineOfSight(SEA, { ...A, heightMetres: 100 }, eastOf(5000, 100));
    expect(r.contract).toBe(LINE_OF_SIGHT_CONTRACT);
    expect(r.parameters).toMatchObject({ refractionK: 0.13, waterSurfaceMetres: 0, stepMetres: 50, datum: 'TEST' });
    expect(r.limits.join(' ')).toMatch(/Bare earth/);
    expect(r.distanceMetres).toBeCloseTo(5000, -1);
    expect(r.azimuth).toBeCloseTo(90, 0);
    expect(Object.isFrozen(r)).toBe(true);
  });
});

describe('two implementations of the same question', () => {
  // hills of 100 to 900 m; the horizon's finite-range assessment and the line-of-sight profile must agree except at the edge
  const hills = [[4000, 1000, 600, 800], [-6000, 3000, 900, 1200], [2000, -5000, 500, 900], [9000, 7000, 300, 1500]];
  const terrain = terrainOf((lon, lat) => {
    const e = (lon - A.lon) * M_PER_DEG_LON;
    const n = (lat - A.lat) * M_PER_DEG_LAT;
    return hills.reduce((sum, [he, hn, a, s]) => sum + a * Math.exp(-(((e - he) ** 2) + ((n - hn) ** 2)) / (2 * s * s)), 0);
  });
  const horizon = computeHorizon(terrain, { ...A, aboveGroundMetres: 2 }, { maxRangeKm: 30, azimuthStepDegrees: 0.25 });
  const eye = horizon.observer.eyeMetres;

  it('agree on whether an aircraft at a given range, bearing and height is hidden, on every one of 600 random cases', () => {
    let seed = 12345;
    const random = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
    let compared = 0;
    let obstructed = 0;
    let clear = 0;
    for (let i = 0; i < 600; i += 1) {
      const azimuth = random() * 360;
      const distance = 1500 + random() * 18000;
      const height = 20 + random() * 1200;
      const radius = radiusOfCurvature(A.lat, azimuth);
      const to = { ...destination(A.lon, A.lat, azimuth, distance, radius), heightMetres: height };
      const los = lineOfSight(terrain, { ...A, heightMetres: eye }, to, { stepMetres: 25 });
      const elevation = elevationAngle(distance, height, eye, radius / (1 - DEFAULT_REFRACTION_K));
      const state = horizon.assess(azimuth, elevation, { distanceMetres: distance });
      // measured over 3000 cases while writing this: no disagreement, with no band left out around the boundary
      compared += 1;
      if (los.state === 'OBSTRUCTED') obstructed += 1; else clear += 1;
      expect(state, `az ${azimuth.toFixed(2)} d ${distance.toFixed(0)} h ${height.toFixed(0)} clearance ${los.minClearanceMetres.toFixed(1)}`).toBe(los.state);
    }
    expect(compared).toBe(600);
    // both outcomes occur, so agreement is not trivial
    expect(obstructed).toBeGreaterThan(50);
    expect(clear).toBeGreaterThan(50);
    expect(EARTH_RADIUS_M).toBeGreaterThan(6.3e6);
  });
});

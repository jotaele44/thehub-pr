import { describe, expect, it } from 'vitest';
import {
  DEFAULT_REFRACTION_K, EARTH_RADIUS_M, computeHorizon, destination, elevationAngle, radiusOfCurvature, sampleDistances, terrainStatus,
} from './horizon';
import { functionTerrain, gridTerrain } from './terrain';

const OBS = { lon: -66.1057, lat: 18.4663 };
const DEG = 180 / Math.PI;
const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 111320 * Math.cos((OBS.lat * Math.PI) / 180);
const enu = (lon, lat) => ({ e: (lon - OBS.lon) * M_PER_DEG_LON, n: (lat - OBS.lat) * M_PER_DEG_LAT });
const polar = (lon, lat) => {
  const { e, n } = enu(lon, lat);
  return { r: Math.hypot(e, n), az: ((Math.atan2(e, n) * DEG) + 360) % 360, e, n };
};
const terrainOf = (f, datum = 'TEST') => functionTerrain({ heightAt: f, datum, label: 'synthetic' });
const SEA = terrainOf(() => 0);
const R_EFF = EARTH_RADIUS_M / (1 - DEFAULT_REFRACTION_K);

// An 800 m ridge 9 to 11 km away, between azimuth 80 and 100 degrees, standing in the sea
const RIDGE = terrainOf((lon, lat) => {
  const { r, az } = polar(lon, lat);
  return r >= 9000 && r <= 11000 && az >= 80 && az <= 100 ? 800 : 0;
});

describe('the geometry it stands on', () => {
  it('has the WGS84 radius of curvature: meridian and prime vertical at the equator, the polar radius at the pole', () => {
    expect(radiusOfCurvature(0, 0)).toBeCloseTo(6335439.327, 0);
    expect(radiusOfCurvature(0, 90)).toBeCloseTo(6378137, 0);
    expect(radiusOfCurvature(90, 0)).toBeCloseTo(6399593.626, 0);
    expect(radiusOfCurvature(90, 90)).toBeCloseTo(6399593.626, 0);
    const mid = radiusOfCurvature(45, 45);
    expect(mid).toBeGreaterThan(radiusOfCurvature(45, 0));
    expect(mid).toBeLessThan(radiusOfCurvature(45, 90));
  });

  it('travels a degree of arc to a degree of latitude, and along the equator to a degree of longitude', () => {
    const arc = (EARTH_RADIUS_M * Math.PI) / 180;
    const north = destination(10, 0, 0, arc, EARTH_RADIUS_M);
    expect(north.lat).toBeCloseTo(1, 9);
    expect(north.lon).toBeCloseTo(10, 9);
    const east = destination(10, 0, 90, arc, EARTH_RADIUS_M);
    expect(east.lon).toBeCloseTo(11, 9);
    expect(east.lat).toBeCloseTo(0, 9);
    expect(destination(179.9, 0, 90, 2 * arc, EARTH_RADIUS_M).lon).toBeCloseTo(-178.1, 6);
  });

  it('gives the elevation of a point: the flat limit, the curvature drop, and a point at the eye\'s own height', () => {
    expect(elevationAngle(1000, 100, 0, 1e13)).toBeCloseTo(Math.atan(0.1) * DEG, 6);
    expect(elevationAngle(10000, 0, 0, EARTH_RADIUS_M)).toBeCloseTo(-(10000 / (2 * EARTH_RADIUS_M)) * DEG, 4);
    expect(Math.abs(elevationAngle(20, 100, 100, EARTH_RADIUS_M))).toBeLessThan(1e-3);
  });

  it('samples fine near the observer and no coarser than 100 m anywhere, ending exactly at the range', () => {
    const d = sampleDistances(60000);
    expect(d[0]).toBe(20);
    expect(d[d.length - 1]).toBe(60000);
    for (let i = 1; i < d.length; i += 1) {
      expect(d[i]).toBeGreaterThan(d[i - 1]);
      expect(d[i] - d[i - 1]).toBeLessThanOrEqual(100.0001);
    }
    expect(d[1] - d[0]).toBeLessThanOrEqual(25);
  });
});

describe('the sea horizon, against its closed form', () => {
  it('is minus acos(R / (R + h)) from an eye at height h, whatever the azimuth', () => {
    const h = computeHorizon(SEA, { ...OBS, aboveGroundMetres: 100 });
    const expected = -Math.acos(R_EFF / (R_EFF + 100)) * DEG; // about -0.2996 degrees
    expect(expected).toBeCloseTo(-0.2996, 3);
    expect(h.rays).toHaveLength(720);
    for (const ray of h.rays) {
      expect(Math.abs(ray.elevation - expected)).toBeLessThan(0.003);
      // the sea horizon is sqrt(2 R_eff h) away, about 38 km
      expect(ray.distanceKm).toBeGreaterThan(36);
      expect(ray.distanceKm).toBeLessThan(40);
      expect(ray.complete).toBe(true);
    }
    expect(h.summary).toMatchObject({ rays: 720, incompleteRays: 0, raysWithNoData: 0 });
    expect(Math.abs(h.elevationAt(123.456) - expected)).toBeLessThan(0.003);
  });

  it('dips less with the refraction coefficient up: by the factor sqrt(1 - k)', () => {
    const none = computeHorizon(SEA, { ...OBS, aboveGroundMetres: 100 }, { refractionK: 0 });
    const standard = computeHorizon(SEA, { ...OBS, aboveGroundMetres: 100 });
    const stronger = computeHorizon(SEA, { ...OBS, aboveGroundMetres: 100 }, { refractionK: 0.25 });
    expect(none.elevationAt(10)).toBeCloseTo(-Math.sqrt((2 * 100) / EARTH_RADIUS_M) * DEG, 2);
    expect(standard.elevationAt(10) / none.elevationAt(10)).toBeCloseTo(Math.sqrt(1 - 0.13), 2);
    expect(stronger.elevationAt(10) / none.elevationAt(10)).toBeCloseTo(Math.sqrt(1 - 0.25), 2);
    expect(standard.parameters.refractionK).toBe(0.13);
  });

  it('puts the observer\'s own ground under the eye: a person on a 100 m hill has the horizon of a 100 m eye', () => {
    const hill = terrainOf((lon, lat) => (polar(lon, lat).r < 10 ? 100 : 0));
    const h = computeHorizon(hill, OBS, {});
    expect(h.observer).toMatchObject({ groundMetres: 100, eyeMetres: 100 });
    expect(Math.abs(h.elevationAt(200) - -Math.acos(R_EFF / (R_EFF + 100)) * DEG)).toBeLessThan(0.003);
  });

  it('does not count the sea floor as ground: heights under the water surface are raised to it', () => {
    const floor = terrainOf((lon, lat) => (polar(lon, lat).r < 10 ? 100 : -50));
    const clamped = computeHorizon(floor, OBS, {});
    const unclamped = computeHorizon(floor, OBS, { waterSurfaceMetres: null });
    expect(Math.abs(clamped.elevationAt(0) - -Math.acos(R_EFF / (R_EFF + 100)) * DEG)).toBeLessThan(0.003);
    // with the floor treated as ground the horizon would sit lower, by the extra 50 m of drop
    expect(unclamped.elevationAt(0)).toBeLessThan(clamped.elevationAt(0) - 0.04);
    expect(clamped.parameters.waterSurfaceMetres).toBe(0);
  });
});

describe('a ridge, against its closed form', () => {
  const horizon = computeHorizon(RIDGE, { ...OBS, aboveGroundMetres: 2 });

  it('rises to the angle of its near edge, from the eye over the curved Earth, and only in its own azimuths', () => {
    // 800 m at 9 km from a 2 m eye: atan((800 - 2 - d^2 / (2 R_eff)) / d); the sampling places the first ridge sample up to 90 m past the edge
    const near = Math.atan((800 - 2 - (9000 ** 2) / (2 * R_EFF)) / 9000) * DEG;
    const far = Math.atan((800 - 2 - (9090 ** 2) / (2 * R_EFF)) / 9090) * DEG;
    expect(near).toBeCloseTo(5.03, 2);
    const peak = horizon.elevationAt(90);
    expect(peak).toBeLessThanOrEqual(near + 0.07);
    expect(peak).toBeGreaterThanOrEqual(far - 0.07);
    expect(horizon.summary.maxElevation).toBeGreaterThan(near - 0.1);
    expect(horizon.summary.maxElevationAzimuth).toBeGreaterThanOrEqual(80);
    expect(horizon.summary.maxElevationAzimuth).toBeLessThanOrEqual(100);
    expect(horizon.summary.maxElevationDistanceKm).toBeGreaterThan(8.9);
    expect(horizon.summary.maxElevationDistanceKm).toBeLessThan(9.2);
    // outside the ridge's azimuths the horizon is the sea's: a fraction of a degree below the horizontal
    expect(horizon.elevationAt(0)).toBeLessThan(0);
    expect(horizon.elevationAt(0)).toBeGreaterThan(-0.1);
    expect(horizon.elevationAt(180)).toBeLessThan(0);
  });

  it('hides a body below the ridge, shows one above it, and hides only what is behind the ridge when the target has a distance', () => {
    expect(horizon.assess(90, 3)).toBe('OBSTRUCTED');
    expect(horizon.assess(90, 6)).toBe('CLEAR');
    // an aircraft 5 km away is in front of the ridge: the ridge cannot hide it, whatever its elevation
    expect(horizon.assess(90, 3, { distanceMetres: 5000 })).toBe('CLEAR');
    // one 12 km away is behind it
    expect(horizon.assess(90, 3, { distanceMetres: 12000 })).toBe('OBSTRUCTED');
    // a body past the ridge's azimuths is clear; one under the curve of the sea is hidden by it
    expect(horizon.assess(0, 1)).toBe('CLEAR');
    expect(horizon.assess(0, -1)).toBe('OBSTRUCTED');
  });

  it('is the same through terrainStatus, which also takes a plain { elevationAt } and no horizon at all', () => {
    expect(terrainStatus(horizon, 90, 3)).toBe('OBSTRUCTED');
    expect(terrainStatus(null, 90, 3)).toBe('NOT_CHECKED');
    expect(terrainStatus({ elevationAt: () => 20 }, 0, 11)).toBe('OBSTRUCTED');
    expect(terrainStatus({ elevationAt: () => 2 }, 0, 11)).toBe('CLEAR');
    expect(terrainStatus({ elevationAt: () => null }, 0, 11)).toBe('UNKNOWN');
  });
});

describe('missing data is not clear ground', () => {
  // the ridge, and no data at all beyond 20 km east of the observer
  const holey = terrainOf((lon, lat) => {
    const { r, az, e } = polar(lon, lat);
    if (e > 20000) return null;
    return r >= 9000 && r <= 11000 && az >= 80 && az <= 100 ? 800 : 0;
  });
  const horizon = computeHorizon(holey, { ...OBS, aboveGroundMetres: 2 });

  it('says UNKNOWN, not CLEAR, for a body above terrain that is there when the ray runs out of data', () => {
    expect(horizon.assess(90, 6)).toBe('UNKNOWN');
    expect(horizon.assess(90, 6, { distanceMetres: 15000 })).toBe('CLEAR');
    expect(horizon.assess(60, 5)).toBe('UNKNOWN'); // east of north-east: runs out of data at 20 km east
    // but terrain that is there still hides what is behind it, data beyond or not
    expect(horizon.assess(90, 3)).toBe('OBSTRUCTED');
    // and the west, where data is complete, is clear
    expect(horizon.assess(270, 5)).toBe('CLEAR');
    expect(horizon.summary.incompleteRays).toBeGreaterThan(100);
    expect(horizon.rays.find((r) => r.azimuth === 90).complete).toBe(false);
    expect(horizon.rays.find((r) => r.azimuth === 270).complete).toBe(true);
  });

  it('has no horizon at all for a ray with no data anywhere, and null for it', () => {
    const none = terrainOf((lon, lat) => (polar(lon, lat).r < 10 ? 0 : null));
    const h = computeHorizon(none, OBS);
    expect(h.elevationAt(10)).toBeNull();
    expect(h.summary).toMatchObject({ raysWithNoData: 720, maxElevation: null });
    expect(h.assess(10, 5)).toBe('UNKNOWN');
  });

  it('cannot start where there is no terrain at the observer, and refuses nonsense', () => {
    expect(() => computeHorizon(terrainOf(() => null), OBS)).toThrow(/no terrain data at the observer/);
    expect(() => computeHorizon(SEA, { lon: Number.NaN, lat: 1 })).toThrow(/longitude and a latitude/);
    expect(() => computeHorizon(SEA, { ...OBS, aboveGroundMetres: -1 })).toThrow(/above the ground/);
    expect(() => computeHorizon(SEA, OBS, { refractionK: 0.9 })).toThrow(/refraction coefficient/);
    expect(() => computeHorizon(SEA, OBS, { azimuthStepDegrees: 0 })).toThrow(/azimuth step/);
    expect(() => computeHorizon(SEA, OBS, { maxRangeKm: 1000 })).toThrow(/range/);
  });
});

describe('held to a second algorithm over a height grid', () => {
  // Four Gaussian hills on a 50 m grid; the check scans every cell instead of walking rays.
  const hills = [[6000, 4000, 500, 2500], [-12000, 9000, 700, 3000], [3000, -15000, 400, 2000], [-8000, -6000, 300, 4000]];
  const heightOf = (e, n) => hills.reduce((sum, [he, hn, a, s]) => sum + a * Math.exp(-(((e - he) ** 2) + ((n - hn) ** 2)) / (2 * s * s)), 0);
  const half = 25000;
  const size = 1001;
  const bbox = [OBS.lon - half / M_PER_DEG_LON, OBS.lat - half / M_PER_DEG_LAT, OBS.lon + half / M_PER_DEG_LON, OBS.lat + half / M_PER_DEG_LAT];
  const heights = new Float32Array(size * size);
  for (let r = 0; r < size; r += 1) {
    for (let c = 0; c < size; c += 1) {
      const lon = bbox[0] + ((bbox[2] - bbox[0]) * c) / (size - 1);
      const lat = bbox[3] - ((bbox[3] - bbox[1]) * r) / (size - 1);
      const { e, n } = enu(lon, lat);
      heights[r * size + c] = heightOf(e, n);
    }
  }
  const terrain = gridTerrain({ heights, width: size, height: size, bbox, datum: 'TEST', label: 'hills' });
  const ground = terrain.heightAt(OBS.lon, OBS.lat);
  const eye = ground + 2;
  const horizon = computeHorizon(terrain, { ...OBS, aboveGroundMetres: 2 }, { maxRangeKm: 24 });

  it('agrees with a scan of every cell within half a degree of each azimuth, to a tenth of a degree and far better on average', () => {
    const best = new Float64Array(720).fill(-90);
    for (let r = 0; r < size; r += 1) {
      for (let c = 0; c < size; c += 1) {
        const lon = bbox[0] + ((bbox[2] - bbox[0]) * c) / (size - 1);
        const lat = bbox[3] - ((bbox[3] - bbox[1]) * r) / (size - 1);
        const { r: dist, az } = polar(lon, lat);
        if (dist < 20 || dist > 24000) continue;
        const angle = elevationAngle(dist, Math.max(0, heights[r * size + c]), eye, R_EFF);
        const centre = Math.round(az / 0.5);
        for (const k of [centre - 1, centre, centre + 1]) {
          const bin = ((k % 720) + 720) % 720;
          const away = Math.abs((((az - bin * 0.5) % 360) + 540) % 360 - 180);
          if (away <= 0.25 && angle > best[bin]) best[bin] = angle;
        }
      }
    }
    let worst = 0;
    let total = 0;
    let highest = -90;
    for (let k = 0; k < 720; k += 1) {
      const difference = Math.abs(horizon.rays[k].elevation - best[k]);
      worst = Math.max(worst, difference);
      total += difference;
      highest = Math.max(highest, best[k]);
    }
    expect(highest).toBeGreaterThan(2); // the hills really do stand in the sky
    expect(worst).toBeLessThan(0.1);
    expect(total / 720).toBeLessThan(0.02);
  });
});

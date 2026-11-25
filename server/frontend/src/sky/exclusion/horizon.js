// The terrain horizon (FDX-033): for every azimuth around an observer, how high the ground rises in the sky, from a
// height field, with the Earth's curvature and a declared refraction coefficient. It answers "could the terrain hide a
// body in this direction?" for the Sun, Moon, planets, stars and satellites (infinitely far, for this purpose) and, with
// a distance, for an aircraft or any nearer target: only terrain nearer than the target can hide it.
//
// The rules that keep it honest:
//  - A height field cell with no data is UNKNOWN, never flat ground. A ray whose samples include missing data is
//    "incomplete", and a body above its terrain angle is then UNKNOWN, not CLEAR. Only a body below the angle of terrain
//    that is actually there is OBSTRUCTED.
//  - Water is not an obstruction: heights below the water surface (bathymetry) are raised to it (0 in PRVD02).
//  - Bare earth only: buildings and trees are not in a DEM, so a real horizon is at least this high.
//  - Terrain beyond the scanned range is not looked at; CLEAR means clear of the terrain scanned.
//  - Refraction is a coefficient k (default 0.13, the standard terrestrial value): it is applied by the usual effective
//    Earth radius R / (1 - k). It varies with weather from about 0 to 0.25 and more over water; the result states what was used.

export const HORIZON_CONTRACT = 'sky-horizon-v1';
export const EARTH_RADIUS_M = 6371008.8;
export const DEFAULT_REFRACTION_K = 0.13;
const WGS84_A = 6378137;
const WGS84_E2 = 0.00669437999014;
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const MIN_ANGLE = -90;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

// The radius of the Earth's curvature along an azimuth at a latitude (WGS84): between the meridian and the prime vertical.
export function radiusOfCurvature(latitudeDegrees, azimuthDegrees) {
  const s = Math.sin(latitudeDegrees * RAD);
  const w = 1 - WGS84_E2 * s * s;
  const meridian = (WGS84_A * (1 - WGS84_E2)) / (w * Math.sqrt(w));
  const primeVertical = WGS84_A / Math.sqrt(w);
  const a = azimuthDegrees * RAD;
  return 1 / (Math.cos(a) ** 2 / meridian + Math.sin(a) ** 2 / primeVertical);
}

// The point reached from (lon, lat) by travelling `distance` metres along `azimuth` on a sphere of radius `radius`.
export function destination(lon, lat, azimuthDegrees, distance, radius) {
  const phi1 = lat * RAD;
  const lambda1 = lon * RAD;
  const theta = azimuthDegrees * RAD;
  const delta = distance / radius;
  const sinPhi2 = Math.sin(phi1) * Math.cos(delta) + Math.cos(phi1) * Math.sin(delta) * Math.cos(theta);
  const phi2 = Math.asin(Math.max(-1, Math.min(1, sinPhi2)));
  const lambda2 = lambda1 + Math.atan2(Math.sin(theta) * Math.sin(delta) * Math.cos(phi1), Math.cos(delta) - Math.sin(phi1) * sinPhi2);
  return { lon: ((lambda2 * DEG + 540) % 360) - 180, lat: phi2 * DEG };
}

// The sample distances along a ray: fine near the observer, coarser far away, the same for every azimuth.
export function sampleDistances(maxRangeMetres, { minStep = 20, maxStep = 100, relativeStep = 0.01 } = {}) {
  const distances = [];
  let d = minStep;
  while (d < maxRangeMetres) {
    distances.push(d);
    d += Math.min(maxStep, Math.max(minStep, d * relativeStep));
  }
  distances.push(maxRangeMetres);
  return Float64Array.from(distances);
}

// The elevation angle, in degrees, of a point at height `heightMetres` and ground distance `distance`, seen from an eye at
// `eyeMetres`, on a sphere of radius `effectiveRadius` (the ray bent by refraction is a straight line on that sphere).
export function elevationAngle(distance, heightMetres, eyeMetres, effectiveRadius) {
  const s = distance / effectiveRadius;
  return Math.atan2((effectiveRadius + heightMetres) * Math.cos(s) - (effectiveRadius + eyeMetres), (effectiveRadius + heightMetres) * Math.sin(s)) * DEG;
}

export function computeHorizon(terrain, observer, options = {}) {
  const {
    azimuthStepDegrees = 0.5, maxRangeKm = 60, refractionK = DEFAULT_REFRACTION_K, waterSurfaceMetres = 0,
  } = options;
  if (!finite(observer?.lon) || !finite(observer?.lat)) throw new RangeError('The observer needs a longitude and a latitude.');
  const above = observer.aboveGroundMetres ?? 0;
  if (!finite(above) || above < 0 || above > 5000) throw new RangeError('The observer\'s height above the ground must be from 0 to 5000 metres.');
  if (!finite(refractionK) || refractionK < -0.5 || refractionK >= 0.5) throw new RangeError('The refraction coefficient must be between -0.5 and 0.5 (0.13 is the standard).');
  if (!finite(azimuthStepDegrees) || azimuthStepDegrees < 0.05 || azimuthStepDegrees > 10) throw new RangeError('The azimuth step must be from 0.05 to 10 degrees.');
  if (!finite(maxRangeKm) || maxRangeKm < 1 || maxRangeKm > 300) throw new RangeError('The range must be from 1 to 300 km.');
  const surface = (h) => (waterSurfaceMetres === null || h > waterSurfaceMetres ? h : waterSurfaceMetres);
  const ground = terrain.heightAt(observer.lon, observer.lat);
  if (ground === null || ground === undefined) throw new RangeError('There is no terrain data at the observer, so a horizon cannot be computed from here.');
  const eye = surface(ground) + above;
  const distances = sampleDistances(maxRangeKm * 1000);
  const count = Math.round(360 / azimuthStepDegrees);
  const rays = [];
  for (let k = 0; k < count; k += 1) {
    const azimuth = k * azimuthStepDegrees;
    const radius = radiusOfCurvature(observer.lat, azimuth);
    const effective = radius / (1 - refractionK);
    const cumulative = new Float32Array(distances.length);
    let best = MIN_ANGLE;
    let bestAt = 0;
    let firstMissing = -1;
    let missing = 0;
    for (let i = 0; i < distances.length; i += 1) {
      const p = destination(observer.lon, observer.lat, azimuth, distances[i], radius);
      const h = terrain.heightAt(p.lon, p.lat);
      if (h === null || h === undefined) {
        missing += 1;
        if (firstMissing < 0) firstMissing = i;
      } else {
        const angle = elevationAngle(distances[i], surface(h), eye, effective);
        if (angle > best) { best = angle; bestAt = i; }
      }
      cumulative[i] = best;
    }
    rays.push({ azimuth, elevation: best > MIN_ANGLE ? best : null, distanceMetres: best > MIN_ANGLE ? distances[bestAt] : null, cumulative, firstMissing, missing });
  }

  // A ray's blocking angle among terrain nearer than `distance`, and whether every sample up to there had data.
  const rayAt = (ray, distance) => {
    let lo = 0;
    let hi = distances.length - 1;
    if (!(distance < distances[hi])) return { angle: ray.cumulative[hi], complete: ray.firstMissing < 0 };
    if (distance <= distances[0]) return { angle: MIN_ANGLE, complete: true };
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (distances[mid] <= distance) lo = mid; else hi = mid; }
    return { angle: ray.cumulative[lo], complete: ray.firstMissing < 0 || ray.firstMissing > lo };
  };
  const bracket = (azimuth) => {
    const position = (((azimuth % 360) + 360) % 360) / azimuthStepDegrees;
    const i = Math.floor(position) % count;
    return { a: rays[i], b: rays[(i + 1) % count], f: position - Math.floor(position) };
  };

  const elevationAt = (azimuth) => {
    const { a, b, f } = bracket(azimuth);
    if (a.elevation === null || b.elevation === null) return null;
    return a.elevation * (1 - f) + b.elevation * f;
  };

  // Is a target at this direction (and ground distance, if it is not at infinity) hidden by the terrain?
  // OBSTRUCTED: below the angle of terrain nearer than it. Otherwise CLEAR if every sample up to it had data, else UNKNOWN.
  const assess = (azimuth, elevation, { distanceMetres = Infinity } = {}) => {
    const { a, b, f } = bracket(azimuth);
    const ra = rayAt(a, distanceMetres);
    const rb = rayAt(b, distanceMetres);
    const angle = ra.angle * (1 - f) + rb.angle * f;
    if (elevation < angle) return 'OBSTRUCTED';
    return ra.complete && rb.complete ? 'CLEAR' : 'UNKNOWN';
  };

  const known = rays.filter((r) => r.elevation !== null);
  const peak = known.reduce((m, r) => (m === null || r.elevation > m.elevation ? r : m), null);
  return Object.freeze({
    contract: HORIZON_CONTRACT,
    observer: Object.freeze({ lon: observer.lon, lat: observer.lat, groundMetres: ground, eyeMetres: eye, aboveGroundMetres: above, datum: terrain.datum }),
    terrain: Object.freeze({ label: terrain.label, datum: terrain.datum, caveats: terrain.caveats ?? Object.freeze([]), tilesRead: terrain.tilesRead ?? null }),
    parameters: Object.freeze({
      azimuthStepDegrees, maxRangeKm, refractionK, waterSurfaceMetres, samplesPerRay: distances.length, radiusModel: 'WGS84 radius of curvature along the azimuth, divided by (1 - k)',
    }),
    elevationAt, assess,
    rays: Object.freeze(rays.map((r) => Object.freeze({ azimuth: r.azimuth, elevation: r.elevation, distanceKm: r.distanceMetres === null ? null : r.distanceMetres / 1000, complete: r.firstMissing < 0 }))),
    summary: Object.freeze({
      maxElevation: peak ? peak.elevation : null, maxElevationAzimuth: peak ? peak.azimuth : null, maxElevationDistanceKm: peak ? peak.distanceMetres / 1000 : null,
      incompleteRays: rays.filter((r) => r.firstMissing >= 0).length, rays: count, raysWithNoData: rays.filter((r) => r.elevation === null).length,
    }),
    limits: Object.freeze([
      `Terrain is scanned to ${maxRangeKm} km; terrain further away is not looked at, so CLEAR means clear of the terrain scanned.`,
      `Refraction is the coefficient k = ${refractionK} (standard terrestrial 0.13): real air varies from about 0 to 0.25 and more over water, which moves a distant ridge by a fraction of a degree.`,
      'Bare earth: buildings, trees and structures are not in a DEM, so the real horizon is at least this high.',
      `Azimuth is sampled every ${azimuthStepDegrees} degrees and interpolated: a ridge narrower than that can be missed.`,
      'A direction where the height field has no data is UNKNOWN, not clear. Water is the water surface, not the sea floor.',
    ]),
  });
}

// One word for the three engines: the state of a target at a direction against a horizon (or no horizon at all).
// `horizon` may be a computeHorizon result, or any { elevationAt(azimuth) } returning the terrain angle (or null).
export function terrainStatus(horizon, azimuth, elevation, { distanceMetres = Infinity } = {}) {
  if (!horizon) return 'NOT_CHECKED';
  if (typeof horizon.assess === 'function') return horizon.assess(azimuth, elevation, { distanceMetres });
  const terrain = horizon.elevationAt(azimuth);
  if (terrain === null || terrain === undefined) return 'UNKNOWN';
  return elevation >= terrain ? 'CLEAR' : 'OBSTRUCTED';
}

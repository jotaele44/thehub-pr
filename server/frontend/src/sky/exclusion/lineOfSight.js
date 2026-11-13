// Line of sight between two places over terrain (FDX-032): is the straight sight line from one point to another clear of
// the ground between them, with the Earth's curvature and a declared refraction coefficient. Heights are metres above
// the terrain's vertical datum (PRVD02 for CUDEM), not ellipsoidal heights: a caller with ellipsoidal heights converts
// them with a declared geoid separation, or says the datum is not bound.
//
// The states: OBSTRUCTED (ground rises into the sight line at a named place), CLEAR (every sample had data and none
// rose into it), UNKNOWN (no obstruction found but the height field has no data at some samples, which is not the same
// as clear). Bare earth only: buildings and trees are not in a DEM. Water is the water surface, not the sea floor.
import { DEFAULT_REFRACTION_K, destination, radiusOfCurvature } from './horizon.js';

export const LINE_OF_SIGHT_CONTRACT = 'sky-line-of-sight-v1';
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const MAX_SAMPLES = 6000;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

function bearingAndDistance(a, b, radius) {
  const phi1 = a.lat * RAD; const phi2 = b.lat * RAD; const dLambda = (b.lon - a.lon) * RAD;
  const y = Math.sin(dLambda) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
  const h = Math.sin((phi2 - phi1) / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  return { azimuth: (Math.atan2(y, x) * DEG + 360) % 360, distance: 2 * radius * Math.asin(Math.min(1, Math.sqrt(h))) };
}

function requirePoint(name, p) {
  if (!finite(p?.lon) || !finite(p?.lat) || !finite(p?.heightMetres)) throw new RangeError(`${name} needs a longitude, a latitude and a height in metres above the terrain's datum.`);
}

export function lineOfSight(terrain, from, to, {
  refractionK = DEFAULT_REFRACTION_K, waterSurfaceMetres = 0, stepMetres = 50,
} = {}) {
  requirePoint('The first point', from);
  requirePoint('The second point', to);
  if (!finite(refractionK) || refractionK < -0.5 || refractionK >= 0.5) throw new RangeError('The refraction coefficient must be between -0.5 and 0.5.');
  if (!finite(stepMetres) || stepMetres < 5) throw new RangeError('The step must be at least 5 metres.');
  const surface = (h) => (waterSurfaceMetres === null || h > waterSurfaceMetres ? h : waterSurfaceMetres);
  const radius = radiusOfCurvature((from.lat + to.lat) / 2, bearingAndDistance(from, to, 6371008.8).azimuth);
  const { azimuth, distance } = bearingAndDistance(from, to, radius);
  const effective = radius / (1 - refractionK);
  const samples = Math.max(2, Math.min(MAX_SAMPLES, Math.ceil(distance / stepMetres)));
  let minClearance = Infinity;
  let minAt = null;
  let missing = 0;
  let firstMissing = null;
  let blocking = null;
  for (let i = 1; i < samples; i += 1) {
    const d = (distance * i) / samples;
    const p = destination(from.lon, from.lat, azimuth, d, radius);
    const h = terrain.heightAt(p.lon, p.lat);
    if (h === null || h === undefined) {
      missing += 1;
      if (firstMissing === null) firstMissing = d;
      continue;
    }
    const line = from.heightMetres + ((to.heightMetres - from.heightMetres) * d) / distance;
    const bulge = (d * (distance - d)) / (2 * effective);
    const clearance = line - surface(h) - bulge;
    if (clearance < minClearance) { minClearance = clearance; minAt = { distanceMetres: d, lon: p.lon, lat: p.lat, terrainMetres: surface(h) }; }
    if (clearance < 0 && (blocking === null || clearance < blocking.clearanceMetres)) blocking = { distanceMetres: d, lon: p.lon, lat: p.lat, terrainMetres: surface(h), clearanceMetres: clearance };
  }
  let state = 'CLEAR';
  if (blocking) state = 'OBSTRUCTED';
  else if (missing > 0) state = 'UNKNOWN';
  return Object.freeze({
    contract: LINE_OF_SIGHT_CONTRACT, state, distanceMetres: distance, azimuth,
    minClearanceMetres: Number.isFinite(minClearance) ? minClearance : null, closestApproach: minAt ? Object.freeze(minAt) : null,
    blockedAt: blocking ? Object.freeze(blocking) : null,
    samples: samples - 1, samplesWithoutData: missing, firstMissingDistanceMetres: firstMissing,
    parameters: Object.freeze({ refractionK, waterSurfaceMetres, stepMetres, datum: terrain.datum }),
    limits: Object.freeze([
      'Bare earth: buildings, trees and structures are not in a DEM, so a sight line that is CLEAR here can still be blocked on site.',
      'The sight line is sampled at the step stated; a ridge narrower than the step can be missed.',
      'UNKNOWN means the height field had no data at some samples and none of the samples that had data blocked the line: it is not clear.',
    ]),
  });
}

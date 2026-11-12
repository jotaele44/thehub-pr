// Celestial exclusion (FDX-034): which Sun, Moon, naked-eye planets and bright catalogue stars were in a reported sight
// line (or camera field of view) at some moment of the observation window, and above the horizon. This is context for
// ruling out the ordinary. A body "in the sight line" is a geometric coincidence, never an identification, and an empty
// list is not a finding: the checked set is stated beside it (not every star, not Uranus, Neptune, comets or asteroids).
import { angularSeparation } from './geometry.js';
import { terrainStatus } from './horizon.js';
import { matchDirection, sightlineAt, windowSamples } from './observation.js';
import { STARS, STAR_CATALOG, starPosition } from './stars.js';
import { bodyPosition, skyState } from '../astronomy.js';

export const CELESTIAL_CONTRACT = 'sky-celestial-exclusion-v1';
export const BODIES = Object.freeze(['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn']);
const SUN_MAGNITUDE = -26.74;
// The fastest a star moves across the sky is the Earth's rotation, 15 degrees an hour at the celestial equator
// (0.0042 degrees a second); the Moon, Sun and planets add less than a few percent of that. The step is chosen so a
// target cannot slip through a sight line between two samples by more than RESOLUTION_DEGREES.
const SKY_RATE_DEGREES_PER_SECOND = 0.0043;
const RESOLUTION_DEGREES = 0.02;
const MAX_SAMPLES = 400;
const MIN_STEP_SECONDS = 1;
const MAX_STEP_SECONDS = 60;

function sightlineSpeed(observation) {
  const { motion, direction } = observation;
  if (!motion) return 0;
  return angularSeparation(direction.azimuth, direction.elevation, motion.endAzimuth, motion.endElevation) / motion.durationSeconds;
}

// The sampling plan: the step in seconds, how many samples, and the angular resolution that implies.
export function samplingPlan(observation, targetRateDegreesPerSecond = SKY_RATE_DEGREES_PER_SECOND) {
  const relativeRate = targetRateDegreesPerSecond + sightlineSpeed(observation);
  const windowSeconds = (observation.window.end - observation.window.start) / 1000;
  let step = Math.min(MAX_STEP_SECONDS, Math.max(MIN_STEP_SECONDS, (2 * RESOLUTION_DEGREES) / relativeRate));
  if (windowSeconds / step > MAX_SAMPLES) step = windowSeconds / MAX_SAMPLES;
  const instants = windowSamples(observation, step);
  return { stepSeconds: step, samples: instants.length, resolutionDegrees: (relativeRate * step) / 2, instants };
}

// Is the object above the horizon at this direction, counting the terrain horizon when one is given? `horizon` is a
// computeHorizon result, or any { elevationAt(azimuth) } returning the terrain's elevation angle (null where unknown).
// A body is hidden only when terrain that is there hides it; where the terrain is not known it is UNKNOWN, not hidden.
function aboveHorizon(altitude, azimuth, horizon) {
  const terrain = terrainStatus(horizon, azimuth, altitude);
  return { above: altitude >= 0 && terrain !== 'OBSTRUCTED', terrain };
}

function scan(observation, plan, positionAt, horizon) {
  let best = null;
  let first = null;
  let last = null;
  let inside = 0;
  let insideAny = false;
  for (const ms of plan.instants) {
    const p = positionAt(ms);
    const m = matchDirection(observation, p.azimuth, p.altitude, ms);
    const visible = aboveHorizon(p.altitude, p.azimuth, horizon);
    if (!best || m.separationDegrees < best.separationDegrees) best = { ms, separationDegrees: m.separationDegrees, altitude: p.altitude, azimuth: p.azimuth, visible };
    if (m.inside) insideAny = true;
    if (m.inside && visible.above) { inside += 1; first = first ?? ms; last = ms; }
  }
  return {
    minSeparationDegrees: best.separationDegrees, minSeparationAt: new Date(best.ms).toISOString(), altitudeAtClosest: best.altitude, azimuthAtClosest: best.azimuth,
    aboveHorizonAtClosest: best.visible.above, terrainAtClosest: best.visible.terrain, insideSomeTime: insideAny, candidate: inside > 0,
    firstInside: first === null ? null : new Date(first).toISOString(), lastInside: last === null ? null : new Date(last).toISOString(),
    insideFraction: inside / plan.instants.length,
  };
}

export function checkCelestial(observation, { horizon = null, stars = STARS } = {}) {
  const { observer } = observation;
  const plan = samplingPlan(observation);
  const state = skyState({ time: observation.time, lat: observer.lat, lon: observer.lon, elevation: observer.height, tzHours: 0 });
  const place = { lat: observer.lat, lon: observer.lon, elevation: observer.height };
  const entries = [];
  const magnitudeOf = { Sun: SUN_MAGNITUDE, Moon: state.moon.magnitude ?? null };
  for (const planet of state.planets) magnitudeOf[planet.body] = planet.magnitude ?? null;
  for (const body of BODIES) {
    const result = scan(observation, plan, (ms) => { const p = bodyPosition(body, new Date(ms), place); return { azimuth: p.azimuth, altitude: p.altitude }; }, horizon);
    entries.push({ kind: body === 'Sun' ? 'sun' : (body === 'Moon' ? 'moon' : 'planet'), name: body, hip: null, magnitude: magnitudeOf[body], ...result });
  }
  for (const star of stars) {
    const result = scan(observation, plan, (ms) => { const p = starPosition(star, new Date(ms), place); return { azimuth: p.azimuth, altitude: p.altitude }; }, horizon);
    entries.push({ kind: 'star', name: star.label, hip: star.hip, magnitude: star.magnitude, ...result });
  }
  const byCloseness = (a, b) => a.minSeparationDegrees - b.minSeparationDegrees;
  const candidates = entries.filter((e) => e.candidate).sort(byCloseness);
  const nearest = entries.filter((e) => !e.candidate).sort(byCloseness).slice(0, 5);
  return Object.freeze({
    contract: CELESTIAL_CONTRACT,
    sampling: Object.freeze({ stepSeconds: plan.stepSeconds, samples: plan.samples, resolutionDegrees: plan.resolutionDegrees }),
    daylight: Object.freeze({ label: state.daylight.label, sunAltitudeAirless: state.daylight.sunAltitudeAirless }),
    checked: Object.freeze({ sun: 1, moon: 1, planets: 5, stars: stars.length, starLimitMagnitude: STAR_CATALOG.limit.magnitude, notAllStars: true }),
    candidates: Object.freeze(candidates.map((e) => Object.freeze(e))),
    nearest: Object.freeze(nearest.map((e) => Object.freeze(e))),
    conventions: Object.freeze([
      'Apparent topocentric positions with standard refraction, as an observer sees them; the Sun, Moon and planets from astronomy-engine, stars from a J2000 catalogue rotated to the date.',
      `Stars: the ${stars.length} brighter than V ${STAR_CATALOG.limit.magnitude}, with no proper motion, parallax or aberration (a few arcseconds to 1.6 arcminutes, far less than a sight line's tolerance).`,
      'A candidate is inside the sight line or field of view at some sampled moment of the window and above the horizon (the terrain horizon when one was given).',
    ]),
    limits: Object.freeze([
      'Not every star: only those brighter than the catalogue limit. Uranus, Neptune, comets and asteroids are not checked.',
      'A body in the sight line is a geometric coincidence, not an identification. An empty list is not evidence of anything: the checked set above is what was ruled out.',
      'Visibility against the sky is not judged: in daylight or twilight most stars and planets cannot be seen even when they are in the sight line (Venus and Jupiter sometimes can). The daylight class is given.',
      'Brightness is the catalogue or ephemeris magnitude, not what a person or a camera records.',
    ]),
    sightlineAtTime: sightlineAt(observation, observation.time.getTime()),
  });
}

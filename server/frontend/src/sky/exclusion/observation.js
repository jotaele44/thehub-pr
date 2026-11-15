// A reported observation as the "rule out the ordinary" engines take it (Phase 6, P6-C; TWIN-118, FDX-039). The page
// is for ruling out the ordinary, so this is an INPUT the user types or loads: it is held in memory, never stored, never
// made a case, and never fetched. Nothing here asks the browser for a location. Every field that could be silently
// assumed is either required (the azimuth reference) or recorded in `notes` as undeclared (time uncertainty, height).
//
// An observation is a sight line, or a camera's field of view, at a UTC instant with an uncertainty in time, seen from an
// observer. Optionally the direction moves: from the direction at `time` to an end direction at `endTime`, along the
// great circle between them at a constant rate (a straight apparent track; anything more is not modelled).
import { instantFrom } from '../astronomy.js';
import { frustumContains, frustumMargin, validateFrustum } from './frustum.js';
import { angularSeparation, normalizeAzimuth, unitVector, validateObserver } from './geometry.js';

export const OBSERVATION_CONTRACT = 'sky-observation-v1';
// The engines sample over the window, so it is bounded; the bound is stated, not hidden.
export const MAX_WINDOW_SECONDS = 6 * 3600;
const MAX_UNCERTAINTY_SECONDS = 86400;
const DEG = 180 / Math.PI;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

function requireDirection(label, azimuth, elevation) {
  if (!finite(azimuth)) throw new RangeError(`${label} azimuth is not a number: ${String(azimuth)}`);
  if (!finite(elevation) || elevation < -90 || elevation > 90) throw new RangeError(`${label} elevation must be a number between -90 and 90 degrees: ${String(elevation)}`);
}

// A bearing as the user gave it, in true degrees, with a note when a conversion was applied.
function trueAzimuth(direction, notes) {
  const reference = direction.azimuthReference;
  if (reference !== 'TRUE' && reference !== 'MAGNETIC') throw new RangeError('The azimuth reference must be declared: TRUE (from true north) or MAGNETIC (from magnetic north).');
  if (reference === 'TRUE') return { azimuth: normalizeAzimuth(direction.azimuth), declination: null };
  const declination = direction.magneticDeclinationDegrees;
  if (!finite(declination) || declination < -90 || declination > 90) throw new RangeError('A magnetic bearing needs the magnetic declination for the place and date, in degrees east of true north (between -90 and 90); it is not guessed.');
  notes.push(`The bearing was magnetic and was converted to true north with the declination given (${declination} degrees east).`);
  return { azimuth: normalizeAzimuth(direction.azimuth + declination), declination };
}

export function parseObservation(input) {
  const notes = [];
  const time = instantFrom(input?.time);
  let uncertainty = 0;
  let uncertaintyDeclared = false;
  if (input.timeUncertaintySeconds !== undefined) {
    uncertainty = input.timeUncertaintySeconds;
    if (!finite(uncertainty) || uncertainty < 0 || uncertainty >= MAX_UNCERTAINTY_SECONDS) throw new RangeError('The time uncertainty must be a number of seconds from 0 to less than a day.');
    uncertaintyDeclared = true;
  } else {
    notes.push('The time uncertainty was not declared; 0 s is used, so the check is for that exact instant only.');
  }
  const observer = validateObserver(input.observer);
  if (input.observer.height === undefined) notes.push('The observer height was not declared; 0 m above the ellipsoid is used.');

  const given = input.direction;
  requireDirection('The', given?.azimuth, given?.elevation);
  const { azimuth, declination } = trueAzimuth(given, notes);
  const hasTolerance = given.toleranceDegrees !== undefined;
  const hasFrustum = given.frustum !== undefined;
  if (hasTolerance && hasFrustum) throw new RangeError('Give a tolerance or a field of view, not both.');
  if (!hasTolerance && !hasFrustum) throw new RangeError('Give a tolerance or a field of view: how far from the sight line something may be and still count.');
  let tolerance = null;
  let frustum = null;
  if (hasTolerance) {
    tolerance = given.toleranceDegrees;
    if (!finite(tolerance) || tolerance <= 0 || tolerance > 90) throw new RangeError('The tolerance must be more than 0 and at most 90 degrees.');
  } else {
    frustum = validateFrustum(given.frustum);
  }
  const direction = Object.freeze({
    azimuth, elevation: given.elevation, azimuthAsGiven: given.azimuth, azimuthReference: given.azimuthReference,
    magneticDeclinationDegrees: declination, toleranceDegrees: tolerance, frustum,
  });

  let motion = null;
  let windowStart = time.getTime();
  let windowEnd = time.getTime();
  if (input.motion !== undefined) {
    const m = input.motion;
    requireDirection('The end', m.endAzimuth, m.endElevation);
    if (m.endTime === undefined) throw new RangeError('A moving sight line needs the time it reached the end direction.');
    const endTime = instantFrom(m.endTime);
    if (!(endTime.getTime() > time.getTime())) throw new RangeError('The end time must be after the time of the direction.');
    const end = trueAzimuth({ azimuth: m.endAzimuth, azimuthReference: given.azimuthReference, magneticDeclinationDegrees: given.magneticDeclinationDegrees }, []);
    motion = Object.freeze({ endAzimuth: end.azimuth, endElevation: m.endElevation, endTime, durationSeconds: (endTime.getTime() - time.getTime()) / 1000 });
    windowEnd = endTime.getTime();
  }
  const start = windowStart - uncertainty * 1000;
  const finish = windowEnd + uncertainty * 1000;
  if ((finish - start) / 1000 > MAX_WINDOW_SECONDS) throw new RangeError(`The observation window is longer than ${MAX_WINDOW_SECONDS / 3600} hours, which the engines do not work over.`);
  windowStart = start;
  windowEnd = finish;

  return Object.freeze({
    contract: OBSERVATION_CONTRACT, time, timeUncertaintySeconds: uncertainty, timeUncertaintyDeclared: uncertaintyDeclared,
    window: Object.freeze({ start: new Date(windowStart), end: new Date(windowEnd) }), observer, direction, motion,
    notes: Object.freeze(notes),
  });
}

// Spherical interpolation between two directions, as unit vectors.
function slerp(a, b, fraction) {
  const angle = Math.acos(Math.max(-1, Math.min(1, a.e * b.e + a.n * b.n + a.u * b.u)));
  if (angle < 1e-12) return a;
  const wa = Math.sin((1 - fraction) * angle) / Math.sin(angle);
  const wb = Math.sin(fraction * angle) / Math.sin(angle);
  return { e: wa * a.e + wb * b.e, n: wa * a.n + wb * b.n, u: wa * a.u + wb * b.u };
}

// Where the sight line points at an instant: fixed, or along the great circle from the start direction to the end
// direction, held at the start before the time and at the end after the end time.
export function sightlineAt(observation, ms) {
  const { direction, motion } = observation;
  if (!motion) return { azimuth: direction.azimuth, elevation: direction.elevation };
  const start = observation.time.getTime();
  const fraction = Math.max(0, Math.min(1, (ms - start) / (motion.endTime.getTime() - start)));
  if (fraction === 0) return { azimuth: direction.azimuth, elevation: direction.elevation };
  const v = slerp(unitVector(direction.azimuth, direction.elevation), unitVector(motion.endAzimuth, motion.endElevation), fraction);
  return { azimuth: normalizeAzimuth(Math.atan2(v.e, v.n) * DEG), elevation: Math.asin(Math.max(-1, Math.min(1, v.u))) * DEG };
}

// Is a direction within the observation at an instant: inside the tolerance cone, or inside the camera's field of view?
// Returns the angular separation from the sight line, whether it is inside, and the margin (negative when inside, in
// degrees: how far inside the tolerance or the nearer edge of the field of view; null behind the camera).
export function matchDirection(observation, azimuth, elevation, ms) {
  const centre = sightlineAt(observation, ms);
  const separationDegrees = angularSeparation(centre.azimuth, centre.elevation, azimuth, elevation);
  const { frustum, toleranceDegrees } = observation.direction;
  if (frustum) {
    const marginDegrees = frustumMargin(frustum, centre, azimuth, elevation);
    return { separationDegrees, inside: frustumContains(frustum, centre, azimuth, elevation), marginDegrees };
  }
  return { separationDegrees, inside: separationDegrees <= toleranceDegrees, marginDegrees: separationDegrees - toleranceDegrees };
}

// Instants across the observation window, both ends included, no more than `stepSeconds` apart.
export function windowSamples(observation, stepSeconds) {
  if (!finite(stepSeconds) || stepSeconds <= 0) throw new RangeError('The sampling step must be a positive number of seconds.');
  const start = observation.window.start.getTime();
  const end = observation.window.end.getTime();
  if (end === start) return [start];
  const count = Math.ceil((end - start) / (stepSeconds * 1000));
  return Array.from({ length: count + 1 }, (_, i) => (i === count ? end : start + (i * (end - start)) / count));
}


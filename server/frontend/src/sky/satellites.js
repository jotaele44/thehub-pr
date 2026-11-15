// Satellites for the Sky workspace (TWIN-042..046, 054, 055, 116): where the International Space Station, the
// Hubble Space Telescope and the Chinese space station (the Tianhe core module) are for a given UTC instant and
// observer, when they pass over, and whether a pass could be seen. Computed here, in the browser, from the
// orbital elements CelesTrak publishes (GP JSON, the successor of the TLE) with satellite.js (MIT, SGP4) and the
// Sun from astronomy-engine; the only network call is the element download in loadSatelliteElements.
//
// What this is not: a forecast of what an eye or a camera will see. SGP4 is held to Vallado's published
// verification set and to an independent implementation (satellites.test.js), which shows the code does what the
// model says, not that the model predicts a sighting. Brightness is not estimated. Elements describe the orbit
// near their epoch, so the further an instant is from it the less the answer means; past the age limit below the
// answer is refused. A past observation needs element sets from its own time, which this does not have.
import { GeoVector, KM_PER_AU, MakeTime, RotateVector, Rotation_EQJ_EQD } from 'astronomy-engine';
import {
  degreesToRadians, ecfToLookAngles, eciToEcf, eciToGeodetic, gstime, json2satrec, propagate, radiansToDegrees,
  SatRecError,
} from 'satellite.js';
import { bodyPosition, instantFrom, makeObserver } from './astronomy.js';

export const SATELLITE_CONTRACT = 'sky-satellites-v1';
export const SATELLITE_ENGINE = Object.freeze({ name: 'satellite.js', version: '7.1.0' });

export const SATELLITES = Object.freeze([
  Object.freeze({ id: 'ISS', noradId: 25544, label: 'International Space Station' }),
  Object.freeze({ id: 'HST', noradId: 20580, label: 'Hubble Space Telescope' }),
  Object.freeze({
    id: 'CSS', noradId: 48274, label: 'Chinese space station (Tianhe core module)',
    note: 'Elements are those of the Tianhe core module, used for the station; docked modules are separate catalogue objects.',
  }),
]);

export const CELESTRAK_GP_URL = 'https://celestrak.org/NORAD/elements/gp.php';
export const gpUrl = (noradId) => `${CELESTRAK_GP_URL}?CATNR=${encodeURIComponent(noradId)}&FORMAT=json`;

// A labelled policy, not physics: SGP4 error grows by kilometres per day for a low orbit, so confidence is stepped
// by the distance (either way) between the instant asked about and the elements' epoch.
export const ELEMENT_POLICY = Object.freeze({
  kind: 'policy', normalDays: 3, lowerDays: 7, refuseDays: 14,
  note: 'Within 3 days of the epoch: normal. 3 to 7: lower confidence. 7 to 14: low confidence. Beyond 14: refused.',
});

export const OBSERVER_DARK_SUN_ALTITUDE = -6;
export const EARTH_SHADOW_RADIUS_KM = 6378.137;
export const VISIBLE_LABEL = 'Visible-pass candidate (geometry only; brightness not estimated)';

export const SATELLITE_CONVENTIONS = Object.freeze({
  model: `SGP4 from CelesTrak GP elements (${SATELLITE_ENGINE.name} ${SATELLITE_ENGINE.version}); positions in the TEME frame.`,
  lookAngles: 'Azimuth from north through east and geometric elevation (no refraction), from the observer\'s geodetic position; Earth rotation from GMST with UT1-UTC ignored.',
  sunlit: 'A satellite is sunlit unless it is behind the Earth and inside a cylinder of the Earth\'s equatorial radius along the Sun direction (umbra only, no penumbra, no atmosphere). The Sun comes from astronomy-engine, rotated to the equator of date to match TEME (they differ by the equation of the equinoxes, about 0.005 degrees).',
  observerDark: `The observer's sky counts as dark when the geometric Sun centre is at or below ${OBSERVER_DARK_SUN_ALTITUDE} degrees.`,
  visible: `${VISIBLE_LABEL}: above the minimum elevation, sunlit, and the observer's sky dark. It says nothing about brightness, weather or obstructions.`,
  elements: ELEMENT_POLICY.note,
  past: 'Elements are current ones. They cannot reproduce a past event: that needs element sets from its own time.',
});

const MS_PER_DAY = 86400e3;
// How far below the minimum elevation a sampled peak can be and still hide the top of a pass between two samples: the
// elevation of a low-Earth-orbit satellite changes by well under half a degree beyond the highest sample at a 20-second step.
const GRAZING_MARGIN_DEGREES = 2;
const DEFAULT_PASS_HOURS = 24;
const MAX_PASS_HOURS = 72;

const fail = (reason, message, extra = {}) => Object.freeze({ ok: false, reason, message, ...extra });
const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const toNumber = (value) => (typeof value === 'string' && value.trim() !== '' ? Number(value) : value);
const normalizeDegrees = (value) => ((value % 360) + 360) % 360;

// [low, high, low is open, high is open]: rev/day above 0 up to 20, eccentricity below 1, angles in degrees.
const RANGES = Object.freeze({
  MEAN_MOTION: [0, 20, true, false], ECCENTRICITY: [0, 1, false, true], INCLINATION: [0, 180, false, false],
  RA_OF_ASC_NODE: [0, 360, false, true], ARG_OF_PERICENTER: [0, 360, false, true], MEAN_ANOMALY: [0, 360, false, true],
});
const inRange = (value, [low, high, lowOpen, highOpen]) => (lowOpen ? value > low : value >= low) && (highOpen ? value < high : value <= high);
const REQUIRED_NUMBERS = Object.freeze([
  'NORAD_CAT_ID', 'MEAN_MOTION', 'ECCENTRICITY', 'INCLINATION', 'RA_OF_ASC_NODE', 'ARG_OF_PERICENTER', 'MEAN_ANOMALY',
  'BSTAR', 'MEAN_MOTION_DOT', 'MEAN_MOTION_DDOT',
]);

// CelesTrak writes EPOCH without a zone; it is UTC.
function parseEpoch(text) {
  if (typeof text !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$/.test(text)) {
    throw new RangeError(`EPOCH "${String(text)}" is not an ISO date-time.`);
  }
  const date = new Date(text.endsWith('Z') ? text : `${text}Z`);
  if (Number.isNaN(date.getTime())) throw new RangeError(`EPOCH "${text}" is not a valid instant.`);
  return date;
}

// One CelesTrak GP record (OMM JSON) into elements SGP4 can run. Anything missing, out of range or not SGP4 is
// refused with the reason; nothing is defaulted.
export function parseGp(record) {
  if (!record || typeof record !== 'object' || Array.isArray(record)) throw new TypeError('A GP record must be an object.');
  const clean = {};
  for (const key of REQUIRED_NUMBERS) {
    const value = toNumber(record[key]);
    if (!finite(value)) throw new RangeError(`GP record has no usable ${key}.`);
    clean[key] = value;
  }
  for (const [key, range] of Object.entries(RANGES)) {
    if (!inRange(clean[key], range)) throw new RangeError(`GP record ${key} ${clean[key]} is outside its range.`);
  }
  if (!Number.isInteger(clean.NORAD_CAT_ID) || clean.NORAD_CAT_ID <= 0) throw new RangeError('GP record NORAD_CAT_ID is not a catalogue number.');
  const theory = record.MEAN_ELEMENT_THEORY;
  if (theory !== undefined && String(theory).toUpperCase() !== 'SGP4') throw new RangeError(`GP record uses ${theory}, not SGP4.`);
  const ephemerisType = record.EPHEMERIS_TYPE;
  if (ephemerisType !== undefined && Number(ephemerisType) !== 0) throw new RangeError('GP record is not an SGP4 element set (EPHEMERIS_TYPE is not 0).');
  const name = typeof record.OBJECT_NAME === 'string' ? record.OBJECT_NAME.trim() : '';
  if (!name) throw new RangeError('GP record has no OBJECT_NAME.');
  const epoch = parseEpoch(record.EPOCH);

  const omm = {
    ...clean,
    OBJECT_NAME: name,
    OBJECT_ID: typeof record.OBJECT_ID === 'string' ? record.OBJECT_ID : '',
    EPOCH: epoch.toISOString().replace('Z', ''),
    MEAN_ELEMENT_THEORY: 'SGP4',
    REF_FRAME: 'TEME',
    TIME_SYSTEM: 'UTC',
    CLASSIFICATION_TYPE: typeof record.CLASSIFICATION_TYPE === 'string' ? record.CLASSIFICATION_TYPE : 'U',
    EPHEMERIS_TYPE: 0,
    ELEMENT_SET_NO: finite(toNumber(record.ELEMENT_SET_NO)) ? toNumber(record.ELEMENT_SET_NO) : 0,
    REV_AT_EPOCH: finite(toNumber(record.REV_AT_EPOCH)) ? toNumber(record.REV_AT_EPOCH) : 0,
  };
  const satrec = json2satrec(omm);
  if (satrec.error) throw new RangeError(`SGP4 rejected the elements: ${SatRecError[satrec.error] ?? satrec.error}.`);
  const atEpoch = propagate(satrec, epoch);
  if (!atEpoch || !atEpoch.position) throw new RangeError(`SGP4 gives no state at the epoch: ${SatRecError[satrec.error] ?? satrec.error}.`);

  return Object.freeze({
    noradId: clean.NORAD_CAT_ID, name, objectId: omm.OBJECT_ID, epoch,
    meanMotionRevPerDay: clean.MEAN_MOTION, periodMinutes: 1440 / clean.MEAN_MOTION,
    inclinationDegrees: clean.INCLINATION, eccentricity: clean.ECCENTRICITY, satrec,
  });
}

// How far an instant is from the elements' epoch, and what the policy makes of that distance.
export function elementAge(element, instant) {
  const signedDays = (instantFrom(instant).getTime() - element.epoch.getTime()) / MS_PER_DAY;
  const days = Math.abs(signedDays);
  let state = 'REFUSED';
  let confidence = 'NONE';
  if (days <= ELEMENT_POLICY.normalDays) { state = 'NORMAL'; confidence = 'NORMAL'; }
  else if (days <= ELEMENT_POLICY.lowerDays) { state = 'LOWER'; confidence = 'LOWER'; }
  else if (days <= ELEMENT_POLICY.refuseDays) { state = 'LOW'; confidence = 'LOW'; }
  return Object.freeze({ signedDays, days, state, confidence, policy: ELEMENT_POLICY.kind });
}

// Where the satellite is: TEME position (km) and velocity (km/s), or the reason there is no answer.
export function stateAt(element, instant) {
  const date = instantFrom(instant);
  const age = elementAge(element, date);
  if (age.state === 'REFUSED') {
    return fail('ELEMENTS_TOO_OLD', `The elements are ${age.days.toFixed(1)} days from this instant; the limit is ${ELEMENT_POLICY.refuseDays} days.`, { age });
  }
  const result = propagate(element.satrec, date);
  if (!result || !result.position || typeof result.position !== 'object') {
    const code = element.satrec.error;
    return fail('SGP4_ERROR', `SGP4 gives no state here: ${SatRecError[code] ?? code}.`, { code, age });
  }
  return Object.freeze({ ok: true, time: date, positionKm: result.position, velocityKmS: result.velocity, frame: 'TEME', age });
}

// The Sun's geocentric vector (km) in the true equator and equinox of date, which is TEME to about 0.005 degrees.
export function sunVectorKm(instant) {
  const time = MakeTime(instantFrom(instant));
  const inDate = RotateVector(Rotation_EQJ_EQD(time), GeoVector('Sun', time, true));
  return Object.freeze({ x: inDate.x * KM_PER_AU, y: inDate.y * KM_PER_AU, z: inDate.z * KM_PER_AU });
}

// Cylindrical Earth shadow. Sunlit when on the Sun's side of the Earth's centre, or farther than the Earth's
// radius from the Earth-Sun axis.
export function shadowState(positionKm, sunKm) {
  const sunLength = Math.hypot(sunKm.x, sunKm.y, sunKm.z);
  const alongSunKm = (positionKm.x * sunKm.x + positionKm.y * sunKm.y + positionKm.z * sunKm.z) / sunLength;
  const offAxisKm = Math.sqrt(Math.max(0, positionKm.x ** 2 + positionKm.y ** 2 + positionKm.z ** 2 - alongSunKm ** 2));
  return Object.freeze({ sunlit: alongSunKm >= 0 || offAxisKm >= EARTH_SHADOW_RADIUS_KM, alongSunKm, offAxisKm });
}

// The geometry every sample needs: the state, and azimuth, elevation and range from a validated observer.
function geometryAt(element, instant, place) {
  const state = stateAt(element, instant);
  if (!state.ok) return state;
  const gmst = gstime(state.time);
  const angles = ecfToLookAngles({
    longitude: degreesToRadians(place.lon), latitude: degreesToRadians(place.lat), height: (place.elevation ?? 0) / 1000,
  }, eciToEcf(state.positionKm, gmst));
  return { ok: true, state, gmst, azimuth: normalizeDegrees(radiansToDegrees(angles.azimuth)), elevation: radiansToDegrees(angles.elevation), rangeKm: angles.rangeSat };
}

// Where the satellite is in the observer's sky, geometrically, and nothing more: no Sun, no shadow. The cheap call for
// scanning a window of time (the exclusion engine); lookAt adds the sub-satellite point and the lit state.
export function directionAt(element, instant, observer) {
  const geometry = geometryAt(element, instant, makeObserver(observer));
  if (!geometry.ok) return geometry;
  return Object.freeze({ ok: true, time: geometry.state.time, azimuth: geometry.azimuth, elevation: geometry.elevation, rangeKm: geometry.rangeKm, age: geometry.state.age });
}

// Where the satellite is in the observer's sky, and whether the Sun lights it.
export function lookAt(element, instant, observer) {
  const geometry = geometryAt(element, instant, makeObserver(observer));
  if (!geometry.ok) return geometry;
  const { state, gmst } = geometry;
  const subpoint = eciToGeodetic(state.positionKm, gmst);
  return Object.freeze({
    ok: true, time: state.time, azimuth: geometry.azimuth, elevation: geometry.elevation, rangeKm: geometry.rangeKm,
    subpoint: Object.freeze({ latitude: radiansToDegrees(subpoint.latitude), longitude: radiansToDegrees(subpoint.longitude), heightKm: subpoint.height }),
    sunlit: shadowState(state.positionKm, sunVectorKm(state.time)).sunlit, age: state.age,
  });
}

// Is the observer's sky dark enough, and is the satellite lit and above the minimum elevation, at this instant?
function visibilityAt(look, observer, minElevation) {
  const sunAltitude = bodyPosition('Sun', look.time, observer, { refraction: null }).altitude;
  const observerDark = sunAltitude <= OBSERVER_DARK_SUN_ALTITUDE;
  return { sunAltitude, observerDark, visible: look.elevation >= minElevation && look.sunlit && observerDark };
}

// Time at which `value(ms)` crosses zero between a point below and a point above, to well under a second.
function bisect(value, lowMs, highMs) {
  let low = lowMs;
  let high = highMs;
  const lowSign = Math.sign(value(low));
  for (let i = 0; i < 40 && Math.abs(high - low) > 100; i += 1) {
    const mid = (low + high) / 2;
    if (Math.sign(value(mid)) === lowSign) low = mid; else high = mid;
  }
  return (low + high) / 2;
}

// The time of greatest elevation inside a pass (it rises, peaks, then falls, so a golden-section search finds it).
function peak(elevationAt, startMs, endMs) {
  const ratio = (Math.sqrt(5) - 1) / 2;
  let a = startMs;
  let b = endMs;
  let c = b - ratio * (b - a);
  let d = a + ratio * (b - a);
  for (let i = 0; i < 60 && b - a > 100; i += 1) {
    if (elevationAt(c) > elevationAt(d)) b = d; else a = c;
    c = b - ratio * (b - a);
    d = a + ratio * (b - a);
  }
  return (a + b) / 2;
}

function explain(samples, minElevation) {
  const above = samples.filter((s) => s.look.elevation >= minElevation);
  if (!above.some((s) => s.sunlit)) return 'The satellite is in the Earth\'s shadow for the whole pass.';
  if (!above.some((s) => s.observerDark)) return `The sky is too bright: the Sun is above ${OBSERVER_DARK_SUN_ALTITUDE} degrees for the whole pass.`;
  return 'The satellite is lit only while the sky is too bright, and in shadow once the sky is dark.';
}

// Passes above `minElevation` that overlap the window, each with its rise, culmination and set (AOS, TCA, LOS),
// and whether it is a visible-pass candidate. Fails as a whole, with the reason, if any instant has no state.
export function findPasses(element, observer, start, { hours = DEFAULT_PASS_HOURS, minElevation = 10, stepSeconds = 20 } = {}) {
  const place = makeObserver(observer);
  if (!finite(hours) || hours <= 0 || hours > MAX_PASS_HOURS) throw new RangeError(`Hours must be between 0 and ${MAX_PASS_HOURS}.`);
  if (!finite(minElevation) || minElevation < 0 || minElevation > 80) throw new RangeError('Minimum elevation must be between 0 and 80 degrees.');
  if (!finite(stepSeconds) || stepSeconds < 5 || stepSeconds > 60) throw new RangeError('Step must be between 5 and 60 seconds.');
  const startMs = instantFrom(start).getTime();
  const endMs = startMs + hours * 3600e3;
  const lookback = 45 * 60e3;
  for (const edge of [startMs - lookback, endMs + lookback]) {
    const age = elementAge(element, edge);
    if (age.state === 'REFUSED') return fail('ELEMENTS_TOO_OLD', `The elements are ${age.days.toFixed(1)} days from this window; the limit is ${ELEMENT_POLICY.refuseDays} days.`, { age });
  }

  let broken = null;
  const elevationAt = (ms) => {
    const geometry = geometryAt(element, new Date(ms), place);
    if (!geometry.ok) { broken = broken ?? geometry; return -90; }
    return geometry.elevation;
  };
  const above = (ms) => elevationAt(ms) - minElevation;
  const step = stepSeconds * 1000;

  // Walk back out of a pass already in progress, and forward out of one still going at the end of the window.
  let from = startMs;
  if (above(from) >= 0) { while (above(from - step) >= 0 && startMs - from < lookback) from -= step; from -= step; }
  const to = (() => { let t = endMs; if (above(t) >= 0) { while (above(t + step) >= 0 && t - endMs < lookback) t += step; t += step; } return t; })();

  const crossings = [];
  const samples = [{ ms: from, elevation: elevationAt(from) }];
  let previous = from;
  let previousUp = samples[0].elevation >= minElevation;
  for (let t = from + step; t <= to; t += step) {
    const elevation = elevationAt(t);
    samples.push({ ms: t, elevation });
    const up = elevation >= minElevation;
    if (up !== previousUp) crossings.push({ rising: up, ms: bisect(above, previous, t) });
    previous = t;
    previousUp = up;
  }
  // A pass that clears the minimum for less than one step can fall between two samples that are both below it, so the
  // sign test above never sees it. A pass is one hump in the elevation, so a sampled local maximum that is below the
  // minimum but close to it may hide the top of such a hump: find the true top between its neighbours, and if that clears
  // the minimum, add the rise and the set around it.
  for (let i = 1; i + 1 < samples.length; i += 1) {
    const [before, here, after] = [samples[i - 1], samples[i], samples[i + 1]];
    if (before.elevation >= minElevation || here.elevation >= minElevation || after.elevation >= minElevation) continue;
    if (!(here.elevation > before.elevation && here.elevation >= after.elevation)) continue;
    if (here.elevation < minElevation - GRAZING_MARGIN_DEGREES) continue;
    const top = peak(elevationAt, before.ms, after.ms);
    if (above(top) >= 0) crossings.push({ rising: true, ms: bisect(above, before.ms, top) }, { rising: false, ms: bisect(above, top, after.ms) });
  }
  crossings.sort((x, y) => x.ms - y.ms);
  if (broken) return broken;

  const windows = [];
  let open = null;
  if (above(from) >= 0) open = from;
  for (const crossing of crossings) {
    if (crossing.rising) open = crossing.ms;
    else if (open !== null) { windows.push([open, crossing.ms]); open = null; }
  }
  if (open !== null) windows.push([open, to]);

  const passes = windows
    .filter(([aos, los]) => los > startMs && aos < endMs && los > aos)
    .map(([aos, los]) => {
      const tca = peak(elevationAt, aos, los);
      const sampleStep = 5000;
      const samples = [];
      for (let t = aos; t <= los + 1; t += sampleStep) {
        const look = lookAt(element, new Date(Math.min(t, los)), place);
        if (look.ok) samples.push({ look, sunlit: look.sunlit, ...visibilityAt(look, place, minElevation) });
      }
      const visibleSamples = samples.filter((s) => s.visible);
      const atCulmination = lookAt(element, new Date(tca), place);
      const atStart = lookAt(element, new Date(aos), place);
      const atEnd = lookAt(element, new Date(los), place);
      const candidate = visibleSamples.length > 0;
      return Object.freeze({
        aos: new Date(aos), tca: new Date(tca), los: new Date(los), durationSeconds: Math.round((los - aos) / 1000),
        maxElevation: atCulmination.elevation, aosAzimuth: atStart.azimuth, tcaAzimuth: atCulmination.azimuth, losAzimuth: atEnd.azimuth,
        rangeAtCulminationKm: atCulmination.rangeKm,
        sunlitSeconds: samples.filter((s) => s.sunlit).length * 5,
        sunAltitudeAtCulmination: bodyPosition('Sun', new Date(tca), place, { refraction: null }).altitude,
        visibility: Object.freeze({
          candidate, label: candidate ? VISIBLE_LABEL : 'Not a visible-pass candidate',
          from: candidate ? visibleSamples[0].look.time : null, to: candidate ? visibleSamples[visibleSamples.length - 1].look.time : null,
          reason: candidate ? null : explain(samples, minElevation),
        }),
        confidence: elementAge(element, tca).confidence,
      });
    });

  return Object.freeze({
    ok: true, passes: Object.freeze(passes), window: Object.freeze({ start: new Date(startMs), end: new Date(endMs) }),
    minElevation, stepSeconds, conventions: SATELLITE_CONVENTIONS,
  });
}

// Az/el of the satellite along an interval, for drawing its track across the sky (above the horizon only).
export function skyTrack(element, observer, from, to, stepSeconds = 15) {
  const place = makeObserver(observer);
  const fromMs = instantFrom(from).getTime();
  const toMs = instantFrom(to).getTime();
  if (!(toMs > fromMs) || !(stepSeconds >= 1)) throw new RangeError('A track needs an interval and a positive step.');
  const points = [];
  for (let ms = fromMs; ms <= toMs; ms += stepSeconds * 1000) {
    const look = lookAt(element, new Date(ms), place);
    if (!look.ok) return look;
    if (look.elevation >= 0) points.push(Object.freeze({ time: look.time, azimuth: look.azimuth, altitude: look.elevation, sunlit: look.sunlit }));
  }
  return Object.freeze({ ok: true, points: Object.freeze(points) });
}

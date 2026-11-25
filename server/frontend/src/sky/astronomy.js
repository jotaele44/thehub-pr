// Astronomical state for the Sky workspace (TWIN-047..053, 111..115, 122..131): where the Sun, the Moon and the
// five naked-eye planets are for a given UTC instant and observer, when they rise and set, how dark it is, and
// the Moon's phase. Computed here, in the browser, with astronomy-engine (MIT, no dependencies); nothing is
// fetched and no producer is called. The engine is held to JPL Horizons and USNO by astronomy.test.js, using the
// values frozen in referenceEphemerides.json, within the tolerances measured when they were frozen.
//
// Conventions are stated in every state (conventions) so a reader can tell what each number means:
// altitudes are apparent (standard refraction) unless named airless; rise and set use the upper limb at the
// horizon; twilight is cut on the geometric Sun centre; times are UTC instants shown at a fixed UTC offset.
import {
  Elongation, Equator, Horizon, Illumination, MakeTime, MoonPhase, Observer, SearchAltitude, SearchHourAngle,
  SearchMoonQuarter, SearchRiseSet,
} from 'astronomy-engine';

export const SKY_CONTRACT = 'sky-state-v1';
export const ENGINE = Object.freeze({ name: 'astronomy-engine', version: '2.1.19' });
export const NAKED_EYE_PLANETS = Object.freeze(['Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn']);

// Sun altitude cuts (degrees, geometric centre): the Sun's upper limb meets the horizon at -0.833 once standard
// refraction (34') and the Sun's semidiameter (16') are counted.
const SUNRISE_ALTITUDE = -0.8333;
const TWILIGHT_LIMITS = Object.freeze({ CIVIL: -6, NAUTICAL: -12, ASTRONOMICAL: -18 });
// A principal phase is named only within a degree of the exact phase (about two hours of the Moon's motion).
const PRINCIPAL_PHASE_WINDOW_DEGREES = 1;
const QUARTER_NAMES = Object.freeze(['New Moon', 'First Quarter', 'Full Moon', 'Last Quarter']);
// Refraction lifts what can be seen. Below this geometric altitude (degrees) a body has no apparent position to
// lift, so its displayed altitude is the geometric one. (JPL Horizons instead extends its value at -1 degree to
// every depth, a constant +0.6466 degree, which is why the 'jplhor' model is used only to reproduce Horizons.)
const REFRACTION_FLOOR = -1;
// Apparent semidiameters used only to decide "above or below the horizon all day" on a day with no event.
const SEMIDIAMETER_DEGREES = Object.freeze({ Sun: 0.2667, Moon: 0.25 });

export const CONVENTIONS = Object.freeze({
  position: 'Apparent topocentric position (aberration included); azimuth from north through east.',
  refraction: 'Altitudes include standard atmospheric refraction for a body above the horizon or within 1 degree below it; deeper below the horizon there is no apparent position, so the geometric altitude is shown. altitudeAirless is always the geometric altitude.',
  riseSet: 'Rise and set: the upper limb at the horizon with standard refraction and the body\'s semidiameter (Sun centre at -0.833 degrees).',
  twilight: 'Civil twilight begins at -0.833 degrees, nautical at -6, astronomical at -12, night below -18 (geometric Sun centre).',
  time: 'Instants are UTC; local clock time is shown at the stated fixed UTC offset, with no daylight-saving rules applied.',
  engine: `${ENGINE.name} ${ENGINE.version}`,
});

export function instantFrom(value) {
  let date;
  if (value instanceof Date) date = value;
  else if (typeof value === 'number') date = new Date(value);
  else if (typeof value === 'string' && value.trim()) {
    // A bare local date-time would be read in the viewer's zone: require a UTC designator or an offset.
    if (/T\d{2}:\d{2}/.test(value) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value.trim())) {
      throw new RangeError(`Time "${value}" needs a UTC designator (Z) or an offset.`);
    }
    date = new Date(value);
  }
  if (!date || Number.isNaN(date.getTime())) throw new RangeError(`Time is not a valid instant: ${String(value)}`);
  return date;
}

export function makeObserver({ lat, lon, elevation = 0 }) {
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) throw new RangeError('Latitude must be between -90 and 90 degrees.');
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) throw new RangeError('Longitude must be between -180 and 180 degrees.');
  if (!Number.isFinite(elevation) || elevation < -500 || elevation > 10000) throw new RangeError('Elevation must be between -500 and 10000 metres.');
  return Object.freeze({ lat, lon, elevation });
}

function checkOffset(tzHours) {
  if (!Number.isFinite(tzHours) || tzHours < -12 || tzHours > 14) throw new RangeError('UTC offset must be between -12 and +14 hours.');
  return tzHours;
}

const engineObserver = (observer) => new Observer(observer.lat, observer.lon, observer.elevation ?? 0);

// Where a body is: azimuth (north through east) and altitude, with refraction 'normal' (standard), 'jplhor'
// (the model JPL Horizons uses) or null (airless), plus right ascension (hours) and declination (degrees) of date.
export function bodyPosition(body, instant, observer, { refraction = 'normal' } = {}) {
  const date = instantFrom(instant);
  const time = MakeTime(date);
  const engine = engineObserver(observer);
  const equator = Equator(body, time, engine, true, true);
  const horizon = Horizon(time, engine, equator.ra, equator.dec, refraction ?? undefined);
  return { body, azimuth: horizon.azimuth, altitude: horizon.altitude, ra: equator.ra, dec: equator.dec };
}

const TWILIGHT_CLASSES = Object.freeze({
  DAYLIGHT: 'Daylight',
  CIVIL_TWILIGHT: 'Civil twilight',
  NAUTICAL_TWILIGHT: 'Nautical twilight',
  ASTRONOMICAL_TWILIGHT: 'Astronomical twilight',
  NIGHT: 'Night',
});

// Class from the geometric Sun-centre altitude, in degrees.
export function twilightClass(sunAltitudeAirless) {
  let id = 'NIGHT';
  if (sunAltitudeAirless > SUNRISE_ALTITUDE) id = 'DAYLIGHT';
  else if (sunAltitudeAirless > TWILIGHT_LIMITS.CIVIL) id = 'CIVIL_TWILIGHT';
  else if (sunAltitudeAirless > TWILIGHT_LIMITS.NAUTICAL) id = 'NAUTICAL_TWILIGHT';
  else if (sunAltitudeAirless > TWILIGHT_LIMITS.ASTRONOMICAL) id = 'ASTRONOMICAL_TWILIGHT';
  return Object.freeze({ id, label: TWILIGHT_CLASSES[id] });
}

// The local calendar day containing an instant, at a fixed UTC offset (hours).
export function localDayWindow(instant, tzHours = 0) {
  const offset = checkOffset(tzHours) * 3600e3;
  const shifted = instantFrom(instant).getTime() + offset;
  const start = new Date(Math.floor(shifted / 86400e3) * 86400e3 - offset);
  return Object.freeze({ start, end: new Date(start.getTime() + 86400e3), tzHours });
}

// HH:MM at a fixed UTC offset (whole minutes, nearest); an em dash for no time.
export function formatClock(date, tzHours = 0) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return '—';
  const minutes = Math.round((date.getTime() + tzHours * 3600e3) / 60000);
  const ofDay = ((minutes % 1440) + 1440) % 1440;
  return `${String(Math.floor(ofDay / 60)).padStart(2, '0')}:${String(ofDay % 60).padStart(2, '0')}`;
}

// Rise, upper transit and set inside a window (the local day). A day can have only one of them, or none:
// `status` says which, and for a day with none whether the body stays above or below the horizon, decided from
// its apparent altitude at the start of the window (no event means it never crosses).
export function riseTransitSet(body, observer, window) {
  const engine = engineObserver(observer);
  const start = MakeTime(window.start);
  const inside = (time) => (time && time.date >= window.start && time.date < window.end ? time.date : null);
  const rise = inside(SearchRiseSet(body, engine, +1, start, 1));
  const set = inside(SearchRiseSet(body, engine, -1, start, 1));
  const transit = inside(SearchHourAngle(body, engine, 0, start).time);
  const result = { rise, transit, set };
  if (body === 'Sun') {
    result.civilTwilightBegin = inside(SearchAltitude('Sun', engine, +1, start, 1, TWILIGHT_LIMITS.CIVIL));
    result.civilTwilightEnd = inside(SearchAltitude('Sun', engine, -1, start, 1, TWILIGHT_LIMITS.CIVIL));
  }
  if (rise && set) result.status = 'RISES_AND_SETS';
  else if (rise) result.status = 'RISES_ONLY';
  else if (set) result.status = 'SETS_ONLY';
  else {
    const apparent = bodyPosition(body, window.start, observer, { refraction: 'normal' }).altitude;
    result.status = apparent > -(SEMIDIAMETER_DEGREES[body] ?? 0) ? 'ABOVE_HORIZON_ALL_DAY' : 'BELOW_HORIZON_ALL_DAY';
  }
  return result;
}

function phaseNameOf(angle) {
  const nearest = Math.round(angle / 90) % 4;
  // Angular distance (0..180) from the nearest principal phase, across the 0/360 wrap.
  const away = Math.abs(((angle - nearest * 90 + 540) % 360) - 180);
  if (away <= PRINCIPAL_PHASE_WINDOW_DEGREES) return QUARTER_NAMES[nearest];
  if (angle < 90) return 'Waxing Crescent';
  if (angle < 180) return 'Waxing Gibbous';
  if (angle < 270) return 'Waning Gibbous';
  return 'Waning Crescent';
}

// The Moon's phase: elongation angle from the Sun (0 new, 180 full), the illuminated fraction of the disc as
// seen from the Earth's centre, a name, and the next quarter.
export function moonPhase(instant) {
  const date = instantFrom(instant);
  const time = MakeTime(date);
  const angle = MoonPhase(time);
  const quarter = SearchMoonQuarter(time);
  return Object.freeze({
    angle,
    illuminatedFraction: Illumination('Moon', time).phase_fraction,
    name: phaseNameOf(angle),
    nextQuarter: Object.freeze({ name: QUARTER_NAMES[quarter.quarter], time: quarter.time.date }),
  });
}

function bodyState(body, instant, observer, window) {
  const apparent = bodyPosition(body, instant, observer, { refraction: 'normal' });
  const airless = bodyPosition(body, instant, observer, { refraction: null });
  const altitude = airless.altitude > REFRACTION_FLOOR ? apparent.altitude : airless.altitude;
  const time = MakeTime(instantFrom(instant));
  const illumination = Illumination(body, time);
  return {
    body,
    azimuth: apparent.azimuth,
    altitude,
    altitudeAirless: airless.altitude,
    aboveHorizon: altitude > 0,
    magnitude: illumination.mag,
    illuminatedFraction: illumination.phase_fraction,
    ...riseTransitSet(body, observer, window),
  };
}

// The whole Sky readout for an instant and an observer. `tzHours` is the fixed UTC offset that defines "the
// day" for rise, set and twilight times; it defaults to UTC and is never guessed from the longitude.
export function skyState({ time, lat, lon, elevation = 0, tzHours = 0 }) {
  const instant = instantFrom(time);
  const observer = makeObserver({ lat, lon, elevation });
  const window = localDayWindow(instant, tzHours);
  const sun = bodyState('Sun', instant, observer, window);
  const moon = bodyState('Moon', instant, observer, window);
  const phase = moonPhase(instant);
  const planets = NAKED_EYE_PLANETS.map((body) => ({
    ...bodyState(body, instant, observer, window),
    elongation: Elongation(body, MakeTime(instant)).elongation,
  }));
  return {
    contract: SKY_CONTRACT,
    time: instant.toISOString(),
    observer: { lat, lon, elevation, tzHours },
    window: { start: window.start.toISOString(), end: window.end.toISOString() },
    conventions: CONVENTIONS,
    daylight: { ...twilightClass(sun.altitudeAirless), sunAltitudeAirless: sun.altitudeAirless },
    sun,
    moon: { ...moon, phase },
    planets,
  };
}

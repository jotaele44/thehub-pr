// The "Rule out the ordinary" form, as data (P6-C): what a person types, turned into the inputs the engines take, or into
// the first thing that is wrong with it and the field it is in. Nothing here is stored or sent, and nothing is guessed: a
// field that decides the answer (the time, the place, the direction, the azimuth reference, how close counts) is
// required, and one that can be left out (the time uncertainty, the height) is recorded as undeclared by the engine.
import { parseObservation } from './observation.js';

export const EMPTY_OBSERVATION_DRAFT = Object.freeze({
  time: '', timeUncertainty: '', lat: '', lon: '', height: '',
  azimuth: '', elevation: '', azimuthReference: '', declination: '',
  extent: 'TOLERANCE', tolerance: '', hfov: '', vfov: '', roll: '0',
  moving: false, endAzimuth: '', endElevation: '', endTime: '',
});

export const EMPTY_DECLARATION_DRAFT = Object.freeze({
  source: '', altitudeReference: '', altitudeUnits: '', geoidSeparation: '', altitudeUncertainty: '', horizontalUncertainty: '', clockOffset: '', gapSeconds: '',
});

export const DEFAULT_TERRAIN_DRAFT = Object.freeze({ enabled: false, aboveGround: '2', refractionK: '0.13', radiusKm: '40' });

class FieldError extends Error {
  constructor(field, message) {
    super(message);
    this.field = field;
  }
}

const blank = (value) => value === undefined || value === null || String(value).trim() === '';

function number(draft, field, label, { required = false } = {}) {
  const raw = draft[field];
  if (blank(raw)) {
    if (required) throw new FieldError(field, `${label} is required.`);
    return undefined;
  }
  const value = Number(String(raw).trim());
  if (!Number.isFinite(value)) throw new FieldError(field, `${label} is not a number: ${String(raw).trim()}`);
  return value;
}

// The observation the engines take, from the form's strings. `{ ok: true, observation }` or `{ ok: false, field, message }`.
export function observationFromDraft(draft) {
  try {
    if (blank(draft.time)) throw new FieldError('time', 'The time (UTC) is required, for example 2026-11-04T12:02:04Z. A time with no zone is not read, because it would be read in your time zone.');
    const lat = number(draft, 'lat', 'Latitude', { required: true });
    const lon = number(draft, 'lon', 'Longitude', { required: true });
    const height = number(draft, 'height', 'Observer height');
    const azimuth = number(draft, 'azimuth', 'Azimuth', { required: true });
    const elevation = number(draft, 'elevation', 'Elevation', { required: true });
    if (draft.azimuthReference !== 'TRUE' && draft.azimuthReference !== 'MAGNETIC') throw new FieldError('azimuthReference', 'Say whether the azimuth is from true north or from magnetic north. It is not assumed.');
    const direction = { azimuth, elevation, azimuthReference: draft.azimuthReference };
    if (draft.azimuthReference === 'MAGNETIC') {
      direction.magneticDeclinationDegrees = number(draft, 'declination', 'Magnetic declination', { required: true });
    }
    if (draft.extent === 'FRUSTUM') {
      direction.frustum = {
        horizontalFovDegrees: number(draft, 'hfov', 'Horizontal field of view', { required: true }),
        verticalFovDegrees: number(draft, 'vfov', 'Vertical field of view', { required: true }),
        rollDegrees: number(draft, 'roll', 'Roll') ?? 0,
      };
    } else {
      direction.toleranceDegrees = number(draft, 'tolerance', 'Tolerance', { required: true });
    }
    const input = { time: draft.time.trim(), observer: { lat, lon }, direction };
    if (height !== undefined) input.observer.height = height;
    const uncertainty = number(draft, 'timeUncertainty', 'Time uncertainty');
    if (uncertainty !== undefined) input.timeUncertaintySeconds = uncertainty;
    if (draft.moving) {
      if (blank(draft.endTime)) throw new FieldError('endTime', 'A moving sight line needs the time it reached the end direction.');
      input.motion = {
        endAzimuth: number(draft, 'endAzimuth', 'End azimuth', { required: true }),
        endElevation: number(draft, 'endElevation', 'End elevation', { required: true }),
        endTime: draft.endTime.trim(),
      };
    }
    return { ok: true, observation: parseObservation(input) };
  } catch (error) {
    if (error instanceof FieldError) return { ok: false, field: error.field, message: error.message };
    if (error instanceof RangeError) return { ok: false, field: fieldOf(error.message), message: error.message };
    throw error;
  }
}

// The engines' own refusals name what they refused; this points the form at the field that holds it.
function fieldOf(message) {
  const m = message.toLowerCase();
  if (m.includes('time uncertainty')) return 'timeUncertainty';
  if (m.includes('end time')) return 'endTime';
  if (m.includes('end') && m.includes('elevation')) return 'endElevation';
  if (m.includes('end') && m.includes('azimuth')) return 'endAzimuth';
  if (m.includes('declination')) return 'declination';
  if (m.includes('azimuth reference')) return 'azimuthReference';
  if (m.includes('latitude')) return 'lat';
  if (m.includes('longitude')) return 'lon';
  if (m.includes('height')) return 'height';
  if (m.includes('tolerance')) return 'tolerance';
  if (m.includes('horizontal field')) return 'hfov';
  if (m.includes('vertical field')) return 'vfov';
  if (m.includes('roll')) return 'roll';
  if (m.includes('field of view') || m.includes('frustum')) return 'hfov';
  if (m.includes('elevation')) return 'elevation';
  if (m.includes('azimuth')) return 'azimuth';
  if (m.includes('time') || m.includes('instant') || m.includes('utc')) return 'time';
  if (m.includes('window')) return 'timeUncertainty';
  return null;
}

// The track declaration the parsers take, from the form's strings: the source, the altitude reference and unit are required.
export function declarationFromDraft(draft) {
  try {
    const out = { source: draft.source, altitudeReference: draft.altitudeReference || undefined, altitudeUnits: draft.altitudeUnits || undefined };
    const optional = [['geoidSeparation', 'geoidSeparationMetres', 'Geoid separation'], ['altitudeUncertainty', 'altitudeUncertaintyMetres', 'Altitude uncertainty'], ['horizontalUncertainty', 'horizontalUncertaintyMetres', 'Horizontal uncertainty'], ['clockOffset', 'clockOffsetSeconds', 'Clock offset'], ['gapSeconds', 'gapSeconds', 'Gap length']];
    for (const [field, key, label] of optional) {
      const value = number(draft, field, label);
      if (value !== undefined) out[key] = value;
    }
    return { ok: true, declaration: out };
  } catch (error) {
    if (error instanceof FieldError) return { ok: false, field: error.field, message: error.message };
    throw error;
  }
}

// Which declaration field a refusal from the track declaration is about, as `declaration.<field>`.
export function declarationFieldOf(message) {
  const m = message.toLowerCase();
  const table = [
    ['where the tracks came from', 'source'], ['altitude reference', 'altitudeReference'], ['altitude unit', 'altitudeUnits'], ['geoid separation', 'geoidSeparation'],
    ['altitudeuncertaintymetres', 'altitudeUncertainty'], ['pressure) altitude', 'altitudeUncertainty'], ['horizontaluncertaintymetres', 'horizontalUncertainty'],
    ['clock offset', 'clockOffset'], ['gap length', 'gapSeconds'],
  ];
  const hit = table.find(([needle]) => m.includes(needle));
  return hit ? `declaration.${hit[1]}` : 'declaration';
}

export function terrainOptionsFromDraft(draft) {
  try {
    const aboveGroundMetres = number(draft, 'aboveGround', 'Height above the ground', { required: true });
    const refractionK = number(draft, 'refractionK', 'Refraction coefficient', { required: true });
    const radiusKm = number(draft, 'radiusKm', 'Terrain range', { required: true });
    return { ok: true, options: { aboveGroundMetres, refractionK, radiusKm } };
  } catch (error) {
    if (error instanceof FieldError) return { ok: false, field: error.field, message: error.message };
    throw error;
  }
}

// The form started from the observer and instant already chosen above (the person presses a button; nothing is copied
// silently, and the page never asks the browser for a location). The height is NOT copied: the workspace's elevation is a
// height above sea level and the engines take a height above the WGS84 ellipsoid (about 43 m lower in Puerto Rico), so
// carrying one into the other would be a quiet datum mistake. The person declares it, or leaves it for the stated default.
export function draftFromWorkspace(draft, { observer, instant }) {
  return { ...draft, time: instant.toISOString().replace('.000Z', 'Z'), lat: String(observer.lat), lon: String(observer.lon) };
}

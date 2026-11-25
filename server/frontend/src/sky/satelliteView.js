// What the Sky workspace shows about the satellites at one instant for one observer, built from the element sets
// loadSatelliteElements returned. Pure: no fetching, no clock. A satellite whose elements did not load stays in the
// list as FAILED with the reason; one that loaded but cannot be placed (elements too far from the instant, or an
// SGP4 error) says so and has no position.
import { elementAge, findPasses, lookAt, skyTrack } from './satellites.js';

export const PASS_HOURS = 24;
export const PASS_MIN_ELEVATION = 10;
export const TRACK_MARGIN_SECONDS = 30;

export function satelliteSnapshot(loaded, observer, instant) {
  const items = loaded.items.map((item) => {
    const basics = { id: item.id, noradId: item.noradId, label: item.label, url: item.url };
    if (item.state !== 'LOADED') return Object.freeze({ ...basics, state: 'FAILED', error: item.error, element: null, age: null, look: null, position: 'NO_ELEMENTS' });
    const age = elementAge(item.element, instant);
    const look = lookAt(item.element, instant, observer);
    return Object.freeze({
      ...basics, state: 'LOADED', error: null, element: item.element, name: item.name, age,
      look: look.ok ? look : null, lookError: look.ok ? null : look.message,
      position: look.ok ? (look.elevation >= 0 ? 'ABOVE_HORIZON' : 'BELOW_HORIZON') : 'NO_ANSWER',
    });
  });
  return Object.freeze({ items, requested: loaded.requested, loaded: items.filter((item) => item.state === 'LOADED').length, retrievedAt: loaded.retrievedAt });
}

// The satellites that have a position, in the form the chart draws.
export function chartSatellites(snapshot) {
  return snapshot.items.filter((item) => item.look).map((item) => ({
    body: item.id, label: item.id, kind: 'satellite', azimuth: item.look.azimuth, altitude: item.look.elevation,
    aboveHorizon: item.look.elevation >= 0, sunlit: item.look.sunlit,
  }));
}

// Passes from the instant onward for one loaded satellite, or the reason there are none to show.
export function upcomingPasses(item, observer, instant, { hours = PASS_HOURS, minElevation = PASS_MIN_ELEVATION } = {}) {
  if (item.state !== 'LOADED') return { ok: false, reason: 'NO_ELEMENTS', message: item.error ?? 'No orbital elements.' };
  try {
    return findPasses(item.element, observer, instant, { hours, minElevation });
  } catch (error) {
    if (error instanceof RangeError) return { ok: false, reason: 'INVALID_INPUT', message: error.message };
    throw error;
  }
}

// The az/el track of one pass, from a little before its rise to a little after its set.
export function passTrack(item, observer, pass) {
  const margin = TRACK_MARGIN_SECONDS * 1000;
  return skyTrack(item.element, observer, new Date(pass.aos.getTime() - margin), new Date(pass.los.getTime() + margin), 10);
}

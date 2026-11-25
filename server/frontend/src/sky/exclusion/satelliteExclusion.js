// Satellite exclusion (FDX-035): which of the satellites the Sky workspace tracks were in a reported sight line (or
// camera field of view) at some moment of the observation window, and above the horizon, with the pass geometry that
// follows from it: where it was, whether the Sun lit it, whether the observer's sky was dark. The denominator is part of
// the answer: three objects are checked (the ISS, Hubble and the Chinese space station), not all satellites, and an
// object whose elements did not load, or whose elements are too far from the observation, is listed as NOT_CHECKED with
// the reason, never as ruled out. A past observation cannot be checked: the elements are current ones, and historical
// element sets need credentials this workspace never uses.
import { bodyPosition } from '../astronomy.js';
import {
  ELEMENT_POLICY, OBSERVER_DARK_SUN_ALTITUDE, VISIBLE_LABEL, directionAt, elementAge, lookAt,
} from '../satellites.js';
import { angularSeparation } from './geometry.js';
import { terrainStatus } from './horizon.js';
import { matchDirection, windowSamples } from './observation.js';
import { apparentElevation } from './refraction.js';

export const SATELLITE_EXCLUSION_CONTRACT = 'sky-satellite-exclusion-v1';
const COARSE_STEP_SECONDS = 2;
const FINE_STEP_SECONDS = 0.1;
const FINE_HALF_WINDOW_SECONDS = 4;

function notChecked(item, reason, message) {
  return Object.freeze({ id: item.id, name: item.label, noradId: item.noradId, status: 'NOT_CHECKED', reason, message });
}

function terrainState(elevation, azimuth, horizon) {
  const terrain = terrainStatus(horizon, azimuth, elevation);
  return { above: elevation >= 0 && terrain !== 'OBSTRUCTED', terrain };
}

function scanOne(observation, element, horizon) {
  const { observer } = observation;
  const place = { lat: observer.lat, lon: observer.lon, elevation: observer.height };
  const at = (ms) => {
    const d = directionAt(element, new Date(ms), place);
    if (!d.ok) return { ok: false, reason: d };
    return { ok: true, azimuth: d.azimuth, elevation: apparentElevation(d.elevation), rangeKm: d.rangeKm };
  };
  const evaluate = (ms) => {
    const d = at(ms);
    if (!d.ok) return d;
    const m = matchDirection(observation, d.azimuth, d.elevation, ms);
    return { ...d, ms, separation: m.separationDegrees, inside: m.inside, visible: terrainState(d.elevation, d.azimuth, horizon) };
  };

  // Coarse pass over the whole window, then a fine pass around every coarse local minimum that could matter.
  const coarse = windowSamples(observation, COARSE_STEP_SECONDS).map(evaluate);
  const failed = coarse.find((c) => !c.ok);
  if (failed) return { error: failed.reason };
  let maxRate = 0;
  for (let i = 1; i < coarse.length; i += 1) {
    const dt = (coarse[i].ms - coarse[i - 1].ms) / 1000;
    if (dt > 0) maxRate = Math.max(maxRate, angularSeparation(coarse[i].azimuth, coarse[i].elevation, coarse[i - 1].azimuth, coarse[i - 1].elevation) / dt);
  }
  const reach = (observation.direction.toleranceDegrees ?? Math.max(observation.direction.frustum.horizontalFovDegrees, observation.direction.frustum.verticalFovDegrees)) + maxRate * COARSE_STEP_SECONDS + 1;
  const records = [...coarse];
  for (let i = 0; i < coarse.length; i += 1) {
    const isMinimum = (i === 0 || coarse[i].separation <= coarse[i - 1].separation) && (i === coarse.length - 1 || coarse[i].separation <= coarse[i + 1].separation);
    if (!isMinimum || coarse[i].separation > reach) continue;
    const lo = Math.max(observation.window.start.getTime(), coarse[i].ms - FINE_HALF_WINDOW_SECONDS * 1000);
    const hi = Math.min(observation.window.end.getTime(), coarse[i].ms + FINE_HALF_WINDOW_SECONDS * 1000);
    for (let ms = lo; ms <= hi; ms += FINE_STEP_SECONDS * 1000) {
      const e = evaluate(ms);
      if (e.ok) records.push(e);
    }
  }
  records.sort((a, b) => a.ms - b.ms);
  let best = records[0];
  let first = null;
  let last = null;
  let insideAny = false;
  for (const r of records) {
    if (r.separation < best.separation) best = r;
    if (r.inside) insideAny = true;
    if (r.inside && r.visible.above) { first = first ?? r.ms; last = r.ms; }
  }
  return { best, first, last, insideAny, maxRate, place };
}

export function checkSatellites(observation, loaded, { horizon = null } = {}) {
  const { observer, window } = observation;
  const items = [];
  for (const item of loaded.items) {
    if (item.state !== 'LOADED') {
      items.push(notChecked(item, 'ELEMENTS_NOT_LOADED', `The orbital elements did not load (${item.error}), so this object was not checked.`));
      continue;
    }
    const worst = [elementAge(item.element, window.start), elementAge(item.element, window.end)].sort((a, b) => b.days - a.days)[0];
    if (worst.state === 'REFUSED') {
      items.push(notChecked(item, 'ELEMENTS_TOO_OLD', `The elements' epoch is ${worst.days.toFixed(1)} days from the observation; the limit is ${ELEMENT_POLICY.refuseDays} days. Elements are current ones: a past observation needs element sets from its own time (Space-Track, which needs credentials and is never used here), so this object was not checked.`));
      continue;
    }
    const scan = scanOne(observation, item.element, horizon);
    if (scan.error) {
      items.push(notChecked(item, scan.error.reason ?? 'PROPAGATION_FAILED', `SGP4 gave no position inside the window: ${scan.error.message ?? 'unknown error'}.`));
      continue;
    }
    const { best } = scan;
    const lit = lookAt(item.element, new Date(best.ms), { lat: observer.lat, lon: observer.lon, elevation: observer.height });
    const sunAltitude = bodyPosition('Sun', new Date(best.ms), { lat: observer.lat, lon: observer.lon, elevation: observer.height }, { refraction: null }).altitude;
    const observerDark = sunAltitude <= OBSERVER_DARK_SUN_ALTITUDE;
    const candidate = scan.first !== null;
    items.push(Object.freeze({
      id: item.id, name: item.label, noradId: item.noradId, status: 'CHECKED',
      elements: Object.freeze({ epoch: item.element.epoch.toISOString(), ageDaysAtObservation: worst.days, confidence: worst.confidence }),
      minSeparationDegrees: best.separation, minSeparationAt: new Date(best.ms).toISOString(), azimuthAtClosest: best.azimuth, elevationAtClosest: best.elevation, rangeKmAtClosest: best.rangeKm,
      aboveHorizonAtClosest: best.visible.above, terrainAtClosest: best.visible.terrain,
      insideSomeTime: scan.insideAny, candidate,
      firstInside: scan.first === null ? null : new Date(scan.first).toISOString(), lastInside: scan.last === null ? null : new Date(scan.last).toISOString(),
      sunlitAtClosest: lit.ok ? lit.sunlit : null, observerSunAltitudeAtClosest: sunAltitude, observerDark,
      visibleCandidate: Boolean(candidate && lit.ok && lit.sunlit && observerDark),
      visibleLabel: candidate && lit.ok && lit.sunlit && observerDark ? VISIBLE_LABEL : 'Not a visible-pass candidate (not lit, or the sky is not dark, or not in the sight line)',
      resolutionDegrees: (scan.maxRate * FINE_STEP_SECONDS) / 2,
    }));
  }
  const checked = items.filter((i) => i.status === 'CHECKED');
  const candidates = checked.filter((i) => i.candidate).sort((a, b) => a.minSeparationDegrees - b.minSeparationDegrees);
  return Object.freeze({
    contract: SATELLITE_EXCLUSION_CONTRACT,
    denominator: Object.freeze({ checked: checked.length, requested: items.length, names: Object.freeze(items.map((i) => i.id)), notAllSatellites: true }),
    items: Object.freeze(items),
    candidates: Object.freeze(candidates),
    limits: Object.freeze([
      `${items.length} objects are asked about (the ISS, Hubble and the Chinese space station's Tianhe module); ${checked.length} could be checked. This is not all satellites: a miss here does not rule satellites out.`,
      'Elements are current CelesTrak element sets. A time more than 14 days from an element epoch is refused, and a past observation cannot be checked without historical element sets.',
      'A satellite in the sight line is a geometric coincidence, not an identification. Brightness is not estimated: lit and dark-sky flags are geometry only (a cylindrical Earth shadow, observer Sun at or below -6 degrees).',
      'Directions are lifted by standard refraction like a person sees them; SGP4 positions are tens of metres at the epoch and kilometres days away.',
    ]),
  });
}

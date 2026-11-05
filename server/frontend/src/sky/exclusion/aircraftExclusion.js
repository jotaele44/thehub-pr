// Aircraft exclusion (FDX-036) and trajectory coverage (FDX-037): which of the aircraft in the tracks the user supplied
// were in a reported sight line (or camera field of view) at some moment of the observation window, how well the
// window is covered by reports, and what that rests on. Nothing is fetched and nothing is stored.
//
// The rules that keep this honest:
//  - A track is checked only inside the span of its own reports. Before the first and after the last report nothing is
//    extrapolated: that time is OUTSIDE_TRACK, which is missing data, not "no aircraft".
//  - Between two reports no more than the gap length apart the position is filled in by a straight line and labelled
//    INTERPOLATED; a longer interval, or one that would need an implausible speed, is a GAP and is never filled in.
//    The reports themselves are OBSERVED. A candidate says which of the two it rests on.
//  - The aircraft is geometric, not refracted (its ray crosses only part of the atmosphere; standard terrestrial
//    refraction is about 0.06 degrees at 100 km, below any sight line's tolerance). It counts only when the line of sight
//    clears the Earth's curvature and, when a terrain horizon is given, the terrain.
//  - Declared position uncertainty widens nothing silently: it is reported beside the result, and an aircraft that is
//    outside the sight line but could be inside it given that uncertainty is listed separately as "possible".
//  - A track in the sight line is a geometric coincidence, not an identification and not evidence of intent. A callsign
//    is a label the file carries.
import { ecefToEnu, enuToAzEl } from './geometry.js';
import { TRACK_POLICY } from './aircraftTracks.js';
import { EARTH_RADIUS_M, terrainStatus } from './horizon.js';
import { matchDirection, sightlineAt } from './observation.js';

export const AIRCRAFT_EXCLUSION_CONTRACT = 'sky-aircraft-exclusion-v1';
const STEP_DEGREES = 0.25;
const MAX_SAMPLES_PER_SEGMENT = 400;
const REFINE_ITERATIONS = 60;
const BISECT_ITERATIONS = 40;
const DEG = 180 / Math.PI;
const BEHIND_CAMERA_MARGIN = 180;

// How far below the horizontal the Earth's curvature lets a straight line of sight go from a height above the surface,
// with the refraction coefficient k when a horizon (which states its own) is in use: acos(R_eff / (R_eff + h)).
export function earthDipDegrees(heightMetres, refractionK = 0) {
  const h = Math.max(0, heightMetres);
  const effective = EARTH_RADIUS_M / (1 - refractionK);
  return Math.acos(effective / (effective + h)) * DEG;
}

// Is the aircraft hidden by the terrain between it and the observer? Only terrain nearer than the aircraft counts, so an
// aircraft in front of a ridge is not hidden by it. Where the terrain is not known it is UNKNOWN, never "hidden".
function terrainState(elevation, azimuth, horizon, dip, groundDistanceMetres) {
  const terrain = terrainStatus(horizon, azimuth, elevation, { distanceMetres: groundDistanceMetres });
  return { above: elevation >= -dip && terrain !== 'OBSTRUCTED', terrain };
}

function notChecked(track, reason, message) {
  return Object.freeze({ id: track.id, label: track.label, status: 'NOT_CHECKED', reason, message, quality: track.quality });
}

// A stretch between two reports is filled in only when it is short enough and the speed it implies is plausible.
function segmentUsable(a, b, policy) {
  const seconds = (b.ms - a.ms) / 1000;
  const speed = Math.hypot(b.ecef.x - a.ecef.x, b.ecef.y - a.ecef.y, b.ecef.z - a.ecef.z) / seconds;
  return seconds <= policy.gapSeconds && speed <= policy.maxPlausibleSpeedMetresPerSecond;
}

function interpolate(a, b, ms) {
  const f = (ms - a.ms) / (b.ms - a.ms);
  return { x: a.ecef.x + f * (b.ecef.x - a.ecef.x), y: a.ecef.y + f * (b.ecef.y - a.ecef.y), z: a.ecef.z + f * (b.ecef.z - a.ecef.z) };
}

// Minimise f over [lo, hi] by ternary search; f is smooth and unimodal in the bracket a coarse local minimum gives.
function refine(f, lo, hi) {
  let a = lo;
  let b = hi;
  for (let i = 0; i < REFINE_ITERATIONS && b - a > 0.5; i += 1) {
    const m1 = a + (b - a) / 3;
    const m2 = b - (b - a) / 3;
    if (f(m1) <= f(m2)) b = m2; else a = m1;
  }
  return (a + b) / 2;
}

function bisect(f, outside, inside) {
  let o = outside;
  let i = inside;
  for (let k = 0; k < BISECT_ITERATIONS && Math.abs(i - o) > 1; k += 1) {
    const mid = (o + i) / 2;
    if (f(mid)) i = mid; else o = mid;
  }
  return i;
}

// Where a track puts the aircraft in the observer's sky at one instant: a report (OBSERVED), a straight-line position
// between two reports (INTERPOLATED), a stretch that is not filled in (GAP) or a time outside the track (OUTSIDE_TRACK,
// never extrapolated). Geometric direction, no refraction.
export function aircraftLookAt(observer, track, ms, policy = TRACK_POLICY) {
  const obs = track.observations;
  if (obs.length === 0 || ms < obs[0].ms || ms > obs[obs.length - 1].ms) return { state: 'OUTSIDE_TRACK' };
  let lo = 0;
  let hi = obs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (obs[mid].ms <= ms) lo = mid; else hi = mid;
  }
  const a = obs[lo];
  const b = obs[Math.min(lo + 1, obs.length - 1)];
  let state = 'OBSERVED';
  let ecef = a.ecef;
  if (a.ms !== ms) {
    if (b.ms === ms) ecef = b.ecef;
    else if (segmentUsable(a, b, policy)) { state = 'INTERPOLATED'; ecef = interpolate(a, b, ms); } else return { state: 'GAP' };
  }
  const look = enuToAzEl(ecefToEnu(ecef, observer));
  return { state, azimuth: look.azimuth, elevation: look.elevation, rangeM: look.range };
}

function checkTrack(observation, track, horizon, declaration) {
  const { observer, window } = observation;
  const ws = window.start.getTime();
  const we = window.end.getTime();
  const { observations: obs, quality } = track;
  if (!quality.eligible) {
    return notChecked(track, 'NOT_ELIGIBLE', `Only ${quality.validObservations} valid report${quality.validObservations === 1 ? '' : 's'}; at least ${declaration.policy.minimumValidObservations} are needed for a trajectory (the Skywatcher rule), so this track was not compared.`);
  }
  const first = obs[0].ms;
  const last = obs[obs.length - 1].ms;
  if (last < ws || first > we) {
    return notChecked(track, 'NO_DATA_IN_WINDOW', `The track has reports from ${quality.spanStart} to ${quality.spanEnd} and none in the observation window. No data is not the same as no aircraft: this track says nothing about the window.`);
  }
  const dip = earthDipDegrees(observer.height, horizon?.parameters?.refractionK ?? 0);

  const evaluate = (ecef, ms, state) => {
    const enu = ecefToEnu(ecef, observer);
    const look = enuToAzEl(enu);
    const m = matchDirection(observation, look.azimuth, look.elevation, ms);
    const visible = terrainState(look.elevation, look.azimuth, horizon, dip, look.range * Math.cos((look.elevation * Math.PI) / 180));
    const margin = m.marginDegrees === null || m.marginDegrees === undefined ? BEHIND_CAMERA_MARGIN : m.marginDegrees;
    return { ms, state, azimuth: look.azimuth, elevation: look.elevation, rangeM: look.range, separation: m.separationDegrees, inside: m.inside, margin, visible, hit: m.inside && visible.above };
  };

  const records = [];
  let interpolatedSeconds = 0;
  let gapSecondsInWindow = 0;
  let reportsInWindow = 0;
  for (let i = 0; i < obs.length; i += 1) {
    const o = obs[i];
    if (o.ms >= ws && o.ms <= we) { reportsInWindow += 1; records.push(evaluate(o.ecef, o.ms, 'OBSERVED')); }
  }
  for (let i = 0; i + 1 < obs.length; i += 1) {
    const a = obs[i];
    const b = obs[i + 1];
    const lo = Math.max(a.ms, ws);
    const hi = Math.min(b.ms, we);
    if (hi < lo) continue;
    if (!segmentUsable(a, b, declaration.policy)) { gapSecondsInWindow += (hi - lo) / 1000; continue; }
    interpolatedSeconds += (hi - lo) / 1000;
    const at = (ms) => evaluate(interpolate(a, b, ms), ms, 'INTERPOLATED');
    const marginAt = (ms) => at(ms).margin;
    const start = at(lo);
    const end = at(hi);
    const sweep = hi === lo ? 0 : sweepBetween(start, end) + sightlineSweep(observation, lo, hi);
    const n = Math.max(1, Math.min(MAX_SAMPLES_PER_SEGMENT, Math.ceil(sweep / STEP_DEGREES)));
    const local = [start];
    for (let k = 1; k < n; k += 1) local.push(at(lo + ((hi - lo) * k) / n));
    if (hi > lo) local.push(end);
    // Around every coarse local minimum of the margin, the exact minimum: a pass through a narrow sight line between
    // two samples is not missed.
    const coarse = [...local];
    for (let k = 0; k < coarse.length && coarse.length > 1; k += 1) {
      const isMin = (k === 0 || coarse[k].margin <= coarse[k - 1].margin) && (k === coarse.length - 1 || coarse[k].margin <= coarse[k + 1].margin);
      if (!isMin) continue;
      const left = coarse[Math.max(0, k - 1)].ms;
      const right = coarse[Math.min(coarse.length - 1, k + 1)].ms;
      if (right > left) local.push(at(refine(marginAt, left, right)));
    }
    local.sort((p, q) => p.ms - q.ms);
    // The moments the aircraft enters and leaves the sight line, to the millisecond, between neighbouring evaluations.
    const edges = [];
    for (let k = 1; k < local.length; k += 1) {
      const p = local[k - 1];
      const q = local[k];
      if (p.hit === q.hit || q.ms - p.ms <= 1) continue;
      edges.push(at(bisect((ms) => at(ms).hit, p.hit ? q.ms : p.ms, p.hit ? p.ms : q.ms)));
    }
    records.push(...local, ...edges);
  }
  if (records.length === 0) {
    return notChecked(track, 'NO_INTERPOLABLE_DATA', `The track overlaps the window only across gaps longer than ${declaration.policy.gapSeconds} s (or needing an implausible speed), which are not filled in. This track says nothing about the window.`);
  }
  records.sort((p, q) => p.ms - q.ms);
  let best = records[0];
  let firstHit = null;
  let lastHit = null;
  let observedHits = 0;
  for (const r of records) {
    if (r.margin < best.margin) best = r;
    if (r.hit) {
      firstHit = firstHit === null ? r.ms : Math.min(firstHit, r.ms);
      lastHit = lastHit === null ? r.ms : Math.max(lastHit, r.ms);
      if (r.state === 'OBSERVED') observedHits += 1;
    }
  }
  const windowSeconds = (we - ws) / 1000;
  const coveredSeconds = Math.min(windowSeconds, interpolatedSeconds);
  const outsideSeconds = Math.max(0, windowSeconds - interpolatedSeconds - gapSecondsInWindow);
  let coverage;
  if (windowSeconds === 0) coverage = 'COVERED';
  else if (coveredSeconds >= windowSeconds - 1e-6) coverage = 'COVERED';
  else coverage = coveredSeconds > 0 || reportsInWindow > 0 ? 'PARTIAL' : 'NONE';

  const horizontal = declaration.horizontalUncertaintyMetres;
  const vertical = declaration.altitudeUncertaintyMetres;
  const uncertaintyMetres = horizontal === null && vertical === null ? null : Math.hypot(horizontal ?? 0, vertical ?? 0);
  const angularUncertaintyDegrees = uncertaintyMetres === null ? null : Math.atan2(uncertaintyMetres, best.rangeM) * DEG;
  const candidate = firstHit !== null;
  return Object.freeze({
    id: track.id, label: track.label, status: 'CHECKED', quality,
    coverage: Object.freeze({
      state: coverage, windowSeconds, interpolatedSeconds: coveredSeconds, gapSeconds: gapSecondsInWindow, outsideTrackSeconds: outsideSeconds, reportsInWindow,
    }),
    minSeparationDegrees: best.separation, marginAtClosestDegrees: best.margin === BEHIND_CAMERA_MARGIN ? null : best.margin, closestAt: new Date(best.ms).toISOString(), closestState: best.state,
    azimuthAtClosest: best.azimuth, elevationAtClosest: best.elevation, rangeKmAtClosest: best.rangeM / 1000,
    aboveHorizonAtClosest: best.visible.above, terrainAtClosest: best.visible.terrain,
    insideSomeTime: records.some((r) => r.inside), candidate,
    basis: candidate ? (observedHits > 0 ? 'OBSERVED' : 'INTERPOLATED') : null,
    firstInside: firstHit === null ? null : new Date(firstHit).toISOString(), lastInside: lastHit === null ? null : new Date(lastHit).toISOString(),
    angularUncertaintyDegrees,
    possibleWithinUncertainty: !candidate && angularUncertaintyDegrees !== null && best.margin !== BEHIND_CAMERA_MARGIN && best.margin - angularUncertaintyDegrees <= 0 && best.visible.above,
  });
}

function sweepBetween(a, b) {
  const rad = Math.PI / 180;
  const ca = Math.cos(a.elevation * rad);
  const cb = Math.cos(b.elevation * rad);
  const dot = ca * cb * Math.cos((a.azimuth - b.azimuth) * rad) + Math.sin(a.elevation * rad) * Math.sin(b.elevation * rad);
  return Math.acos(Math.max(-1, Math.min(1, dot))) * DEG;
}

function sightlineSweep(observation, lo, hi) {
  if (!observation.motion) return 0;
  const p = sightlineAt(observation, lo);
  const q = sightlineAt(observation, hi);
  return sweepBetween(p, q);
}

export function checkAircraft(observation, parsed, { horizon = null } = {}) {
  const items = parsed.tracks.map((track) => checkTrack(observation, track, horizon, parsed.declaration));
  const checked = items.filter((i) => i.status === 'CHECKED');
  const byCloseness = (a, b) => a.minSeparationDegrees - b.minSeparationDegrees;
  const candidates = checked.filter((i) => i.candidate).sort(byCloseness);
  const possible = checked.filter((i) => i.possibleWithinUncertainty).sort(byCloseness);
  const d = parsed.declaration;
  return Object.freeze({
    contract: AIRCRAFT_EXCLUSION_CONTRACT,
    denominator: Object.freeze({ tracks: items.length, checked: checked.length, notChecked: items.length - checked.length, notAllAircraft: true }),
    source: Object.freeze({ declared: d.source, altitudeReference: d.altitudeReference, altitudeUnits: d.altitudeUnits, geoidSeparationMetres: d.geoidSeparationMetres, clockOffsetSeconds: d.clockOffsetSeconds, clockOffsetDeclared: d.clockOffsetDeclared }),
    policy: d.policy,
    items: Object.freeze(items),
    candidates: Object.freeze(candidates),
    possible: Object.freeze(possible),
    conventions: Object.freeze([
      'Look angles are geometric from the observer to each position at WGS84 ellipsoidal heights; no refraction is applied to an aircraft, whose ray crosses only part of the atmosphere (about 0.06 degrees at 100 km, below a sight line\'s tolerance).',
      'A report is OBSERVED. A position between two reports no more than the gap length apart is INTERPOLATED along a straight line; nothing is extrapolated, and a longer interval is a GAP that is not filled in.',
      'A candidate is inside the sight line or field of view at an evaluated moment (a report, or a moment between two reports) with the line of sight above the Earth\'s curvature and the terrain horizon when one was given.',
    ]),
    limits: Object.freeze([
      `${items.length} track${items.length === 1 ? '' : 's'} supplied, ${checked.length} compared. This is not all air traffic: an aircraft that is not in the file (not broadcasting, not received, not supplied) is not excluded.`,
      'A track in the sight line is a geometric coincidence, not an identification and not evidence of intent. A callsign is a label the file carries, not an airframe.',
      'Between two reports a straight line is assumed: a turn inside the interval is not modelled. Report positions carry only the uncertainty the declaration states; undeclared uncertainty is not zero.',
      d.altitudeReference === 'BAROMETRIC' ? 'Altitudes are barometric: a pressure altitude is not a geometric height, and the declared uncertainty is all this check knows about the difference.' : 'Altitudes are used as declared; an altitude from a source with a different reference would move an aircraft up or down by tens of metres.',
    ]),
  });
}

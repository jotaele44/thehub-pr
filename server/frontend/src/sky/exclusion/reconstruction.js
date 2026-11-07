// The reconstruction of the sky at a reported instant and the `sky-exclusion-v1` receipt (FDX-040, TWIN-118): one record
// of what was checked against a reported sight line, what was found in it, what could not be checked, and what this
// kind of check can never rule in or out. It is a computed record of a geometric check. It is NOT_CERTIFIED, it is not a
// finding, and it does not say what was seen.
//
// The principle it is written to: rule out the ordinary before promoting an unexplained result, and remember that the
// absence of an identified ordinary explanation is not evidence of an extraordinary one. So the conclusion is one of
// three plain statements: NO ORDINARY CANDIDATE IDENTIFIED (with the sets that were checked, and the reminder), ORDINARY
// CANDIDATES LISTED (each a geometric coincidence, not an identification), or NOT ASSESSED (nothing could be checked, so
// nothing is ruled out). Words that claim an anomaly, an identification of intent or a classification of what was seen
// are not produced anywhere in it.
//
// Labels carried through: MODELLED (a body or satellite computed from an ephemeris or orbital elements) is not
// OBSERVED (an aircraft report); an INTERPOLATED aircraft position is a straight line between two reports; missing data
// is never zero; a track in the sight line is not targeting; a callsign is not an identity.
import { sha256StableJson } from '../../gis/integrity.js';
import { bodyPosition, skyState } from '../astronomy.js';
import { ELEMENT_POLICY, directionAt, elementAge } from '../satellites.js';
import { aircraftLookAt, earthDipDegrees } from './aircraftExclusion.js';
import { BODIES } from './celestialExclusion.js';
import { terrainStatus } from './horizon.js';
import { matchDirection, sightlineAt } from './observation.js';
import { apparentElevation } from './refraction.js';
import { STARS, STAR_CATALOG, starPosition } from './stars.js';

export const EXCLUSION_RECEIPT_CONTRACT = 'sky-exclusion-v1';
export const RECONSTRUCTION_CONTRACT = 'sky-reconstruction-v1';
export const HEADLINE_NONE = 'NO ORDINARY CANDIDATE IDENTIFIED';
export const PRINCIPLE = 'Absence of an identified ordinary explanation is not evidence of an extraordinary one.';
export const CERTIFICATION = Object.freeze({
  status: 'NOT_CERTIFIED',
  meaning: 'A computed record of a geometric check. It is not a finding, it is not certified by any authority, and it is not evidence of anything.',
});
export const BLIND_SPOTS = Object.freeze([
  'Aircraft that are not in the tracks supplied: not broadcasting, not received, or not provided.',
  'Satellites other than the three checked (the ISS, Hubble and the Chinese space station), rocket bodies and satellite trains.',
  'Balloons, drones, kites, lanterns and anything else in the air that is in no data set here.',
  'Meteors, fireballs and re-entries, aurora, lightning and other atmospheric light.',
  'Optical effects: lens flare, reflections off glass, sensor artefacts and the movement of the camera.',
  'Birds, insects and airborne debris.',
  'Planets beyond Saturn, comets, asteroids, and stars fainter than the catalogue limit.',
  'Error in the reported time, place, direction and tolerance, and misperception or misreporting.',
]);
const MAX_OBJECTS = 800;

// ---- the sky at the reported instant ----------------------------------------------------------------------------------

function placed(observation, horizon, category, name, azimuth, elevation, extra) {
  const ms = observation.time.getTime();
  const m = matchDirection(observation, azimuth, elevation, ms);
  const dip = category === 'aircraft' ? earthDipDegrees(observation.observer.height, horizon?.parameters?.refractionK ?? 0) : 0;
  const terrain = terrainStatus(horizon, azimuth, elevation, { distanceMetres: extra.groundDistanceMetres ?? Infinity });
  return {
    category, name, azimuth, elevation, state: extra.state, separationFromSightlineDegrees: m.separationDegrees, insideSightline: m.inside,
    aboveHorizon: elevation >= -dip && terrain !== 'OBSTRUCTED', terrain,
    ...(extra.detail ?? {}),
  };
}

// Where everything the checks know about stands in the observer's sky at the reported instant, against the sight line:
// the Sun, Moon, planets and bright stars (MODELLED), the satellites whose elements were loaded (MODELLED, SGP4), and the
// aircraft in the supplied tracks (OBSERVED at a report, INTERPOLATED between two; a track with no position then is listed
// as unavailable with the reason, never placed). This is the picture the receipt's candidates are read against.
export function reconstructSky(observation, {
  satellites = null, aircraft = null, horizon = null, starLimitMagnitude = 2.5,
} = {}) {
  const { observer } = observation;
  const place = { lat: observer.lat, lon: observer.lon, elevation: observer.height };
  const instant = observation.time;
  const state = skyState({ time: instant, lat: observer.lat, lon: observer.lon, elevation: observer.height, tzHours: 0 });
  const magnitude = { Sun: -26.74, Moon: state.moon.magnitude ?? null };
  for (const p of state.planets) magnitude[p.body] = p.magnitude ?? null;
  const objects = [];
  const unavailable = [];
  for (const body of BODIES) {
    const p = bodyPosition(body, instant, place);
    objects.push(placed(observation, horizon, 'celestial', body, p.azimuth, p.altitude, { state: 'MODELLED', detail: { kind: body === 'Sun' ? 'sun' : (body === 'Moon' ? 'moon' : 'planet'), magnitude: magnitude[body] } }));
  }
  for (const star of STARS) {
    if (star.magnitude > starLimitMagnitude) continue;
    const p = starPosition(star, instant, place);
    objects.push(placed(observation, horizon, 'celestial', star.label, p.azimuth, p.altitude, { state: 'MODELLED', detail: { kind: 'star', hip: star.hip, magnitude: star.magnitude } }));
  }
  if (satellites) {
    for (const item of satellites.items) {
      if (item.state !== 'LOADED') { unavailable.push({ category: 'satellite', name: item.label, id: item.id, reason: 'ELEMENTS_NOT_LOADED' }); continue; }
      if (elementAge(item.element, instant).state === 'REFUSED') { unavailable.push({ category: 'satellite', name: item.label, id: item.id, reason: 'ELEMENTS_TOO_OLD' }); continue; }
      const d = directionAt(item.element, instant, place);
      if (!d.ok) { unavailable.push({ category: 'satellite', name: item.label, id: item.id, reason: d.reason ?? 'PROPAGATION_FAILED' }); continue; }
      objects.push(placed(observation, horizon, 'satellite', item.label, d.azimuth, apparentElevation(d.elevation), { state: 'MODELLED', detail: { id: item.id, noradId: item.noradId, rangeKm: d.rangeKm } }));
    }
  }
  if (aircraft) {
    for (const track of aircraft.tracks) {
      if (!track.quality.eligible) { unavailable.push({ category: 'aircraft', name: track.label ?? track.id, id: track.id, reason: 'NOT_ELIGIBLE' }); continue; }
      const look = aircraftLookAt(observer, track, instant.getTime(), aircraft.declaration.policy);
      if (look.state !== 'OBSERVED' && look.state !== 'INTERPOLATED') { unavailable.push({ category: 'aircraft', name: track.label ?? track.id, id: track.id, reason: look.state }); continue; }
      objects.push(placed(observation, horizon, 'aircraft', track.label ?? track.id, look.azimuth, look.elevation, {
        state: look.state, groundDistanceMetres: look.rangeM * Math.cos((look.elevation * Math.PI) / 180), detail: { id: track.id, rangeKm: look.rangeM / 1000 },
      }));
    }
  }
  objects.sort((a, b) => a.separationFromSightlineDegrees - b.separationFromSightlineDegrees);
  const sight = sightlineAt(observation, instant.getTime());
  return Object.freeze({
    contract: RECONSTRUCTION_CONTRACT, time: instant.toISOString(), sightline: Object.freeze({ azimuth: sight.azimuth, elevation: sight.elevation }),
    objects: Object.freeze(objects.slice(0, MAX_OBJECTS).map((o) => Object.freeze(o))), objectsOmitted: Math.max(0, objects.length - MAX_OBJECTS),
    unavailable: Object.freeze(unavailable.map((u) => Object.freeze(u))),
    conventions: Object.freeze([
      'Positions are at the reported instant only. The Sun, Moon, planets, stars and satellites are MODELLED from an ephemeris or orbital elements and carry standard refraction; an aircraft is OBSERVED at a report or INTERPOLATED on a straight line between two, geometric, with no refraction.',
      `Stars shown are brighter than V ${starLimitMagnitude}; the checks use the catalogue to V ${STAR_CATALOG.limit.magnitude}.`,
      'A track that has no position at the instant (a gap, outside its reports, too few reports) is listed as unavailable with the reason; it is not placed anywhere.',
    ]),
  });
}

// ---- the receipt ------------------------------------------------------------------------------------------------------

const ISO = (d) => (d instanceof Date ? d.toISOString() : d);

function describeObservation(observation) {
  const d = observation.direction;
  return {
    contract: observation.contract, time: ISO(observation.time), timeUncertaintySeconds: observation.timeUncertaintySeconds, timeUncertaintyDeclared: observation.timeUncertaintyDeclared,
    window: { start: ISO(observation.window.start), end: ISO(observation.window.end) },
    observer: { lat: observation.observer.lat, lon: observation.observer.lon, heightEllipsoidMetres: observation.observer.height },
    direction: {
      azimuthTrue: d.azimuth, azimuthAsGiven: d.azimuthAsGiven, azimuthReference: d.azimuthReference, magneticDeclinationDegrees: d.magneticDeclinationDegrees,
      elevation: d.elevation, toleranceDegrees: d.toleranceDegrees, frustum: d.frustum,
    },
    motion: observation.motion ? { endAzimuth: observation.motion.endAzimuth, endElevation: observation.motion.endElevation, endTime: ISO(observation.motion.endTime), durationSeconds: observation.motion.durationSeconds } : null,
    notes: [...observation.notes],
  };
}

function celestialPart(celestial, notRun) {
  if (!celestial) return { ran: false, reason: notRun.celestial ?? 'Not run in this session.' };
  return {
    ran: true, contract: celestial.contract, sampling: celestial.sampling, daylight: celestial.daylight, checked: celestial.checked,
    nearest: celestial.nearest.map((e) => ({ kind: e.kind, name: e.name, minSeparationDegrees: e.minSeparationDegrees, closestAt: e.minSeparationAt })),
    conventions: celestial.conventions, limits: celestial.limits,
  };
}

function satellitePart(satellites, notRun) {
  if (!satellites) return { ran: false, reason: notRun.satellites ?? 'Not run in this session.' };
  return {
    ran: true, contract: satellites.contract, denominator: satellites.denominator,
    items: satellites.items.map((i) => (i.status === 'CHECKED'
      ? { id: i.id, noradId: i.noradId, status: i.status, elements: i.elements, minSeparationDegrees: i.minSeparationDegrees, closestAt: i.minSeparationAt, terrainAtClosest: i.terrainAtClosest, candidate: i.candidate }
      : { id: i.id, noradId: i.noradId, status: i.status, reason: i.reason, message: i.message })),
    limits: satellites.limits,
  };
}

function aircraftPart(aircraft, notRun) {
  if (!aircraft) return { ran: false, reason: notRun.aircraft ?? 'Not run in this session.' };
  return {
    ran: true, contract: aircraft.contract, denominator: aircraft.denominator, source: aircraft.source, policy: aircraft.policy,
    items: aircraft.items.map((i) => (i.status === 'CHECKED'
      ? { id: i.id, label: i.label, status: i.status, quality: { track_quality: i.quality.track_quality, gap_count: i.quality.gap_count, validObservations: i.quality.validObservations, spanStart: i.quality.spanStart, spanEnd: i.quality.spanEnd }, coverage: i.coverage, minSeparationDegrees: i.minSeparationDegrees, closestAt: i.closestAt, terrainAtClosest: i.terrainAtClosest, candidate: i.candidate, basis: i.basis, angularUncertaintyDegrees: i.angularUncertaintyDegrees }
      : { id: i.id, label: i.label, status: i.status, reason: i.reason, message: i.message })),
    conventions: aircraft.conventions, limits: aircraft.limits,
  };
}

function horizonPart(horizon, terrain) {
  if (!horizon) return null;
  return {
    contract: horizon.contract, observer: horizon.observer, terrain: { ...horizon.terrain, tilesRead: terrain?.tilesRead ?? horizon.terrain.tilesRead }, parameters: horizon.parameters, summary: horizon.summary,
    rays: horizon.rays.map((r) => [r.azimuth, r.elevation === null ? null : Math.round(r.elevation * 1000) / 1000, r.complete]), limits: horizon.limits,
  };
}

function collectCandidates(celestial, satellites, aircraft) {
  const out = [];
  for (const c of celestial?.candidates ?? []) {
    out.push({
      category: 'celestial', kind: c.kind, name: c.name, basis: 'MODELLED', minSeparationDegrees: c.minSeparationDegrees, closestAt: c.minSeparationAt,
      firstInside: c.firstInside, lastInside: c.lastInside, terrain: c.terrainAtClosest, magnitude: c.magnitude,
      note: 'A geometric coincidence with the reported sight line, not an identification. Visibility against the sky is not judged.',
    });
  }
  for (const c of satellites?.candidates ?? []) {
    out.push({
      category: 'satellite', kind: 'satellite', name: c.name, id: c.id, noradId: c.noradId, basis: 'MODELLED', minSeparationDegrees: c.minSeparationDegrees, closestAt: c.minSeparationAt,
      firstInside: c.firstInside, lastInside: c.lastInside, terrain: c.terrainAtClosest, sunlitAtClosest: c.sunlitAtClosest, observerDark: c.observerDark, visibleCandidate: c.visibleCandidate,
      elementsConfidence: c.elements.confidence, rangeKm: c.rangeKmAtClosest,
      note: 'A geometric coincidence with the reported sight line, not an identification. Lit and dark-sky flags are geometry only; brightness is not estimated.',
    });
  }
  for (const c of aircraft?.candidates ?? []) {
    out.push({
      category: 'aircraft', kind: 'aircraft track', name: c.label ?? c.id, id: c.id, basis: c.basis, minSeparationDegrees: c.minSeparationDegrees, closestAt: c.closestAt,
      firstInside: c.firstInside, lastInside: c.lastInside, terrain: c.terrainAtClosest, rangeKm: c.rangeKmAtClosest, trackQuality: c.quality.track_quality,
      note: 'A track in the sight line is a geometric coincidence, not an identification and not evidence of intent. A callsign is a label the file carries, not an airframe.',
    });
  }
  return out.sort((a, b) => a.minSeparationDegrees - b.minSeparationDegrees);
}

function possibleAircraft(aircraft) {
  return (aircraft?.possible ?? []).map((c) => ({
    category: 'aircraft', name: c.label ?? c.id, id: c.id, minSeparationDegrees: c.minSeparationDegrees, angularUncertaintyDegrees: c.angularUncertaintyDegrees, closestAt: c.closestAt,
    note: 'Outside the sight line by its nominal position, but inside it if the declared position uncertainty is taken at its full size. Listed, not counted as a candidate.',
  }));
}

function collectNotChecked(satellites, aircraft, notRun, celestial, horizon) {
  const out = [];
  if (!celestial) out.push({ category: 'celestial', what: 'the Sun, Moon, planets and stars', reason: notRun.celestial ?? 'Not run in this session.' });
  if (!satellites) out.push({ category: 'satellite', what: 'satellites', reason: notRun.satellites ?? 'Not run in this session.' });
  for (const i of satellites?.items ?? []) if (i.status === 'NOT_CHECKED') out.push({ category: 'satellite', what: i.name, reason: i.reason, message: i.message });
  if (!aircraft) out.push({ category: 'aircraft', what: 'aircraft', reason: notRun.aircraft ?? 'Not run in this session.' });
  for (const i of aircraft?.items ?? []) {
    if (i.status === 'NOT_CHECKED') out.push({ category: 'aircraft', what: i.label ?? i.id, reason: i.reason, message: i.message });
    else if (i.coverage.state !== 'COVERED') out.push({ category: 'aircraft', what: i.label ?? i.id, reason: 'PARTIAL_COVERAGE', message: `The track covers ${i.coverage.interpolatedSeconds} of ${i.coverage.windowSeconds} s of the window (${i.coverage.gapSeconds} s in gaps, ${i.coverage.outsideTrackSeconds} s outside the track). The rest of the window says nothing about this track.` });
  }
  if (!horizon) out.push({ category: 'terrain', what: 'the terrain horizon and line of sight', reason: notRun.terrain ?? 'No terrain horizon was used.' });
  return out;
}

function conclusion(celestial, satellites, aircraft, candidates, notChecked) {
  const sets = [];
  if (celestial) sets.push(`the Sun, the Moon, ${celestial.checked.planets} planets and ${celestial.checked.stars} stars brighter than V ${celestial.checked.starLimitMagnitude}`);
  if (satellites) sets.push(`${satellites.denominator.checked} of ${satellites.denominator.requested} satellites (${satellites.denominator.names.join(', ')})`);
  if (aircraft) sets.push(`${aircraft.denominator.checked} of ${aircraft.denominator.tracks} supplied aircraft track${aircraft.denominator.tracks === 1 ? '' : 's'}`);
  const checkedAnything = Boolean(celestial) || (satellites?.denominator.checked ?? 0) > 0 || (aircraft?.denominator.checked ?? 0) > 0;
  const unchecked = notChecked.length > 0 ? ` ${notChecked.length} item${notChecked.length === 1 ? ' was' : 's were'} not checked or only partly checked; see "Not checked, or only partly" below, and notChecked in the receipt.` : '';
  if (!checkedAnything) {
    return { kind: 'NOT_ASSESSED', headline: 'NOT ASSESSED', text: `No check could be run, so nothing is ruled out and nothing is ruled in.${unchecked} ${PRINCIPLE}` };
  }
  if (candidates.length === 0) {
    return {
      kind: 'NO_ORDINARY_CANDIDATE_IDENTIFIED', headline: HEADLINE_NONE,
      text: `${HEADLINE_NONE} among the sets that were checked: ${sets.join('; ')}.${unchecked} ${PRINCIPLE} The checked sets are small next to what can be in a sky; the blind spots below (blindSpots in the receipt) are ordinary explanations that this check cannot assess at all.`,
    };
  }
  const n = candidates.length;
  return {
    kind: 'ORDINARY_CANDIDATES_LISTED', headline: `${n} ORDINARY CANDIDATE${n === 1 ? '' : 'S'} LISTED`,
    text: `${n} object${n === 1 ? ' was' : 's were'} inside the reported sight line at some moment of the window, among the sets checked: ${sets.join('; ')}. Each is a geometric coincidence, not an identification: being in a sight line shows neither that it is what was seen nor anything about intent.${unchecked} ${PRINCIPLE}`,
  };
}

function dedupe(lists) {
  return [...new Set(lists.flat().filter(Boolean))];
}

// Build the receipt. `generatedAt` is outside the digest, so the same inputs give the same contentDigest. Everything is
// passed through JSON so that the digest is of exactly what a downloaded file contains.
export async function buildExclusionReceipt({
  observation, celestial = null, satellites = null, aircraft = null, horizon = null, terrain = null, alignment = null,
  reconstruction = null, notRun = {}, generatedAt = new Date(),
} = {}) {
  if (!observation || observation.contract !== 'sky-observation-v1') throw new RangeError('A receipt needs a parsed observation (parseObservation).');
  if (!(generatedAt instanceof Date) || Number.isNaN(generatedAt.getTime())) throw new RangeError('generatedAt must be a valid date.');
  const candidates = collectCandidates(celestial, satellites, aircraft);
  const notChecked = collectNotChecked(satellites, aircraft, notRun, celestial, horizon);
  const terrainUnknown = candidates.filter((c) => c.terrain === 'UNKNOWN' || c.terrain === 'NOT_CHECKED').length;
  const body = JSON.parse(JSON.stringify({
    contract: EXCLUSION_RECEIPT_CONTRACT,
    certification: CERTIFICATION,
    conclusion: conclusion(celestial, satellites, aircraft, candidates, notChecked),
    observation: describeObservation(observation),
    privacy: 'This receipt holds the observer location and time exactly as entered. It was generated in this browser and has not been sent anywhere; it is yours to keep or discard.',
    candidates,
    possibleWithinUncertainty: possibleAircraft(aircraft),
    notChecked,
    blindSpots: BLIND_SPOTS,
    checks: { celestial: celestialPart(celestial, notRun), satellites: satellitePart(satellites, notRun), aircraft: aircraftPart(aircraft, notRun) },
    terrain: horizonPart(horizon, terrain),
    terrainNote: terrainUnknown > 0
      ? `${terrainUnknown} candidate${terrainUnknown === 1 ? ' was' : 's were'} not tested against terrain that is known (no terrain horizon was given, or it had no data in that direction), so terrain may have hidden ${terrainUnknown === 1 ? 'it' : 'them'}.`
      : null,
    alignment: alignment ? { contract: alignment.contract, mirrors: alignment.mirrors, counts: alignment.counts, sources: alignment.sources, gaps: alignment.gaps, warnings: alignment.warnings, notes: alignment.notes } : null,
    reconstruction,
    rules: [
      'MODELLED is not OBSERVED: bodies and satellites are computed, aircraft positions are reports or straight lines between them.',
      'MISSING DATA is not ZERO: a track, a source or a terrain cell with no data is listed as such and never read as empty.',
      'A track in the sight line is a geometric coincidence, not targeting; a callsign is a label, not an identity.',
      PRINCIPLE,
    ],
    limits: dedupe([celestial?.limits ?? [], satellites?.limits ?? [], aircraft?.limits ?? [], horizon?.limits ?? [], reconstruction?.conventions ?? [], alignment?.limits ?? []]),
    engines: {
      observation: observation.contract, celestial: celestial?.contract ?? null, satellites: satellites?.contract ?? null, aircraft: aircraft?.contract ?? null,
      horizon: horizon?.contract ?? null, alignment: alignment?.contract ?? null, reconstruction: reconstruction?.contract ?? null,
      elementPolicy: ELEMENT_POLICY,
    },
  }));
  const contentDigest = await sha256StableJson(body);
  return Object.freeze({
    ...body, generatedAt: generatedAt.toISOString(),
    contentDigest,
    digestNote: contentDigest ? 'SHA-256 of the receipt body as stable JSON (sorted keys, compact), without generatedAt and without this digest.' : 'The browser gave no SHA-256 (no secure context), so no digest was computed; nothing was made up.',
  });
}

export function receiptJson(receipt) {
  if (!receipt || receipt.contract !== EXCLUSION_RECEIPT_CONTRACT) throw new RangeError('That is not a sky-exclusion-v1 receipt.');
  return `${JSON.stringify(receipt, null, 2)}\n`;
}

export function receiptFileName(receipt) {
  const stamp = String(receipt.observation.time).replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  return `sky-exclusion-${stamp}-${(receipt.contentDigest ?? 'nodigest').slice(0, 12)}.json`;
}


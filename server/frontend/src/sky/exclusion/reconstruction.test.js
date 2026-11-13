import { describe, expect, it, vi } from 'vitest';
import { sha256StableJson } from '../../gis/integrity';
import aircraftReference from './fixtures/aircraftReference.json';
import elementsText from '../fixtures/satellite-elements.json?raw';
import satelliteReference from '../fixtures/satelliteReference.json';
import { loadSatelliteElements } from '../satelliteElements';
import { gpUrl } from '../satellites';
import { aircraftLookAt, checkAircraft } from './aircraftExclusion';
import { parseTrackCsv } from './aircraftTracks';
import { checkCelestial } from './celestialExclusion';
import { alignSources } from './clockAlignment';
import { computeHorizon } from './horizon';
import { parseObservation } from './observation';
import { apparentElevation } from './refraction';
import {
  BLIND_SPOTS, CERTIFICATION, EXCLUSION_RECEIPT_CONTRACT, HEADLINE_NONE, PRINCIPLE, buildExclusionReceipt, receiptFileName, receiptJson, reconstructSky,
} from './reconstruction';
import { checkSatellites } from './satelliteExclusion';
import { functionTerrain } from './terrain';

const frozen = JSON.parse(elementsText).items;
const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const answers = { [gpUrl(25544)]: frozen.ISS.payload, [gpUrl(20580)]: frozen.HST.payload, [gpUrl(48274)]: frozen.CSS.payload };
const loaded = (failures = {}) => loadSatelliteElements({ fetchImpl: vi.fn(async (url) => failures[url] ?? ok(answers[url])), now: new Date('2026-11-04T08:00:00Z') });
const OBSERVER = aircraftReference.observer;
const EPOCH = Date.parse(aircraftReference.generated_by.epoch);
const DECLARED = { source: 'synthetic tracks of the reference fixture', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
const tracks = () => parseTrackCsv(
  ['time,lat,lon,altitude,id', ...Object.values(aircraftReference.tracks).flatMap((t) => t.rows.map((r) => `${r.time},${r.lat},${r.lon},${r.altitude_m},${t.id}`))].join('\n'),
  DECLARED,
);
const sightAt = (seconds, azimuth, elevation, tolerance = 1, uncertainty = 10) => parseObservation({
  time: new Date(EPOCH + seconds * 1000).toISOString(), timeUncertaintySeconds: uncertainty, observer: OBSERVER,
  direction: { azimuth, elevation, azimuthReference: 'TRUE', toleranceDegrees: tolerance },
});
const trackA = () => tracks().tracks.find((t) => t.id === 'A');
const passDirection = () => aircraftLookAt(OBSERVER, trackA(), EPOCH + 124000, tracks().declaration.policy);
const FORBIDDEN = /anomal|\bUFO\b|\bUAP\b|extraterrestrial|unexplained|mysterious|proven|debunk/i;

async function everything(observation, { horizon = null, failures = {} } = {}) {
  const sat = await loaded(failures);
  const parsed = tracks();
  const celestial = checkCelestial(observation, { horizon });
  const satellites = await checkSatellites(observation, sat, { horizon });
  const aircraft = checkAircraft(observation, parsed, { horizon });
  const reconstruction = reconstructSky(observation, { satellites: sat, aircraft: parsed, horizon });
  return { celestial, satellites, aircraft, reconstruction, sat, parsed };
}

describe('the sky at the reported instant', () => {
  it('places the bodies, the satellites and the aircraft against the sight line, and says which is modelled and which observed', async () => {
    const look = passDirection();
    const observation = sightAt(124, look.azimuth, look.elevation, 1, 0);
    const { reconstruction } = await everything(observation);
    expect(reconstruction.contract).toBe('sky-reconstruction-v1');
    const states = new Set(reconstruction.objects.map((o) => o.state));
    expect([...states].sort()).toEqual(['INTERPOLATED', 'MODELLED', 'OBSERVED'].filter((s) => states.has(s)));
    const a = reconstruction.objects.find((o) => o.category === 'aircraft' && o.id === 'A');
    // 124 s falls between the reports at 120 and 125 s
    expect(a).toMatchObject({ state: 'INTERPOLATED', insideSightline: true });
    expect(a.separationFromSightlineDegrees).toBeLessThan(1e-6);
    // sorted by separation from the sight line, the aircraft first
    expect(reconstruction.objects[0].id).toBe('A');
    for (let i = 1; i < reconstruction.objects.length; i += 1) {
      expect(reconstruction.objects[i].separationFromSightlineDegrees).toBeGreaterThanOrEqual(reconstruction.objects[i - 1].separationFromSightlineDegrees);
    }
    expect(reconstruction.objects.filter((o) => o.category === 'celestial').some((o) => o.name === 'Sun')).toBe(true);
    expect(reconstruction.objects.filter((o) => o.kind === 'star').every((o) => o.magnitude <= 2.5)).toBe(true);
    expect(reconstruction.conventions.join(' ')).toMatch(/MODELLED.*OBSERVED.*INTERPOLATED/);
  });

  it('calls a position between two reports INTERPOLATED, and lists a track with no position as unavailable, never placed', async () => {
    const between = sightAt(147.5, 0, 10, 1, 0);
    const { reconstruction } = await everything(between);
    expect(reconstruction.objects.find((o) => o.id === 'A').state).toBe('INTERPOLATED');
    // B has a gap from 100 to 190 s
    expect(reconstruction.objects.find((o) => o.id === 'B')).toBeUndefined();
    expect(reconstruction.unavailable).toContainEqual({ category: 'aircraft', name: 'B', id: 'B', reason: 'GAP' });
    expect(reconstruction.conventions.join(' ')).toMatch(/not placed anywhere/);
  });

  it('lists a satellite whose elements did not load as unavailable, and lays the terrain over everything when a horizon is given', async () => {
    const failure = { [gpUrl(20580)]: { ok: false, status: 503, json: async () => ({}) } };
    const sat = await loaded(failure);
    const horizon = computeHorizon(functionTerrain({ heightAt: () => 0, datum: 'T', label: 'sea' }), { lon: OBSERVER.lon, lat: OBSERVER.lat, aboveGroundMetres: 5 });
    const r = reconstructSky(sightAt(124, 0, 10), { satellites: sat, horizon });
    expect(r.unavailable).toContainEqual({ category: 'satellite', name: 'Hubble Space Telescope', id: 'HST', reason: 'ELEMENTS_NOT_LOADED' });
    // over open sea the horizon is the curve of the water: what is up is CLEAR, what is below the horizon is hidden by it
    expect(r.objects.filter((o) => o.elevation >= 0).every((o) => o.terrain === 'CLEAR' && o.aboveHorizon)).toBe(true);
    const below = r.objects.filter((o) => o.elevation < -1);
    expect(below.length).toBeGreaterThan(10);
    expect(below.every((o) => o.terrain === 'OBSTRUCTED' && !o.aboveHorizon)).toBe(true);
  });
});

describe('the receipt: three conclusions and no others', () => {
  it('says NO ORDINARY CANDIDATE IDENTIFIED, with what was checked and the reminder, when the sight line is on nothing checked', async () => {
    const observation = sightAt(300, 200, 60, 0.5, 5);
    const parts = await everything(observation);
    expect(parts.celestial.candidates).toHaveLength(0);
    expect(parts.satellites.candidates).toHaveLength(0);
    expect(parts.aircraft.candidates).toHaveLength(0);
    const receipt = await buildExclusionReceipt({ observation, ...parts });
    expect(receipt.conclusion.kind).toBe('NO_ORDINARY_CANDIDATE_IDENTIFIED');
    expect(receipt.conclusion.headline).toBe(HEADLINE_NONE);
    expect(receipt.conclusion.text.startsWith(`${HEADLINE_NONE} among the sets that were checked:`)).toBe(true);
    expect(receipt.conclusion.text).toContain(PRINCIPLE);
    expect(receipt.conclusion.text).toMatch(/the Sun, the Moon, 5 planets and 288 stars brighter than V 3.5/);
    expect(receipt.conclusion.text).toMatch(/3 of 3 satellites \(ISS, HST, CSS\)/);
    expect(receipt.conclusion.text).toMatch(/2 of 2 supplied aircraft tracks/);
    expect(receipt.conclusion.text).toMatch(/the blind spots below \(blindSpots in the receipt\) are ordinary explanations that this check cannot assess at all/);
    expect(receipt.candidates).toEqual([]);
  });

  it('lists each candidate as a geometric coincidence, never an identification, with its basis', async () => {
    const look = passDirection();
    const observation = sightAt(124, look.azimuth, look.elevation, 1, 10);
    const parts = await everything(observation);
    const receipt = await buildExclusionReceipt({ observation, ...parts });
    expect(receipt.conclusion.kind).toBe('ORDINARY_CANDIDATES_LISTED');
    expect(receipt.conclusion.headline).toMatch(/^\d+ ORDINARY CANDIDATES? LISTED$/);
    expect(receipt.conclusion.text).toMatch(/Each is a geometric coincidence, not an identification/);
    expect(receipt.conclusion.text).toMatch(/nor anything about intent|neither that it is what was seen nor anything about intent/);
    const aircraft = receipt.candidates.find((c) => c.category === 'aircraft');
    expect(aircraft).toMatchObject({ id: 'A', basis: 'OBSERVED', kind: 'aircraft track' });
    expect(aircraft.note).toMatch(/not evidence of intent/);
    expect(aircraft.note).toMatch(/callsign is a label/);
    for (let i = 1; i < receipt.candidates.length; i += 1) {
      expect(receipt.candidates[i].minSeparationDegrees).toBeGreaterThanOrEqual(receipt.candidates[i - 1].minSeparationDegrees);
    }
  });

  it('carries a satellite candidate with its lit and dark-sky flags as geometry only', async () => {
    const sat = await loaded();
    const lit = satelliteReference.satellites.ISS.observers['San Juan'].looks.find((l) => l.sunlit && l.elevation > 20);
    const observation = parseObservation({
      time: lit.time, observer: { lat: 18.4663, lon: -66.1057, height: 0 },
      direction: { azimuth: lit.azimuth, elevation: apparentElevation(lit.elevation), azimuthReference: 'TRUE', toleranceDegrees: 0.5 },
    });
    const receipt = await buildExclusionReceipt({ observation, celestial: checkCelestial(observation), satellites: await checkSatellites(observation, sat) });
    const iss = receipt.candidates.find((c) => c.category === 'satellite');
    expect(iss).toMatchObject({ id: 'ISS', noradId: 25544, basis: 'MODELLED', sunlitAtClosest: true, observerDark: true, visibleCandidate: true, elementsConfidence: 'NORMAL' });
    expect(iss.note).toMatch(/brightness is not estimated/);
    expect(receipt.checks.aircraft).toEqual({ ran: false, reason: 'Not run in this session.' });
    expect(receipt.notChecked).toContainEqual({ category: 'aircraft', what: 'aircraft', reason: 'Not run in this session.' });
    expect(receipt.notChecked).toContainEqual({ category: 'terrain', what: 'the terrain horizon and line of sight', reason: 'No terrain horizon was used.' });
  });

  it('says NOT ASSESSED when nothing could be checked, and does not say no candidate was identified', async () => {
    const observation = sightAt(300, 200, 60, 0.5, 5);
    const receipt = await buildExclusionReceipt({ observation, notRun: { celestial: 'turned off', satellites: 'elements not loaded', aircraft: 'no tracks supplied' } });
    expect(receipt.conclusion).toMatchObject({ kind: 'NOT_ASSESSED', headline: 'NOT ASSESSED' });
    expect(receipt.conclusion.text).toMatch(/nothing is ruled out and nothing is ruled in/);
    expect(receipt.conclusion.text).not.toContain(HEADLINE_NONE);
    expect(receipt.checks.satellites.reason).toBe('elements not loaded');
    expect(receipt.notChecked.map((n) => n.reason)).toEqual(['turned off', 'elements not loaded', 'no tracks supplied', 'No terrain horizon was used.']);
  });

  it('lists what was not checked, or only partly: a failed satellite load, a track with a gap in the window', async () => {
    const failure = { [gpUrl(48274)]: { ok: false, status: 503, json: async () => ({}) } };
    // 90 to 110 s: B has reports to 100 s and then a gap
    const observation = sightAt(100, 200, 60, 0.5, 10);
    const parts = await everything(observation, { failures: failure });
    const receipt = await buildExclusionReceipt({ observation, ...parts });
    const css = receipt.notChecked.find((n) => n.category === 'satellite');
    expect(css).toMatchObject({ reason: 'ELEMENTS_NOT_LOADED' });
    expect(css.message).toMatch(/did not load/);
    const partial = receipt.notChecked.find((n) => n.category === 'aircraft' && n.reason === 'PARTIAL_COVERAGE');
    expect(partial.what).toBe('B');
    expect(partial.message).toMatch(/gaps/);
    expect(receipt.conclusion.text).toMatch(/items? (was|were) not checked or only partly checked/);
    expect(receipt.conclusion.text).toMatch(/2 of 3 satellites/);
  });

  it('says when a candidate was not tested against terrain, and when the terrain was', async () => {
    const look = passDirection();
    const observation = sightAt(124, look.azimuth, look.elevation, 1, 10);
    const parts = await everything(observation);
    const without = await buildExclusionReceipt({ observation, ...parts });
    expect(without.terrainNote).toMatch(/not tested against terrain that is known/);
    expect(without.terrain).toBeNull();
    const sea = functionTerrain({ heightAt: () => 0, datum: 'TEST', label: 'sea' });
    const horizon = computeHorizon(sea, { lon: OBSERVER.lon, lat: OBSERVER.lat, aboveGroundMetres: 5 });
    const withTerrain = await everything(observation, { horizon });
    const receipt = await buildExclusionReceipt({ observation, ...withTerrain, horizon });
    expect(receipt.terrainNote).toBeNull();
    expect(receipt.terrain.summary.rays).toBe(720);
    expect(receipt.terrain.rays).toHaveLength(720);
    expect(receipt.terrain.limits.join(' ')).toMatch(/Bare earth/);
  });
});

describe('the receipt: what it states about itself', () => {
  it('is NOT_CERTIFIED, lists the blind spots and the rules, and holds the observation exactly as entered', async () => {
    const observation = parseObservation({
      time: '2026-11-04T12:02:04Z', observer: { lat: 18.4663, lon: -66.1057 },
      direction: { azimuth: 350, elevation: 11, azimuthReference: 'MAGNETIC', magneticDeclinationDegrees: -10.5, toleranceDegrees: 2 },
    });
    const receipt = await buildExclusionReceipt({ observation, celestial: checkCelestial(observation) });
    expect(receipt.contract).toBe(EXCLUSION_RECEIPT_CONTRACT);
    expect(receipt.certification).toEqual(CERTIFICATION);
    expect(receipt.certification.status).toBe('NOT_CERTIFIED');
    expect(receipt.certification.meaning).toMatch(/not a finding/);
    expect(receipt.blindSpots).toEqual(BLIND_SPOTS);
    expect(receipt.blindSpots.length).toBeGreaterThanOrEqual(8);
    expect(receipt.rules.join(' ')).toMatch(/MODELLED is not OBSERVED/);
    expect(receipt.rules.join(' ')).toMatch(/MISSING DATA is not ZERO/);
    expect(receipt.rules.join(' ')).toMatch(/not targeting; a callsign is a label, not an identity/);
    expect(receipt.rules).toContain(PRINCIPLE);
    expect(receipt.observation.direction).toMatchObject({ azimuthAsGiven: 350, azimuthReference: 'MAGNETIC', magneticDeclinationDegrees: -10.5, azimuthTrue: 339.5 });
    expect(receipt.observation.timeUncertaintyDeclared).toBe(false);
    expect(receipt.observation.notes.join(' ')).toMatch(/time uncertainty was not declared/);
    expect(receipt.privacy).toMatch(/has not been sent anywhere/);
  });

  it('never uses the words that claim an anomaly, an identification of what was seen or a proof', async () => {
    for (const [seconds, az, el] of [[300, 200, 60], [124, passDirection().azimuth, passDirection().elevation]]) {
      const observation = sightAt(seconds, az, el, 1, 10);
      const receipt = await buildExclusionReceipt({ observation, ...(await everything(observation)) });
      const text = receiptJson(receipt);
      expect(text).not.toMatch(FORBIDDEN);
    }
    expect(receiptJson(await buildExclusionReceipt({ observation: sightAt(1, 1, 1), notRun: {} }))).not.toMatch(FORBIDDEN);
  });

  it('includes the clock alignment summary without its events, when sources were aligned', async () => {
    const observation = sightAt(300, 200, 60, 0.5, 5);
    const alignment = alignSources([{ sourceId: 'cam', sensorType: 'camera_frame', clockOffsetSeconds: 2, clockOffsetBasis: 'NTP check', events: [{ id: 'f', time: new Date(EPOCH + 300000).toISOString() }] }]);
    const receipt = await buildExclusionReceipt({ observation, celestial: checkCelestial(observation), alignment });
    expect(receipt.alignment).toMatchObject({ contract: 'sky-clock-alignment-v1', counts: { sources: 1, events: 1, timestamps: 1, gaps: 0 } });
    expect(receipt.alignment.sources[0]).toMatchObject({ clockOffsetSeconds: 2, clockOffsetBasis: 'NTP check' });
    expect(receipt.alignment.events).toBeUndefined();
    expect(receipt.limits.join(' ')).toMatch(/never inferred from the events/);
  });
});

describe('the receipt is reproducible and checkable by anyone', () => {
  it('has a digest that does not depend on when it was made, and does depend on what is in it', async () => {
    const observation = sightAt(300, 200, 60, 0.5, 5);
    const parts = { celestial: checkCelestial(observation) };
    const one = await buildExclusionReceipt({ observation, ...parts, generatedAt: new Date('2026-11-05T00:00:00Z') });
    const later = await buildExclusionReceipt({ observation, ...parts, generatedAt: new Date('2027-01-01T00:00:00Z') });
    const other = await buildExclusionReceipt({ observation: sightAt(300, 200, 60, 0.6, 5), celestial: checkCelestial(sightAt(300, 200, 60, 0.6, 5)) });
    expect(one.contentDigest).toMatch(/^[0-9a-f]{64}$/);
    expect(later.contentDigest).toBe(one.contentDigest);
    expect(other.contentDigest).not.toBe(one.contentDigest);
    expect(one.generatedAt).toBe('2026-11-05T00:00:00.000Z');
  });

  it('survives being written and read back, and the digest can be recomputed from the file alone', async () => {
    const look = passDirection();
    const observation = sightAt(124, look.azimuth, look.elevation, 1, 10);
    const receipt = await buildExclusionReceipt({ observation, ...(await everything(observation)) });
    const file = JSON.parse(receiptJson(receipt));
    const { generatedAt, contentDigest, digestNote, ...body } = file;
    expect(generatedAt).toBe(receipt.generatedAt);
    expect(digestNote).toMatch(/SHA-256 of the receipt body as stable JSON/);
    expect(await sha256StableJson(body)).toBe(contentDigest);
    expect(receiptFileName(receipt)).toBe(`sky-exclusion-${receipt.observation.time.replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')}-${receipt.contentDigest.slice(0, 12)}.json`);
    expect(receiptFileName(receipt)).toMatch(/^sky-exclusion-20261104T120204Z|^sky-exclusion-2026110412/);
  });

  it('says so, and makes nothing up, when the browser offers no SHA-256', async () => {
    const original = globalThis.crypto;
    Object.defineProperty(globalThis, 'crypto', { value: {}, configurable: true });
    try {
      const receipt = await buildExclusionReceipt({ observation: sightAt(1, 1, 1), celestial: checkCelestial(sightAt(1, 1, 1)) });
      expect(receipt.contentDigest).toBeNull();
      expect(receipt.digestNote).toMatch(/no secure context.*nothing was made up/);
      expect(receiptFileName(receipt)).toMatch(/nodigest\.json$/);
    } finally {
      Object.defineProperty(globalThis, 'crypto', { value: original, configurable: true });
    }
  });

  it('refuses what is not an observation, a bad date, or something that is not a receipt', async () => {
    await expect(buildExclusionReceipt({})).rejects.toThrow(/parsed observation/);
    await expect(buildExclusionReceipt({ observation: { contract: 'x' } })).rejects.toThrow(/parsed observation/);
    await expect(buildExclusionReceipt({ observation: sightAt(1, 1, 1), generatedAt: new Date('nope') })).rejects.toThrow(/valid date/);
    expect(() => receiptJson({ contract: 'something-else' })).toThrow(/not a sky-exclusion-v1 receipt/);
    expect(() => receiptJson(null)).toThrow(/not a sky-exclusion-v1 receipt/);
  });

  it('is frozen', async () => {
    const receipt = await buildExclusionReceipt({ observation: sightAt(1, 1, 1), celestial: checkCelestial(sightAt(1, 1, 1)) });
    expect(Object.isFrozen(receipt)).toBe(true);
  });
});

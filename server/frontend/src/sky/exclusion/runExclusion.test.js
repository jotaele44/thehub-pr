import { describe, expect, it, vi } from 'vitest';
import elementsText from '../fixtures/satellite-elements.json?raw';
import { loadSatelliteElements } from '../satelliteElements';
import { gpUrl } from '../satellites';
import aircraftReference from './fixtures/aircraftReference.json';
import { EMPTY_DECLARATION_DRAFT, EMPTY_OBSERVATION_DRAFT, DEFAULT_TERRAIN_DRAFT } from './exclusionForm';
import { detectTrackFormat, runExclusion } from './runExclusion';

const frozen = JSON.parse(elementsText).items;
const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const answers = { [gpUrl(25544)]: frozen.ISS.payload, [gpUrl(20580)]: frozen.HST.payload, [gpUrl(48274)]: frozen.CSS.payload };
const satelliteData = () => loadSatelliteElements({ fetchImpl: vi.fn(async (url) => ok(answers[url])), now: new Date('2026-11-04T08:00:00Z') });
const EPOCH = Date.parse(aircraftReference.generated_by.epoch);
const csv = ['time,lat,lon,altitude,id', ...Object.values(aircraftReference.tracks).flatMap((t) => t.rows.map((r) => `${r.time},${r.lat},${r.lon},${r.altitude_m},${t.id}`))].join('\n');
const DECLARATION = { ...EMPTY_DECLARATION_DRAFT, source: 'reference tracks', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
const draft = (patch = {}) => ({
  ...EMPTY_OBSERVATION_DRAFT, time: new Date(EPOCH + 300000).toISOString(), timeUncertainty: '5',
  lat: String(aircraftReference.observer.lat), lon: String(aircraftReference.observer.lon), height: String(aircraftReference.observer.height),
  azimuth: '200', elevation: '60', azimuthReference: 'TRUE', tolerance: '0.5', ...patch,
});

describe('runExclusion', () => {
  it('runs all three checks and returns a receipt when everything is supplied', async () => {
    const r = await runExclusion({ observationDraft: draft(), tracks: { text: csv, name: 'tracks.csv', declarationDraft: DECLARATION }, satelliteData: await satelliteData() });
    expect(r.ok).toBe(true);
    expect(r.celestial.contract).toBe('sky-celestial-exclusion-v1');
    expect(r.satellites.denominator).toMatchObject({ checked: 3, requested: 3 });
    expect(r.aircraft.denominator).toMatchObject({ tracks: 2, checked: 2 });
    expect(r.receipt.contract).toBe('sky-exclusion-v1');
    expect(r.receipt.conclusion.kind).toBe('NO_ORDINARY_CANDIDATE_IDENTIFIED');
    expect(r.receipt.contentDigest).toMatch(/^[0-9a-f]{64}$/);
    expect(r.reconstruction.objects.length).toBeGreaterThan(50);
    expect(r.notRun.terrain).toBe('The terrain option was not turned on.');
  });

  it('runs the celestial check alone when nothing else is supplied, and lists the rest as not run with the reason', async () => {
    const r = await runExclusion({ observationDraft: draft() });
    expect(r.ok).toBe(true);
    expect(r.satellites).toBeNull();
    expect(r.aircraft).toBeNull();
    expect(r.receipt.checks.satellites).toEqual({ ran: false, reason: 'The satellite element sets are not loaded (see Satellites above).' });
    expect(r.receipt.checks.aircraft).toEqual({ ran: false, reason: 'No aircraft tracks were supplied.' });
    expect(r.receipt.notChecked.map((n) => n.category)).toEqual(['satellite', 'aircraft', 'terrain']);
    expect(r.receipt.conclusion.text).toMatch(/3 items were not checked or only partly checked/);
  });

  it('returns the first problem in the form with its field and does not run', async () => {
    expect(await runExclusion({ observationDraft: draft({ azimuthReference: '' }) })).toMatchObject({ ok: false, field: 'azimuthReference' });
    expect(await runExclusion({ observationDraft: draft({ time: '' }) })).toMatchObject({ ok: false, field: 'time' });
  });

  it('stops, with the reason, when the tracks asked for cannot be read, and reports a declaration fault against the declaration', async () => {
    const noSource = await runExclusion({ observationDraft: draft(), tracks: { text: csv, name: 't.csv', declarationDraft: { ...DECLARATION, source: '' } } });
    expect(noSource).toMatchObject({ ok: false, field: 'declaration.source' });
    expect(noSource.message).toMatch(/where the tracks came from/);
    const noReference = await runExclusion({ observationDraft: draft(), tracks: { text: csv, name: 't.csv', declarationDraft: { ...DECLARATION, altitudeReference: '' } } });
    expect(noReference).toMatchObject({ ok: false, field: 'declaration.altitudeReference' });
    expect(noReference.message).toMatch(/altitude reference/);
    const badFile = await runExclusion({ observationDraft: draft(), tracks: { text: 'time,lat,lon\n1,2,3', name: 't.csv', declarationDraft: DECLARATION } });
    expect(badFile).toMatchObject({ ok: false, field: 'tracks' });
    expect(badFile.message).toMatch(/"altitude" is missing/);
    const badNumber = await runExclusion({ observationDraft: draft(), tracks: { text: csv, name: 't.csv', declarationDraft: { ...DECLARATION, clockOffset: 'late' } } });
    expect(badNumber).toMatchObject({ ok: false, field: 'declaration.clockOffset' });
  });

  it('reads GeoJSON as well as CSV, by file name or by content', async () => {
    expect(detectTrackFormat('x.csv', '{')).toBe('CSV');
    expect(detectTrackFormat('x.geojson', 'a')).toBe('GeoJSON');
    expect(detectTrackFormat('x.json', 'a')).toBe('GeoJSON');
    expect(detectTrackFormat('x.txt', '  {"type":"Feature"}')).toBe('GeoJSON');
    expect(detectTrackFormat('x.txt', 'time,lat')).toBe('CSV');
    const geo = JSON.stringify({
      type: 'FeatureCollection',
      features: aircraftReference.tracks.A.rows.slice(0, 30).map((r) => ({ type: 'Feature', properties: { time: r.time, id: 'A' }, geometry: { type: 'Point', coordinates: [r.lon, r.lat, r.altitude_m] } })),
    });
    const r = await runExclusion({ observationDraft: draft({ time: new Date(EPOCH + 60000).toISOString() }), tracks: { text: geo, name: 'tracks.geojson', declarationDraft: DECLARATION } });
    expect(r.ok).toBe(true);
    expect(r.aircraft.denominator).toMatchObject({ tracks: 1, checked: 1 });
  });

  it('uses the terrain when asked and it reads, and says so in the receipt', async () => {
    const flat = { datum: 'TEST', label: 'flat sea', heightAt: () => 0, caveats: ['test'], tilesRead: ['a.tif'] };
    const read = vi.fn(async () => flat);
    const r = await runExclusion({ observationDraft: draft(), terrain: { enabled: true, draft: DEFAULT_TERRAIN_DRAFT } }, { terrainFromCudem: read });
    expect(read).toHaveBeenCalledWith({ lon: aircraftReference.observer.lon, lat: aircraftReference.observer.lat }, { radiusKm: 40 });
    expect(r.horizon.parameters).toMatchObject({ refractionK: 0.13, maxRangeKm: 40 });
    expect(r.receipt.terrain.terrain.tilesRead).toEqual(['a.tif']);
    expect(r.receipt.notChecked.map((n) => n.category)).not.toContain('terrain');
  });

  it('goes on without terrain when it cannot be read, and lists that it was not checked, with the reason', async () => {
    const read = vi.fn(async () => { throw new Error('The observer is outside the CUDEM coverage (Puerto Rico and its waters), so there is no terrain to read.'); });
    const r = await runExclusion({ observationDraft: draft(), terrain: { enabled: true, draft: DEFAULT_TERRAIN_DRAFT } }, { terrainFromCudem: read });
    expect(r.ok).toBe(true);
    expect(r.horizon).toBeNull();
    const note = r.receipt.notChecked.find((n) => n.category === 'terrain');
    expect(note.reason).toMatch(/The terrain could not be used: The observer is outside the CUDEM coverage/);
    expect(r.receipt.terrain).toBeNull();
  });

  it('refuses a blank terrain option rather than guessing it', async () => {
    const r = await runExclusion({ observationDraft: draft(), terrain: { enabled: true, draft: { ...DEFAULT_TERRAIN_DRAFT, refractionK: '' } } });
    expect(r).toMatchObject({ ok: false, field: 'terrain.refractionK' });
  });
});

import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TERRAIN_DRAFT, EMPTY_DECLARATION_DRAFT, EMPTY_OBSERVATION_DRAFT, declarationFieldOf, declarationFromDraft, draftFromWorkspace, observationFromDraft, terrainOptionsFromDraft,
} from './exclusionForm';

const GOOD = { ...EMPTY_OBSERVATION_DRAFT, time: '2026-11-04T12:02:04Z', lat: '18.4663', lon: '-66.1057', azimuth: '350', elevation: '11', azimuthReference: 'TRUE', tolerance: '2' };
const bad = (patch) => observationFromDraft({ ...GOOD, ...patch });

describe('observationFromDraft', () => {
  it('turns a complete form into an observation, and records what was left undeclared', () => {
    const r = observationFromDraft(GOOD);
    expect(r.ok).toBe(true);
    expect(r.observation.contract).toBe('sky-observation-v1');
    expect(r.observation.time.toISOString()).toBe('2026-11-04T12:02:04.000Z');
    expect(r.observation.direction).toMatchObject({ azimuth: 350, elevation: 11, toleranceDegrees: 2, azimuthReference: 'TRUE' });
    expect(r.observation.notes.join(' ')).toMatch(/time uncertainty was not declared/);
    expect(r.observation.notes.join(' ')).toMatch(/observer height was not declared/);
  });

  it('takes a declared time uncertainty and height, a magnetic bearing with its declination, and a moving sight line', () => {
    const r = observationFromDraft({ ...GOOD, timeUncertainty: '30', height: '12.5', azimuthReference: 'MAGNETIC', declination: '-10.5', moving: true, endAzimuth: '20', endElevation: '15', endTime: '2026-11-04T12:02:34Z' });
    expect(r.ok).toBe(true);
    expect(r.observation).toMatchObject({ timeUncertaintySeconds: 30, timeUncertaintyDeclared: true });
    expect(r.observation.observer.height).toBe(12.5);
    expect(r.observation.direction.azimuth).toBeCloseTo(339.5, 9);
    expect(r.observation.motion).toMatchObject({ endElevation: 15, durationSeconds: 30 });
  });

  it('takes a camera field of view in place of a tolerance', () => {
    const r = observationFromDraft({ ...GOOD, extent: 'FRUSTUM', tolerance: '', hfov: '60', vfov: '40' });
    expect(r.ok).toBe(true);
    expect(r.observation.direction.frustum).toMatchObject({ horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 0 });
    expect(r.observation.direction.toleranceDegrees).toBeNull();
  });

  it('names the field of the first thing that is missing, and never fills it in', () => {
    expect(bad({ time: '' })).toMatchObject({ ok: false, field: 'time' });
    expect(bad({ time: '2026-11-04T12:02:04' })).toMatchObject({ ok: false, field: 'time' });
    expect(bad({ time: '2026-11-04T12:02:04' }).message).toMatch(/UTC designator/);
    expect(bad({ lat: '' })).toMatchObject({ ok: false, field: 'lat', message: 'Latitude is required.' });
    expect(bad({ lon: '' })).toMatchObject({ field: 'lon' });
    expect(bad({ azimuth: '' })).toMatchObject({ field: 'azimuth' });
    expect(bad({ elevation: '' })).toMatchObject({ field: 'elevation' });
    expect(bad({ azimuthReference: '' })).toMatchObject({ field: 'azimuthReference' });
    expect(bad({ azimuthReference: '' }).message).toMatch(/not assumed/);
    expect(bad({ tolerance: '' })).toMatchObject({ field: 'tolerance', message: 'Tolerance is required.' });
    expect(bad({ azimuthReference: 'MAGNETIC', declination: '' })).toMatchObject({ field: 'declination' });
    expect(bad({ extent: 'FRUSTUM', tolerance: '', hfov: '', vfov: '40' })).toMatchObject({ field: 'hfov' });
    expect(bad({ extent: 'FRUSTUM', tolerance: '', hfov: '60', vfov: '' })).toMatchObject({ field: 'vfov' });
    expect(bad({ moving: true, endTime: '' })).toMatchObject({ field: 'endTime' });
    expect(bad({ moving: true, endTime: '2026-11-04T12:03:00Z', endAzimuth: '', endElevation: '5' })).toMatchObject({ field: 'endAzimuth' });
  });

  it('says what is not a number, and points at the field the engine refused', () => {
    expect(bad({ lat: 'north' })).toMatchObject({ ok: false, field: 'lat', message: 'Latitude is not a number: north' });
    expect(bad({ lat: '91' })).toMatchObject({ field: 'lat' });
    expect(bad({ lon: '181' })).toMatchObject({ field: 'lon' });
    expect(bad({ elevation: '95' })).toMatchObject({ field: 'elevation' });
    expect(bad({ tolerance: '0' })).toMatchObject({ field: 'tolerance' });
    expect(bad({ tolerance: '120' })).toMatchObject({ field: 'tolerance' });
    expect(bad({ timeUncertainty: '-1' })).toMatchObject({ field: 'timeUncertainty' });
    expect(bad({ timeUncertainty: '100000' })).toMatchObject({ field: 'timeUncertainty' });
    expect(bad({ timeUncertainty: '30000' })).toMatchObject({ field: 'timeUncertainty' });
    expect(bad({ height: '99999' })).toMatchObject({ field: 'height' });
    expect(bad({ moving: true, endAzimuth: '20', endElevation: '15', endTime: '2026-11-04T12:00:00Z' })).toMatchObject({ field: 'endTime' });
    expect(bad({ extent: 'FRUSTUM', tolerance: '', hfov: '200', vfov: '40' }).ok).toBe(false);
  });
});

describe('declarationFromDraft', () => {
  it('passes the declared source, reference and unit through, and the optional numbers only when given', () => {
    const r = declarationFromDraft({ ...EMPTY_DECLARATION_DRAFT, source: 'file X', altitudeReference: 'MSL', altitudeUnits: 'ft', geoidSeparation: '-43.1', horizontalUncertainty: '30', clockOffset: '-2' });
    expect(r).toEqual({ ok: true, declaration: { source: 'file X', altitudeReference: 'MSL', altitudeUnits: 'ft', geoidSeparationMetres: -43.1, horizontalUncertaintyMetres: 30, clockOffsetSeconds: -2 } });
  });

  it('leaves a blank reference and unit undefined, so the track parser refuses them by name', () => {
    const r = declarationFromDraft({ ...EMPTY_DECLARATION_DRAFT, source: 'x' });
    expect(r.declaration.altitudeReference).toBeUndefined();
    expect(r.declaration.altitudeUnits).toBeUndefined();
    expect(declarationFromDraft({ ...EMPTY_DECLARATION_DRAFT, geoidSeparation: 'minus' })).toMatchObject({ ok: false, field: 'geoidSeparation' });
  });
});

describe('declarationFieldOf', () => {
  it('points each refusal of the track declaration at its own field', async () => {
    const { validateDeclaration } = await import('./aircraftTracks');
    const base = { source: 'x', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
    const field = (patch) => { try { validateDeclaration({ ...base, ...patch }); return null; } catch (e) { return declarationFieldOf(e.message); } };
    expect(field({ source: '' })).toBe('declaration.source');
    expect(field({ altitudeReference: undefined })).toBe('declaration.altitudeReference');
    expect(field({ altitudeUnits: undefined })).toBe('declaration.altitudeUnits');
    expect(field({ altitudeReference: 'MSL' })).toBe('declaration.geoidSeparation');
    expect(field({ altitudeReference: 'BAROMETRIC' })).toBe('declaration.altitudeUncertainty');
    expect(field({ altitudeUncertaintyMetres: -3 })).toBe('declaration.altitudeUncertainty');
    expect(field({ horizontalUncertaintyMetres: -3 })).toBe('declaration.horizontalUncertainty');
    expect(field({ clockOffsetSeconds: 999999 })).toBe('declaration.clockOffset');
    expect(field({ gapSeconds: 0 })).toBe('declaration.gapSeconds');
    expect(declarationFieldOf('something else')).toBe('declaration');
  });
});

describe('terrainOptionsFromDraft and draftFromWorkspace', () => {
  it('reads the terrain options and refuses a blank', () => {
    expect(terrainOptionsFromDraft(DEFAULT_TERRAIN_DRAFT)).toEqual({ ok: true, options: { aboveGroundMetres: 2, refractionK: 0.13, radiusKm: 40 } });
    expect(terrainOptionsFromDraft({ ...DEFAULT_TERRAIN_DRAFT, aboveGround: '' })).toMatchObject({ ok: false, field: 'aboveGround' });
    expect(terrainOptionsFromDraft({ ...DEFAULT_TERRAIN_DRAFT, radiusKm: 'far' })).toMatchObject({ ok: false, field: 'radiusKm' });
  });

  it('starts the form from the workspace observer and instant, but does not carry its elevation over as an ellipsoidal height', () => {
    const next = draftFromWorkspace(EMPTY_OBSERVATION_DRAFT, { observer: { lat: 18.4663, lon: -66.1057, elevation: 30 }, instant: new Date('2026-11-04T12:00:00.000Z') });
    expect(next).toMatchObject({ time: '2026-11-04T12:00:00Z', lat: '18.4663', lon: '-66.1057', height: '' });
    expect(next.azimuth).toBe('');
  });
});

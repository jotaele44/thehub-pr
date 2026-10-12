import { describe, expect, it } from 'vitest';
import { getOnlineSourceDefinition } from './sourceRegistry';
import {
  DOCUMENTED_LAYERS, GROUP_STYLES, MODELLED_LABEL, PROFILE_MAX_SAMPLES, buildProfile, crossings, groupOf, haversineKm,
  interpretivePaint, modelledStatement, profileCsv, profilePath, profileSamples, profileStats, splitHubFeatures,
} from './interpretive';

function feature(id, category, props = {}) {
  return {
    type: 'Feature', id, geometry: { type: 'Point', coordinates: [-66.5, 18.2] },
    properties: { evidence_id: id, category, geometry_precision: 'OBSERVED_POINT', declared_epistemic_class: 'CURATED', ...props },
  };
}
const square = (west, south, east, north) => ({
  type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
});

describe('documented and modelled groups', () => {
  it('names only registry layers, and none of them claims to be subsurface geometry', () => {
    expect(DOCUMENTED_LAYERS.map((layer) => layer.sourceId)).toEqual(['pr-sige-sumideros', 'pr-sige-acuiferos', 'pr-sige-cuencas']);
    for (const layer of DOCUMENTED_LAYERS) {
      expect(getOnlineSourceDefinition(layer.sourceId).sourceId).toBe(layer.sourceId);
      expect(layer.role).toMatch(/not subsurface geometry|surface hydrography/);
    }
  });

  it('keeps a record the producer declared INTERPRETIVE out of the documented group, whatever its category', () => {
    expect(groupOf(feature('a', 'mineral_occurrence'))).toBe('documented');
    expect(groupOf(feature('b', 'mineral_occurrence', { declared_epistemic_class: 'INTERPRETIVE' }))).toBe('modelled');
    expect(groupOf(feature('c', 'utility_asset'))).toBeNull();
    // COMPUTED (a threshold alert) and undeclared are not models.
    expect(groupOf(feature('d', 'x', { declared_epistemic_class: 'COMPUTED' }))).toBeNull();
    expect(groupOf(feature('e', 'x', { declared_epistemic_class: null }))).toBeNull();
  });

  it('splits Hub records into groups without mutating them and counts what it leaves out', () => {
    const input = [feature('a', 'mineral_occurrence'), feature('b', 'x', { declared_epistemic_class: 'INTERPRETIVE' }), feature('c', 'sensor_site')];
    const split = splitHubFeatures(input);
    expect(split.documented.map((item) => item.id)).toEqual(['a']);
    expect(split.modelled.map((item) => item.id)).toEqual(['b']);
    expect(split.documented[0].properties.group).toBe('DOCUMENTED');
    expect(split.modelled[0].properties.group).toBe('MODELLED');
    expect(split.other).toBe(1);
    expect(input[0].properties.group).toBeUndefined();
  });

  it('never lets a model share the documented look', () => {
    const { documented, modelled } = GROUP_STYLES;
    expect(modelled.label).toBe(MODELLED_LABEL);
    expect(modelled.label).toMatch(/not observed geometry/);
    expect(modelled.swatch).not.toBe(documented.swatch);
    expect(modelled.color).not.toBe(documented.color);
    // Every circle property is switched on the group, so a modelled point cannot inherit a documented style.
    const paint = interpretivePaint({ mineral_occurrence: '#009E73' });
    for (const expression of Object.values(paint)) {
      expect(expression[0]).toBe('case');
      expect(expression[1]).toEqual(['==', ['get', 'group'], 'MODELLED']);
    }
    expect(paint['circle-stroke-color'][2]).toBe(modelled.color);
  });

  it('says why the modelled group is empty, and what a model is when it is not', () => {
    expect(modelledStatement(0)).toMatch(/No producer exports a modelled or interpretive layer/);
    expect(modelledStatement(0)).toMatch(/test fixtures and are not shown/);
    expect(modelledStatement(2)).toBe('2 records declared INTERPRETIVE by their producer. Each is modelled, never observed geometry.');
    expect(modelledStatement(1)).toMatch(/^1 record declared/);
  });
});

describe('terrain profile', () => {
  it('measures great-circle distance and samples a line end to end', () => {
    expect(haversineKm([0, 0], [0, 1])).toBeCloseTo(111.195, 2);
    const samples = profileSamples([0, 0], [2, 0], 5);
    expect(samples).toHaveLength(5);
    expect([samples[0].lon, samples[0].lat, samples[0].km]).toEqual([0, 0, 0]);
    expect(samples[2].lon).toBeCloseTo(1, 9);
    expect(samples[2].lat).toBeCloseTo(0, 9);
    expect(samples[4].lon).toBeCloseTo(2, 9);
    expect(samples[4].km).toBeCloseTo(haversineKm([0, 0], [2, 0]), 9);
    expect(profileSamples([0, 0], [0, 1], 1)).toHaveLength(2);
    expect(profileSamples([0, 0], [0, 1], 9999)).toHaveLength(PROFILE_MAX_SAMPLES);
    expect(profileSamples([5, 5], [5, 5], 4).every((sample) => sample.km === 0)).toBe(true);
  });

  it('keeps no-data samples as gaps, never zeros, and states one datum', () => {
    const samples = profileSamples([0, 0], [0, 3], 4);
    const profile = buildProfile(samples, [10, null, Number.NaN, 40], 'PRVD02');
    expect(profile.datum).toBe('PRVD02');
    expect(profile.samples.map((item) => item.metres)).toEqual([10, null, null, 40]);
    expect(profileStats(profile)).toEqual({ min: 10, max: 40, withHeight: 2, gaps: 2 });
    expect(profileStats(buildProfile(samples, [null, null, null, null], 'PRVD02'))).toBeNull();
    expect(() => buildProfile(samples, [1, 2, 3, 4], '')).toThrow(/datum/);
    expect(() => buildProfile(samples, [1, 2, 3, 4], undefined)).toThrow(/datum/);
  });

  it('exports every sample with its datum and leaves gaps empty', () => {
    const profile = buildProfile(profileSamples([0, 0], [0, 2], 3), [5, null, 7], 'PRVD02');
    const lines = profileCsv(profile).trim().split('\n');
    expect(lines[0]).toBe('distance_km,longitude,latitude,height_m_PRVD02');
    expect(lines[1]).toMatch(/^0,0,0,5$/);
    expect(lines[2].endsWith(',')).toBe(true);
    expect(lines[3].endsWith(',7')).toBe(true);
  });

  it('draws a path that breaks at gaps instead of bridging them', () => {
    const profile = buildProfile(profileSamples([0, 0], [0, 4], 5), [10, 20, null, 30, 40], 'PRVD02');
    const { path } = profilePath(profile, { width: 100, height: 50, pad: 0 });
    expect(path.match(/M/g)).toHaveLength(2);
    expect(path.match(/L/g)).toHaveLength(2);
    expect(profilePath(buildProfile(profileSamples([0, 0], [0, 1], 2), [null, null], 'PRVD02')).path).toBe('');
  });

  it('marks the surface intervals where the line crosses a documented layer', () => {
    // Samples every 0.5 degree of longitude along the equator from 0 to 3.
    const profile = buildProfile(profileSamples([0, 0], [3, 0], 7), new Array(7).fill(1), 'PRVD02');
    const layers = [
      { id: 'karst', label: 'Sumideros', features: [{ geometry: square(0.9, -1, 2.1, 1) }] },
      { id: 'aquifer', label: 'Acuíferos', features: [{ geometry: square(50, 50, 51, 51) }] },
    ];
    const found = crossings(profile, layers);
    expect(found).toHaveLength(1);
    expect(found[0].layerId).toBe('karst');
    expect(found[0].startKm).toBeCloseTo(haversineKm([0, 0], [1, 0]), 6);
    expect(found[0].endKm).toBeCloseTo(haversineKm([0, 0], [2, 0]), 6);
    expect(found[0].samples).toBe(3);
  });
});

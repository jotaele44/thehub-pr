import { describe, expect, it } from 'vitest';
import {
  PRECISION_STYLES, areaReferenceGroups, bboxAreaM2, boundaryProvenance, categoryColors, circleAreaM2, circlePolygon,
  describeArea, featurePaint, foldPlaceName, joinAreaReferences, municipalityAt, objectTypesOf, parseBboxText,
  visibleFeatures,
} from './propertyMap';

const square = (minLon, minLat, maxLon, maxLat) => ({
  type: 'Polygon',
  coordinates: [[[minLon, minLat], [maxLon, minLat], [maxLon, maxLat], [minLon, maxLat], [minLon, minLat]]],
});
const BOUNDARIES = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { NAME: 'Vieques Municipio', BASENAME: 'Vieques', GEOID: '72147' }, geometry: square(-65.6, 18.05, -65.2, 18.2) },
    { type: 'Feature', properties: { NAME: 'Mayagüez Municipio', BASENAME: 'Mayagüez', GEOID: '72097' },
      geometry: { type: 'MultiPolygon', coordinates: [square(-67.3, 18.1, -67.05, 18.3).coordinates, square(-67.95, 18.05, -67.85, 18.15).coordinates] } },
    { type: 'Feature', properties: { BASENAME: 'Holed' },
      geometry: { type: 'Polygon', coordinates: [square(-66, 18, -65.9, 18.1).coordinates[0], square(-65.97, 18.03, -65.93, 18.07).coordinates[0]] } },
  ],
};
const ref = (municipality, count, objectTypes = {}, extra = {}) => ({
  producer: 'ovnis-pr', stream: 'observations', category: 'uap_case', municipality_as_recorded: municipality, count,
  object_type_counts: objectTypes, ...extra,
});

describe('precision styling', () => {
  it('draws observed solid, interpreted ringed and representative hollow, never alike', () => {
    expect(PRECISION_STYLES.OBSERVED_POINT.marker).toBe('solid');
    expect(PRECISION_STYLES.INTERPRETED_POINT.marker).toBe('ringed');
    expect(PRECISION_STYLES.REPRESENTATIVE_POINT.marker).toBe('hollow');
    expect(PRECISION_STYLES.AREA_REFERENCE.marker).toBe('outline');
    const paint = featurePaint({ mineral_occurrence: '#E69F00' });
    // A representative point has no fill: only its ring is drawn.
    expect(paint['circle-opacity']).toEqual(['match', ['get', 'geometry_precision'], 'OBSERVED_POINT', 0.95, 'INTERPRETED_POINT', 0.55, 0]);
    expect(paint['circle-color']).toEqual(['match', ['get', 'category'], 'mineral_occurrence', '#E69F00', '#9ca3af']);
    expect(featurePaint({})['circle-color']).toBe('#9ca3af');
  });

  it('assigns category colours from the data in sorted order', () => {
    const colors = categoryColors([{ category: 'utility_asset' }, { category: 'CONTAMINATION' }, { category: 'utility_asset' }]);
    expect(Object.keys(colors)).toEqual(['CONTAMINATION', 'utility_asset']);
    expect(colors.CONTAMINATION).not.toBe(colors.utility_asset);
  });

  it('hides only the categories the viewer turned off', () => {
    const features = [{ properties: { category: 'a' } }, { properties: { category: 'b' } }];
    expect(visibleFeatures(features, new Set(['a']))).toEqual([features[1]]);
  });
});

describe('municipality join', () => {
  it('folds accents, case and the Municipio suffix', () => {
    expect(foldPlaceName('  MAYAGÜEZ  Municipio ')).toBe('mayaguez');
    expect(foldPlaceName('vieques')).toBe(foldPlaceName('Vieques Municipio'));
  });

  it('outlines exact municipio names and lists every other value as recorded', () => {
    const refs = [ref('vieques', 2, { UAP: 1, Lights: 1 }), ref('Mayaguez', 1, { UAP: 1 }), ref('southwest', 27, { UAP: 20, Other: 7 }),
      ref('Barceloneta/Arecibo', 1)];
    const join = joinAreaReferences(refs, BOUNDARIES);
    expect(join.matched).toEqual([
      { name: 'Vieques', count: 2, recordedAs: ['vieques'] },
      { name: 'Mayagüez', count: 1, recordedAs: ['Mayaguez'] },
    ]);
    // A region or a two-municipio value is never split or guessed.
    expect(join.unmatched).toEqual([{ value: 'southwest', count: 27 }, { value: 'Barceloneta/Arecibo', count: 1 }]);
    expect(join.matchedTotal).toBe(3);
    expect(join.outline.features.map((f) => f.properties)).toEqual([
      { municipio: 'Vieques', reference_count: 2, geometry_precision: 'AREA_REFERENCE' },
      { municipio: 'Mayagüez', reference_count: 1, geometry_precision: 'AREA_REFERENCE' },
    ]);
  });

  it('counts one object type when asked and joins nothing without a boundary layer', () => {
    const refs = [ref('vieques', 2, { UAP: 1, Lights: 1 }), ref('southwest', 3, { Mutilation: 3 })];
    expect(joinAreaReferences(refs, BOUNDARIES, { objectType: 'Mutilation' }).unmatched).toEqual([{ value: 'southwest', count: 3 }]);
    expect(joinAreaReferences(refs, BOUNDARIES, { objectType: 'Mutilation' }).matched).toEqual([]);
    const unjoined = joinAreaReferences(refs, null);
    expect(unjoined.matched).toEqual([]);
    expect(unjoined.outline.features).toEqual([]);
    expect(unjoined.unmatchedTotal).toBe(5);
  });

  it('never sums two producers or two streams into one group', () => {
    const groups = areaReferenceGroups([ref('vieques', 1), ref('vieques', 1, {}, { stream: 'entities' }),
      ref('Vieques', 1, {}, { producer: 'aguayluz-pr', category: 'utility_asset', stream: 'entities' })]);
    expect(groups.map((g) => g.key)).toEqual([
      'aguayluz-pr|entities|utility_asset', 'ovnis-pr|entities|uap_case', 'ovnis-pr|observations|uap_case']);
    expect(objectTypesOf([ref('a', 1, { UAP: 1 }), ref('b', 1, { Lights: 1, UAP: 1 })])).toEqual(['Lights', 'UAP']);
  });
});

describe('point in polygon', () => {
  it('finds the containing municipio, honours holes and multipolygons, and returns null outside', () => {
    expect(municipalityAt(BOUNDARIES, -65.4, 18.1)).toBe('Vieques');
    expect(municipalityAt(BOUNDARIES, -67.9, 18.1)).toBe('Mayagüez');
    expect(municipalityAt(BOUNDARIES, -65.99, 18.01)).toBe('Holed');
    expect(municipalityAt(BOUNDARIES, -65.95, 18.05)).toBeNull();
    expect(municipalityAt(BOUNDARIES, -66.5, 18.5)).toBeNull();
    expect(municipalityAt(null, -65.4, 18.1)).toBeNull();
  });
});

describe('areas', () => {
  it('measures a bbox and a circle on the reference sphere', () => {
    // One degree square at the equator is about 12,364 km².
    expect(bboxAreaM2([0, 0, 1, 1]) / 1e6).toBeCloseTo(12363.7, 0);
    expect(circleAreaM2(1000)).toBeCloseTo(Math.PI * 1e6, -1);
    const area = describeArea(4046.8564224);
    expect(area.acres).toBeCloseTo(1, 10);
    expect(area.hectares).toBeCloseTo(0.40468564224, 10);
  });

  it('draws a closed radius ring', () => {
    const ring = circlePolygon(-66.5, 18.2, 1000, 16).geometry.coordinates[0];
    expect(ring).toHaveLength(17);
    expect(ring[0][0]).toBeCloseTo(ring[16][0], 9);
    expect(ring[0][1]).toBeCloseTo(18.2 + 1000 / 6371008.8 * (180 / Math.PI), 6);
  });

  it('refuses a malformed or inverted AOI', () => {
    expect(parseBboxText('-66.6,18.1,-66.3,18.3')).toEqual([-66.6, 18.1, -66.3, 18.3]);
    for (const bad of ['', '1,2,3', 'a,b,c,d', '-66.3,18.1,-66.6,18.3', '-200,0,10,10']) {
      expect(() => parseBboxText(bad)).toThrow(/minLon,minLat,maxLon,maxLat/);
    }
  });
});

describe('boundary provenance', () => {
  it('reports the acquisition hashes and certification, and nothing when not loaded', () => {
    const layer = { snapshotSha256: 'a'.repeat(64), queryReceiptSha256: 'b'.repeat(64), certification: { status: 'PASS' },
      sourceManifest: { retrievalUtc: '2026-10-03T00:00:00Z' }, manifest: { featureCount: 78 } };
    const record = boundaryProvenance(layer, { sourceId: 's', certification: 'LIVE_PASS', outputCrs: 'EPSG:4326' },
      { label: 'U.S. Census TIGERweb', authority: 'U.S. Census Bureau' });
    expect(record).toMatchObject({ provider: 'U.S. Census TIGERweb', acquisitionStatus: 'PASS', featureCount: 78,
      snapshotSha256: 'a'.repeat(64), retrievedAt: '2026-10-03T00:00:00Z' });
    expect(boundaryProvenance(null)).toBeNull();
  });
});

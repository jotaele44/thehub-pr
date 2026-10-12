import { describe, expect, it } from 'vitest';
import { bboxAreaM2, polygonAreaM2 } from './propertyMap';
import {
  MIN_COMBINED_RECORDS, NOT_A_FINDING, aoiFromBbox, aoiFromMunicipio, aoisOverlap, binomialPValue, clopperPearson, compareAois,
  comparisonReceipt, formatP, rateRatioInterval,
} from './aoiComparison';

const square = (west, south, east, north) => ({
  type: 'Polygon', coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
});

describe('spherical polygon area', () => {
  it('matches the bbox area for a lon/lat rectangle and subtracts holes', () => {
    const box = [-66.5, 18.0, -66.0, 18.5];
    expect(polygonAreaM2(square(...box))).toBeCloseTo(bboxAreaM2(box), 3);
    const hole = [[-66.4, 18.1], [-66.4, 18.2], [-66.3, 18.2], [-66.3, 18.1], [-66.4, 18.1]];
    const withHole = { type: 'Polygon', coordinates: [...square(...box).coordinates, hole] };
    expect(polygonAreaM2(withHole)).toBeCloseTo(bboxAreaM2(box) - bboxAreaM2([-66.4, 18.1, -66.3, 18.2]), 3);
    const multi = { type: 'MultiPolygon', coordinates: [square(-66, 18, -65.9, 18.1).coordinates, square(-65.8, 18, -65.7, 18.1).coordinates] };
    expect(polygonAreaM2(multi)).toBeCloseTo(bboxAreaM2([-66, 18, -65.9, 18.1]) + bboxAreaM2([-65.8, 18, -65.7, 18.1]), 3);
    expect(polygonAreaM2({ type: 'Point', coordinates: [0, 0] })).toBe(0);
  });
});

describe('exact binomial test and interval (reference values from R binom.test)', () => {
  it('two-sided p-value, minimum-likelihood method', () => {
    expect(binomialPValue(8, 10, 0.5)).toBeCloseTo(0.109375, 9);
    expect(binomialPValue(0, 10, 0.5)).toBeCloseTo(0.001953125, 9);
    expect(binomialPValue(5, 10, 0.5)).toBe(1);
    // Not symmetric (p = 0.1): outcomes 0, 3, 4, 5... are no more likely than 3. Summed exactly with rational arithmetic: 0.444650.
    expect(binomialPValue(3, 20, 0.1)).toBeCloseTo(0.444650, 6);
  });

  it('Clopper-Pearson 95% interval', () => {
    const [low, high] = clopperPearson(8, 10);
    expect(low).toBeCloseTo(0.4439045, 5);
    expect(high).toBeCloseTo(0.9747893, 5);
    const [zeroLow, zeroHigh] = clopperPearson(0, 10);
    expect(zeroLow).toBe(0);
    expect(zeroHigh).toBeCloseTo(0.3084971, 5);
    expect(clopperPearson(10, 10)[1]).toBe(1);
  });

  it('turns the proportion into a rate ratio per unit area', () => {
    // Equal areas: ratio = p / (1 - p).
    const [low, high] = rateRatioInterval(8, 10, 1, 1);
    expect(low).toBeCloseTo(0.4439045 / (1 - 0.4439045), 4);
    expect(high).toBeCloseTo(0.9747893 / (1 - 0.9747893), 3);
    // Twice the study area halves the rate ratio for the same counts.
    expect(rateRatioInterval(8, 10, 2, 1)[0]).toBeCloseTo(low / 2, 4);
    expect(rateRatioInterval(10, 10, 1, 1)[1]).toBe(Infinity);
    expect(rateRatioInterval(0, 10, 1, 1)[0]).toBe(0);
  });
});

describe('AOIs', () => {
  it('builds a bbox AOI with its area and method, and refuses a malformed one', () => {
    const aoi = aoiFromBbox('study', 'Study', '-66.5, 18.0, -66.0, 18.5');
    expect(aoi.kind).toBe('bbox');
    expect(aoi.areaM2).toBeCloseTo(bboxAreaM2([-66.5, 18, -66, 18.5]), 3);
    expect(aoi.areaMethod).toMatch(/spherical/);
    expect(() => aoiFromBbox('x', 'X', '1,2,3')).toThrow(/minLon,minLat,maxLon,maxLat/);
  });

  it('builds a municipio AOI from the boundary layer by its recorded name, never from a near match', () => {
    const layer = { features: [{ type: 'Feature', properties: { NAME: 'Vieques Municipio', BASENAME: 'Vieques' }, geometry: square(-65.6, 18.05, -65.45, 18.2) }] };
    const aoi = aoiFromMunicipio('c1', 'Vieques', layer);
    expect(aoi.kind).toBe('municipio');
    expect(aoi.areaMethod).toMatch(/spherical/);
    expect(aoi.source).toMatch(/TIGERweb/);
    expect(() => aoiFromMunicipio('c2', 'Viequez', layer)).toThrow(/no municipio named "Viequez"/);
    expect(() => aoiFromMunicipio('c3', 'Vieques', null)).toThrow(/boundary layer is not loaded/);
  });

  it('detects overlap, containment and touching, and passes disjoint areas', () => {
    const a = square(0, 0, 2, 2);
    expect(aoisOverlap(a, square(3, 3, 4, 4))).toBe(false);
    expect(aoisOverlap(a, square(1, 1, 3, 3))).toBe(true); // crossing edges
    expect(aoisOverlap(a, square(0.5, 0.5, 1, 1))).toBe(true); // inside
    expect(aoisOverlap(square(0.5, 0.5, 1, 1), a)).toBe(true);
    expect(aoisOverlap(a, square(2, 0, 3, 2))).toBe(true); // sharing an edge counts: no record is counted twice
    const multi = { type: 'MultiPolygon', coordinates: [square(10, 10, 11, 11).coordinates, square(0.5, 0.5, 1, 1).coordinates] };
    expect(aoisOverlap(a, multi)).toBe(true);
    expect(aoisOverlap(square(5, 5, 6, 6), multi)).toBe(false);
  });
});

function point(id, lon, lat, precision, extra = {}) {
  return {
    type: 'Feature', id,
    geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: { evidence_id: id, producer: 'aguayluz-pr', stream: 'entities', category: 'utility_asset', geometry_precision: precision, ...extra },
  };
}
const box = (id, label, ...bounds) => aoiFromBbox(id, label, bounds.join(','));

describe('comparison against negative controls', () => {
  // Study 1 x 1 degree west of 0; control 2 x 1 degree east, so the control is twice the area.
  const study = box('s', 'Study', -1, 0, 0, 1);
  const control = box('c', 'Control', 1, 0, 3, 1);

  it('refuses what cannot be a comparison, with the reason', () => {
    expect(compareAois({ features: [], study, controls: [] }).errors).toEqual(['At least one control AOI is required.']);
    const overlapping = box('o', 'Overlap', -0.5, 0.5, 0.5, 1.5);
    expect(compareAois({ features: [], study, controls: [overlapping] }).errors[0]).toMatch(/Control "Overlap" overlaps the study AOI "Study"/);
    const twin = box('t', 'Twin', 1.5, 0, 2.5, 1);
    expect(compareAois({ features: [], study, controls: [control, twin] }).errors[0]).toMatch(/Controls "Control" and "Twin" overlap/);
    const flat = { ...study, id: 'f', label: 'Flat', areaM2: 0 };
    expect(compareAois({ features: [], study: flat, controls: [control] }).errors[0]).toMatch(/Flat has no area/);
  });

  it('counts only points whose declared precision places them, and keeps stand-ins separate', () => {
    const features = [
      point('a', -0.5, 0.5, 'OBSERVED_POINT'),
      point('b', -0.4, 0.5, 'INTERPRETED_POINT'),
      point('c', -0.3, 0.5, 'REPRESENTATIVE_POINT'),
      point('d', 2, 0.5, 'OBSERVED_POINT'),
      point('e', 9, 9, 'OBSERVED_POINT'), // outside every AOI
    ];
    const result = compareAois({ features, study, controls: [control] });
    expect(result.errors).toBeUndefined();
    const row = result.rows[0];
    expect(row.category).toBe('utility_asset');
    expect(row.study.count).toBe(2);
    expect(row.study.undetermined).toBe(1); // a stand-in position inside the study AOI: membership not determined
    expect(row.controls.count).toBe(1);
    expect(result.outside).toBe(1);
    expect(result.label).toBe(NOT_A_FINDING);
    expect(NOT_A_FINDING).toBe('BACKGROUND COMPARISON — not a finding');
  });

  it('computes densities per km2 from the areas used, and the ratio, interval and exact test', () => {
    // 8 study and 2 control records; the study is half the control's area.
    const features = [
      ...Array.from({ length: 8 }, (_, i) => point(`s${i}`, -0.9 + i * 0.1, 0.5, 'OBSERVED_POINT')),
      ...Array.from({ length: 2 }, (_, i) => point(`c${i}`, 1.5 + i, 0.5, 'OBSERVED_POINT')),
    ];
    const result = compareAois({ features, study, controls: [control] });
    const row = result.rows[0];
    const km2 = (aoi) => aoi.areaM2 / 1e6;
    expect(row.study.perKm2).toBeCloseTo(8 / km2(study), 9);
    expect(row.controls.perKm2).toBeCloseTo(2 / km2(control), 9);
    expect(row.status).toBe('COMPARED');
    expect(row.ratio).toBeCloseTo((8 / km2(study)) / (2 / km2(control)), 9);
    const [low, high] = rateRatioInterval(8, 10, km2(study), km2(control));
    expect(row.ci).toEqual([low, high]);
    expect(row.p).toBeCloseTo(binomialPValue(8, 10, km2(study) / (km2(study) + km2(control))), 12);
    expect(result.total.study.count).toBe(8);
    expect(result.areas.studyKm2).toBeCloseTo(km2(study), 9);
    expect(result.areas.controlsKm2).toBeCloseTo(km2(control), 9);
  });

  it('reports no ratio when there are too few records, instead of a number from nothing', () => {
    const features = [point('a', -0.5, 0.5, 'OBSERVED_POINT'), point('b', 2, 0.5, 'OBSERVED_POINT')];
    expect(features.length).toBeLessThan(MIN_COMBINED_RECORDS);
    const row = compareAois({ features, study, controls: [control] }).rows[0];
    expect(row.status).toBe('TOO_FEW');
    expect(row.ratio).toBeNull();
    expect(row.p).toBeNull();
    expect(row.ci).toBeNull();
  });

  it('keeps categories, streams and producers apart and states how many comparisons were made', () => {
    const many = (producer, category, stream) => Array.from({ length: 6 }, (_, i) => point(`${producer}${category}${i}`, -0.9 + i * 0.1, 0.5, 'OBSERVED_POINT', { producer, category, stream }));
    const features = [...many('p1', 'x', 'entities'), ...many('p2', 'x', 'entities'), ...many('p1', 'x', 'observations'), ...many('p1', 'y', 'entities')];
    const result = compareAois({ features, study, controls: [control] });
    expect(result.rows).toHaveLength(4);
    expect(new Set(result.rows.map((row) => row.key)).size).toBe(4);
    expect(result.comparisons).toBe(4);
    expect(result.multiplicity).toMatch(/4 comparisons.*not adjusted for multiple comparisons/);
  });

  it('with no control records the ratio is infinite and says so, with the exact test still valid', () => {
    const features = Array.from({ length: 6 }, (_, i) => point(`s${i}`, -0.9 + i * 0.1, 0.5, 'OBSERVED_POINT'));
    const row = compareAois({ features, study, controls: [control] }).rows[0];
    expect(row.status).toBe('COMPARED');
    expect(row.ratio).toBe(Infinity);
    expect(row.controls.count).toBe(0);
    expect(row.p).toBeLessThan(0.05);
  });

  it('builds a receipt that names its method, its areas and the store it was computed over', () => {
    const features = Array.from({ length: 6 }, (_, i) => point(`s${i}`, -0.9 + i * 0.1, 0.5, 'OBSERVED_POINT'));
    const result = compareAois({ features, study, controls: [control] });
    const receipt = comparisonReceipt({
      result, store: { kind: 'bounded-sample', cap_per_stream: 400, streams: { entities: { sampled: 6, actual: 600 } } },
      generatedAt: '2026-10-07T12:00:00.000Z', spatialContract: 'federation-spatial-features-v1',
    });
    expect(receipt.certification).toBe('NOT_CERTIFIED');
    expect(receipt.label).toBe(NOT_A_FINDING);
    expect(receipt.generated_at).toBe('2026-10-07T12:00:00.000Z');
    expect(receipt.store.sample).toBe(true);
    expect(receipt.store.text).toMatch(/bounded sample/);
    expect(receipt.aois.map((item) => [item.role, item.kind, item.area_method])).toEqual([
      ['study', 'bbox', expect.stringMatching(/spherical/)], ['control', 'bbox', expect.stringMatching(/spherical/)],
    ]);
    expect(receipt.method.membership).toMatch(/OBSERVED_POINT and INTERPRETED_POINT/);
    expect(receipt.method.test).toMatch(/exact conditional binomial/);
    expect(receipt.method.minimum_combined_records).toBe(MIN_COMBINED_RECORDS);
    expect(receipt.method.synthetic_records).toBe('excluded');
    expect(receipt.rows).toHaveLength(1);
    expect(receipt.rows[0].ratio).toBe('infinite (no control records)');
    expect(JSON.parse(JSON.stringify(receipt)).rows[0].ratio).toBe('infinite (no control records)');
  });
});

describe('p-value display', () => {
  it('prints three decimals and never a bare 0.000, which would read as a certainty', () => {
    expect(formatP(0.109375)).toBe('0.109');
    expect(formatP(1)).toBe('1.000');
    expect(formatP(0.001)).toBe('0.001');
    expect(formatP(0.0004)).toBe('<0.001');
    expect(formatP(0)).toBe('<0.001');
  });
});

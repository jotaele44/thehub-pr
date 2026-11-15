import { describe, expect, it } from 'vitest';
import {
  DIGITAL_TWIN_PANELS, activeIn, filterByTime, findingFeatures, findingStatement, geojsonExport, liveCounts, liveStatement,
  localMetres, panelFrom, timeBounds, timeWindow, usdaExport,
} from './digitalTwin';

function record(id, props = {}, coordinates = [-66.5, 18.2]) {
  return { type: 'Feature', id, geometry: { type: 'Point', coordinates },
    properties: { evidence_id: id, category: 'CONTAMINATION', producer: 'aguayluz-pr', geometry_precision: 'OBSERVED_POINT',
      time_start: null, time_end: null, temporal_state: 'UNKNOWN', ...props } };
}
const YEAR_1952 = { time_start: '1952-01-01T00:00:00.000Z', time_end: '1952-12-31T23:59:59.999Z' };
const ALERT_2019 = { time_start: '2019-10-01T00:00:00.000Z', time_end: '2019-12-31T00:00:00.000Z' };

describe('time', () => {
  const bounds = timeBounds({ start: '1952-01-01T00:00:00.000Z', end: '2020-01-01T00:00:00.000Z' });

  it('keeps a year-only record active anywhere in its year, never narrowed to a day', () => {
    const july = Date.parse('1952-07-01T00:00:00Z');
    expect(activeIn(YEAR_1952, [july, july])).toBe(true);
    expect(activeIn(YEAR_1952, [Date.parse('1953-01-02T00:00:00Z'), Date.parse('1953-02-01T00:00:00Z')])).toBe(false);
    expect(activeIn({ time_start: null }, [0, 1])).toBeNull();
  });

  it('windows are cumulative or trailing, and an absent extent means no filter', () => {
    const cursor = Date.parse('2019-11-01T00:00:00Z');
    expect(timeWindow(cursor, 'cumulative', bounds)).toEqual([bounds.start, cursor]);
    expect(timeWindow(cursor, 'month', bounds)).toEqual([cursor - 30 * 86_400_000, cursor]);
    expect(timeWindow(cursor, 'month', null)).toBeNull();
    expect(timeBounds(null)).toBeNull();
  });

  it('counts undated records instead of placing them in time', () => {
    const features = [record('a', YEAR_1952), record('b', ALERT_2019), record('c')];
    const window = timeWindow(Date.parse('1960-01-01T00:00:00Z'), 'cumulative', bounds);
    const shown = filterByTime(features, window);
    expect(shown.visible.map((f) => f.id)).toEqual(['a', 'c']);
    expect([shown.undated, shown.outside]).toEqual([1, 1]);
    expect(filterByTime(features, window, { showUndated: false }).visible.map((f) => f.id)).toEqual(['a']);
  });
});

describe('counters', () => {
  it('never calls a recent record live without a declared cadence', () => {
    const counts = liveCounts([record('a', { temporal_state: 'HISTORICAL' }), record('b', { temporal_state: 'CURRENT' })]);
    expect(counts).toEqual({ LIVE: 0, CURRENT: 1 });
    expect(liveStatement(counts)).toMatch(/^No live feed; 1 current/);
    expect(liveStatement({ LIVE: 0, CURRENT: 0 })).toMatch(/No producer declares a live cadence/);
    expect(liveStatement({ LIVE: 2, CURRENT: 0 })).toMatch(/^2 live/);
  });

  it('says why there are no findings on the map', () => {
    expect(findingFeatures([record('a'), record('f', { category: 'finding' })]).map((f) => f.id)).toEqual(['f']);
    expect(findingStatement(0)).toMatch(/findings ledger records none yet/);
    expect(findingStatement(2)).toBe('2 findings with declared geometry');
  });
});

describe('exports', () => {
  const features = [record('evo:alerts:a', ALERT_2019, [-66.5, 18.2]), record('evo:entities:"q"', {}, [-66.4, 18.3])];
  const context = { generatedAt: '2026-10-04T00:00:00.000Z', window: [Date.parse('2019-01-01T00:00:00Z'), Date.parse('2020-01-01T00:00:00Z')],
    filters: { hidden_categories: [] }, counts: { visible: 2 }, layers: { terrain: 'noaa-ncei-cudem-pr-ninth-m9525' } };

  it('GeoJSON keeps every evidence link and states the export provenance', () => {
    const body = geojsonExport(features, context);
    expect(body.federation_export).toMatchObject({ contract: 'federation-spatial-features-v1', certification: 'NOT_CERTIFIED',
      time_window: { from: '2019-01-01T00:00:00.000Z', to: '2020-01-01T00:00:00.000Z' } });
    expect(body.features.map((f) => f.properties.evidence_id)).toEqual(['evo:alerts:a', 'evo:entities:"q"']);
  });

  it('USD is one Points prim in local metres with z = 0 and escaped primvars', () => {
    const text = usdaExport(features, { ...context, origin: { lon: -66.5, lat: 18.2 } });
    expect(text.startsWith('#usda 1.0\n')).toBe(true);
    expect(text).toContain('def Points "FederationRecords"');
    expect(text).toContain('point3f[] points = [(0, 0, 0), (');
    expect(text).toContain('string vertical = "none: z = 0; terrain heights are not exported"');
    expect(text).toContain('string certification = "NOT_CERTIFIED"');
    expect(text).toContain('string[] primvars:evidence_id = ["evo:alerts:a", "evo:entities:\\"q\\""]');
    const [east, north] = localMetres(-66.4, 18.3, { lon: -66.5, lat: 18.2 });
    expect(east).toBeCloseTo(10563, -1);
    expect(north).toBeCloseTo(11119, -1);
  });
});

describe('panels', () => {
  it('deep-links only known panels', () => {
    expect(DIGITAL_TWIN_PANELS.map((p) => p.id)).toEqual(['perspective', 'ortho', 'overhead', 'details']);
    expect(panelFrom(new URLSearchParams('panel=ortho'))).toBe('ortho');
    expect(panelFrom(new URLSearchParams('panel=nope'))).toBeNull();
  });
});

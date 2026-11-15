import { describe, expect, it } from 'vitest';
import { CHART_RADIUS, projectSky } from '../skyChart';
import { computeHorizon } from './horizon';
import { functionTerrain } from './terrain';
import { coneOutline, horizonGeometry, overlayGeometry, pathData, projectPolyline } from './exclusionView';
import { angularSeparation } from './geometry';
import { parseObservation } from './observation';

const observer = { lat: 18.4663, lon: -66.1057 };
const observe = (direction, extra = {}) => parseObservation({ time: '2026-11-04T12:00:00Z', observer, direction: { azimuthReference: 'TRUE', ...direction }, ...extra });
const sky = (objects, unavailable = []) => ({ objects, unavailable });
const obj = (category, name, azimuth, elevation, separation, extra = {}) => ({ category, name, azimuth, elevation, state: 'MODELLED', separationFromSightlineDegrees: separation, insideSightline: false, aboveHorizon: elevation >= 0, terrain: 'NOT_CHECKED', ...extra });

describe('coneOutline', () => {
  it('is a ring of directions all the same angle from the centre, whatever the centre', () => {
    for (const centre of [{ azimuth: 0, elevation: 45 }, { azimuth: 270, elevation: 10 }, { azimuth: 123, elevation: 80 }, { azimuth: 10, elevation: 89.9 }]) {
      const ring = coneOutline(centre, 5);
      expect(ring).toHaveLength(72);
      for (const p of ring) expect(angularSeparation(centre.azimuth, centre.elevation, p.azimuth, p.elevation)).toBeCloseTo(5, 9);
    }
  });

  it('closes up: the last point is one step from the first, and the ring is not flat on the sky near the zenith', () => {
    const ring = coneOutline({ azimuth: 0, elevation: 90 }, 10, 36);
    expect(ring).toHaveLength(36);
    for (const p of ring) expect(p.elevation).toBeCloseTo(80, 6);
  });
});

describe('projectPolyline and pathData', () => {
  it('projects a ring above the horizon as one closed loop', () => {
    const p = projectPolyline(coneOutline({ azimuth: 90, elevation: 50 }, 5));
    expect(p.closed).toBe(true);
    expect(p.segments).toHaveLength(1);
    expect(pathData(p).startsWith('M')).toBe(true);
    expect(pathData(p).endsWith('Z')).toBe(true);
  });

  it('splits at the horizon: a ring that dips below it is drawn in the pieces above, open', () => {
    const p = projectPolyline(coneOutline({ azimuth: 90, elevation: 2 }, 5));
    expect(p.closed).toBe(false);
    expect(p.segments.length).toBeGreaterThanOrEqual(1);
    expect(pathData(p)).not.toContain('Z');
    const all = projectPolyline(coneOutline({ azimuth: 90, elevation: -30 }, 5));
    expect(all.segments).toEqual([]);
    expect(pathData(all)).toBe('');
  });
});

describe('overlayGeometry', () => {
  it('draws a tolerance sight line as a cone about its direction, at the chart position of that direction', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    const g = overlayGeometry(observation, sky([]));
    expect(g.sightline.kind).toBe('cone');
    const expected = projectSky(90, 45);
    expect(g.sightline.centreXY.x).toBeCloseTo(expected.x, 1);
    expect(g.sightline.centreXY.y).toBeCloseTo(expected.y, 1);
    expect(g.sightline.shapes).toHaveLength(1);
    expect(g.sightline.shapes[0]).toMatchObject({ at: 'start', closed: true, visible: true });
    expect(g.sightline.trackD).toBeNull();
    expect(g.sightline.belowHorizon).toBe(false);
  });

  it('draws a camera field of view as its outline, and says so', () => {
    const observation = observe({ azimuth: 180, elevation: 40, frustum: { horizontalFovDegrees: 60, verticalFovDegrees: 40, rollDegrees: 0 } });
    const g = overlayGeometry(observation, sky([]));
    expect(g.sightline.kind).toBe('frustum');
    expect(g.sightline.shapes[0].d.startsWith('M')).toBe(true);
    expect(g.sightline.shapes[0].closed).toBe(true);
  });

  it('draws a moving sight line as its start, its end and the track between them', () => {
    const observation = observe({ azimuth: 90, elevation: 30, toleranceDegrees: 2 }, { motion: { endAzimuth: 120, endElevation: 50, endTime: '2026-11-04T12:00:30Z' } });
    const g = overlayGeometry(observation, sky([]));
    expect(g.sightline.shapes.map((s) => s.at)).toEqual(['start', 'end']);
    expect(g.sightline.trackD.startsWith('M')).toBe(true);
    expect(g.sightline.trackD.split('L').length).toBe(25);
  });

  it('puts objects above the horizon on the chart, lists those below it by name, and never plots a negative altitude', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    const g = overlayGeometry(observation, sky([obj('celestial', 'Sun', 90, 45, 0), obj('celestial', 'Moon', 200, -20, 140), obj('aircraft', 'A', 10, 5, 60, { id: 'A', state: 'OBSERVED' })]));
    expect(g.objects.map((o) => o.name)).toEqual(['Sun', 'A']);
    expect(g.below).toEqual([{ category: 'celestial', name: 'Moon', elevation: -20 }]);
    for (const o of g.objects) expect(Math.hypot(o.x, o.y)).toBeLessThanOrEqual(CHART_RADIUS + 1e-6);
  });

  it('names every candidate and the four nearest objects that are not stars, and no star that is not a candidate', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    const stars = Array.from({ length: 30 }, (_, i) => obj('celestial', `star ${i}`, i * 10, 30 + (i % 5), 1 + i, { kind: 'star' }));
    const planets = Array.from({ length: 6 }, (_, i) => obj('celestial', `planet ${i}`, 20 + i * 20, 25, 40 + i, { kind: 'planet' }));
    const iss = obj('satellite', 'International Space Station', 300, 20, 100, { id: 'ISS' });
    const g = overlayGeometry(observation, sky([...stars, ...planets, iss]), [{ category: 'satellite', id: 'ISS', name: 'International Space Station' }]);
    const labelled = g.objects.filter((o) => o.labelled);
    expect(labelled.map((o) => o.name).sort()).toEqual(['International Space Station', 'planet 0', 'planet 1', 'planet 2', 'planet 3']);
    expect(g.objects.filter((o) => o.kind === 'star' && o.labelled)).toEqual([]);
    expect(g.objects.find((o) => o.id === 'ISS')).toMatchObject({ candidate: true, label: 'ISS', labelDx: 0, labelDy: -11, labelAnchor: 'middle' });
    const others = labelled.filter((o) => !o.candidate);
    expect(new Set(others.map((o) => o.labelDy)).size).toBe(others.length);
  });

  it('names a star when it is a candidate', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    const g = overlayGeometry(observation, sky([obj('celestial', 'Vega', 100, 40, 0.5, { kind: 'star' })]), [{ category: 'celestial', name: 'Vega' }]);
    expect(g.objects[0]).toMatchObject({ candidate: true, labelled: true, label: 'Vega' });
  });

  it('puts a label to the left of an object on the right half of the chart, and to the right of one on the left half', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    // east is at the left of the chart (x < 0), west at the right
    const g = overlayGeometry(observation, sky([obj('celestial', 'East', 90, 40, 1, { kind: 'planet' }), obj('celestial', 'West', 270, 40, 2, { kind: 'planet' })]));
    const east = g.objects.find((o) => o.name === 'East');
    const west = g.objects.find((o) => o.name === 'West');
    expect(east.x).toBeLessThan(0);
    expect(east).toMatchObject({ labelDx: 9, labelAnchor: 'start' });
    expect(west.x).toBeGreaterThan(30);
    expect(west).toMatchObject({ labelDx: -9, labelAnchor: 'end' });
  });

  it('carries the tracks with no position, so the chart can say they are not drawn', () => {
    const observation = observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 });
    const g = overlayGeometry(observation, sky([], [{ category: 'aircraft', name: 'B', id: 'B', reason: 'GAP' }]));
    expect(g.unavailable).toEqual([{ category: 'aircraft', name: 'B', id: 'B', reason: 'GAP' }]);
  });
});

describe('horizonGeometry', () => {
  const origin = { lon: -66.1057, lat: 18.4663 };
  const terrain = (f) => functionTerrain({ heightAt: f, datum: 'TEST', label: 'synthetic' });
  const polar = (lon, lat) => {
    const e = (lon - origin.lon) * 111320 * Math.cos((origin.lat * Math.PI) / 180);
    const n = (lat - origin.lat) * 110574;
    return { r: Math.hypot(e, n), az: ((Math.atan2(e, n) * 180) / Math.PI + 360) % 360 };
  };

  it('is nothing when there is no horizon', () => {
    expect(horizonGeometry(null)).toBeNull();
    expect(overlayGeometry(observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 }), sky([])).horizon).toBeNull();
  });

  it('shades only the ground that rises above the horizontal: a ridge makes a band, open sea makes none', () => {
    const sea = horizonGeometry(computeHorizon(terrain(() => 0), { ...origin, aboveGroundMetres: 2 }));
    const ridge = horizonGeometry(computeHorizon(terrain((lon, lat) => { const p = polar(lon, lat); return p.r >= 9000 && p.r <= 11000 && p.az >= 80 && p.az <= 100 ? 800 : 0; }), { ...origin, aboveGroundMetres: 2 }));
    expect(sea.noDataD).toBeNull();
    expect(sea.peak.elevation).toBeLessThan(0);
    // a profile at the rim everywhere: the polygon points all sit at the chart radius
    const radii = sea.maskD.split(' Z')[1].match(/-?\d+\.?\d* -?\d+\.?\d*/g).map((pair) => Math.hypot(...pair.split(' ').map(Number)));
    for (const r of radii) expect(r).toBeCloseTo(CHART_RADIUS, 0);
    expect(ridge.peak.elevation).toBeGreaterThan(4.9);
    expect(ridge.peak.azimuth).toBeGreaterThanOrEqual(80);
    expect(ridge.peak.azimuth).toBeLessThanOrEqual(100);
    const ridgeRadii = ridge.maskD.split(' Z')[1].match(/-?\d+\.?\d* -?\d+\.?\d*/g).map((pair) => Math.hypot(...pair.split(' ').map(Number)));
    expect(Math.min(...ridgeRadii)).toBeLessThan(CHART_RADIUS - 4);
    expect(ridge.maskD.startsWith('M0 -100 A100 100')).toBe(true);
  });

  it('marks the directions with no data as a dotted arc outside the rim, never as clear', () => {
    const holey = horizonGeometry(computeHorizon(terrain((lon, lat) => (polar(lon, lat).r > 5000 && polar(lon, lat).az > 60 && polar(lon, lat).az < 120 ? null : 0)), { ...origin, aboveGroundMetres: 2 }));
    expect(holey.noDataRays).toBeGreaterThan(100);
    expect(holey.noDataRays).toBeLessThan(holey.rays);
    expect(holey.noDataD.startsWith('M')).toBe(true);
    // the arc lies just outside the rim
    const points = holey.noDataD.match(/-?\d+\.?\d* -?\d+\.?\d*/g).map((pair) => Math.hypot(...pair.split(' ').map(Number)));
    for (const r of points) expect(r).toBeCloseTo(CHART_RADIUS + 3, 0);
  });

  it('is part of the overlay when a horizon is given', () => {
    const horizon = computeHorizon(terrain(() => 0), { ...origin, aboveGroundMetres: 2 });
    const g = overlayGeometry(observe({ azimuth: 90, elevation: 45, toleranceDegrees: 3 }), sky([]), [], horizon);
    expect(g.horizon.rays).toBe(720);
  });
});

import { describe, expect, it, vi } from 'vitest';
import { CUDEM_PR } from '../../gis/cudem';
import {
  MAX_GRID_CELLS, compositeTerrain, functionTerrain, gridTerrain, terrainFromCudem,
} from './terrain';

// heights = 100 + 1000 * lon + 2000 * lat: a plane, so bilinear interpolation reproduces it exactly
function planeGrid({ west = 0, south = 0, east = 1, north = 1, width = 11, height = 11, hole = null } = {}) {
  const heights = new Float32Array(width * height);
  const dx = (east - west) / (width - 1);
  const dy = (north - south) / (height - 1);
  for (let r = 0; r < height; r += 1) {
    for (let c = 0; c < width; c += 1) heights[r * width + c] = 100 + 1000 * (west + c * dx) + 2000 * (south + (height - 1 - r) * dy);
  }
  if (hole) for (const [r, c] of hole) heights[r * width + c] = Number.NaN;
  return { heights, width, height, bbox: [west, south, east, north], datum: 'TEST-DATUM', label: 'plane' };
}

describe('gridTerrain', () => {
  it('reproduces a plane exactly between the nodes and at them', () => {
    const t = gridTerrain(planeGrid());
    for (const [lon, lat] of [[0, 0], [1, 1], [0.5, 0.5], [0.123, 0.987], [0.999, 0.001]]) {
      expect(t.heightAt(lon, lat)).toBeCloseTo(100 + 1000 * lon + 2000 * lat, 3);
    }
    expect(t.datum).toBe('TEST-DATUM');
    expect(t.spacingDegrees).toBeCloseTo(0.1, 12);
  });

  it('has no data outside its box, and at a hole it uses the nearest node if that has data and says nothing otherwise', () => {
    const t = gridTerrain(planeGrid({ hole: [[5, 5]] }));
    expect(t.heightAt(-0.01, 0.5)).toBeNull();
    expect(t.heightAt(0.5, 1.01)).toBeNull();
    expect(t.heightAt(Number.NaN, 0.5)).toBeNull();
    // the node at row 5, column 5 is (0.5, 0.5) and is missing: asking exactly there has no data
    expect(t.heightAt(0.5, 0.5)).toBeNull();
    // next to the hole, in a cell with one missing corner, the nearest node answers when it has data
    expect(t.heightAt(0.54, 0.54)).toBeNull();
    expect(t.heightAt(0.58, 0.58)).toBeCloseTo(100 + 1000 * 0.6 + 2000 * 0.6, 3);
  });

  it('refuses a grid that is not a grid, a box that is inside out, and terrain with no declared datum', () => {
    const g = planeGrid();
    expect(() => gridTerrain({ ...g, heights: new Float32Array(5) })).toThrow(/at least 2 by 2/);
    expect(() => gridTerrain({ ...g, bbox: [1, 0, 0, 1] })).toThrow(/east beyond its west/);
    expect(() => gridTerrain({ ...g, datum: '' })).toThrow(/vertical datum/);
    expect(() => functionTerrain({ heightAt: () => 0 })).toThrow(/vertical datum/);
    expect(() => functionTerrain({ datum: 'X' })).toThrow(/heightAt/);
  });
});

describe('compositeTerrain', () => {
  it('lets the first terrain with data answer, and falls through where it has none', () => {
    const fine = gridTerrain({ ...planeGrid({ west: 0.4, south: 0.4, east: 0.6, north: 0.6, width: 21, height: 21 }), label: 'fine' });
    const coarse = gridTerrain({ ...planeGrid({ width: 6, height: 6 }), label: 'coarse' });
    const both = compositeTerrain([fine, coarse]);
    expect(both.heightAt(0.5, 0.5)).toBeCloseTo(100 + 500 + 1000, 3);
    expect(both.heightAt(0.9, 0.9)).toBeCloseTo(100 + 900 + 1800, 3);
    expect(both.heightAt(2, 2)).toBeNull();
    expect(both.label).toBe('fine over coarse');
    expect(both.spacingDegrees).toBeCloseTo(0.01, 12);
  });

  it('will not mix datums', () => {
    expect(() => compositeTerrain([gridTerrain(planeGrid()), gridTerrain({ ...planeGrid(), datum: 'OTHER' })])).toThrow(/different vertical datums/);
    expect(() => compositeTerrain([])).toThrow(/at least one/);
  });
});

describe('terrainFromCudem', () => {
  const centre = { lon: -66.1057, lat: 18.4663 };

  it('reads a fine grid near the observer and a coarse one to the radius, from the injected reader, and declares the datum and the bare-earth limit', async () => {
    const read = vi.fn(async ([west, south, east], width, height) => {
      const heights = new Float32Array(width * height);
      for (let r = 0; r < height; r += 1) {
        for (let c = 0; c < width; c += 1) heights[r * width + c] = 10 + 1000 * (west + ((east - west) * c) / (width - 1) - centre.lon);
      }
      return { heights, tilesRead: [`t${Math.round(south * 100)}`] };
    });
    const terrain = await terrainFromCudem(centre, { radiusKm: 30 }, { heightGrid: read });
    expect(read).toHaveBeenCalledTimes(2);
    const [near, far] = read.mock.calls;
    expect(near[0][2] - near[0][0]).toBeLessThan(far[0][2] - far[0][0]);
    expect(terrain.datum).toBe(CUDEM_PR.verticalDatum);
    expect(terrain.heightAt(centre.lon, centre.lat)).toBeCloseTo(10, 3);
    expect(terrain.heightAt(centre.lon + 0.2, centre.lat)).toBeCloseTo(10 + 200, 2);
    expect(terrain.source).toBe(CUDEM_PR.sourceId);
    expect(terrain.tilesRead.length).toBeGreaterThan(0);
    expect(terrain.caveats.join(' ')).toMatch(/Bare earth: buildings, trees/);
    expect(terrain.caveats.join(' ')).toMatch(/gravity-related, orthometric/);
    expect(terrain.label).toMatch(/within 5 km and a 223 m grid to 30 km/);
  });

  it('will not read outside CUDEM, or an enormous grid', async () => {
    await expect(terrainFromCudem({ lon: 2, lat: 48 }, {}, { heightGrid: vi.fn() })).rejects.toThrow(/outside the CUDEM coverage/);
    await expect(terrainFromCudem({ lon: Number.NaN, lat: 18 }, {}, { heightGrid: vi.fn() })).rejects.toThrow(/longitude and a latitude/);
    const small = vi.fn(async (bbox, width, height) => ({ heights: new Float32Array(width * height), tilesRead: [] }));
    await expect(terrainFromCudem(centre, { radiusKm: 200, farSpacingDegrees: 0.0001 }, { heightGrid: small })).rejects.toThrow(new RegExp(`at most ${MAX_GRID_CELLS}`));
  });

  it('carries missing data through as no data, not as zero', async () => {
    const read = async (_bbox, width, height) => ({ heights: new Float32Array(width * height).fill(Number.NaN), tilesRead: [] });
    const terrain = await terrainFromCudem(centre, { radiusKm: 10 }, { heightGrid: read });
    expect(terrain.heightAt(centre.lon, centre.lat)).toBeNull();
    expect(terrain.tilesRead).toEqual([]);
  });
});

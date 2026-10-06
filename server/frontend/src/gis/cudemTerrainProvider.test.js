import { describe, expect, it, vi } from 'vitest';
import { EllipsoidTerrainProvider, Math as CesiumMath, WebMercatorTilingScheme } from 'cesium';
import { IMAGERY_BASEMAPS } from './basemaps';
import { MIN_TERRAIN_LEVEL, ORTHO_MINIMUM_TERRAIN_LEVEL, createCudemTerrainProvider, tileHeights } from './cudemTerrainProvider';

const INSIDE = [-66.6, 18.1, -66.5, 18.2];

// The imagery level Cesium selects for a terrain tile (ImageryLayer's
// getLevelWithMaximumTexelSpacing, 256 px Web Mercator tiles).
function imageryLevel(terrain, level, latitude) {
  const scheme = new WebMercatorTilingScheme();
  const levelZero = (scheme.ellipsoid.maximumRadius * scheme.rectangle.width * Math.cos(CesiumMath.toRadians(latitude)))
    / (256 * scheme.getNumberOfXTilesAtLevel(0));
  return Math.round(Math.log2(levelZero / terrain.getLevelMaximumGeometricError(level)));
}

describe('CUDEM terrain tiles', () => {
  it('reads CUDEM for tiles over Puerto Rico and draws missing cells at 0', async () => {
    const grid = vi.fn(async () => ({ heights: Float32Array.from([10, Number.NaN, 30, 40]), tilesRead: ['t1'] }));
    const onTiles = vi.fn();
    const heights = await tileHeights(INSIDE, MIN_TERRAIN_LEVEL, { grid, samples: 2, onTiles });
    expect(Array.from(heights)).toEqual([10, 0, 30, 40]);
    expect(grid).toHaveBeenCalledWith(INSIDE, 2, 2);
    expect(onTiles).toHaveBeenCalledWith(['t1']);
  });

  it('is flat, without fetching, outside CUDEM coverage or at coarse levels', async () => {
    const grid = vi.fn();
    expect(Array.from(await tileHeights([-80, 30, -79, 31], 12, { grid, samples: 2 }))).toEqual([0, 0, 0, 0]);
    expect(Array.from(await tileHeights(INSIDE, MIN_TERRAIN_LEVEL - 1, { grid, samples: 2 }))).toEqual([0, 0, 0, 0]);
    expect(grid).not.toHaveBeenCalled();
  });

  it('hangs the orthoimagery only on terrain tiles whose own imagery level reaches its minimum zoom', () => {
    const { minzoom } = IMAGERY_BASEMAPS.usgsImagery;
    for (const terrain of [createCudemTerrainProvider(), new EllipsoidTerrainProvider()]) {
      for (const latitude of [17.75, 18.75]) {
        expect(imageryLevel(terrain, ORTHO_MINIMUM_TERRAIN_LEVEL, latitude)).toBe(minzoom);
        expect(imageryLevel(terrain, ORTHO_MINIMUM_TERRAIN_LEVEL - 1, latitude)).toBeLessThan(minzoom);
      }
    }
  });
});

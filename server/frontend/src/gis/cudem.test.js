import { describe, expect, it } from 'vitest';
import { fromArrayBuffer, writeArrayBuffer } from 'geotiff';
import { CUDEM_PR, CUDEM_TILES, CUDEM_TILE_NAMES, covers, elevationAt, formatElevation, heightGrid, tileBounds, tilesFor } from './cudem';

// A synthetic geographic GeoTIFF covering [west, south, west + size, south + size].
function syntheticTile(west, south, size, pixels, valueAt) {
  const values = new Float32Array(pixels * pixels);
  for (let row = 0; row < pixels; row += 1) {
    for (let col = 0; col < pixels; col += 1) values[row * pixels + col] = valueAt(row, col);
  }
  return writeArrayBuffer(values, {
    width: pixels, height: pixels, BitsPerSample: [32], SampleFormat: [3],
    ModelPixelScale: [size / pixels, size / pixels, 0],
    ModelTiepoint: [0, 0, 0, west, south + size, 0],
    GeographicTypeGeoKey: 4269,
  });
}

const TILES = [
  { name: 'a', url: 'mem://a', bbox: [0, 0, 1, 1] },
  { name: 'b', url: 'mem://b', bbox: [1, 0, 2, 1] },
];
const BUFFERS = {
  'mem://a': syntheticTile(0, 0, 1, 20, () => 100),
  // Tile b holds 200 except a nodata block in its north-east corner.
  'mem://b': syntheticTile(1, 0, 1, 20, (row, col) => (row < 5 && col >= 15 ? CUDEM_PR.nodata : 200)),
};
const open = (url) => fromArrayBuffer(BUFFERS[url]);

describe('CUDEM manifest', () => {
  it('lists the 26 published tiles and derives each from its north-west corner name', () => {
    // NOAA's urllist9525.txt lists 26 tiles (Spiderweb's registry note says 25).
    expect(CUDEM_TILE_NAMES).toHaveLength(26);
    expect(new Set(CUDEM_TILES.map((tile) => tile.url)).size).toBe(26);
    // The GeoTIFF tiepoint of n18x00_w066x00 is (-66.000185, 18.000185): the name is the NW corner.
    expect(tileBounds('ncei19_n18x00_w066x00_2022v2.tif')).toEqual([-66, 17.75, -65.75, 18]);
    expect(tileBounds('ncei19_n18x25_w068x00_2022v1.tif')).toEqual([-68, 18, -67.75, 18.25]);
    expect(() => tileBounds('elsewhere.tif')).toThrow(/not a CUDEM tile name/);
    for (const tile of CUDEM_TILES) {
      expect(tile.bbox[0]).toBeGreaterThanOrEqual(CUDEM_PR.extent[0]);
      expect(tile.bbox[2]).toBeLessThanOrEqual(CUDEM_PR.extent[2]);
    }
  });

  it('declares one vertical datum and states the height caveats', () => {
    expect(CUDEM_PR.verticalDatum).toMatch(/PRVD02, EPSG:6641/);
    expect(CUDEM_PR.heightCaveats.join(' ')).toMatch(/geoid separation/);
    expect(CUDEM_PR.heightCaveats.join(' ')).toMatch(/without a horizontal transformation/);
  });

  it('finds the tiles a box touches and nothing outside Puerto Rico', () => {
    expect(tilesFor([-66.1, 18.1, -66.05, 18.15]).map((tile) => tile.name)).toEqual(['ncei19_n18x25_w066x25_2022v2.tif']);
    expect(tilesFor([-60, 10, -59, 11])).toEqual([]);
    // A point on the meridian two tiles share touches both.
    expect(tilesFor([-66.5, 18.2, -66.5, 18.2]).map((tile) => tile.name))
      .toEqual(['ncei19_n18x25_w066x50_2022v2.tif', 'ncei19_n18x25_w066x75_2022v2.tif']);
    expect(covers([-66.5, 18.2, -66.4, 18.3])).toBe(true);
    expect(covers([-70, 18, -69, 19])).toBe(false);
  });
});

describe('CUDEM heights', () => {
  it('mosaics heights across tiles, rows north to south, and marks no-data cells', async () => {
    const { heights, tilesRead } = await heightGrid([0.1, 0.1, 1.9, 0.9], 5, 3, { open, tiles: TILES });
    expect(tilesRead).toEqual(['a', 'b']);
    const row = (r) => Array.from(heights.slice(r * 5, r * 5 + 5));
    // Columns at lon 0.1, 0.55 fall in a; 1.45, 1.9 in b; lon 1.0 sits on the shared edge.
    expect(row(2)[0]).toBe(100);
    expect(row(2)[4]).toBe(200);
    expect(row(0)[4]).toBeNaN(); // north-east nodata block in tile b
  });

  it('lists only the tiles that supplied heights', async () => {
    // The box touches tile a only along the shared edge, where a has no pixel column left.
    const { heights, tilesRead } = await heightGrid([1, 0.2, 1.5, 0.8], 3, 3, { open, tiles: TILES });
    expect(tilesRead).toEqual(['b']);
    expect(Array.from(heights)).toEqual(new Array(9).fill(200));
  });

  it('leaves cells outside every tile without data', async () => {
    const { heights, tilesRead } = await heightGrid([5, 5, 6, 6], 3, 3, { open, tiles: TILES });
    expect(tilesRead).toEqual([]);
    expect(Array.from(heights).every(Number.isNaN)).toBe(true);
  });

  it('reads a point elevation and formats it with its datum', async () => {
    const inA = await elevationAt(0.5, 0.5, { open, tiles: TILES });
    expect(inA).toEqual({ metres: 100, tile: 'a' });
    expect(formatElevation(inA)).toBe('100.0 m PRVD02 · CUDEM m9525 1/9″');
    expect(await elevationAt(1.95, 0.95, { open, tiles: TILES })).toBeNull(); // nodata
    // On the edge a and b share, the height and the tile named are the tile that holds the pixel.
    expect(await elevationAt(1, 0.5, { open, tiles: TILES })).toEqual({ metres: 200, tile: 'b' });
    expect(await elevationAt(9, 9, { open, tiles: TILES })).toBeNull(); // outside coverage
    expect(formatElevation(null)).toBeNull();
  });
});

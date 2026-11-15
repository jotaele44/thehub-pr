import { describe, expect, it } from 'vitest';
import { fromArrayBuffer, writeArrayBuffer } from 'geotiff';
import { GEOID18_PR, formatHeight, geoidBinding, geoidCovers, geoidHeight, readGeoidGrid, sharedDatum } from './geoid';

// A synthetic geoid GeoTIFF in NGS's layout: longitudes 0-360, rows north to south.
function geoidTiff({ width, height, west, north, step, rasterType, valueAt }) {
  const values = new Float32Array(width * height);
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) values[row * width + col] = valueAt(col, row);
  }
  return writeArrayBuffer(values, {
    width, height, BitsPerSample: [32], SampleFormat: [3],
    ModelPixelScale: [step, step, 0],
    ModelTiepoint: [0, 0, 0, west, north, 0],
    GeographicTypeGeoKey: 6318,
    GTRasterTypeGeoKey: rasterType,
  });
}

// Node (col, row) holds -40 - col - 10 * row, so the field is linear and bilinear
// interpolation must reproduce it exactly.
const linear = (col, row) => -40 - col - 10 * row;
const POINT = 2;
const AREA = 1;
const SPEC = { width: 5, height: 4, west: 291, north: 21, step: 0.5, valueAt: linear };

describe('GEOID18 grid', () => {
  it('puts the first node at the tiepoint for a PixelIsPoint grid', async () => {
    const grid = await readGeoidGrid(await fromArrayBuffer(geoidTiff({ ...SPEC, rasterType: POINT })));
    expect([grid.originLon, grid.originLat, grid.stepLon, grid.stepLat]).toEqual([291, 21, 0.5, -0.5]);
    // 291 east is -69 west; the node at (col 1, row 2) is at lon -68.5, lat 20.
    expect(geoidHeight(grid, -68.5, 20)).toBe(linear(1, 2));
  });

  it('moves a PixelIsArea tiepoint from the cell corner to the node', async () => {
    const grid = await readGeoidGrid(await fromArrayBuffer(geoidTiff({ ...SPEC, rasterType: AREA })));
    expect(grid.originLon).toBeCloseTo(291.25, 12);
    expect(grid.originLat).toBeCloseTo(20.75, 12);
  });

  it('interpolates bilinearly and reproduces nodes exactly', async () => {
    const grid = await readGeoidGrid(await fromArrayBuffer(geoidTiff({ ...SPEC, rasterType: POINT })));
    expect(geoidHeight(grid, -69, 21)).toBe(linear(0, 0));
    expect(geoidHeight(grid, -67, 19.5)).toBe(linear(4, 3));
    // A quarter of the way east and a third of the way south of node (1, 1): linear field, exact.
    const lon = -68.5 + 0.25 * 0.5;
    const lat = 20.5 - (1 / 3) * 0.5;
    expect(geoidHeight(grid, lon, lat)).toBeCloseTo(-40 - (1 + 0.25) - 10 * (1 + 1 / 3), 4);
  });

  it('reports no height outside the grid or beside a node without a value', async () => {
    const grid = await readGeoidGrid(await fromArrayBuffer(geoidTiff({
      ...SPEC, rasterType: POINT, valueAt: (col, row) => (col === 2 && row === 1 ? Number.NaN : linear(col, row)),
    })));
    expect(geoidHeight(grid, -70, 20)).toBeNull();
    expect(geoidHeight(grid, -68, 22)).toBeNull();
    expect(geoidHeight(grid, -66.9, 20)).toBeNull();
    expect(geoidHeight(grid, -68.2, 20.4)).toBeNull(); // the cell touching the empty node
    expect(geoidHeight(grid, -68.9, 20.9)).not.toBeNull();
  });

  it('accepts longitudes in either convention', async () => {
    const grid = await readGeoidGrid(await fromArrayBuffer(geoidTiff({ ...SPEC, rasterType: POINT })));
    expect(geoidHeight(grid, 291.5, 20)).toBe(geoidHeight(grid, -68.5, 20));
  });
});

describe('GEOID18 binding and heights', () => {
  const cudem = { status: 'READY_FOR_RUNTIME_BINDING', verticalDatum: 'PRVD02 (EPSG:6641)' };

  it('binds only a certified terrain whose datum is the geoid\'s orthometric datum', () => {
    expect(geoidBinding(cudem).status).toBe('BOUND');
    expect(geoidBinding({ ...cudem, status: 'OPEN_VERTICAL_DATUM' }).status).toBe('NOT_BOUND');
    expect(geoidBinding(null).reason).toMatch(/no certified terrain/);
    const other = geoidBinding({ ...cudem, verticalDatum: 'NAVD88 (EPSG:5703)' });
    expect(other.status).toBe('NOT_BOUND');
    expect(other.reason).toMatch(/NAVD88 \(EPSG:5703\); GEOID18 relates PRVD02/);
    expect(geoidBinding({ status: 'READY_FOR_RUNTIME_BINDING' }).reason).toMatch(/undeclared datum/);
  });

  it('knows its extent', () => {
    expect(GEOID18_PR.extent).toEqual([-69, 15, -64, 21]);
    expect(geoidCovers([-66.2, 18.3, -66.1, 18.5])).toBe(true);
    expect(geoidCovers([-80, 30, -79, 31])).toBe(false);
  });

  it('labels a height with its datum, or says the datum is not declared', () => {
    expect(formatHeight({ value: 1322.74, datum: 'PRVD02', source: 'CUDEM m9525 1/9″' })).toBe('1322.7 m PRVD02 · CUDEM m9525 1/9″');
    expect(formatHeight({ value: 12, datum: 'NAD83(2011) ellipsoidal' })).toBe('12.0 m NAD83(2011) ellipsoidal');
    expect(formatHeight({ value: 5 })).toBe('5.0 m (datum not declared)');
    expect(formatHeight({ value: Number.NaN, datum: 'PRVD02' })).toBeNull();
  });

  it('refuses to put heights of different or undeclared datums on one axis', () => {
    expect(sharedDatum([{ datum: 'PRVD02' }, { datum: 'PRVD02' }])).toBe('PRVD02');
    expect(() => sharedDatum([{ datum: 'PRVD02' }, { datum: 'NAD83(2011) ellipsoidal' }])).toThrow(/different or undeclared datums/);
    expect(() => sharedDatum([{ datum: 'PRVD02' }, {}])).toThrow(/different or undeclared datums/);
  });
});

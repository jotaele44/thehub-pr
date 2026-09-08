import { describe, expect, it } from 'vitest';
import { validatePointCloudFixture, validateTilesetStructure } from './advanced3dStructure';

describe('advanced 3D structural gates', () => {
  it('accepts a bounded 3D Tiles 1.1 fixture without promoting spatial identity', () => {
    const result = validateTilesetStructure({
      asset: { version: '1.1' },
      geometricError: 500,
      root: {
        boundingVolume: { box: [6378137, 0, 0, 10, 0, 0, 0, 10, 0, 0, 0, 10] },
        geometricError: 0,
        content: { uri: 'empty.gltf' },
      },
    });
    expect(result.status).toBe('PASS_STRUCTURAL_3D_TILES_1_1');
    expect(result.spatialIdentityCertified).toBe(false);
    expect(result.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });

  it('rejects unsafe or malformed tileset content references', () => {
    expect(() => validateTilesetStructure({
      asset: { version: '1.1' }, geometricError: 1,
      root: { boundingVolume: { box: Array(12).fill(0) }, geometricError: 0, content: { uri: '../escape.gltf' } },
    })).toThrow(/bounded and relative/);
  });

  it('keeps finite XYZ point-cloud Z semantics open without a uniform vertical datum', () => {
    const result = validatePointCloudFixture({
      rows: ['200000 300000 100', '200010 300000 101'],
      crs: 'EPSG:6566',
      verticalDatum: 'UNRESOLVED',
      verticalDatumStatus: 'UNRESOLVED',
    });
    expect(result.status).toBe('OPEN_VERTICAL_DATUM');
    expect(result.pointCount).toBe(2);
    expect(result.spatialIdentityCertified).toBe(false);
  });

  it('fails malformed XYZ rows', () => {
    expect(() => validatePointCloudFixture({ rows: ['200000 x 100'], crs: 'EPSG:6566' })).toThrow(/finite X Y Z/);
  });
});

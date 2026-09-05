import { describe, expect, it } from 'vitest';
import { ADVANCED_3D_FIXTURES, evaluatedAdvanced3dFixtures } from './advanced3dFixtures';

describe('advanced 3D promotion fixtures', () => {
  it('keeps mixed-datum terrain normalization-open', () => {
    const terrain = evaluatedAdvanced3dFixtures().find((x) => x.kind === 'terrain');
    expect(terrain.status).toBe('OPEN_VERTICAL_DATUM');
    expect(terrain.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });

  it('binds a real local 3D Tiles tileset without promoting spatial identity', () => {
    const tiles = evaluatedAdvanced3dFixtures().find((x) => x.kind === '3d-tiles');
    expect(tiles.status).toBe('READY_FOR_RUNTIME_BINDING');
    expect(tiles.hrefManifestation).toBe('/fixtures/gis/3dtiles/tileset.json');
    expect(tiles.tilesetVersion).toBe('1.1');
    expect(tiles.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });

  it('requires explicit horizontal CRS for point-cloud fixture while leaving vertical datum unresolved', () => {
    const cloud = evaluatedAdvanced3dFixtures().find((x) => x.kind === 'point-cloud');
    expect(cloud.status).toBe('READY_FOR_RUNTIME_BINDING');
    expect(cloud.crs).toBe('EPSG:6566');
    expect(cloud.verticalDatum).toBe('UNRESOLVED');
    expect(cloud.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });

  it('contains exactly one bounded fixture per advanced kind', () => {
    expect(new Set(ADVANCED_3D_FIXTURES.map((x) => x.kind))).toEqual(new Set(['terrain', '3d-tiles', 'point-cloud']));
  });
});

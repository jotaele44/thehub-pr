import { describe, expect, it } from 'vitest';
import { certifyAdvanced3dSource } from './advanced3dContracts';

describe('advanced 3D source contracts', () => {
  it('requires a bound uniform vertical datum before terrain runtime binding', () => {
    const missing = certifyAdvanced3dSource({ kind: 'terrain', sourceId: 'terrain-a', hrefManifestation: 'https://example.invalid/terrain' });
    expect(missing.status).toBe('OPEN_VERTICAL_DATUM');

    const mixed = certifyAdvanced3dSource({
      kind: 'terrain',
      sourceId: 'terrain-mixed',
      hrefManifestation: 'https://example.invalid/terrain',
      verticalDatum: 'gravity-related mixed coverage',
      verticalDatumStatus: 'MIXED_COVERAGE',
    });
    expect(mixed.status).toBe('OPEN_VERTICAL_DATUM');
    expect(mixed.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');

    const bound = certifyAdvanced3dSource({
      kind: 'terrain',
      sourceId: 'terrain-bound',
      hrefManifestation: 'https://example.invalid/terrain',
      verticalDatum: 'EGM96',
      verticalDatumStatus: 'UNIFORM_BOUND',
    });
    expect(bound.status).toBe('READY_FOR_RUNTIME_BINDING');
  });

  it('requires CRS for point clouds', () => {
    const result = certifyAdvanced3dSource({ kind: 'point-cloud', sourceId: 'pc-a', hrefManifestation: 'https://example.invalid/cloud.laz' });
    expect(result.status).toBe('OPEN_CRS');
  });

  it('permits metadata-complete 3D Tiles candidates without promoting identity', () => {
    const result = certifyAdvanced3dSource({ kind: '3d-tiles', sourceId: 'tiles-a', hrefManifestation: 'https://example.invalid/tileset.json' });
    expect(result.status).toBe('READY_FOR_RUNTIME_BINDING');
    expect(result.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });
});

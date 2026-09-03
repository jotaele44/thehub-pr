import { describe, expect, it } from 'vitest';
import { certifyAdvanced3dSource } from './advanced3dContracts';

describe('advanced 3D source contracts', () => {
  it('requires a vertical datum before terrain runtime binding', () => {
    const result = certifyAdvanced3dSource({ kind: 'terrain', sourceId: 'terrain-a', hrefManifestation: 'https://example.invalid/terrain' });
    expect(result.status).toBe('OPEN_VERTICAL_DATUM');
    expect(result.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });

  it('requires CRS for point clouds', () => {
    const result = certifyAdvanced3dSource({ kind: 'point-cloud', sourceId: 'pc-a', hrefManifestation: 'https://example.invalid/cloud.laz' });
    expect(result.status).toBe('OPEN_CRS');
  });

  it('permits metadata-complete candidates without promoting identity', () => {
    const result = certifyAdvanced3dSource({ kind: '3d-tiles', sourceId: 'tiles-a', hrefManifestation: 'https://example.invalid/tileset.json' });
    expect(result.status).toBe('READY_FOR_RUNTIME_BINDING');
    expect(result.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });
});

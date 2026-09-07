import { describe, expect, it } from 'vitest';
import { ADVANCED_3D_SOURCES, evaluatedAdvanced3dSources } from './advanced3dSourceRegistry';

describe('advanced 3D source registry', () => {
  it('registers the real Terrain3D service without promoting runtime certification', () => {
    expect(ADVANCED_3D_SOURCES[0]).toMatchObject({
      sourceId: 'esri-worldelevation3d-terrain3d',
      kind: 'terrain',
      verticalDatumStatus: 'MIXED_COVERAGE',
    });
    const evaluated = evaluatedAdvanced3dSources()[0];
    expect(evaluated.status).toBe('OPEN_VERTICAL_DATUM');
    expect(evaluated.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });
});

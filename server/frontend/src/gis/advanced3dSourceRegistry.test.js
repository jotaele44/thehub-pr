import { describe, expect, it } from 'vitest';
import { ADVANCED_3D_SOURCES, evaluatedAdvanced3dSources, terrainSource } from './advanced3dSourceRegistry';
import { TERRAIN_VERTICAL_DATUM_READY_STATUS } from './advanced3dContracts';

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

  it('binds only the uniform-datum CUDEM terrain; the mixed-coverage source stays open', () => {
    const cudem = terrainSource('noaa-ncei-cudem-pr-ninth-m9525');
    expect(cudem).toMatchObject({ verticalDatum: 'PRVD02 (EPSG:6641)', verticalDatumStatus: TERRAIN_VERTICAL_DATUM_READY_STATUS });
    expect(cudem.status).toBe('READY_FOR_RUNTIME_BINDING');
    expect(terrainSource('esri-worldelevation3d-terrain3d').status).toBe('OPEN_VERTICAL_DATUM');
    expect(terrainSource('nowhere')).toBeNull();
  });
});

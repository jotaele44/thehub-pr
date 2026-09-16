import { describe, expect, it } from 'vitest';
import { certifyCogFromValidatorReceipt, inspectCogStructure } from './cogCertification';

describe('COG certification contract', () => {
  it('classifies a tiled TIFF only as a COG candidate', () => {
    const result = inspectCogStructure({
      TileWidth: 256,
      TileLength: 256,
      TileOffsets: [1024, 2048],
      TileByteCounts: [900, 900],
    });
    expect(result.status).toBe('COG_CANDIDATE_REQUIRES_BYTE_LAYOUT_VALIDATOR');
    expect(result.cogCertified).toBe(false);
  });

  it('rejects strip-organized TIFF as COG', () => {
    expect(inspectCogStructure({ StripOffsets: [1024], StripByteCounts: [500] }).status).toBe('NOT_COG_STRIP_LAYOUT');
  });

  it('requires an external validator PASS and whole-asset hash', () => {
    const structure = inspectCogStructure({ TileWidth: 256, TileLength: 256, TileOffsets: [1024], TileByteCounts: [900] });
    expect(() => certifyCogFromValidatorReceipt(structure, { status: 'PASS', validator: 'OTHER' })).toThrow(/GDAL_COG_VALIDATOR/);
    expect(() => certifyCogFromValidatorReceipt(structure, { status: 'PASS', validator: 'GDAL_COG_VALIDATOR' })).toThrow(/whole-asset/);
    const certified = certifyCogFromValidatorReceipt(structure, {
      status: 'PASS',
      validator: 'GDAL_COG_VALIDATOR',
      validatorVersion: 'fixture',
      fullAssetSha256: 'a'.repeat(64),
    });
    expect(certified.status).toBe('COG_PASS_BOUNDED');
    expect(certified.cogCertified).toBe(true);
  });
});

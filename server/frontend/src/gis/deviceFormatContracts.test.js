import { describe, expect, it } from 'vitest';
import { classifyDeviceFormat, requireParsedFormatContract } from './deviceFormatContracts';

describe('device format contracts', () => {
  it('classifies extensions as discovery only', () => {
    expect(classifyDeviceFormat('raw.KMZ')).toMatchObject({ rawName: 'raw.KMZ', extension: 'kmz', format: 'KMZ', status: 'DISCOVERY_ONLY' });
    expect(classifyDeviceFormat('data.gpkg').format).toBe('GEOPACKAGE');
    expect(classifyDeviceFormat('archive.zip').format).toBe('ARCHIVE_UNRESOLVED');
  });

  it('does not permit extension discovery to become parsed identity', () => {
    expect(() => requireParsedFormatContract(classifyDeviceFormat('points.csv'))).toThrow(/schema\/encoding\/CRS inspection/);
  });

  it('keeps RAW and NORMALIZED hashes separate after parsing', () => {
    const result = requireParsedFormatContract({ status: 'PARSED_WITH_SCHEMA', rawSha256: 'raw', normalizedSha256: 'normalized' });
    expect(result.rawSha256).not.toBe(result.normalizedSha256);
    expect(result.canonicalIdentityStatus).toBe('CANDIDATE_NOT_IDENTITY');
  });
});

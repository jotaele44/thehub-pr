import { describe, expect, it } from 'vitest';
import { assertRasterGeometryReadyForDirectWgs84Placement, inspectRasterGeometry } from './rasterCertification';

function imageFixture({ epsg = 4326, origin = [-67, 19], resolution = [0.001, -0.001], bbox = [-67, 18, -66, 19] } = {}) {
  return {
    getWidth: () => 1000,
    getHeight: () => 1000,
    getGeoKeys: () => ({ GeographicTypeGeoKey: epsg }),
    getOrigin: () => origin,
    getResolution: () => resolution,
    getBoundingBox: () => bbox,
  };
}

describe('raster geometry certification', () => {
  it('certifies only finite native EPSG:4326 affine geometry', () => {
    const result = inspectRasterGeometry(imageFixture());
    expect(result.status).toBe('PASS_NATIVE_WGS84_AFFINE');
    expect(result.pixelGeometryCertified).toBe(true);
    expect(assertRasterGeometryReadyForDirectWgs84Placement(result)).toBe(result);
  });

  it('fails closed when projected CRS requires reprojection', () => {
    const image = imageFixture();
    image.getGeoKeys = () => ({ ProjectedCSTypeGeoKey: 26920 });
    const result = inspectRasterGeometry(image);
    expect(result.status).toBe('OPEN_REPROJECTION_REQUIRED');
    expect(result.pixelGeometryCertified).toBe(false);
    expect(() => assertRasterGeometryReadyForDirectWgs84Placement(result)).toThrow(/not certified/);
  });

  it('keeps Puerto Rico State Plane EPSG:6566 reprojection-open', () => {
    const image = imageFixture({ origin: [200000, 300000], resolution: [1, -1], bbox: [200000, 299000, 201000, 300000] });
    image.getGeoKeys = () => ({ ProjectedCSTypeGeoKey: 6566 });
    const result = inspectRasterGeometry(image);
    expect(result.crs).toBe('EPSG:6566');
    expect(result.status).toBe('OPEN_REPROJECTION_REQUIRED');
    expect(result.pixelGeometryCertified).toBe(false);
  });

  it('fails closed on missing CRS and degenerate transforms', () => {
    const missing = imageFixture();
    missing.getGeoKeys = () => ({});
    expect(inspectRasterGeometry(missing).status).toBe('UNRESOLVED_CRS');
    expect(inspectRasterGeometry(imageFixture({ resolution: [0, -0.001] })).status).toBe('UNRESOLVED_GEOTRANSFORM');
  });
});

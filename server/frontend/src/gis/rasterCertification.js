const EPSG_PATTERN = /^EPSG:(\d+)$/i;

function finitePair(value) {
  return Array.isArray(value) && value.length >= 2 && value.slice(0, 2).every((item) => Number.isFinite(Number(item)));
}

function finiteBbox(value) {
  return Array.isArray(value) && value.length >= 4 && value.slice(0, 4).every((item) => Number.isFinite(Number(item)));
}

function normalizeCrs(image) {
  const geoKeys = image.getGeoKeys?.() || {};
  const projected = Number(geoKeys.ProjectedCSTypeGeoKey);
  const geographic = Number(geoKeys.GeographicTypeGeoKey);
  if (Number.isInteger(projected) && projected > 0 && projected !== 32767) return `EPSG:${projected}`;
  if (Number.isInteger(geographic) && geographic > 0 && geographic !== 32767) return `EPSG:${geographic}`;
  return null;
}

export function inspectRasterGeometry(image) {
  if (!image) throw new Error('raster certification requires a GeoTIFF image');
  const width = Number(image.getWidth?.());
  const height = Number(image.getHeight?.());
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    throw new Error('raster certification requires positive integer dimensions');
  }

  const origin = image.getOrigin?.();
  const resolution = image.getResolution?.();
  const bbox = image.getBoundingBox?.();
  const crs = normalizeCrs(image);
  const crsMatch = crs?.match(EPSG_PATTERN);
  const epsg = crsMatch ? Number(crsMatch[1]) : null;
  const hasFiniteTransform = finitePair(origin) && finitePair(resolution) && Number(resolution[0]) !== 0 && Number(resolution[1]) !== 0;
  const hasFiniteBbox = finiteBbox(bbox) && Number(bbox[0]) < Number(bbox[2]) && Number(bbox[1]) < Number(bbox[3]);
  const isWgs84 = epsg === 4326;

  let status = 'OPEN_REPROJECTION_REQUIRED';
  if (!crs) status = 'UNRESOLVED_CRS';
  else if (!hasFiniteTransform || !hasFiniteBbox) status = 'UNRESOLVED_GEOTRANSFORM';
  else if (isWgs84) status = 'PASS_NATIVE_WGS84_AFFINE';

  return Object.freeze({
    width,
    height,
    crs,
    epsg,
    origin: finitePair(origin) ? Object.freeze(origin.slice(0, 2).map(Number)) : null,
    resolution: finitePair(resolution) ? Object.freeze(resolution.slice(0, 2).map(Number)) : null,
    bbox: finiteBbox(bbox) ? Object.freeze(bbox.slice(0, 4).map(Number)) : null,
    hasFiniteTransform,
    hasFiniteBbox,
    status,
    pixelGeometryCertified: status === 'PASS_NATIVE_WGS84_AFFINE',
    reprojectionRequired: status === 'OPEN_REPROJECTION_REQUIRED',
  });
}

export function assertRasterGeometryReadyForDirectWgs84Placement(inspection) {
  if (inspection?.status !== 'PASS_NATIVE_WGS84_AFFINE') {
    throw new Error(`raster pixel geometry is not certified for direct WGS84 placement: ${inspection?.status || 'UNRESOLVED'}`);
  }
  return inspection;
}

const FORMAT_BY_EXTENSION = Object.freeze({
  geojson: 'GEOJSON', json: 'GEOJSON', kml: 'KML', kmz: 'KMZ', shp: 'SHAPEFILE_COMPONENT', zip: 'ARCHIVE_UNRESOLVED',
  gpkg: 'GEOPACKAGE', csv: 'DELIMITED_TEXT', tsv: 'DELIMITED_TEXT', gpx: 'GPX', pmtiles: 'PMTILES', tif: 'GEOTIFF', tiff: 'GEOTIFF',
});

export function classifyDeviceFormat(filename) {
  const rawName = String(filename || '');
  const extension = rawName.includes('.') ? rawName.split('.').pop().toLowerCase() : '';
  const format = FORMAT_BY_EXTENSION[extension] || 'UNSUPPORTED';
  return Object.freeze({ rawName, extension, format, status: format === 'UNSUPPORTED' ? 'BLOCKED_UNSUPPORTED' : 'DISCOVERY_ONLY' });
}

export function requireParsedFormatContract(candidate) {
  if (!candidate || candidate.status !== 'PARSED_WITH_SCHEMA') {
    throw new Error('device format cannot be promoted before schema/encoding/CRS inspection');
  }
  if (!candidate.rawSha256 || !candidate.normalizedSha256) throw new Error('RAW and NORMALIZED identities must remain separate and hashed');
  return Object.freeze({ ...candidate, canonicalIdentityStatus: candidate.canonicalIdentityStatus || 'CANDIDATE_NOT_IDENTITY' });
}

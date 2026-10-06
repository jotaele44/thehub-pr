import { certifyAdvanced3dSource } from './advanced3dContracts';
import { CUDEM_PR } from './cudem';

// Esri documents WorldElevation3D/Terrain3D as the default cached elevation
// source for ArcGIS scenes, but also documents mixed gravity-related coverage
// rather than one uniform vertical coordinate system. Keep this source real and
// usable for discovery while fail-closing runtime certification until a bounded
// vertical-datum normalization contract is supplied.
export const ADVANCED_3D_SOURCES = Object.freeze([
  Object.freeze({
    kind: 'terrain',
    sourceId: 'esri-worldelevation3d-terrain3d',
    providerId: 'esri',
    label: 'Esri WorldElevation3D / Terrain3D',
    hrefManifestation: 'https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer',
    protocol: 'arcgis-tiled-elevation-imageservice',
    horizontalCrs: 'WGS84_WEB_MERCATOR_AUXILIARY_SPHERE',
    verticalDatum: 'GRAVITY_RELATED_MIXED_COVERAGE',
    verticalDatumStatus: 'MIXED_COVERAGE',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
    evidenceNote: 'Provider documentation states mixed gravity-related elevation coverage; do not promote a uniform vertical datum.',
  }),
  // NOAA's metadata declares one vertical datum for the whole dataset
  // ("Puerto Rico Vertical Datum of 2002 height (m)", EPSG:6641), so this is the
  // terrain the Digital Twin may bind (see cudem.js for its height caveats).
  Object.freeze({
    kind: 'terrain',
    sourceId: CUDEM_PR.sourceId,
    providerId: 'noaa-ncei',
    label: CUDEM_PR.label,
    hrefManifestation: CUDEM_PR.baseUrl,
    protocol: 'cloud-optimized-geotiff-tiles',
    horizontalCrs: 'NAD83 (EPSG:4269)',
    verticalDatum: 'PRVD02 (EPSG:6641)',
    verticalDatumStatus: 'UNIFORM_BOUND',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
    evidenceNote: `Provider metadata (${CUDEM_PR.metadataUrl}) declares PRVD02 heights in metres for the whole dataset.`,
  }),
]);

export function terrainSource(sourceId) {
  const source = ADVANCED_3D_SOURCES.find((item) => item.sourceId === sourceId && item.kind === 'terrain');
  return source ? certifyAdvanced3dSource(source) : null;
}

export function evaluatedAdvanced3dSources() {
  return ADVANCED_3D_SOURCES.map((source) => certifyAdvanced3dSource(source));
}

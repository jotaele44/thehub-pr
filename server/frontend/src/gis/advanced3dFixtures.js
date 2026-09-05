import { certifyAdvanced3dSource } from './advanced3dContracts';

export const ADVANCED_3D_FIXTURES = Object.freeze([
  Object.freeze({
    kind: 'terrain',
    sourceId: 'esri-worldelevation3d-terrain3d',
    providerId: 'esri',
    hrefManifestation: 'https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer',
    horizontalCrs: 'WGS84_WEB_MERCATOR_AUXILIARY_SPHERE',
    verticalDatum: 'GRAVITY_RELATED_MIXED_COVERAGE',
    verticalDatumStatus: 'MIXED_COVERAGE',
    evidenceClass: 'AUTHORITATIVE_PROVIDER_METADATA',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
  }),
  Object.freeze({
    kind: '3d-tiles',
    sourceId: 'fixture-3dtiles-unit-box',
    hrefManifestation: '/fixtures/gis/3dtiles/tileset.json',
    tilesetVersion: '1.1',
    boundingVolumeType: 'box',
    evidenceClass: 'LOCAL_VALID_3D_TILES_FIXTURE',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
  }),
  Object.freeze({
    kind: 'point-cloud',
    sourceId: 'fixture-pointcloud-epsg6566',
    hrefManifestation: '/fixtures/gis/pointcloud/points.xyz',
    crs: 'EPSG:6566',
    verticalDatum: 'UNRESOLVED',
    evidenceClass: 'LOCAL_POINT_CLOUD_FIXTURE_WITH_EXPLICIT_HORIZONTAL_CRS',
    canonicalIdentityStatus: 'CANDIDATE_NOT_IDENTITY',
  }),
]);

export function evaluatedAdvanced3dFixtures() {
  return ADVANCED_3D_FIXTURES.map((fixture) => certifyAdvanced3dSource(fixture));
}

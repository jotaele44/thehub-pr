export const GIS_RUNTIME_RESPONSIBILITIES = Object.freeze({
  leaflet: Object.freeze({ role: 'TRANSITIONAL_2D_ADAPTER', status: 'PROVISIONAL', retireWhen: 'MapLibre adapter reaches feature parity' }),
  maplibre: Object.freeze({ role: 'CANONICAL_2D_2_5D_RENDERER', status: 'TARGET' }),
  deckgl: Object.freeze({ role: 'GPU_ANALYTIC_OVERLAY', status: 'TARGET', separateUserMode: false }),
  cesium: Object.freeze({ role: 'ADVANCED_3D_GLOBE_3D_TILES_RENDERER', status: 'TARGET' }),
  stac: Object.freeze({ role: 'IMAGERY_DISCOVERY_PROTOCOL', status: 'TARGET' }),
  cog: Object.freeze({ role: 'PREFERRED_CLOUD_RASTER_MANIFESTATION', status: 'TARGET' }),
  pmtiles: Object.freeze({ role: 'STATIC_TILE_ARCHIVE_MANIFESTATION', status: 'TARGET' }),
});

export const SOURCE_PROTOCOL_ADAPTERS = Object.freeze({
  'local-geojson': Object.freeze({ role: 'DEVICE_GEOJSON_ACQUISITION', runtimeStatus: 'IMPLEMENTED', certification: 'BOUNDED' }),
  'arcgis-feature-layer-geojson': Object.freeze({ role: 'REMOTE_VECTOR_ACQUISITION', runtimeStatus: 'IMPLEMENTED', certification: 'PROVISIONAL_PROVIDER_RUNTIME' }),
  wfs: Object.freeze({ role: 'REMOTE_VECTOR_ACQUISITION', runtimeStatus: 'OPEN', certification: 'OPEN' }),
  stac: Object.freeze({ role: 'EO_DISCOVERY', runtimeStatus: 'OPEN', certification: 'OPEN' }),
  'arcgis-image-service': Object.freeze({ role: 'REMOTE_RASTER_DISCOVERY_OR_RENDER', runtimeStatus: 'OPEN', certification: 'OPEN' }),
});

export const GEOSPATIAL_PROVIDERS = Object.freeze([
  Object.freeze({
    providerId: 'pr-sige',
    label: 'Puerto Rico SIGE',
    authority: 'Gobierno de Puerto Rico',
    classes: Object.freeze(['ARCGIS_REST', 'WFS']),
    catalogUrl: 'https://sige.pr.gov/server/rest/services',
    status: 'ACTIVE',
  }),
  Object.freeze({
    providerId: 'pr-geodata-wfs',
    label: 'Puerto Rico Geodata WFS',
    authority: 'Gobierno de Puerto Rico',
    classes: Object.freeze(['WFS']),
    catalogUrl: 'http://geoserver2.pr.gov/geoserver/pr_geodata/wfs',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'usgs-3dhp',
    label: 'USGS 3D Hydrography Program',
    authority: 'U.S. Geological Survey',
    classes: Object.freeze(['ARCGIS_REST']),
    catalogUrl: 'https://3dhp.nationalmap.gov/arcgis/rest/services/usgs_3dhp_all/FeatureServer',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'usgs-landsat',
    label: 'USGS Landsat STAC',
    authority: 'U.S. Geological Survey',
    classes: Object.freeze(['STAC']),
    catalogUrl: 'https://landsatlook.usgs.gov/stac-server',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'nasa-earthdata',
    label: 'NASA Earthdata CMR-STAC',
    authority: 'NASA',
    classes: Object.freeze(['STAC']),
    catalogUrl: 'https://cmr.earthdata.nasa.gov/stac',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'copernicus-cdse',
    label: 'Copernicus Data Space',
    authority: 'European Commission / Copernicus',
    classes: Object.freeze(['STAC']),
    catalogUrl: 'https://stac.dataspace.copernicus.eu/v1/',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'noaa-digital-coast',
    label: 'NOAA Digital Coast',
    authority: 'NOAA',
    classes: Object.freeze(['CATALOG', 'ARCGIS_IMAGE_SERVICE']),
    catalogUrl: 'https://coast.noaa.gov/digitalcoast/data/',
    status: 'REGISTRY_ONLY',
  }),
  Object.freeze({
    providerId: 'census-tigerweb',
    label: 'U.S. Census TIGERweb',
    authority: 'U.S. Census Bureau',
    classes: Object.freeze(['ARCGIS_REST']),
    catalogUrl: 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb',
    status: 'REGISTRY_ONLY',
  }),
]);

const PR_SIGE_INFRASTRUCTURE = 'https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer';

export const ONLINE_SOURCE_CATALOG = Object.freeze([
  Object.freeze({
    sourceId: 'pr-sige-municipios',
    providerId: 'pr-sige',
    label: 'Municipios',
    category: 'boundaries',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: 'https://sige.pr.gov/server/rest/services/MIPR/LimitesAdministrativos_v10/FeatureServer/0',
    sourceNativeCrs: 'EPSG:32161',
    outputCrs: 'EPSG:4326',
    stableIdField: 'OBJECTID',
    expectedGeometryTypes: Object.freeze(['Polygon', 'MultiPolygon']),
    expectedFeatureCount: 78,
    pageSize: 1000,
    runtimeStatus: 'IMPLEMENTED',
    certification: 'PROVISIONAL_PROVIDER_RUNTIME',
  }),
  Object.freeze({
    sourceId: 'pr-sige-represas',
    providerId: 'pr-sige',
    label: 'Represas',
    category: 'hydro-infrastructure',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: `${PR_SIGE_INFRASTRUCTURE}/1`,
    sourceNativeCrs: 'EPSG:32161',
    outputCrs: 'EPSG:4326',
    stableIdField: 'OBJECTID_1',
    expectedGeometryTypes: Object.freeze(['Point']),
    pageSize: 1000,
    runtimeStatus: 'IMPLEMENTED',
    certification: 'PROVISIONAL_PROVIDER_RUNTIME',
  }),
  Object.freeze({
    sourceId: 'pr-sige-aeropuertos',
    providerId: 'pr-sige',
    label: 'Aeropuertos',
    category: 'transport',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: `${PR_SIGE_INFRASTRUCTURE}/17`,
    sourceNativeCrs: 'EPSG:32161',
    outputCrs: 'EPSG:4326',
    stableIdField: 'OBJECTID_1',
    expectedGeometryTypes: Object.freeze(['Point']),
    pageSize: 1000,
    runtimeStatus: 'IMPLEMENTED',
    certification: 'PROVISIONAL_PROVIDER_RUNTIME',
  }),
  Object.freeze({
    sourceId: 'pr-sige-helipuertos',
    providerId: 'pr-sige',
    label: 'Helipuertos',
    category: 'transport',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: `${PR_SIGE_INFRASTRUCTURE}/18`,
    sourceNativeCrs: 'EPSG:32161',
    outputCrs: 'EPSG:4326',
    stableIdField: 'OBJECTID_1',
    expectedGeometryTypes: Object.freeze(['Point']),
    pageSize: 1000,
    runtimeStatus: 'IMPLEMENTED',
    certification: 'PROVISIONAL_PROVIDER_RUNTIME',
  }),
  Object.freeze({
    sourceId: 'pr-geodata-wfs-catalog',
    providerId: 'pr-geodata-wfs',
    label: 'Puerto Rico WFS catalog (~400 geodatasets)',
    category: 'catalog',
    protocol: 'wfs',
    endpoint: 'http://geoserver2.pr.gov/geoserver/pr_geodata/wfs',
    runtimeStatus: 'OPEN',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'usgs-3dhp-catalog',
    providerId: 'usgs-3dhp',
    label: '3D Hydrography Program',
    category: 'hydrography',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: 'https://3dhp.nationalmap.gov/arcgis/rest/services/usgs_3dhp_all/FeatureServer',
    runtimeStatus: 'OPEN_REQUIRES_LAYER_AND_AOI',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'usgs-landsat-stac',
    providerId: 'usgs-landsat',
    label: 'Landsat STAC',
    category: 'imagery',
    protocol: 'stac',
    endpoint: 'https://landsatlook.usgs.gov/stac-server',
    runtimeStatus: 'OPEN',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'nasa-earthdata-stac',
    providerId: 'nasa-earthdata',
    label: 'Earthdata CMR-STAC',
    category: 'imagery',
    protocol: 'stac',
    endpoint: 'https://cmr.earthdata.nasa.gov/stac',
    runtimeStatus: 'OPEN',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'copernicus-cdse-stac',
    providerId: 'copernicus-cdse',
    label: 'Sentinel / Copernicus STAC',
    category: 'imagery',
    protocol: 'stac',
    endpoint: 'https://stac.dataspace.copernicus.eu/v1/',
    runtimeStatus: 'OPEN',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'noaa-digital-coast-catalog',
    providerId: 'noaa-digital-coast',
    label: 'Digital Coast imagery / elevation catalog',
    category: 'imagery-elevation',
    protocol: 'arcgis-image-service',
    endpoint: 'https://coast.noaa.gov/digitalcoast/data/',
    runtimeStatus: 'OPEN',
    certification: 'OPEN',
  }),
  Object.freeze({
    sourceId: 'census-tigerweb-state-county',
    providerId: 'census-tigerweb',
    label: 'TIGERweb states / counties (current vintage)',
    category: 'boundaries',
    protocol: 'arcgis-feature-layer-geojson',
    endpoint: 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer',
    runtimeStatus: 'OPEN_REQUIRES_LAYER_AND_PR_FILTER',
    certification: 'OPEN',
  }),
]);

export function getProvider(providerId) {
  const provider = GEOSPATIAL_PROVIDERS.find((item) => item.providerId === providerId);
  if (!provider) throw new Error(`unknown providerId: ${providerId}`);
  return provider;
}

export function getOnlineSourceDefinition(sourceId) {
  const source = ONLINE_SOURCE_CATALOG.find((item) => item.sourceId === sourceId);
  if (!source) throw new Error(`unknown online sourceId: ${sourceId}`);
  return source;
}

export function listOnlineSourceDefinitions(providerId = null) {
  return ONLINE_SOURCE_CATALOG.filter((item) => !providerId || item.providerId === providerId);
}

export function createSourceManifest(input = {}) {
  if (!input.providerId || !input.sourceId) throw new Error('source manifest requires providerId and sourceId');
  return Object.freeze({
    sourceId: String(input.sourceId),
    providerId: String(input.providerId),
    sourceClass: String(input.sourceClass || 'unknown'),
    canonicalIdentityStatus: input.canonicalIdentityStatus || 'CANDIDATE_NOT_IDENTITY',
    catalogId: input.catalogId ?? null,
    collectionId: input.collectionId ?? null,
    itemId: input.itemId ?? null,
    assetKey: input.assetKey ?? null,
    hrefManifestation: input.hrefManifestation ?? null,
    acquisitionDatetime: input.acquisitionDatetime ?? null,
    geometry: input.geometry ?? null,
    bbox: input.bbox ?? null,
    crs: input.crs ?? null,
    sourceNativeCrs: input.sourceNativeCrs ?? null,
    bands: Object.freeze([...(input.bands || [])]),
    groundSampleDistanceM: input.groundSampleDistanceM ?? null,
    cloudCoverPercent: input.cloudCoverPercent ?? null,
    license: input.license ?? null,
    attribution: input.attribution ?? null,
    retrievalUtc: input.retrievalUtc ?? null,
    metadataSha256: input.metadataSha256 ?? null,
    queryReceiptSha256: input.queryReceiptSha256 ?? null,
    snapshotSha256: input.snapshotSha256 ?? null,
  });
}

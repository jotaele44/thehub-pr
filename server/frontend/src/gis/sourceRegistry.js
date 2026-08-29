export const GIS_RUNTIME_RESPONSIBILITIES = Object.freeze({
  leaflet: Object.freeze({ role: 'TRANSITIONAL_2D_ADAPTER', status: 'PROVISIONAL', retireWhen: 'MapLibre adapter reaches feature parity' }),
  maplibre: Object.freeze({ role: 'CANONICAL_2D_2_5D_RENDERER', status: 'TARGET' }),
  deckgl: Object.freeze({ role: 'GPU_ANALYTIC_OVERLAY', status: 'TARGET', separateUserMode: false }),
  cesium: Object.freeze({ role: 'ADVANCED_3D_GLOBE_3D_TILES_RENDERER', status: 'TARGET' }),
  stac: Object.freeze({ role: 'IMAGERY_DISCOVERY_PROTOCOL', status: 'TARGET' }),
  cog: Object.freeze({ role: 'PREFERRED_CLOUD_RASTER_MANIFESTATION', status: 'TARGET' }),
  pmtiles: Object.freeze({ role: 'STATIC_TILE_ARCHIVE_MANIFESTATION', status: 'TARGET' }),
});

export const GEOSPATIAL_PROVIDERS = Object.freeze([
  Object.freeze({
    providerId: 'copernicus-cdse',
    class: 'STAC',
    catalogUrl: 'https://stac.dataspace.copernicus.eu/v1/',
    collections: ['Sentinel and complementary Copernicus collections'],
    auth: 'catalog-discovery-public; asset-access-provider-dependent',
    status: 'ACTIVE',
  }),
  Object.freeze({
    providerId: 'usgs-landsat',
    class: 'STAC',
    catalogUrl: 'AUTHORITATIVE_USGS_STAC_DISCOVERY',
    collections: ['Landsat'],
    auth: 'provider-dependent',
    status: 'ACTIVE',
  }),
  Object.freeze({
    providerId: 'nasa-earthdata',
    class: 'STAC_OR_CATALOG',
    catalogUrl: 'AUTHORITATIVE_NASA_EARTHDATA_DISCOVERY',
    collections: ['NASA Earth-observation products'],
    auth: 'collection-dependent',
    status: 'ACTIVE',
  }),
]);

export function createSourceManifest(input = {}) {
  if (!input.providerId || !input.sourceId) throw new Error('source manifest requires providerId and sourceId');
  return Object.freeze({
    sourceId: String(input.sourceId),
    providerId: String(input.providerId),
    sourceClass: String(input.sourceClass || 'unknown'),
    catalogId: input.catalogId ?? null,
    collectionId: input.collectionId ?? null,
    itemId: input.itemId ?? null,
    assetKey: input.assetKey ?? null,
    hrefManifestation: input.hrefManifestation ?? null,
    acquisitionDatetime: input.acquisitionDatetime ?? null,
    geometry: input.geometry ?? null,
    bbox: input.bbox ?? null,
    crs: input.crs ?? null,
    bands: Object.freeze([...(input.bands || [])]),
    groundSampleDistanceM: input.groundSampleDistanceM ?? null,
    cloudCoverPercent: input.cloudCoverPercent ?? null,
    license: input.license ?? null,
    attribution: input.attribution ?? null,
    retrievalUtc: input.retrievalUtc ?? null,
    metadataSha256: input.metadataSha256 ?? null,
  });
}

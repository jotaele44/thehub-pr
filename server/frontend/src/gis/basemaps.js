// Basemaps are display context only: they are never evidence layers and carry
// no certification. Each entry names its provider and attribution.
export const BASEMAPS = Object.freeze({
  cartoDark: Object.freeze({ label: 'CARTO Dark', url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap, &copy; CARTO' }),
  osm: Object.freeze({ label: 'OpenStreetMap', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' }),
});

// USGS The National Map orthoimagery: public domain, no key. Its tile cache has
// no Puerto Rico tiles at zoom 9-10 (HTTP 404, checked 2026-10-03), so the
// imagery is drawn from zoom 11 over the CARTO base and says so.
export const IMAGERY_BASEMAPS = Object.freeze({
  usgsImagery: Object.freeze({
    label: 'USGS orthoimagery',
    url: 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
    attribution: 'USDA, USGS The National Map: Orthoimagery',
    minzoom: 11,
    underlay: BASEMAPS.cartoDark,
    note: 'Orthoimagery (6 in to 1 m) from zoom 11; below that the CARTO base shows. Display context, not an evidence layer.',
  }),
});

export const PROPERTY_MAP_BASEMAPS = Object.freeze({ ...BASEMAPS, ...IMAGERY_BASEMAPS });

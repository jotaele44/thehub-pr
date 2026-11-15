// NOAA NGS GEOID18 for Puerto Rico and the U.S. Virgin Islands: the geoid
// height N that relates PRVD02 orthometric heights H (CUDEM's datum) to
// NAD83(2011) ellipsoidal heights h, as h = H + N. NGS publishes the grid; the
// PROJ project mirrors it as a GeoTIFF on its CDN (CORS open, byte ranges), so
// the browser reads it directly. The grid is 1 arc-minute, its values sit on the
// nodes (PixelIsPoint), and its longitudes run 0-360.
//
// Correction is applied only through geoidBinding: when the terrain's vertical
// datum is the geoid's orthometric datum. Anything else is refused and said so.
import { fromUrl } from 'geotiff';

export const GEOID18_PR = Object.freeze({
  sourceId: 'noaa-ngs-geoid18-prvi',
  label: 'NOAA NGS GEOID18 (Puerto Rico and U.S. Virgin Islands)',
  provider: 'NOAA National Geodetic Survey, mirrored by the PROJ project (PROJ-data)',
  url: 'https://cdn.proj.org/us_noaa_g2018p0.tif',
  model: 'GEOID18',
  orthometricDatum: 'PRVD02 (EPSG:6641)',
  ellipsoidalDatum: 'NAD83(2011) ellipsoidal height (EPSG:6319)',
  resolution: '1 arc-minute grid, values on the nodes',
  extent: Object.freeze([-69, 15, -64, 21]),
  citation: 'NOAA NGS, GEOID18 hybrid geoid model (2019)',
  caveat: 'NAD83(2011) ellipsoidal heights are used as WGS84 ellipsoidal heights without a transformation (the frames differ by about 1-2 m).',
});

// What the 3D view is when the geoid is not applied (not bound, or not readable).
export const GEOID_NOT_APPLIED = Object.freeze({
  caveat: 'Without the geoid, the 3D view places PRVD02 heights on the WGS84 ellipsoid with no geoid separation, so absolute heights there are offset by the local geoid separation (GEOID18: -43.1 m at San Juan, -38.7 m at Cerro de Punta).',
  ellipsoidal: 'Ellipsoidal height is not computed: the geoid is not applied.',
});

function epsg(text) {
  return /EPSG:(\d+)/.exec(String(text || ''))?.[1] || null;
}

// Whether GEOID18 may correct this terrain: the terrain must be certified for
// runtime binding and its vertical datum must be the geoid's orthometric datum.
export function geoidBinding(terrain, geoid = GEOID18_PR) {
  if (!terrain || terrain.status !== 'READY_FOR_RUNTIME_BINDING') {
    return Object.freeze({ status: 'NOT_BOUND', reason: 'no certified terrain to correct' });
  }
  const terrainDatum = epsg(terrain.verticalDatum);
  if (!terrainDatum || terrainDatum !== epsg(geoid.orthometricDatum)) {
    return Object.freeze({
      status: 'NOT_BOUND',
      reason: `terrain heights are ${terrain.verticalDatum || 'of an undeclared datum'}; ${geoid.model} relates ${geoid.orthometricDatum}`,
    });
  }
  return Object.freeze({ status: 'BOUND', reason: `${geoid.model} relates ${geoid.orthometricDatum} to ${geoid.ellipsoidalDatum}` });
}

const PIXEL_IS_POINT = 2;

// The whole grid as { values, width, height, originLon, originLat, stepLon,
// stepLat }, where the origin is the first node. geotiff.js returns the raw
// tiepoint: the node itself for PixelIsPoint, a cell corner for PixelIsArea.
export async function readGeoidGrid(tiff) {
  const image = await tiff.getImage();
  const [tieLon, tieLat] = image.getOrigin();
  const [stepLon, stepLat] = image.getResolution();
  const onNodes = image.getGeoKeys()?.GTRasterTypeGeoKey === PIXEL_IS_POINT;
  const [values] = await image.readRasters();
  return Object.freeze({
    values,
    width: image.getWidth(),
    height: image.getHeight(),
    originLon: onNodes ? tieLon : tieLon + stepLon / 2,
    originLat: onNodes ? tieLat : tieLat + stepLat / 2,
    stepLon,
    stepLat,
  });
}

let loaded = null;

// The GEOID18 grid, read once per page (about 220 kB).
export function openGeoid(url = GEOID18_PR.url) {
  if (!loaded) {
    loaded = fromUrl(url, { allowFullFile: false }).then(readGeoidGrid).catch((error) => {
      loaded = null;
      throw error;
    });
  }
  return loaded;
}

// N in metres at a point, bilinear between the four surrounding nodes; null
// outside the grid or where a node holds no value.
export function geoidHeight(grid, lon, lat) {
  const east = grid.originLon > 180 && lon < 0 ? lon + 360 : lon;
  const x = (east - grid.originLon) / grid.stepLon;
  const y = (lat - grid.originLat) / grid.stepLat;
  if (!(x >= 0 && y >= 0 && x <= grid.width - 1 && y <= grid.height - 1)) return null;
  const x0 = Math.min(Math.floor(x), grid.width - 2);
  const y0 = Math.min(Math.floor(y), grid.height - 2);
  const tx = x - x0;
  const ty = y - y0;
  const at = (col, row) => grid.values[row * grid.width + col];
  const corners = [at(x0, y0), at(x0 + 1, y0), at(x0, y0 + 1), at(x0 + 1, y0 + 1)];
  if (!corners.every(Number.isFinite)) return null;
  const top = corners[0] * (1 - tx) + corners[1] * tx;
  const bottom = corners[2] * (1 - tx) + corners[3] * tx;
  return top * (1 - ty) + bottom * ty;
}

export function geoidCovers([west, south, east, north], geoid = GEOID18_PR) {
  const [gWest, gSouth, gEast, gNorth] = geoid.extent;
  return west <= gEast && gWest <= east && south <= gNorth && gSouth <= north;
}

// A height with its datum and source. A value without a datum is labelled as
// such, never shown as if it had one.
export function formatHeight({ value, datum, source }) {
  if (!Number.isFinite(value)) return null;
  const metres = `${value.toFixed(1)} m`;
  if (!datum) return `${metres} (datum not declared)`;
  return source ? `${metres} ${datum} · ${source}` : `${metres} ${datum}`;
}

// The single datum a series of heights shares; heights of different datums are
// never placed on one axis.
export function sharedDatum(heights) {
  const datums = new Set(heights.map((item) => item.datum || null));
  if (datums.size !== 1 || datums.has(null)) {
    throw new Error(`heights of different or undeclared datums cannot share an axis: ${[...datums].map(String).join(', ')}`);
  }
  return [...datums][0];
}

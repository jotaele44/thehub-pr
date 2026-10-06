// NOAA NCEI CUDEM, Puerto Rico 1/9 arc-second bathymetric-topographic tiles
// (dataset m9525, 2022): the Digital Twin's terrain. One declared vertical
// datum across the whole dataset (NOAA metadata: "Puerto Rico Vertical Datum of
// 2002 height (m)", EPSG:6641), so it passes the fail-closed 3D gate as
// UNIFORM_BOUND (see advanced3dSourceRegistry.js). The tiles are cloud-optimized
// GeoTIFFs on NOAA's public S3 bucket (CORS open, byte ranges), so the browser
// reads only the windows and overviews it needs; nothing is copied or hosted.
//
// Heights are PRVD02 values. Two caveats are stated wherever heights are used:
// the 3D view places them on the WGS84 ellipsoid without a geoid separation, and
// NAD83 positions are used as WGS84 without a horizontal transformation.
import { fromUrl } from 'geotiff';

const BASE_URL = 'https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NCEI_ninth_Topobathy_PuertoRico_9525/';

export const CUDEM_PR = Object.freeze({
  sourceId: 'noaa-ncei-cudem-pr-ninth-m9525',
  datasetId: 'm9525',
  label: 'NOAA NCEI CUDEM Puerto Rico, 1/9 arc-second topobathy (2022)',
  provider: 'NOAA NCEI / NOS Coastal LiDAR Public Data Set',
  verticalDatum: 'Puerto Rico Vertical Datum of 2002 (PRVD02, EPSG:6641)',
  verticalUnits: 'metres',
  horizontalDatum: 'NAD83 (EPSG:4269)',
  resolution: '1/9 arc-second (about 3 m)',
  created: '2022-06-03',
  published: '2022-06-11',
  citation: 'Amante et al. 2023, Continuously Updated Digital Elevation Model (CUDEM)',
  metadataUrl: `${BASE_URL}cudem_ninth_pr_m9525_met.xml`,
  baseUrl: BASE_URL,
  nodata: -9999,
  pixelDegrees: 1 / 9 / 3600,
  tileDegrees: 0.25,
  extent: Object.freeze([-68.0, 17.75, -65.25, 18.75]),
  heightCaveats: Object.freeze([
    'Heights are PRVD02 (gravity-related). The 3D view places them on the WGS84 ellipsoid without a geoid separation, so absolute heights there are offset by the local geoid separation; elevation readouts give the PRVD02 value itself.',
    'NAD83 positions are used as WGS84 without a horizontal transformation (the frames differ at metre scale).',
  ]),
});

// Verbatim from NOAA's urllist9525.txt (26 tiles; one is still version 1).
export const CUDEM_TILE_NAMES = Object.freeze([
  'ncei19_n18x00_w066x00_2022v2.tif', 'ncei19_n18x00_w066x25_2022v2.tif', 'ncei19_n18x00_w066x50_2022v2.tif',
  'ncei19_n18x00_w066x75_2022v2.tif', 'ncei19_n18x00_w067x00_2022v2.tif', 'ncei19_n18x00_w067x25_2022v2.tif',
  'ncei19_n18x25_w065x50_2022v2.tif', 'ncei19_n18x25_w065x75_2022v2.tif', 'ncei19_n18x25_w066x00_2022v2.tif',
  'ncei19_n18x25_w066x25_2022v2.tif', 'ncei19_n18x25_w066x50_2022v2.tif', 'ncei19_n18x25_w066x75_2022v2.tif',
  'ncei19_n18x25_w067x00_2022v2.tif', 'ncei19_n18x25_w067x25_2022v2.tif', 'ncei19_n18x25_w068x00_2022v1.tif',
  'ncei19_n18x50_w065x50_2022v2.tif', 'ncei19_n18x50_w065x75_2022v2.tif', 'ncei19_n18x50_w066x00_2022v2.tif',
  'ncei19_n18x50_w066x25_2022v2.tif', 'ncei19_n18x50_w066x50_2022v2.tif', 'ncei19_n18x50_w066x75_2022v2.tif',
  'ncei19_n18x50_w067x00_2022v2.tif', 'ncei19_n18x50_w067x25_2022v2.tif', 'ncei19_n18x50_w067x50_2022v2.tif',
  'ncei19_n18x75_w067x00_2022v2.tif', 'ncei19_n18x75_w067x25_2022v2.tif',
]);

const NAME_PATTERN = /_n(\d+)x(\d+)_w(\d+)x(\d+)_/;

// A tile name gives its north-west corner (checked against the GeoTIFF tiepoint);
// each tile spans 0.25 degrees. Returns [west, south, east, north].
export function tileBounds(name) {
  const match = NAME_PATTERN.exec(name);
  if (!match) throw new Error(`not a CUDEM tile name: ${name}`);
  const north = Number(match[1]) + Number(match[2]) / 100;
  const west = -(Number(match[3]) + Number(match[4]) / 100);
  return [west, north - CUDEM_PR.tileDegrees, west + CUDEM_PR.tileDegrees, north];
}

export const CUDEM_TILES = Object.freeze(CUDEM_TILE_NAMES.map((name) => Object.freeze({
  name, url: `${BASE_URL}${name}`, bbox: Object.freeze(tileBounds(name)),
})));

// Closed boxes: a point on the edge two tiles share touches both.
function intersects(a, b) {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}

export function tilesFor(bbox, tiles = CUDEM_TILES) {
  return tiles.filter((tile) => intersects(tile.bbox, bbox));
}

export function covers(bbox) {
  return intersects(CUDEM_PR.extent, bbox);
}

const OPEN_LIMIT = 16;
const openTiles = new Map();

// One cached GeoTIFF handle per tile (least recently used are dropped first).
export function openTile(url) {
  if (openTiles.has(url)) {
    const handle = openTiles.get(url);
    openTiles.delete(url);
    openTiles.set(url, handle);
    return handle;
  }
  // NOAA's bucket answers byte ranges with 206. A server that ignores the range
  // is refused: geotiff would place the whole file at the requested offset.
  const handle = fromUrl(url, { allowFullFile: false }).catch((error) => {
    openTiles.delete(url);
    throw error;
  });
  openTiles.set(url, handle);
  if (openTiles.size > OPEN_LIMIT) openTiles.delete(openTiles.keys().next().value);
  return handle;
}

function sampleRange(start, step, count, low, high) {
  let first = -1;
  let last = -1;
  for (let k = 0; k < count; k += 1) {
    const value = start + k * step;
    if (value >= low && value <= high) {
      if (first < 0) first = k;
      last = k;
    }
  }
  return first < 0 ? null : [first, last];
}

// The coarsest image (full resolution or an overview) whose pixels are no
// larger than the sample spacing, so a coarse view reads a small overview.
async function imageFor(tiff, spacing) {
  const first = await tiff.getImage();
  const count = await tiff.getImageCount();
  const images = [];
  for (let index = 0; index < count; index += 1) images.push(await tiff.getImage(index));
  images.sort((a, b) => b.getWidth() - a.getWidth());
  let chosen = images[0];
  for (const image of images) {
    if (Math.abs(image.getResolution(first)[0]) <= spacing) chosen = image;
  }
  return { image: chosen, first };
}

// Heights (PRVD02 metres) on a width x height grid that includes the bbox
// edges, rows from north to south: each sample takes the value of the pixel it
// falls in, from the first tile in NOAA's list that holds one (tiles share
// edges and overlap by a few pixels). Cells without data are NaN. Reports the
// CUDEM tiles that supplied heights, for the provenance panel.
export async function heightGrid([west, south, east, north], width, height, { open = openTile, tiles = CUDEM_TILES } = {}) {
  const heights = new Float32Array(width * height).fill(Number.NaN);
  const dx = width > 1 ? (east - west) / (width - 1) : 0;
  const dy = height > 1 ? (north - south) / (height - 1) : 0;
  const read = [];
  for (const tile of tilesFor([west, south, east, north], tiles)) {
    let supplied = false;
    const columns = sampleRange(west, dx, width, tile.bbox[0], tile.bbox[2]);
    const rows = sampleRange(north, -dy, height, tile.bbox[1], tile.bbox[3]);
    if (!columns || !rows) continue;
    const tiff = await open(tile.url);
    const { image, first } = await imageFor(tiff, Math.min(dx || Infinity, dy || Infinity));
    const [originX, originY] = first.getOrigin();
    const [resX, resY] = image.getResolution(first);
    const imageWidth = image.getWidth();
    const imageHeight = image.getHeight();
    const colOf = (lon) => Math.floor((lon - originX) / resX);
    const rowOf = (lat) => Math.floor((lat - originY) / resY);
    const clampCol = (col) => Math.max(0, Math.min(imageWidth - 1, col));
    const clampRow = (row) => Math.max(0, Math.min(imageHeight - 1, row));
    const c0 = clampCol(colOf(west + columns[0] * dx));
    const c1 = clampCol(colOf(west + columns[1] * dx));
    const r0 = clampRow(rowOf(north - rows[0] * dy));
    const r1 = clampRow(rowOf(north - rows[1] * dy));
    const windowWidth = c1 - c0 + 1;
    const [band] = await image.readRasters({ window: [c0, r0, c1 + 1, r1 + 1] });
    for (let r = rows[0]; r <= rows[1]; r += 1) {
      const row = rowOf(north - r * dy);
      if (row < 0 || row >= imageHeight) continue;
      for (let c = columns[0]; c <= columns[1]; c += 1) {
        const col = colOf(west + c * dx);
        if (col < 0 || col >= imageWidth) continue;
        const value = band[(row - r0) * windowWidth + (col - c0)];
        if (Number.isFinite(value) && value !== CUDEM_PR.nodata && Number.isNaN(heights[r * width + c])) {
          heights[r * width + c] = value;
          supplied = true;
        }
      }
    }
    if (supplied) read.push(tile.name);
  }
  return { heights, tilesRead: read };
}

// The PRVD02 height at a point, or null outside coverage or where CUDEM has no data.
export async function elevationAt(lon, lat, options = {}) {
  const { heights, tilesRead } = await heightGrid([lon, lat, lon, lat], 1, 1, options);
  const value = heights[0];
  return Number.isFinite(value) ? { metres: value, tile: tilesRead[0] } : null;
}

export function formatElevation(result) {
  if (!result) return null;
  return `${result.metres.toFixed(1)} m PRVD02 · CUDEM ${CUDEM_PR.datasetId} 1/9″`;
}

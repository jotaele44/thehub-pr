import { CustomHeightmapTerrainProvider, GeographicTilingScheme, Math as CesiumMath } from 'cesium';
import { IMAGERY_BASEMAPS } from './basemaps';
import { CUDEM_PR, covers, heightGrid } from './cudem';
import { geoidHeight } from './geoid';

// Cesium terrain from the uniform-datum CUDEM (cudem.js). Bind it only after
// certifyAdvanced3dSource returns READY_FOR_RUNTIME_BINDING for its registry
// entry. Outside CUDEM's extent, or at levels too coarse to be worth reading,
// tiles are flat (the geoid, or the ellipsoid without one) and nothing is fetched.
export const TERRAIN_SAMPLES = 65;
export const MIN_TERRAIN_LEVEL = 7;

// Cesium picks a terrain tile's imagery level from the tile's geometric error:
// with these heightmap tiles (and Cesium's flat fallback) a tile at level L
// takes Web Mercator imagery from level L + 1 across Puerto Rico's latitudes,
// and Cesium raises that level to the imagery provider's minimumLevel. Hung on
// coarser tiles, the orthoimagery (no tiles below zoom 11) would ask each of
// them for every zoom-11 tile it covers, millions for the globe's root tiles,
// so its layer starts at the terrain level whose own imagery level is zoom 11.
export const ORTHO_MINIMUM_TERRAIN_LEVEL = IMAGERY_BASEMAPS.usgsImagery.minzoom - 1;

// Adds the geoid height N to each sample (h = H + N) wherever the geoid has a
// value. Samples outside its extent are left as they are: nothing is extrapolated.
function onEllipsoid(heights, [west, south, east, north], samples, geoid) {
  const dx = samples > 1 ? (east - west) / (samples - 1) : 0;
  const dy = samples > 1 ? (north - south) / (samples - 1) : 0;
  for (let row = 0; row < samples; row += 1) {
    for (let col = 0; col < samples; col += 1) {
      const n = geoidHeight(geoid, west + col * dx, north - row * dy);
      if (n !== null) heights[row * samples + col] += n;
    }
  }
}

// Heights for one Cesium tile, as a row-major north-to-south grid. Cells
// CUDEM has no value for are drawn at 0 and never reported as heights. With a
// geoid grid, heights are placed on the ellipsoid (H + N), so a flat tile is
// the sea surface, which follows the geoid, not the ellipsoid.
export async function tileHeights(rectangle, level, { grid = heightGrid, samples = TERRAIN_SAMPLES, onTiles, geoid = null } = {}) {
  const heights = new Float32Array(samples * samples);
  if (level >= MIN_TERRAIN_LEVEL && covers(rectangle)) {
    const { heights: read, tilesRead } = await grid(rectangle, samples, samples);
    for (let index = 0; index < heights.length; index += 1) {
      heights[index] = Number.isFinite(read[index]) ? read[index] : 0;
    }
    if (onTiles && tilesRead.length) onTiles(tilesRead);
  }
  if (geoid) onEllipsoid(heights, rectangle, samples, geoid);
  return heights;
}

// `geoid` is a GEOID18 grid (geoid.js) or null; the provider is built once the
// decision to apply it is settled, because Cesium does not re-request tiles.
export function createCudemTerrainProvider({ onTiles, onError, geoid = null } = {}) {
  const tilingScheme = new GeographicTilingScheme();
  return new CustomHeightmapTerrainProvider({
    width: TERRAIN_SAMPLES,
    height: TERRAIN_SAMPLES,
    tilingScheme,
    credit: `${CUDEM_PR.label} · ${CUDEM_PR.verticalDatum}`,
    callback: (x, y, level) => {
      const rect = tilingScheme.tileXYToRectangle(x, y, level);
      const degrees = [rect.west, rect.south, rect.east, rect.north].map((value) => CesiumMath.toDegrees(value));
      return tileHeights(degrees, level, { onTiles, geoid }).catch((error) => {
        if (onError) onError(error);
        // A flat tile, level 0 so nothing is read, still on the geoid when one is in use.
        return tileHeights(degrees, 0, { geoid });
      });
    },
  });
}

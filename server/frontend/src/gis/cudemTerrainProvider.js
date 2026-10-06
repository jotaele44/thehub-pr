import { CustomHeightmapTerrainProvider, GeographicTilingScheme, Math as CesiumMath } from 'cesium';
import { IMAGERY_BASEMAPS } from './basemaps';
import { CUDEM_PR, covers, heightGrid } from './cudem';

// Cesium terrain from the uniform-datum CUDEM (cudem.js). Bind it only after
// certifyAdvanced3dSource returns READY_FOR_RUNTIME_BINDING for its registry
// entry. Outside CUDEM's extent, or at levels too coarse to be worth reading,
// tiles are flat on the ellipsoid and nothing is fetched.
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

// Heights for one Cesium tile, as a row-major north-to-south grid. Cells
// CUDEM has no value for are drawn at 0 and never reported as heights.
export async function tileHeights(rectangle, level, { grid = heightGrid, samples = TERRAIN_SAMPLES, onTiles } = {}) {
  const flat = new Float32Array(samples * samples);
  if (level < MIN_TERRAIN_LEVEL || !covers(rectangle)) return flat;
  const { heights, tilesRead } = await grid(rectangle, samples, samples);
  for (let index = 0; index < flat.length; index += 1) {
    flat[index] = Number.isFinite(heights[index]) ? heights[index] : 0;
  }
  if (onTiles && tilesRead.length) onTiles(tilesRead);
  return flat;
}

export function createCudemTerrainProvider({ onTiles, onError } = {}) {
  const tilingScheme = new GeographicTilingScheme();
  return new CustomHeightmapTerrainProvider({
    width: TERRAIN_SAMPLES,
    height: TERRAIN_SAMPLES,
    tilingScheme,
    credit: `${CUDEM_PR.label} · ${CUDEM_PR.verticalDatum}`,
    callback: (x, y, level) => {
      const rect = tilingScheme.tileXYToRectangle(x, y, level);
      const degrees = [rect.west, rect.south, rect.east, rect.north].map((value) => CesiumMath.toDegrees(value));
      return tileHeights(degrees, level, { onTiles }).catch((error) => {
        if (onError) onError(error);
        return new Float32Array(TERRAIN_SAMPLES * TERRAIN_SAMPLES);
      });
    },
  });
}

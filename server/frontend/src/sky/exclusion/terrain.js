// Terrain for the horizon and line-of-sight engines (FDX-032/033): a height field read through one function,
// heightAt(lon, lat), that returns metres above the terrain's declared vertical datum, or null where there is no data.
// "No data" is never read as flat ground or as zero: the engines carry it as UNKNOWN.
//
// The Hub's own terrain is NOAA NCEI CUDEM for Puerto Rico (PRVD02 heights, bare earth: no buildings and no trees),
// read through src/gis/cudem.js in the browser. Everything else here is pure.
import { CUDEM_PR, covers, heightGrid } from '../../gis/cudem.js';

export const MAX_GRID_CELLS = 4_000_000;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);

// A regular grid of heights, rows from north to south, columns from west to east, edges included: the shape that
// cudem.heightGrid returns. NaN cells are no data.
export function gridTerrain({ heights, width, height, bbox, datum, label }) {
  if (!(heights?.length === width * height) || !(width >= 2) || !(height >= 2)) throw new RangeError('The grid must be at least 2 by 2 and hold width x height heights.');
  const [west, south, east, north] = bbox;
  if (!(east > west) || !(north > south)) throw new RangeError('The grid\'s bounding box must have its east beyond its west and its north beyond its south.');
  if (typeof datum !== 'string' || !datum) throw new RangeError('The terrain must declare its vertical datum.');
  const dx = (east - west) / (width - 1);
  const dy = (north - south) / (height - 1);
  const at = (row, col) => heights[row * width + col];
  return Object.freeze({
    label: label ?? 'height grid', datum, bbox: Object.freeze([...bbox]), spacingDegrees: Math.max(dx, dy),
    heightAt(lon, lat) {
      if (!finite(lon) || !finite(lat) || lon < west || lon > east || lat < south || lat > north) return null;
      const x = (lon - west) / dx;
      const y = (north - lat) / dy;
      const c0 = Math.min(width - 2, Math.floor(x));
      const r0 = Math.min(height - 2, Math.floor(y));
      const fx = x - c0;
      const fy = y - r0;
      const a = at(r0, c0); const b = at(r0, c0 + 1); const c = at(r0 + 1, c0); const d = at(r0 + 1, c0 + 1);
      if (Number.isFinite(a) && Number.isFinite(b) && Number.isFinite(c) && Number.isFinite(d)) {
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
      }
      // Next to a hole: the nearest node if it has data, otherwise no data (never a guess from the other three).
      const nearest = at(Math.min(height - 1, Math.round(y)), Math.min(width - 1, Math.round(x)));
      return Number.isFinite(nearest) ? nearest : null;
    },
  });
}

// Terrain from a function (a synthetic surface in a test, or any other source): heightAt returns metres or null.
export function functionTerrain({ heightAt, datum, label }) {
  if (typeof heightAt !== 'function') throw new RangeError('The terrain needs a heightAt(lon, lat) function.');
  if (typeof datum !== 'string' || !datum) throw new RangeError('The terrain must declare its vertical datum.');
  return Object.freeze({ label: label ?? 'terrain function', datum, bbox: null, spacingDegrees: null, heightAt });
}

// The first terrain that has data wins, so a fine grid near the observer sits over a coarse one that reaches further.
export function compositeTerrain(terrains, label) {
  if (!terrains.length) throw new RangeError('Give at least one terrain.');
  const datum = terrains[0].datum;
  if (terrains.some((t) => t.datum !== datum)) throw new RangeError('Terrains with different vertical datums are not combined: a height means something different in each.');
  return Object.freeze({
    label: label ?? terrains.map((t) => t.label).join(' over '), datum, bbox: null, spacingDegrees: Math.min(...terrains.map((t) => t.spacingDegrees ?? Infinity)),
    heightAt(lon, lat) {
      for (const t of terrains) {
        const h = t.heightAt(lon, lat);
        if (h !== null && h !== undefined) return h;
      }
      return null;
    },
  });
}

function boxAround({ lon, lat }, radiusKm) {
  const dLat = radiusKm / 111.2;
  const dLon = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180));
  return [lon - dLon, lat - dLat, lon + dLon, lat + dLat];
}

// CUDEM around a point: a fine grid for the nearby ground and a coarse one out to the radius, read from the cloud-
// optimised tiles in the browser (the tile reader picks the overview that matches the grid spacing). Outside CUDEM
// there is no data, which the engines report as UNKNOWN. `deps.heightGrid` is for tests.
export async function terrainFromCudem(centre, {
  radiusKm = 60, nearRadiusKm = 5, nearSpacingDegrees = 0.0003, farSpacingDegrees = 0.002,
} = {}, deps = {}) {
  const read = deps.heightGrid ?? heightGrid;
  if (!finite(centre?.lon) || !finite(centre?.lat)) throw new RangeError('The centre needs a longitude and a latitude.');
  if (!covers([centre.lon, centre.lat, centre.lon, centre.lat])) throw new RangeError('The observer is outside the CUDEM coverage (Puerto Rico and its waters), so there is no terrain to read.');
  const layers = [];
  const tiles = new Set();
  for (const [radius, spacing, name] of [[nearRadiusKm, nearSpacingDegrees, 'near'], [radiusKm, farSpacingDegrees, 'far']]) {
    const bbox = boxAround(centre, radius);
    const width = Math.ceil((bbox[2] - bbox[0]) / spacing) + 1;
    const height = Math.ceil((bbox[3] - bbox[1]) / spacing) + 1;
    if (width * height > MAX_GRID_CELLS) throw new RangeError(`The ${name} grid would have ${width * height} cells; at most ${MAX_GRID_CELLS} are read.`);
    const { heights, tilesRead } = await read(bbox, width, height);
    for (const t of tilesRead) tiles.add(t);
    layers.push(gridTerrain({ heights, width, height, bbox, datum: CUDEM_PR.verticalDatum, label: `CUDEM ${name} grid (${(spacing * 111320).toFixed(0)} m)` }));
  }
  const terrain = compositeTerrain(layers, `${CUDEM_PR.label}, read as a ${(nearSpacingDegrees * 111320).toFixed(0)} m grid within ${nearRadiusKm} km and a ${(farSpacingDegrees * 111320).toFixed(0)} m grid to ${radiusKm} km`);
  return Object.freeze({
    ...terrain, tilesRead: Object.freeze([...tiles].sort()), source: CUDEM_PR.sourceId,
    caveats: Object.freeze([
      ...CUDEM_PR.heightCaveats,
      'Bare earth: buildings, trees and other structures are not in this model, so a real horizon can only be higher than the one computed here.',
      'Heights are read from overviews of the 1/9 arc-second tiles at the grid spacing named above; a hill narrower than that is smoothed.',
    ]),
  });
}

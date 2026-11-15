// Running the "Rule out the ordinary" checks end to end (P6-C): the form's strings and an optional tracks file in, the
// engines' results and the `sky-exclusion-v1` receipt out. Pure apart from the terrain read, which is injected, so the
// whole run is testable without a browser. Nothing here is stored, sent or fetched except the CUDEM tiles the terrain
// option asks for (and the CelesTrak elements the workspace has already read).
//
// A run that cannot do something it was asked to does not quietly do less: a tracks file that does not parse stops the
// run with the reason (the aircraft check was asked for), whereas a terrain read that fails lets the run go on without
// terrain and says so in the receipt's notChecked, because the other checks are still worth having.
import { checkAircraft } from './aircraftExclusion.js';
import { parseTrackCsv, parseTrackGeoJson, validateDeclaration } from './aircraftTracks.js';
import { checkCelestial } from './celestialExclusion.js';
import { declarationFieldOf, declarationFromDraft, observationFromDraft, terrainOptionsFromDraft } from './exclusionForm.js';
import { computeHorizon } from './horizon.js';
import { buildExclusionReceipt, reconstructSky } from './reconstruction.js';
import { checkSatellites } from './satelliteExclusion.js';

export const TRACK_FORMATS = Object.freeze(['CSV', 'GeoJSON']);

export function detectTrackFormat(name, text) {
  const lower = String(name ?? '').toLowerCase();
  if (lower.endsWith('.csv')) return 'CSV';
  if (lower.endsWith('.geojson') || lower.endsWith('.json')) return 'GeoJSON';
  return String(text ?? '').trimStart().startsWith('{') ? 'GeoJSON' : 'CSV';
}

function parseTracks(tracks) {
  const declared = declarationFromDraft(tracks.declarationDraft);
  if (!declared.ok) return { ok: false, field: `declaration.${declared.field}`, message: declared.message };
  // The declaration is checked on its own first, so a missing source or altitude reference is reported against the
  // declaration and not mistaken for a fault in the file.
  try {
    validateDeclaration(declared.declaration);
  } catch (error) {
    if (error instanceof RangeError) return { ok: false, field: declarationFieldOf(error.message), message: error.message };
    throw error;
  }
  try {
    const format = tracks.format ?? detectTrackFormat(tracks.name, tracks.text);
    const parsed = format === 'GeoJSON' ? parseTrackGeoJson(tracks.text, declared.declaration) : parseTrackCsv(tracks.text, declared.declaration);
    return { ok: true, parsed };
  } catch (error) {
    if (error instanceof RangeError) return { ok: false, field: 'tracks', message: error.message };
    throw error;
  }
}

export async function runExclusion({
  observationDraft, tracks = null, satelliteData = null, terrain = null, generatedAt = new Date(),
}, deps = {}) {
  const observed = observationFromDraft(observationDraft);
  if (!observed.ok) return observed;
  const { observation } = observed;
  const notRun = {};

  let parsedTracks = null;
  if (tracks && tracks.text) {
    const parsed = parseTracks(tracks);
    if (!parsed.ok) return parsed;
    parsedTracks = parsed.parsed;
  } else {
    notRun.aircraft = 'No aircraft tracks were supplied.';
  }

  let horizon = null;
  let terrainRead = null;
  if (terrain?.enabled) {
    const options = terrainOptionsFromDraft(terrain.draft);
    if (!options.ok) return { ok: false, field: `terrain.${options.field}`, message: options.message };
    try {
      // Imported only when the terrain option is used: the CUDEM reader brings in the GeoTIFF library, which the rest of the check does not need.
      const read = deps.terrainFromCudem ?? (await import('./terrain.js')).terrainFromCudem;
      terrainRead = await read({ lon: observation.observer.lon, lat: observation.observer.lat }, { radiusKm: options.options.radiusKm });
      horizon = computeHorizon(terrainRead, { lon: observation.observer.lon, lat: observation.observer.lat, aboveGroundMetres: options.options.aboveGroundMetres }, { maxRangeKm: options.options.radiusKm, refractionK: options.options.refractionK });
    } catch (error) {
      notRun.terrain = `The terrain could not be used: ${error.message}`;
    }
  } else {
    notRun.terrain = 'The terrain option was not turned on.';
  }

  const celestial = checkCelestial(observation, { horizon });
  let satellites = null;
  if (satelliteData?.items?.length) {
    satellites = await checkSatellites(observation, satelliteData, { horizon });
  } else {
    notRun.satellites = 'The satellite element sets are not loaded (see Satellites above).';
  }
  const aircraft = parsedTracks ? checkAircraft(observation, parsedTracks, { horizon }) : null;
  const reconstruction = reconstructSky(observation, { satellites: satelliteData?.items?.length ? satelliteData : null, aircraft: parsedTracks, horizon });
  const receipt = await buildExclusionReceipt({
    observation, celestial, satellites, aircraft, horizon, terrain: terrainRead, reconstruction, notRun, generatedAt,
  });
  return {
    ok: true, observation, celestial, satellites, aircraft, horizon, reconstruction, receipt, parsedTracks, notRun,
  };
}

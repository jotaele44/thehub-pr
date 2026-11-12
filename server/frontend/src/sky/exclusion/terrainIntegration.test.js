import { describe, expect, it, vi } from 'vitest';
import elementsText from '../fixtures/satellite-elements.json?raw';
import reference from '../fixtures/satelliteReference.json';
import { loadSatelliteElements } from '../satelliteElements';
import { gpUrl } from '../satellites';
import { aircraftLookAt, checkAircraft } from './aircraftExclusion';
import { parseTrackCsv } from './aircraftTracks';
import { checkCelestial } from './celestialExclusion';
import { computeHorizon, destination, radiusOfCurvature } from './horizon';
import { parseObservation } from './observation';
import { apparentElevation } from './refraction';
import { checkSatellites } from './satelliteExclusion';
import { functionTerrain } from './terrain';

const OBS = { lon: -66.1057, lat: 18.4663 };
const OBSERVER = { lat: OBS.lat, lon: OBS.lon, height: 0 };
const DEG = 180 / Math.PI;
const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 111320 * Math.cos((OBS.lat * Math.PI) / 180);
const polar = (lon, lat) => {
  const e = (lon - OBS.lon) * M_PER_DEG_LON;
  const n = (lat - OBS.lat) * M_PER_DEG_LAT;
  return { r: Math.hypot(e, n), az: ((Math.atan2(e, n) * DEG) + 360) % 360 };
};
const terrainOf = (f) => functionTerrain({ heightAt: f, datum: 'TEST', label: 'synthetic' });
// A mountain wall of the given height 9 to 11 km away across a range of azimuths, standing in the sea
const wall = (from, to, height) => terrainOf((lon, lat) => {
  const { r, az } = polar(lon, lat);
  return r >= 9000 && r <= 11000 && az >= from && az <= to ? height : 0;
});

describe('aircraft against a computed horizon', () => {
  const horizon = computeHorizon(wall(80, 100, 800), { ...OBS, aboveGroundMetres: 0 });
  const DECLARED = { source: 'synthetic', altitudeReference: 'ELLIPSOID', altitudeUnits: 'm' };
  // Two aircraft due east, one 5 km away and one 14 km away, each at the height that puts it about 3 degrees up
  const track = (id, distance, height) => {
    const radius = radiusOfCurvature(OBS.lat, 90);
    const a = destination(OBS.lon, OBS.lat, 90, distance, radius);
    const b = destination(OBS.lon, OBS.lat, 90, distance + 50, radius);
    return [`${id},2026-11-04T12:00:00Z,${a.lat},${a.lon},${height}`, `${id},2026-11-04T12:00:10Z,${b.lat},${b.lon},${height}`];
  };
  const parsed = parseTrackCsv(['id,time,lat,lon,altitude', ...track('near', 5000, 262), ...track('far', 14000, 735 + 14000 ** 2 / (2 * 7.32e6))].join('\n'), DECLARED);
  const aim = (id) => {
    const look = aircraftLookAt(OBSERVER, parsed.tracks.find((t) => t.id === id), Date.parse('2026-11-04T12:00:05Z'), parsed.declaration.policy);
    return { look, observation: parseObservation({ time: '2026-11-04T12:00:05Z', observer: OBSERVER, direction: { azimuth: look.azimuth, elevation: look.elevation, azimuthReference: 'TRUE', toleranceDegrees: 1 } }) };
  };

  it('puts both aircraft about three degrees up, below the ridge\'s five, so only the distance tells them apart', () => {
    for (const id of ['near', 'far']) {
      const { look } = aim(id);
      expect(look.elevation).toBeGreaterThan(2.5);
      expect(look.elevation).toBeLessThan(3.5);
    }
    expect(horizon.elevationAt(90)).toBeGreaterThan(4.9);
  });

  it('does not let a ridge hide an aircraft that is in front of it, and does hide one behind it', () => {
    const near = checkAircraft(aim('near').observation, parsed, { horizon }).items.find((i) => i.id === 'near');
    expect(near).toMatchObject({ status: 'CHECKED', candidate: true, terrainAtClosest: 'CLEAR', aboveHorizonAtClosest: true });
    const far = checkAircraft(aim('far').observation, parsed, { horizon }).items.find((i) => i.id === 'far');
    expect(far).toMatchObject({ status: 'CHECKED', candidate: false, insideSomeTime: true, terrainAtClosest: 'OBSTRUCTED', aboveHorizonAtClosest: false });
    // with no horizon given both are candidates: the terrain is the only thing that separates them
    const none = checkAircraft(aim('far').observation, parsed).items.find((i) => i.id === 'far');
    expect(none).toMatchObject({ candidate: true, terrainAtClosest: 'NOT_CHECKED' });
  });

  it('reports UNKNOWN, and keeps the candidate, where the height field has no data to say', () => {
    const dark = computeHorizon(terrainOf((lon, lat) => (polar(lon, lat).az >= 80 && polar(lon, lat).az <= 100 && polar(lon, lat).r > 12000 ? null : 0)), { ...OBS, aboveGroundMetres: 0 });
    const far = checkAircraft(aim('far').observation, parsed, { horizon: dark }).items.find((i) => i.id === 'far');
    expect(far).toMatchObject({ candidate: true, terrainAtClosest: 'UNKNOWN' });
  });
});

describe('satellites and celestial bodies against a computed horizon', () => {
  const frozen = JSON.parse(elementsText).items;
  const ok = (body) => ({ ok: true, status: 200, json: async () => body });
  const answers = { [gpUrl(25544)]: frozen.ISS.payload, [gpUrl(20580)]: frozen.HST.payload, [gpUrl(48274)]: frozen.CSS.payload };
  const loaded = () => loadSatelliteElements({ fetchImpl: vi.fn(async (url) => ok(answers[url])), now: new Date('2026-11-04T08:00:00Z') });
  const sanJuan = reference.satellites.ISS.observers['San Juan'];
  const lit = sanJuan.looks.find((l) => l.sunlit && l.elevation > 20);
  const aimAtIss = () => parseObservation({
    time: lit.time, observer: OBSERVER,
    direction: { azimuth: lit.azimuth, elevation: apparentElevation(lit.elevation), azimuthReference: 'TRUE', toleranceDegrees: 0.5 },
  });

  it('hides the station behind a mountain wall in its direction, and not behind one that is elsewhere', async () => {
    // the ISS is at azimuth 47.9, elevation 22.3: a wall 9 km away across azimuths 40 to 56 and 6 km high is 33 degrees up
    const blocking = computeHorizon(wall(40, 56, 6000), { ...OBS, aboveGroundMetres: 0 });
    expect(blocking.elevationAt(48)).toBeGreaterThan(30);
    const hidden = await checkSatellites(aimAtIss(), await loaded(), { horizon: blocking });
    expect(hidden.candidates).toHaveLength(0);
    expect(hidden.items.find((i) => i.id === 'ISS')).toMatchObject({ insideSomeTime: true, candidate: false, terrainAtClosest: 'OBSTRUCTED' });
    const elsewhere = computeHorizon(wall(200, 230, 6000), { ...OBS, aboveGroundMetres: 0 });
    const seen = await checkSatellites(aimAtIss(), await loaded(), { horizon: elsewhere });
    expect(seen.items.find((i) => i.id === 'ISS')).toMatchObject({ candidate: true, terrainAtClosest: 'CLEAR' });
  });

  it('keeps a body as a candidate, marked UNKNOWN, where the terrain data runs out', async () => {
    const dark = computeHorizon(terrainOf((lon, lat) => (polar(lon, lat).r > 15000 ? null : 0)), { ...OBS, aboveGroundMetres: 0 });
    const result = await checkSatellites(aimAtIss(), await loaded(), { horizon: dark });
    expect(result.items.find((i) => i.id === 'ISS')).toMatchObject({ candidate: true, terrainAtClosest: 'UNKNOWN' });
  });

  it('applies the same horizon to the Sun, Moon, planets and stars: a wall in front of the Moon hides it', () => {
    // 05:00 local: the waning Moon stands about 37 degrees up in the east (azimuth 98), the Sun is far below the horizon
    const when = '2026-11-04T09:00:00Z';
    const probe = parseObservation({ time: when, observer: OBSERVER, direction: { azimuth: 98, elevation: 37, azimuthReference: 'TRUE', toleranceDegrees: 30 } });
    const moon = checkCelestial(probe).candidates.find((c) => c.name === 'Moon');
    expect(moon).toBeTruthy();
    const target = parseObservation({ time: when, observer: OBSERVER, direction: { azimuth: moon.azimuthAtClosest, elevation: moon.altitudeAtClosest, azimuthReference: 'TRUE', toleranceDegrees: 0.5 } });
    expect(checkCelestial(target).candidates.map((c) => c.name)).toContain('Moon');
    const around = computeHorizon(wall(Math.max(0, moon.azimuthAtClosest - 15), Math.min(359, moon.azimuthAtClosest + 15), 9000), { ...OBS, aboveGroundMetres: 0 });
    const blocked = checkCelestial(target, { horizon: around });
    expect(blocked.candidates.map((c) => c.name)).not.toContain('Moon');
  });
});

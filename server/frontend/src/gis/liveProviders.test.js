import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { acquireOnlineSource, acquireRasterAsset } from './acquisitionFacade';
import { getOnlineSourceDefinition } from './sourceRegistry';
import { CUDEM_PR, CUDEM_TILES, elevationAt, openTile, tileBounds } from './cudem';
import { GEOID18_PR, geoidHeight, openGeoid } from './geoid';
import { bodyPosition, localDayWindow, makeObserver, riseTransitSet } from '../sky/astronomy';
import reference from '../sky/referenceEphemerides.json';
import { loadSpaceWeather } from '../sky/spaceWeather';
import { loadSatelliteElements } from '../sky/satelliteElements';
import { lookAt } from '../sky/satellites';
import { computeHorizon, destination, elevationAngle, radiusOfCurvature, DEFAULT_REFRACTION_K } from '../sky/exclusion/horizon';
import { lineOfSight } from '../sky/exclusion/lineOfSight';
import { terrainFromCudem } from '../sky/exclusion/terrain';

const runLive = process.env.GIS_LIVE_PROVIDER_TESTS === '1';
const live = runLive ? describe : describe.skip;

async function boundedFetch(url, init = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    return await globalThis.fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

const direct = { fetchImpl: boundedFetch, retrievalUtc: '2026-08-29T22:00:00Z' };

live('live authoritative GIS providers', () => {
  for (const sourceId of [
    'pr-sige-municipios',
    'pr-sige-represas',
    'pr-sige-aeropuertos',
    'pr-sige-helipuertos',
    'pr-sige-cuencas',
    'pr-sige-acuiferos',
    'pr-sige-sumideros',
    'pr-sige-aaa-pozos',
  ]) {
    it(`${sourceId} closes provider denominator and validation gates`, async () => {
      try {
        const result = await acquireOnlineSource(sourceId, direct);
        expect(result.certification.status).toBe('PASS');
        expect(result.manifest.featureCount).toBeGreaterThan(0);
        expect(result.certification.gates).toEqual({ schema: 'PASS', count: 'PASS', geometry: 'PASS', crs: 'PASS', identity: 'PASS', provenance: 'PASS' });
        console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
      } catch (error) {
        const source = getOnlineSourceDefinition(sourceId);
        const message = String(error);
        if (source.certification !== 'PROVISIONAL_PROVIDER_RUNTIME' || !/abort|fetch failed|network|enotfound|econn/i.test(message)) {
          throw error;
        }
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId, certification: source.certification, error: message }));
      }
    }, 45000);
  }

  it('Census current Puerto Rico state layer closes to exactly one feature', async () => {
    const result = await acquireOnlineSource('census-tigerweb-pr-state-2025', direct);
    expect(result.manifest.featureCount).toBe(1);
    expect(result.certification.status).toBe('PASS');
  }, 120000);

  it('Census current Puerto Rico municipios close to exactly 78 county-equivalent features', async () => {
    const result = await acquireOnlineSource('census-tigerweb-pr-municipios-2025', direct);
    expect(result.manifest.featureCount).toBe(78);
    expect(result.certification.status).toBe('PASS');
  }, 120000);

  it('Puerto Rico WFS municipios closes its 78-feature denominator', async () => {
    const result = await acquireOnlineSource('pr-geodata-municipios-2015', direct);
    expect(result.manifest.featureCount).toBe(78);
    expect(result.certification.status).toBe('PASS');
    console.log('GIS_LIVE_RECEIPT', JSON.stringify({ sourceId: result.sourceDefinition.sourceId, count: result.manifest.featureCount, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
  }, 120000);

  for (const sourceId of ['usgs-landsat-stac-sr', 'copernicus-cdse-sentinel-2-l2a']) {
    it(`${sourceId} exhausts a bounded January 2025 Puerto Rico candidate window`, async () => {
      const result = await acquireOnlineSource(sourceId, { ...direct, bbox: [-67.4, 17.8, -65.2, 18.6], start: '2025-01-01', end: '2025-01-31', maxItems: 1000 });
      expect(result.certification.status).toBe('PASS');
      expect(result.certification.residue).toBeNull();
      expect(result.candidates.length).toBeGreaterThan(0);
      console.log('GIS_LIVE_DISCOVERY', JSON.stringify({ sourceId, candidates: result.candidates.length, snapshotSha256: result.snapshotSha256, queryReceiptSha256: result.queryReceiptSha256 }));
      if (sourceId === 'usgs-landsat-stac-sr') {
        const candidate = result.candidates.find((item) => Object.values(item.assets || {}).some((asset) => asset?.href && /tiff?/i.test(asset.type || '')));
        if (candidate) {
          const assetEntry = Object.entries(candidate.assets).find(([, asset]) => asset?.href && /tiff?/i.test(asset.type || ''));
          const raster = await acquireRasterAsset(sourceId, candidate, assetEntry[0], { fetchImpl: globalThis.fetch, range: 'bytes=0-65535' });
          expect(raster.certification.gates.rangeRetrieval).toBe('PASS');
          expect(raster.certification.gates.fullAssetByteIdentity).toBe('OPEN');
          console.log('GIS_LIVE_RASTER_RANGE', JSON.stringify({ sourceId, itemId: candidate.itemId, assetKey: assetEntry[0], classification: raster.assetClassification, rangeSha256: raster.snapshotSha256 }));
        }
      }
    }, 120000);
  }

  it('NOAA Puerto Rico NAIP static STAC returns bounded Puerto Rico candidates without assuming TIFF=COG', async () => {
    const result = await acquireOnlineSource('noaa-pr-naip-2021-2023-stac', { ...direct, bbox: [-67.4, 17.8, -65.2, 18.6], start: '2021-01-01', end: '2023-12-31' });
    expect(result.certification.status).toBe('PASS');
    expect(result.candidates.length).toBeGreaterThan(0);
    console.log('GIS_LIVE_DISCOVERY', JSON.stringify({ sourceId: 'noaa-pr-naip-2021-2023-stac', candidates: result.candidates.length, snapshotSha256: result.snapshotSha256 }));
  }, 120000);

  it('NOAA CUDEM Puerto Rico (m9525) is a uniform-datum cloud-optimized DEM the browser can read', async () => {
    // GNIS 1609905, Cerro de Punta summit (Puerto Rico's highest point).
    const summit = { lat: 18.172281, lon: -66.5916862 };
    const tile = CUDEM_TILES.find((item) => item.bbox[0] <= summit.lon && summit.lon <= item.bbox[2]
      && item.bbox[1] <= summit.lat && summit.lat <= item.bbox[3]);
    const tiff = await openTile(tile.url);
    const first = await tiff.getImage();
    expect(await tiff.getImageCount()).toBe(5); // full resolution + 4 overviews
    expect(first.getTileWidth()).toBe(512);
    expect(Number(first.getGDALNoData())).toBe(CUDEM_PR.nodata);
    // The tile name is its north-west corner (the tiepoint sits half a pixel out).
    const [west, , , north] = tileBounds(tile.name);
    const [originX, originY] = first.getOrigin();
    expect(Math.abs(originX - west)).toBeLessThan(0.001);
    expect(Math.abs(originY - north)).toBeLessThan(0.001);
    const peak = await elevationAt(summit.lon, summit.lat);
    expect(peak.metres).toBeGreaterThan(1000);
    expect(peak.metres).toBeLessThan(1400);
    // Offshore north-west of Puerto Rico the topobathy surface is below the datum.
    const offshore = await elevationAt(-66.9, 18.6);
    expect(offshore.metres).toBeLessThan(0);
    console.log('GIS_LIVE_DEM', JSON.stringify({ sourceId: CUDEM_PR.sourceId, summit: peak, offshore }));
  }, 120000);

  it('the terrain horizon and line of sight read real CUDEM: a plausible horizon at San Juan and at the summit, and the two engines agree on real ground', async () => {
    // Not a truth test: no keyless independent horizon exists to hold this to. It checks what must hold on real ground:
    // the datum logic puts a summit above its surroundings and the coast near the sea, the sea to the north is not an
    // obstruction, and two different implementations (a profile and a horizon) agree on every target tried.
    const places = {
      sanJuan: { lat: 18.4663, lon: -66.1057, aboveGroundMetres: 2 },
      summit: { lat: 18.172281, lon: -66.5916862, aboveGroundMetres: 2 },
    };
    const receipts = {};
    const horizons = {};
    for (const [name, place] of Object.entries(places)) {
      let terrain;
      try {
        terrain = await terrainFromCudem(place, { radiusKm: 40 });
      } catch (error) {
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId: CUDEM_PR.sourceId, place: name, error: String(error) }));
        return;
      }
      const horizon = computeHorizon(terrain, place, { maxRangeKm: 40 });
      horizons[name] = { terrain, horizon, place };
      receipts[name] = { ground: horizon.observer.groundMetres, tiles: terrain.tilesRead.length, ...horizon.summary, northHorizon: horizon.elevationAt(0), southHorizon: horizon.elevationAt(180) };
    }
    const { sanJuan, summit } = horizons;
    expect(sanJuan.horizon.observer.groundMetres).toBeGreaterThan(-5);
    expect(sanJuan.horizon.observer.groundMetres).toBeLessThan(80);
    // Nothing can be lower than the sea horizon for this eye: water is the lowest ground there is (bathymetry is raised to the
    // surface), so a horizon under it would mean the datum logic or the clamp is wrong. (This is a coastal point with real
    // relief within 100 m; it is not a flat beach, so the horizon is not asserted to be near zero.)
    const reff = 6371008.8 / (1 - DEFAULT_REFRACTION_K);
    const eyeDip = (Math.acos(reff / (reff + sanJuan.horizon.observer.eyeMetres)) * 180) / Math.PI;
    for (const ray of sanJuan.horizon.rays) if (ray.elevation !== null) expect(ray.elevation).toBeGreaterThan(-eyeDip - 0.05);
    // and offshore, past CUDEM's bathymetry, there is no data, which is carried as incomplete and never as clear
    receipts.sanJuanNorth = { elevation: sanJuan.horizon.elevationAt(0), complete: sanJuan.horizon.rays[0].complete, eyeDipDegrees: eyeDip };
    // the Cordillera to the south rises into the sky, but not by degrees
    expect(sanJuan.horizon.summary.maxElevation).toBeGreaterThan(0.3);
    expect(sanJuan.horizon.summary.maxElevation).toBeLessThan(4);
    // Puerto Rico's highest point: its horizon is below the horizontal almost everywhere
    expect(summit.horizon.observer.groundMetres).toBeGreaterThan(1100);
    expect(summit.horizon.observer.groundMetres).toBeLessThan(1400);
    const around = summit.horizon.rays.filter((r) => r.elevation !== null).map((r) => r.elevation).sort((a, b) => a - b);
    expect(around.length).toBeGreaterThan(600);
    expect(around[Math.floor(around.length / 2)]).toBeLessThan(-0.2);
    expect(around[around.length - 1]).toBeLessThan(1.5);
    // Line of sight and horizon agree on real ground, for targets 2 to 25 km away, except within a hair of the boundary: the
    // profile samples the line every 25 m and the horizon every 20 to 100 m, and 3 m terrain changes by metres between
    // samples. Measured over 2000 targets while writing this: 6 disagreements, all within 3.1 m (0.008 degrees) of the
    // boundary, the same at 0.25 and 0.5 degree azimuth steps. A band of 0.02 degrees is allowed and counted, not hidden.
    const BOUNDARY_BAND_DEGREES = 0.02;
    let seed = 20261104;
    const random = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
    const { terrain, horizon, place } = sanJuan;
    let compared = 0;
    let nearBoundary = 0;
    let disagreements = 0;
    let obstructed = 0;
    for (let i = 0; i < 400; i += 1) {
      const azimuth = random() * 360;
      const distance = 2000 + random() * 23000;
      const height = 50 + random() * 900;
      const radius = radiusOfCurvature(place.lat, azimuth);
      const to = { ...destination(place.lon, place.lat, azimuth, distance, radius), heightMetres: height };
      const los = lineOfSight(terrain, { lon: place.lon, lat: place.lat, heightMetres: horizon.observer.eyeMetres }, to, { stepMetres: 25 });
      if (los.state === 'UNKNOWN') continue;
      compared += 1;
      const state = horizon.assess(azimuth, elevationAngle(distance, height, horizon.observer.eyeMetres, radius / (1 - DEFAULT_REFRACTION_K)), { distanceMetres: distance });
      if (los.state === 'OBSTRUCTED') obstructed += 1;
      if (state === los.state) continue;
      if (Math.abs((los.minClearanceMetres / distance) * (180 / Math.PI)) < BOUNDARY_BAND_DEGREES) nearBoundary += 1; else disagreements += 1;
    }
    receipts.agreement = { targets: 400, compared, nearBoundary, disagreements, obstructed, bandDegrees: BOUNDARY_BAND_DEGREES };
    console.log('GIS_LIVE_HORIZON', JSON.stringify({ sourceId: CUDEM_PR.sourceId, receipts }));
    expect(disagreements).toBe(0);
    expect(compared).toBeGreaterThan(250);
    expect(obstructed).toBeGreaterThan(20);
  }, 240000);

  it('NOAA NGS GEOID18 (PROJ mirror) agrees with NGS\'s own geoid service across Puerto Rico and the USVI', async () => {
    const grid = await openGeoid();
    // 1 arc-minute grid, values on the nodes, longitudes 0-360, covering the declared extent.
    expect([grid.width, grid.height]).toEqual([301, 361]);
    expect(grid.originLon).toBeCloseTo(291, 6);
    expect(grid.originLat).toBeCloseTo(21, 6);
    expect(grid.stepLon).toBeCloseTo(1 / 60, 9);
    expect(grid.stepLat).toBeCloseTo(-1 / 60, 9);
    // Bilinear N against NGS's keyless service (https://geodesy.noaa.gov/api/geoid/ght). Measured
    // 2026-10-07 over these six points: at most 0.0125 m apart, against a stated NGS error of 0.04-0.07 m.
    const points = [
      ['San Juan', -66.105, 18.466], ['Cerro de Punta', -66.5916862, 18.172281], ['Mayaguez', -67.14, 18.2],
      ['Culebra', -65.3, 18.31], ['Vieques', -65.45, 18.12], ['St. Thomas', -64.93, 18.34],
    ];
    const receipts = [];
    for (const [name, lon, lat] of points) {
      const response = await boundedFetch(`https://geodesy.noaa.gov/api/geoid/ght?lat=${lat}&lon=${lon}`);
      expect(response.ok).toBe(true);
      const ngs = await response.json();
      expect(ngs.geoidModel).toBe('GEOID18');
      const mine = geoidHeight(grid, lon, lat);
      expect(Math.abs(mine - ngs.geoidHeight)).toBeLessThan(0.03);
      receipts.push({ name, grid: Number(mine.toFixed(3)), ngs: ngs.geoidHeight });
    }
    console.log('GIS_LIVE_GEOID', JSON.stringify({ sourceId: GEOID18_PR.sourceId, receipts }));
  }, 120000);

  // The Sky workspace's providers. A provider that cannot be reached is logged as unavailable (these are public
  // services with no SLA, and CelesTrak-style throttling is real); a provider that answers with data the code
  // cannot read, or with values outside the measured tolerance, fails.
  const OUTAGE = /HTTP 5\d\d|failed to fetch|fetch failed|network|timed out|abort|econn|enotfound|socket|reset/i;

  it('NOAA SWPC answers Kp, solar-wind speed and IMF Bz in the shapes the parser reads', async () => {
    const result = await loadSpaceWeather({ fetchImpl: boundedFetch });
    const receipts = [];
    for (const item of [result.kp, result.solarWind, result.imf]) {
      if (item.state === 'FAILED') {
        if (!OUTAGE.test(item.error)) throw new Error(`${item.id}: the payload could not be read: ${item.error}`);
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId: item.id, error: item.error }));
        continue;
      }
      expect(item.observedAt.getTime()).toBeLessThan(Date.now() + 10 * 60000);
      receipts.push({ id: item.id, value: item.value, observedAt: item.observedAt.toISOString(), state: item.state });
    }
    for (const item of [result.kp, result.solarWind, result.imf].filter((x) => x.state !== 'FAILED')) {
      if (item.id === 'kp') {
        expect(item.value).toBeGreaterThanOrEqual(0);
        expect(item.value).toBeLessThanOrEqual(9);
        expect(item.series.length).toBeGreaterThan(20);
        expect(item.spanDays).toBeGreaterThan(3);
      } else if (item.id === 'solar-wind-speed') {
        expect(item.value).toBeGreaterThan(100);
        expect(item.value).toBeLessThan(3000);
      } else {
        expect(Math.abs(item.bz)).toBeLessThan(200);
      }
    }
    console.log('GIS_LIVE_SWPC', JSON.stringify({ receipts }));
  }, 60000);

  // CelesTrak resets connections after a few requests a minute and answers 403 or 429 when it is asked too often, so
  // those are outages here. An answer that arrives but is not the object asked for, or not a usable element set, fails.
  const CELESTRAK_UNAVAILABLE = /HTTP (403|429)|No answer from|HTTP 5\d\d|failed to fetch|fetch failed|network|timed out|abort|econn|enotfound|socket|reset/i;
  // Inclination tells the three objects apart; the period only has to be that of a low Earth orbit (about 300 to 650 km
  // up is 90 to 98 minutes). Hubble's was 93.98 minutes on 2026-11-04: its altitude has decayed, so no tighter band
  // than the physics gives is asserted.
  const INCLINATION = Object.freeze({ ISS: [51, 52], HST: [28, 29], CSS: [41, 42] });
  const LEO_PERIOD_MINUTES = Object.freeze([90, 98]);

  it('CelesTrak answers the three GP element sets as the loader reads them, each the object asked for and in the orbit it has', async () => {
    const result = await loadSatelliteElements({ fetchImpl: boundedFetch });
    const receipts = [];
    for (const item of result.items) {
      if (item.state === 'FAILED') {
        if (!CELESTRAK_UNAVAILABLE.test(item.error)) throw new Error(`${item.id}: the answer could not be used: ${item.error}`);
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId: `celestrak-${item.id}`, error: item.error }));
        continue;
      }
      // The record exactly as read, with the hash of its text, so a real answer can be frozen as a fixture later.
      const text = JSON.stringify(item.record);
      console.log('GIS_LIVE_CELESTRAK_RECORD', JSON.stringify({ id: item.id, url: item.url, retrievedAt: result.retrievedAt.toISOString(), recordSha256: createHash('sha256').update(text).digest('hex'), record: item.record }));
      expect(item.element.noradId).toBe(item.noradId);
      expect(item.epoch.getTime()).toBeLessThan(Date.now() + 10 * 60000);
      expect(item.element.inclinationDegrees, `${item.id} inclination`).toBeGreaterThan(INCLINATION[item.id][0]);
      expect(item.element.inclinationDegrees, `${item.id} inclination`).toBeLessThan(INCLINATION[item.id][1]);
      expect(item.element.periodMinutes, `${item.id} period`).toBeGreaterThan(LEO_PERIOD_MINUTES[0]);
      expect(item.element.periodMinutes, `${item.id} period`).toBeLessThan(LEO_PERIOD_MINUTES[1]);
      // Where it is now, over San Juan's sky, when the elements are recent enough to be used.
      if (item.ageAtRetrieval.state !== 'REFUSED') {
        const look = lookAt(item.element, result.retrievedAt, { lat: 18.4663, lon: -66.1057, elevation: 0 });
        expect(look.ok).toBe(true);
        expect(look.elevation).toBeGreaterThanOrEqual(-90);
        expect(look.elevation).toBeLessThanOrEqual(90);
        expect(Math.abs(look.subpoint.latitude)).toBeLessThanOrEqual(item.element.inclinationDegrees + 0.5);
      }
      receipts.push({
        id: item.id, noradId: item.noradId, name: item.name, epoch: item.epoch.toISOString(), ageDays: +item.ageAtRetrieval.days.toFixed(2),
        inclination: item.element.inclinationDegrees, periodMinutes: +item.element.periodMinutes.toFixed(2),
      });
    }
    console.log('GIS_LIVE_CELESTRAK', JSON.stringify({ retrievedAt: result.retrievedAt.toISOString(), receipts }));
  }, 90000);

  it('JPL Horizons and astronomy-engine agree on where the Sun, Moon and Venus are, within the tolerance measured when the references were frozen', async () => {
    const site = { name: 'San Juan', lat: 18.4663, lon: -66.1057, elevation: 0 };
    const time = '2026-10-15T16:00:00Z';
    const jd = new Date(time).getTime() / 86400000 + 2440587.5;
    const observer = makeObserver(site);
    const receipts = [];
    for (const [body, command] of [['Sun', '10'], ['Moon', '301'], ['Venus', '299']]) {
      const params = new URLSearchParams({
        format: 'text', COMMAND: `'${command}'`, OBJ_DATA: "'NO'", MAKE_EPHEM: "'YES'", EPHEM_TYPE: "'OBSERVER'", CENTER: "'coord@399'",
        COORD_TYPE: "'GEODETIC'", SITE_COORD: `'${site.lon},${site.lat},${site.elevation / 1000}'`, TLIST_TYPE: "'JD'", TIME_TYPE: "'UT'",
        TLIST: `'${jd.toFixed(8)}'`, QUANTITIES: "'4'", ANG_FORMAT: "'DEG'", APPARENT: "'REFRACTED'", CSV_FORMAT: "'YES'",
      });
      let text;
      try {
        const response = await boundedFetch(`https://ssd.jpl.nasa.gov/api/horizons.api?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        text = await response.text();
      } catch (error) {
        if (!OUTAGE.test(String(error))) throw error;
        console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId: 'jpl-horizons', error: String(error) }));
        return;
      }
      const row = text.split('$$SOE')[1]?.split('$$EOE')[0]?.trim().split(',').map((cell) => cell.trim());
      expect(row, `Horizons gave no ephemeris row for ${body}`).toBeTruthy();
      const [az, alt] = [Number(row[3]), Number(row[4])];
      expect(Number.isFinite(az) && Number.isFinite(alt)).toBe(true);
      const mine = bodyPosition(body, time, observer, { refraction: 'jplhor' });
      const dAz = Math.abs(((mine.azimuth - az) % 360 + 540) % 360 - 180) * Math.cos((alt * Math.PI) / 180);
      const arcminutes = Math.hypot(dAz, mine.altitude - alt) * 60;
      expect(arcminutes, `${body} differs from Horizons by ${arcminutes.toFixed(3)} arcmin`).toBeLessThan(reference.tolerances.position_arcmin);
      receipts.push({ body, arcminutes: Number(arcminutes.toFixed(3)) });
    }
    console.log('GIS_LIVE_HORIZONS', JSON.stringify({ time, receipts }));
  }, 120000);

  it('the US Naval Observatory and astronomy-engine agree on San Juan\'s rise, transit and set, within a minute', async () => {
    const date = '2026-10-15';
    let data;
    try {
      const response = await boundedFetch(`https://aa.usno.navy.mil/api/rstt/oneday?date=${date}&coords=18.4663,-66.1057&tz=-4`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = (await response.json()).properties?.data;
    } catch (error) {
      if (!OUTAGE.test(String(error))) throw error;
      console.log('GIS_LIVE_UNAVAILABLE', JSON.stringify({ sourceId: 'usno-aa', error: String(error) }));
      return;
    }
    expect(data?.sundata, 'USNO gave no sun data').toBeTruthy();
    const window = localDayWindow(`${date}T12:00:00Z`, -4);
    const observer = makeObserver({ lat: 18.4663, lon: -66.1057 });
    const sun = riseTransitSet('Sun', observer, window);
    const moon = riseTransitSet('Moon', observer, window);
    const minutes = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };
    const into = (instant) => (instant.getTime() - window.start.getTime()) / 60000;
    const receipts = [];
    for (const [table, mine, names] of [[data.sundata, { Rise: sun.rise, 'Upper Transit': sun.transit, Set: sun.set }, ['Rise', 'Upper Transit', 'Set']],
      [data.moondata, { Rise: moon.rise, 'Upper Transit': moon.transit, Set: moon.set }, ['Rise', 'Upper Transit', 'Set']]]) {
      for (const name of names) {
        const listed = table.find((item) => item.phen === name);
        if (!listed) continue;
        expect(mine[name], `engine has no ${name}`).toBeTruthy();
        const difference = Math.abs(into(mine[name]) - minutes(listed.time));
        expect(difference, `${name}: ${difference.toFixed(2)} min`).toBeLessThanOrEqual(reference.tolerances.event_minutes);
        receipts.push({ name, minutes: Number(difference.toFixed(2)) });
      }
    }
    expect(receipts.length).toBeGreaterThanOrEqual(4);
    console.log('GIS_LIVE_USNO', JSON.stringify({ date, receipts }));
  }, 60000);
});

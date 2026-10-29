import { describe, expect, it } from 'vitest';
import { acquireOnlineSource, acquireRasterAsset } from './acquisitionFacade';
import { getOnlineSourceDefinition } from './sourceRegistry';
import { CUDEM_PR, CUDEM_TILES, elevationAt, openTile, tileBounds } from './cudem';
import { GEOID18_PR, geoidHeight, openGeoid } from './geoid';
import { bodyPosition, localDayWindow, makeObserver, riseTransitSet } from '../sky/astronomy';
import reference from '../sky/referenceEphemerides.json';
import { loadSpaceWeather } from '../sky/spaceWeather';

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

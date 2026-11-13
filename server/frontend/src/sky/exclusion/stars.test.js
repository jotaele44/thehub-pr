import { describe, expect, it } from 'vitest';
import usno from './fixtures/usnoCelnavStars.json';
import { angularSeparation } from './geometry';
import { STARS, STAR_CATALOG, starPosition } from './stars';

const byHip = new Map(STARS.map((star) => [star.hip, star]));
const near = (value, expected, digits) => expect(value).toBeCloseTo(expected, digits);

describe('the star catalogue', () => {
  it('holds the stars brighter than V 3.5, brightest first, and says it is not every star', () => {
    expect(STARS).toHaveLength(288);
    expect(STAR_CATALOG.limit).toMatchObject({ magnitude: 3.5, count: 288 });
    expect(STAR_CATALOG.limit.note).toMatch(/not every star/);
    for (const star of STARS) expect(star.magnitude).toBeLessThanOrEqual(3.5);
    for (let i = 1; i < STARS.length; i += 1) expect(STARS[i].magnitude).toBeGreaterThanOrEqual(STARS[i - 1].magnitude);
    expect(new Set(STARS.map((s) => s.hip)).size).toBe(STARS.length);
  });

  it('has the well-known stars where the sky has them (J2000, to the four decimals the catalogue keeps)', () => {
    const known = [
      [32349, 'Sirius', 101.2872, -16.7161, -1.44], [30438, 'Canopus', 95.988, -52.6957, -0.62], [69673, 'Arcturus', 213.9153, 19.1824, -0.05],
      [91262, 'Vega', 279.2347, 38.7837, 0.03], [11767, 'Polaris', 37.9545, 89.2641, 1.97], [24436, 'Rigel', 78.6345, -8.2016, 0.18],
    ];
    for (const [hip, name, ra, dec, magnitude] of known) {
      const star = byHip.get(hip);
      expect(star.name, String(hip)).toBe(name);
      near(star.ra, ra, 3); near(star.dec, dec, 3); near(star.magnitude, magnitude, 2);
    }
  });

  it('names a star by its proper name, then its Bayer designation and constellation, then its Hipparcos number', () => {
    expect(byHip.get(32349).label).toBe('Sirius');
    const unnamed = STARS.find((s) => !s.name && s.bayer);
    expect(unnamed.label).toBe(`${unnamed.bayer} ${unnamed.constellation}`);
    const bare = STARS.find((s) => !s.name && !s.bayer);
    if (bare) expect(bare.label).toBe(`HIP ${bare.hip}`);
  });

  it('carries its source, its licence notice and what it leaves out, so it can be cited and redistributed', () => {
    expect(STAR_CATALOG.source.licence).toMatch(/BSD-3-Clause/);
    expect(STAR_CATALOG.notice).toMatch(/Redistribution and use in source and binary forms/);
    expect(STAR_CATALOG.notice).toMatch(/Olaf Frohn/);
    expect(STAR_CATALOG.source.stars_json_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(STAR_CATALOG.epoch).toMatch(/No proper motion, parallax or aberration/);
  });
});

describe('held to the US Naval Observatory\'s celestial navigation service', () => {
  const observations = usno.cases.flatMap((c) => c.stars.map((s) => ({ c, s })));

  it('has a reference worth the name: 12 site-instants and the navigational stars above the horizon at each', () => {
    expect(usno.cases).toHaveLength(12);
    expect(observations.length).toBe(336);
    for (const c of usno.cases) {
      expect(c.sha256).toMatch(/^[0-9a-f]{64}$/);
      expect(c.url).toContain('aa.usno.navy.mil/api/celnav');
    }
  });

  it('gives each star\'s altitude within 0.04 degrees and its direction within 0.04 degrees of the reference', () => {
    // Measured when the reference was frozen: largest altitude difference 0.026 degrees (mean 0.0036), which is Alpha
    // Centauri's proper motion (3.7 arcsec a year over 26.8 years) that the catalogue does not apply. The direction is
    // compared as an angle on the sky, because azimuth alone is ill-conditioned near the zenith.
    let worstAltitude = 0;
    let worstSeparation = 0;
    for (const { c, s } of observations) {
      const p = starPosition(byHip.get(s.hip), c.time_utc, { lat: c.lat, lon: c.lon, elevation: 0 });
      worstAltitude = Math.max(worstAltitude, Math.abs(p.altitudeAirless - s.hc));
      worstSeparation = Math.max(worstSeparation, angularSeparation(p.azimuthAirless, p.altitudeAirless, s.zn, s.hc));
    }
    expect(worstAltitude).toBeLessThan(0.04);
    expect(worstSeparation).toBeLessThan(0.04);
  });

  it('is off by far less than that for a star that does not move much, and the largest differences are the fast-moving stars', () => {
    const differences = observations.map(({ c, s }) => {
      const p = starPosition(byHip.get(s.hip), c.time_utc, { lat: c.lat, lon: c.lon, elevation: 0 });
      return { name: s.usno_name, d: angularSeparation(p.azimuthAirless, p.altitudeAirless, s.zn, s.hc) };
    });
    const rigil = differences.filter((x) => x.name === 'RIGIL KENTAURUS').map((x) => x.d);
    const others = differences.filter((x) => !['RIGIL KENTAURUS', 'ARCTURUS'].includes(x.name)).map((x) => x.d);
    expect(Math.max(...others)).toBeLessThan(0.02);
    expect(Math.max(...rigil)).toBeGreaterThan(0.01);
  });

  it('lifts a star low in the sky by standard refraction, and leaves one high in the sky where it is', () => {
    // USNO lists nothing below about 1.6 degrees, so refraction is checked where the reference has stars: the 22 between
    // 1.6 and 5 degrees (Bennett's formula gives 0.30 degrees at 2 and 0.17 at 5), and the 99 above 45 degrees. The
    // horizon itself is the refraction model P6-A holds to JPL Horizons.
    let low = 0;
    let high = 0;
    for (const { c, s } of observations) {
      const p = starPosition(byHip.get(s.hip), c.time_utc, { lat: c.lat, lon: c.lon, elevation: 0 });
      const lift = p.altitude - p.altitudeAirless;
      if (s.hc < 5) { low += 1; expect(lift).toBeGreaterThan(0.15); expect(lift).toBeLessThan(0.35); }
      if (s.hc > 45) { high += 1; expect(lift).toBeLessThan(0.02); }
    }
    expect(low).toBe(22);
    expect(high).toBe(99);
  });
});

describe('starPosition', () => {
  const observer = { lat: 18.4663, lon: -66.1057, elevation: 0 };

  it('moves a star about 361 degrees of sky a day: the same place a sidereal day later, not a solar day', () => {
    const sirius = byHip.get(32349);
    const a = starPosition(sirius, '2026-11-04T02:00:00Z', observer);
    const sidereal = starPosition(sirius, new Date(Date.parse('2026-11-04T02:00:00Z') + 86164.0905e3), observer);
    near(sidereal.azimuthAirless, a.azimuthAirless, 1); near(sidereal.altitudeAirless, a.altitudeAirless, 1);
    const solar = starPosition(sirius, '2026-11-05T02:00:00Z', observer);
    expect(angularSeparation(solar.azimuthAirless, solar.altitudeAirless, a.azimuthAirless, a.altitudeAirless)).toBeGreaterThan(0.5);
  });

  it('refuses a time with no zone, as every engine here does', () => {
    expect(() => starPosition(byHip.get(32349), '2026-11-04T02:00:00', observer)).toThrow(/UTC designator/);
  });
});

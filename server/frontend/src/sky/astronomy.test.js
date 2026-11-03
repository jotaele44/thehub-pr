import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import reference from './referenceEphemerides.json';
import {
  ENGINE, NAKED_EYE_PLANETS, SKY_CONTRACT, bodyPosition, formatClock, instantFrom, localDayWindow, makeObserver, moonPhase,
  riseTransitSet, skyState, twilightClass,
} from './astronomy';

// Every expectation below is held to the reference values frozen in referenceEphemerides.json
// (JPL Horizons and USNO, retrieved 2026-10-18) within the tolerances measured when they were frozen.
const TOL = reference.tolerances;
const arcminutes = (a, b) => {
  const dAz = Math.abs(((a.azimuth - b.az) % 360 + 540) % 360 - 180) * Math.cos((b.alt * Math.PI) / 180);
  return Math.hypot(dAz, a.altitude - b.alt) * 60;
};
const minutesOf = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };

describe('positions against JPL Horizons', () => {
  it('matches apparent topocentric azimuth and altitude within the measured tolerance, for 7 bodies, 3 sites and 4 instants', () => {
    expect(reference.horizons.cases).toHaveLength(84);
    for (const c of reference.horizons.cases) {
      const observer = makeObserver({ lat: c.lat, lon: c.lon, elevation: c.elevation_m });
      const airless = bodyPosition(c.body, c.time, observer, { refraction: null });
      const refracted = bodyPosition(c.body, c.time, observer, { refraction: 'jplhor' });
      expect(arcminutes(airless, c.airless), `${c.body} ${c.observer} ${c.time} airless`).toBeLessThan(TOL.position_arcmin);
      expect(arcminutes(refracted, c.refracted), `${c.body} ${c.observer} ${c.time} refracted`).toBeLessThan(TOL.position_arcmin);
    }
  });

  it('reports planet and Moon magnitudes and the Moon\'s illuminated fraction within tolerance', () => {
    for (const c of reference.horizons.cases) {
      if (c.body === 'Sun') continue;
      const state = skyState({ time: c.time, lat: c.lat, lon: c.lon, elevation: c.elevation_m });
      const mine = c.body === 'Moon' ? state.moon : state.planets.find((p) => p.body === c.body);
      expect(Math.abs(mine.magnitude - c.mag), `${c.body} ${c.time} magnitude`).toBeLessThan(TOL.magnitude);
      if (c.body === 'Moon') {
        expect(Math.abs(mine.illuminatedFraction * 100 - c.illum_pct), `Moon ${c.time} illumination`).toBeLessThan(TOL.moon_illuminated_percentage_points);
      }
    }
  });

  it('shows the apparent altitude only where there is an apparent position: refracted within 1 degree of the horizon or above, geometric below', () => {
    // Horizons extends its refraction at -1 degree to every depth (+0.6466 degree), so for a body deep below the
    // horizon the reference to hold the display to is the geometric altitude, not Horizons' refracted one.
    let near = 0;
    let deep = 0;
    for (const c of reference.horizons.cases) {
      const state = skyState({ time: c.time, lat: c.lat, lon: c.lon, elevation: c.elevation_m });
      const mine = c.body === 'Sun' ? state.sun : c.body === 'Moon' ? state.moon : state.planets.find((p) => p.body === c.body);
      const expected = c.airless.alt > -1 ? c.refracted.alt : c.airless.alt;
      expect(Math.abs(mine.altitude - expected) * 60, `${c.body} ${c.observer} ${c.time}`).toBeLessThan(TOL.position_arcmin);
      expect(mine.aboveHorizon).toBe(mine.altitude > 0);
      if (c.airless.alt > -1) near += 1; else deep += 1;
    }
    // The set exercises both branches, not just one of them.
    expect(near).toBeGreaterThan(10);
    expect(deep).toBeGreaterThan(10);
  });

  it('keeps azimuth in [0, 360) and refracts altitude upward near the horizon', () => {
    const observer = makeObserver({ lat: 18.4663, lon: -66.1057 });
    // Sun a little above the horizon at San Juan sunset (USNO 18:02 local = 22:02 UTC on 2026-10-15).
    const airless = bodyPosition('Sun', '2026-10-15T21:55:00Z', observer, { refraction: null });
    const normal = bodyPosition('Sun', '2026-10-15T21:55:00Z', observer, { refraction: 'normal' });
    expect(airless.azimuth).toBeGreaterThanOrEqual(0);
    expect(airless.azimuth).toBeLessThan(360);
    expect(normal.altitude).toBeGreaterThan(airless.altitude);
  });
});

describe('rise, transit, set, twilight and phase against USNO', () => {
  const eventsOf = (day) => {
    const observer = makeObserver({ lat: day.lat, lon: day.lon });
    const window = localDayWindow(`${day.date}T12:00:00Z`, day.tz_hours);
    return { observer, window, sun: riseTransitSet('Sun', observer, window), moon: riseTransitSet('Moon', observer, window) };
  };
  const minutesIntoDay = (date, window) => (date.getTime() - window.start.getTime()) / 60000;

  it('finds every Sun and Moon event USNO lists, within a minute (USNO rounds to whole minutes)', () => {
    let compared = 0;
    for (const day of reference.usno.days) {
      const { window, sun, moon } = eventsOf(day);
      const mine = {
        sun: { Rise: sun.rise, 'Upper Transit': sun.transit, Set: sun.set, 'Begin Civil Twilight': sun.civilTwilightBegin, 'End Civil Twilight': sun.civilTwilightEnd },
        moon: { Rise: moon.rise, 'Upper Transit': moon.transit, Set: moon.set },
      };
      for (const [body, table] of Object.entries(day).filter(([key]) => key === 'sun' || key === 'moon')) {
        for (const [phen, hhmm] of Object.entries(table)) {
          const found = mine[body][phen];
          expect(found, `${day.site} ${day.date} ${body} ${phen}`).toBeTruthy();
          expect(Math.abs(minutesIntoDay(found, window) - minutesOf(hhmm)), `${day.site} ${day.date} ${body} ${phen}`).toBeLessThanOrEqual(TOL.event_minutes);
          compared += 1;
        }
      }
    }
    expect(compared).toBe(72);
  });

  it('names the phase and gives the illuminated fraction as USNO does, and finds the next quarter on time', () => {
    for (const day of reference.usno.days) {
      const noon = new Date(new Date(`${day.date}T00:00:00Z`).getTime() - day.tz_hours * 3600e3 + 12 * 3600e3);
      const phase = moonPhase(noon);
      expect(phase.name, `${day.site} ${day.date}`).toBe(day.curphase);
      expect(Math.abs(phase.illuminatedFraction * 100 - parseFloat(day.fracillum))).toBeLessThan(TOL.moon_illuminated_percentage_points);
      const closest = day.closestphase;
      const localClose = Date.UTC(closest.year, closest.month - 1, closest.day, ...closest.time.split(':').map(Number)) - day.tz_hours * 3600e3;
      // The next quarter is the one USNO names as closest whenever it falls after the instant.
      if (localClose > noon.getTime()) {
        expect(phase.nextQuarter.name, `${day.site} ${day.date}`).toBe(closest.phase);
        expect(Math.abs(phase.nextQuarter.time.getTime() - localClose) / 60000, `${day.site} ${day.date}`).toBeLessThanOrEqual(TOL.quarter_minutes);
      }
    }
  });

  it('calls the four principal phases only within a degree of the exact phase', () => {
    expect(moonPhase('2026-10-18T16:12:00Z').name).toBe('First Quarter');
    expect(moonPhase('2026-10-17T16:12:00Z').name).toBe('Waxing Crescent');
  });
});

describe('days with no rise or set (Tromsø, against Horizons)', () => {
  const observer = makeObserver({ lat: reference.polar.observer.lat, lon: reference.polar.observer.lon });
  it('says the Sun stays above the horizon all day at the midnight sun, and below it all day in the polar night', () => {
    const [midnightSun, polarNight] = reference.polar.days;
    expect(midnightSun.min_alt_airless).toBeGreaterThan(0);
    expect(polarNight.max_alt_airless).toBeLessThan(0);
    const summer = riseTransitSet('Sun', observer, localDayWindow('2026-06-21T12:00:00Z', 0));
    expect(summer.status).toBe('ABOVE_HORIZON_ALL_DAY');
    expect(summer.rise).toBeNull();
    expect(summer.set).toBeNull();
    const winter = riseTransitSet('Sun', observer, localDayWindow('2026-12-21T12:00:00Z', 0));
    expect(winter.status).toBe('BELOW_HORIZON_ALL_DAY');
    expect(winter.rise).toBeNull();
  });

  it('classifies the winter noon sky as civil twilight (Sun -3.1 degrees), not night and not day', () => {
    const state = skyState({ time: '2026-12-21T11:00:00Z', lat: observer.lat, lon: observer.lon });
    expect(state.daylight.id).toBe('CIVIL_TWILIGHT');
  });
});

describe('daylight and twilight classes', () => {
  it('cuts at the standard Sun altitudes (-0.833, -6, -12, -18 degrees)', () => {
    expect(twilightClass(10).id).toBe('DAYLIGHT');
    expect(twilightClass(-0.8).id).toBe('DAYLIGHT');
    expect(twilightClass(-0.9).id).toBe('CIVIL_TWILIGHT');
    expect(twilightClass(-6.01).id).toBe('NAUTICAL_TWILIGHT');
    expect(twilightClass(-12.01).id).toBe('ASTRONOMICAL_TWILIGHT');
    expect(twilightClass(-18.01).id).toBe('NIGHT');
    expect(twilightClass(-80).id).toBe('NIGHT');
  });

  it('agrees with the class implied by Horizons\' Sun altitude at every reference instant', () => {
    for (const c of reference.horizons.cases.filter((x) => x.body === 'Sun')) {
      const state = skyState({ time: c.time, lat: c.lat, lon: c.lon, elevation: c.elevation_m });
      // Stay clear of a boundary the 0.5 arcmin tolerance could straddle.
      const margin = [-0.8333, -6, -12, -18].map((edge) => Math.abs(c.airless.alt - edge));
      if (Math.min(...margin) < 0.05) continue;
      expect(state.daylight.id, `${c.observer} ${c.time}`).toBe(twilightClass(c.airless.alt).id);
    }
  });
});

describe('skyState', () => {
  const input = { time: '2026-10-16T00:30:00Z', lat: 18.4663, lon: -66.1057, tzHours: -4 };

  it('is a deterministic, serializable state that names its contract, conventions and time', () => {
    const a = skyState(input);
    const b = skyState(input);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
    expect(a.contract).toBe(SKY_CONTRACT);
    expect(a.time).toBe('2026-10-16T00:30:00.000Z');
    expect(a.observer).toMatchObject({ lat: 18.4663, lon: -66.1057, elevation: 0, tzHours: -4 });
    expect(a.conventions.refraction).toMatch(/standard/i);
    expect(a.conventions.riseSet).toMatch(/upper limb|semidiameter/i);
    expect(a.conventions.twilight).toMatch(/-6/);
    expect(a.planets.map((p) => p.body)).toEqual([...NAKED_EYE_PLANETS]);
    expect(a.sun.aboveHorizon).toBe(typeof a.sun.altitude === 'number' && a.sun.altitude > 0);
    expect(a.moon.phase.name).toBeTruthy();
  });

  it('marks below-horizon bodies as such but still reports where they are', () => {
    const state = skyState(input);
    const below = state.planets.filter((p) => !p.aboveHorizon);
    expect(below.length).toBeGreaterThan(0);
    for (const p of below) {
      expect(p.altitude).toBeLessThanOrEqual(0);
      expect(Number.isFinite(p.azimuth)).toBe(true);
    }
  });

  it('refuses inputs it cannot compute for, saying why, instead of returning a default', () => {
    expect(() => skyState({ ...input, lat: 91 })).toThrow(/latitude/i);
    expect(() => skyState({ ...input, lon: Number.NaN })).toThrow(/longitude/i);
    expect(() => skyState({ ...input, lon: 200 })).toThrow(/longitude/i);
    expect(() => skyState({ ...input, elevation: 50000 })).toThrow(/elevation/i);
    expect(() => skyState({ ...input, time: 'yesterday-ish' })).toThrow(/time/i);
    expect(() => skyState({ ...input, tzHours: 30 })).toThrow(/UTC offset/i);
  });
});

describe('clock and day-window helpers', () => {
  it('shows a UTC instant as local clock time at a fixed offset, across midnight', () => {
    expect(formatClock(new Date('2026-10-15T22:00:00Z'), -4)).toBe('18:00');
    expect(formatClock(new Date('2026-10-15T23:30:00Z'), 2)).toBe('01:30');
    expect(formatClock(new Date('2026-10-15T00:05:00Z'), 0)).toBe('00:05');
    expect(formatClock(null, 0)).toBe('—');
  });

  it('takes a local calendar day at a fixed UTC offset', () => {
    const window = localDayWindow('2026-10-16T02:00:00Z', -4); // still 22:00 on the 15th in San Juan
    expect(window.start.toISOString()).toBe('2026-10-15T04:00:00.000Z');
    expect(window.end.toISOString()).toBe('2026-10-16T04:00:00.000Z');
  });

  it('parses only real instants', () => {
    expect(instantFrom('2026-10-15T16:00:00Z').toISOString()).toBe('2026-10-15T16:00:00.000Z');
    expect(() => instantFrom('')).toThrow(/time/i);
    expect(() => instantFrom(new Date('x'))).toThrow(/time/i);
  });
});

describe('the pinned engine', () => {
  it('is the version the code says it is, exactly pinned', () => {
    // Vitest runs from the frontend package root; the package's exports map hides its own package.json from imports.
    const manifest = JSON.parse(readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'));
    expect(manifest.dependencies['astronomy-engine']).toBe(ENGINE.version);
    const installed = JSON.parse(readFileSync(resolve(process.cwd(), 'node_modules/astronomy-engine/package.json'), 'utf8'));
    expect(installed.version).toBe(ENGINE.version);
  });
});

import { describe, expect, it } from 'vitest';
import { ALTITUDE_RINGS, CARDINALS, CHART_RADIUS, chartBodies, kpSparkline, labelRect, projectSky } from './skyChart';

const near = (value, expected) => expect(value).toBeCloseTo(expected, 6);

describe('projectSky', () => {
  it('puts the zenith at the centre and the horizon on the rim', () => {
    const zenith = projectSky(123, 90);
    near(zenith.x, 0);
    near(zenith.y, 0);
    near(Math.hypot(...Object.values(projectSky(40, 0))), CHART_RADIUS);
  });

  it('draws the sky as seen looking up: north at the top, east at the left', () => {
    const north = projectSky(0, 0);
    near(north.x, 0);
    near(north.y, -CHART_RADIUS);
    const east = projectSky(90, 0);
    near(east.x, -CHART_RADIUS);
    near(east.y, 0);
    const south = projectSky(180, 0);
    near(south.x, 0);
    near(south.y, CHART_RADIUS);
    const west = projectSky(270, 0);
    near(west.x, CHART_RADIUS);
    near(west.y, 0);
  });

  it('scales the radius linearly with the zenith distance', () => {
    near(Math.hypot(...Object.values(projectSky(10, 45))), CHART_RADIUS / 2);
    near(Math.hypot(...Object.values(projectSky(10, 60))), CHART_RADIUS / 3);
  });

  it('does not draw what is below the horizon', () => {
    expect(projectSky(10, -0.01)).toBeNull();
    expect(projectSky(10, -40)).toBeNull();
    expect(projectSky(10, 0)).not.toBeNull();
  });

  it('refuses coordinates that are not numbers', () => {
    expect(projectSky(Number.NaN, 10)).toBeNull();
    expect(projectSky(10, undefined)).toBeNull();
  });
});

describe('chart furniture', () => {
  it('has the four cardinal directions and altitude rings at 30 and 60 degrees', () => {
    expect(CARDINALS.map((c) => c.label)).toEqual(['N', 'E', 'S', 'W']);
    expect(ALTITUDE_RINGS.map((r) => r.altitude)).toEqual([30, 60]);
    near(ALTITUDE_RINGS[0].radius, (CHART_RADIUS * 60) / 90);
  });
});

describe('chartBodies', () => {
  const sky = {
    sun: { body: 'Sun', azimuth: 90, altitude: 30, aboveHorizon: true },
    moon: { body: 'Moon', azimuth: 270, altitude: -10, aboveHorizon: false, phase: { illuminatedFraction: 0.23 }, illuminatedFraction: 0.23 },
    planets: [
      { body: 'Venus', azimuth: 180, altitude: 10, aboveHorizon: true, magnitude: -4 },
      { body: 'Mars', azimuth: 0, altitude: -5, aboveHorizon: false, magnitude: 1.2 },
    ],
  };

  it('plots what is above the horizon and lists what is not, so nothing disappears silently', () => {
    const { plotted, below } = chartBodies(sky);
    expect(plotted.map((b) => b.body)).toEqual(['Sun', 'Venus']);
    expect(below.map((b) => b.body)).toEqual(['Moon', 'Mars']);
    expect(plotted[0]).toMatchObject({ kind: 'sun', label: 'Sun' });
    near(plotted[0].x, -(CHART_RADIUS * 60) / 90);
  });

  it('gives every body a distinct shape, so meaning never rests on colour alone', () => {
    const { plotted } = chartBodies({ ...sky, moon: { ...sky.moon, altitude: 20, aboveHorizon: true } });
    const shapes = new Set(plotted.map((b) => b.shape));
    expect(plotted.length).toBe(3);
    expect(shapes.size).toBeGreaterThanOrEqual(3);
  });
});

describe('label placement', () => {
  const crowded = {
    // The Sun, Mercury and Venus a few degrees apart low in the west, as on 2026-10-18 at San Juan.
    sun: { body: 'Sun', azimuth: 257.4, altitude: 6.2, aboveHorizon: true },
    moon: { body: 'Moon', azimuth: 157.8, altitude: 44.7, aboveHorizon: true, illuminatedFraction: 0.52 },
    planets: [
      { body: 'Mercury', azimuth: 238.2, altitude: 21.2, aboveHorizon: true, magnitude: 0 },
      { body: 'Venus', azimuth: 246.4, altitude: 7.5, aboveHorizon: true, magnitude: -4.2 },
      { body: 'Mars', azimuth: 319, altitude: -42, aboveHorizon: false, magnitude: 1 },
      { body: 'Jupiter', azimuth: 306, altitude: -37, aboveHorizon: false, magnitude: -1.9 },
      { body: 'Saturn', azimuth: 89.6, altitude: 3.9, aboveHorizon: true, magnitude: 0.3 },
    ],
  };
  const overlaps = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

  it('keeps an isolated body\'s label beside its glyph', () => {
    const { plotted } = chartBodies({ ...crowded, sun: { ...crowded.sun, azimuth: 10, altitude: 70 }, planets: [] , moon: { ...crowded.moon, aboveHorizon: false, altitude: -5 } });
    expect(plotted).toHaveLength(1);
    expect(plotted[0].labelDx).toBe(9);
    expect(plotted[0].labelDy).toBe(3);
  });

  it('does not let two labels overlap each other or another body\'s glyph, even when bodies crowd together', () => {
    const { plotted } = chartBodies(crowded);
    expect(plotted.length).toBe(5);
    const labels = plotted.map((body) => ({ body: body.body, ...labelRect(body) }));
    for (let i = 0; i < labels.length; i += 1) {
      for (let j = i + 1; j < labels.length; j += 1) expect(overlaps(labels[i], labels[j]), `${labels[i].body} and ${labels[j].body} labels`).toBe(false);
      for (const other of plotted) {
        if (other.body === labels[i].body) continue;
        const glyph = { x0: other.x - 7, x1: other.x + 7, y0: other.y - 7, y1: other.y + 7 };
        expect(overlaps(labels[i], glyph), `${labels[i].body} label and ${other.body} glyph`).toBe(false);
      }
    }
  });

  it('is deterministic', () => {
    expect(JSON.stringify(chartBodies(crowded).plotted)).toBe(JSON.stringify(chartBodies(crowded).plotted));
  });
});

describe('kpSparkline', () => {
  const t = (iso) => new Date(iso);
  const series = [
    { time: t('2026-10-11T00:00:00Z'), kp: 4 },
    { time: t('2026-10-11T03:00:00Z'), kp: 5.33 },
    { time: t('2026-10-12T00:00:00Z'), kp: 0 },
    { time: t('2026-10-12T03:00:00Z'), kp: 9 },
  ];

  it('scales Kp from 0 to 9 over the measured span, with a path that starts and ends on the data', () => {
    const line = kpSparkline(series, { width: 200, height: 90 });
    expect(line.points).toHaveLength(4);
    near(line.points[0].x, 0);
    near(line.points[3].x, 200);
    near(line.points[0].y, 90 - (4 / 9) * 90);
    near(line.points[2].y, 90);
    near(line.points[3].y, 0);
    expect(line.path).toMatch(/^M0,50 L/);
    near(line.thresholdY, 90 - (5 / 9) * 90);
  });

  it('keeps time on the x axis, so uneven gaps show as gaps', () => {
    const line = kpSparkline(series, { width: 200, height: 90 });
    expect(line.points[1].x).toBeLessThan(line.points[2].x / 4);
  });

  it('returns nothing to draw for fewer than two points', () => {
    expect(kpSparkline([], { width: 200, height: 90 })).toBeNull();
    expect(kpSparkline(series.slice(0, 1), { width: 200, height: 90 })).toBeNull();
  });
});

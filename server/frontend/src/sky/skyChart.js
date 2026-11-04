// Geometry for the Sky workspace's all-sky chart and Kp sparkline (TWIN-120 as a 2D chart, TWIN-109). Pure: it only
// turns az/alt and time/Kp into coordinates, so the drawing can be checked without a browser.

export const CHART_RADIUS = 100;
const RIM_LABEL_FACTOR = 1.14;

// The sky as seen looking up: north at the top, east at the LEFT (west at the right). The horizon is the rim, the
// zenith the centre, and the radius grows linearly with the zenith distance. A body below the horizon has no place
// on the chart.
export function projectSky(azimuth, altitude, radius = CHART_RADIUS) {
  if (!Number.isFinite(azimuth) || !Number.isFinite(altitude) || altitude < 0) return null;
  const r = (radius * (90 - Math.min(90, altitude))) / 90;
  const angle = (azimuth * Math.PI) / 180;
  return { x: -r * Math.sin(angle), y: -r * Math.cos(angle) };
}

export const CARDINALS = Object.freeze(
  [['N', 0], ['E', 90], ['S', 180], ['W', 270]].map(([label, azimuth]) => {
    const { x, y } = projectSky(azimuth, 0, CHART_RADIUS * RIM_LABEL_FACTOR);
    return Object.freeze({ label, azimuth, x, y });
  }),
);

export const ALTITUDE_RINGS = Object.freeze([30, 60].map((altitude) => (
  Object.freeze({ altitude, radius: (CHART_RADIUS * (90 - altitude)) / 90 })
)));

// A shape per body, so what is what never depends on colour alone.
const SHAPES = Object.freeze({
  Sun: 'sun', Moon: 'moon', Mercury: 'triangle', Venus: 'diamond', Mars: 'square', Jupiter: 'cross', Saturn: 'ringed',
});
const SATELLITE_SHAPE = 'satellite';

// Where a body's label sits: to the right of its glyph (to the left when the right would leave the chart), nudged up or
// down when it would run into another label or another body's glyph. Sizes are the chart's own units (an 8-unit font is about 4.6 units per character).
const LABEL_DX = 9;
const LABEL_BASELINES = Object.freeze([3, 12, -6, 21, -15, 30]);
const CHAR_WIDTH = 4.6;
const GLYPH_HALF = 7;
export const labelRect = (body) => ({
  x0: body.x + body.labelDx, x1: body.x + body.labelDx + body.label.length * CHAR_WIDTH, y0: body.y + body.labelDy - 7, y1: body.y + body.labelDy + 2,
});
const intersects = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

// Half the width of the chart's drawing area (its viewBox runs from -125 to 125 on both axes).
const CHART_EDGE = 125;
const withinChart = (rect) => rect.x0 >= -CHART_EDGE && rect.x1 <= CHART_EDGE && rect.y0 >= -CHART_EDGE && rect.y1 <= CHART_EDGE;

function placeLabels(plotted) {
  const glyphs = plotted.map((body) => ({ body: body.body, x0: body.x - GLYPH_HALF, x1: body.x + GLYPH_HALF, y0: body.y - GLYPH_HALF, y1: body.y + GLYPH_HALF }));
  const placed = [];
  for (const body of plotted) {
    // To the right of the glyph first, then to its left (a body on the western rim would have its label cut off by the
    // edge of the chart). The first place that is inside the chart and clear of every label already placed and every
    // other body's glyph wins; if none is, the right-hand side on the last baseline, as before.
    const left = -(LABEL_DX + body.label.length * CHAR_WIDTH);
    let found = false;
    for (const dx of [LABEL_DX, left]) {
      for (const dy of LABEL_BASELINES) {
        body.labelDx = dx;
        body.labelDy = dy;
        const rect = labelRect(body);
        if (withinChart(rect) && !placed.some((other) => intersects(rect, other)) && !glyphs.some((glyph) => glyph.body !== body.body && intersects(rect, glyph))) {
          found = true;
          break;
        }
      }
      if (found) break;
    }
    if (!found) {
      body.labelDx = LABEL_DX;
      body.labelDy = LABEL_BASELINES[LABEL_BASELINES.length - 1];
    }
    placed.push(labelRect(body));
  }
}

// Bodies (and, when given, satellites) above the horizon with a position on the chart, and the ones below it,
// listed so nothing vanishes silently. A satellite is {body, label, azimuth, altitude, aboveHorizon, sunlit}.
export function chartBodies(sky, satellites = []) {
  const plotted = [];
  const below = [];
  const satelliteItems = new Set(satellites);
  for (const item of [sky.sun, sky.moon, ...sky.planets, ...satellites]) {
    const isSatellite = satelliteItems.has(item);
    const label = item.label ?? item.body;
    const place = item.aboveHorizon ? projectSky(item.azimuth, item.altitude) : null;
    if (!place) {
      below.push({ body: item.body, label, azimuth: item.azimuth, altitude: item.altitude, kind: isSatellite ? 'satellite' : undefined });
      continue;
    }
    plotted.push({
      body: item.body, label, kind: isSatellite ? 'satellite' : (item.body === 'Sun' ? 'sun' : item.body === 'Moon' ? 'moon' : 'planet'),
      shape: isSatellite ? SATELLITE_SHAPE : (SHAPES[item.body] || 'circle'), x: place.x, y: place.y, azimuth: item.azimuth, altitude: item.altitude,
      magnitude: item.magnitude, illuminatedFraction: item.illuminatedFraction, sunlit: isSatellite ? Boolean(item.sunlit) : undefined,
    });
  }
  placeLabels(plotted);
  return { plotted, below };
}

// A path through az/alt points across the sky (those at or above the horizon), with its two ends.
export function chartTrack(points) {
  const placed = (points ?? []).map((p) => projectSky(p.azimuth, p.altitude)).filter(Boolean);
  if (placed.length < 2) return null;
  const path = placed.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
  return { path, start: placed[0], end: placed[placed.length - 1] };
}

const round = (value) => +value.toFixed(2);

// Kp (0..9) against time over the span the data holds. Time is on the x axis, so a gap in the series is a gap in
// the line. The threshold is Kp 5, where NOAA's G1 storm scale begins.
export function kpSparkline(series, { width, height }) {
  if (!Array.isArray(series) || series.length < 2) return null;
  const first = series[0].time.getTime();
  const span = series[series.length - 1].time.getTime() - first;
  if (!(span > 0)) return null;
  const y = (kp) => round(height - (kp / 9) * height);
  const points = series.map((point) => ({ x: round(((point.time.getTime() - first) / span) * width), y: y(point.kp), kp: point.kp, time: point.time }));
  return { points, path: points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' '), thresholdY: y(5) };
}

// What the "Rule out the ordinary" chart draws, as geometry (P6-C): the reported sight line (a cone of the tolerance, or the
// camera's field of view, and its track if it moves) and the objects the reconstruction places at the reported instant, on
// the same all-sky projection as the Sky chart. Pure: it turns directions into coordinates, so the drawing can be checked
// without a browser. An object below the horizon has no place on the chart and is listed instead; a sight line that dips
// below the horizon is drawn in the pieces that are above it.
import { CHART_RADIUS, projectSky } from '../skyChart.js';
import { frustumOutline } from './frustum.js';
import { normalizeAzimuth, unitVector } from './geometry.js';
import { sightlineAt } from './observation.js';

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const round = (value) => +value.toFixed(2);
// Named on the chart: every candidate, and the few Sun, Moon, planets, satellites and aircraft nearest the sight line. Stars are
// not named unless one is a candidate (there are hundreds, and the receipt lists the nearest): their names would print over
// the one object that matters where the sky is crowded.
const NEAREST_LABELLED = 4;
const LABEL_BASELINES = [3, 12, -6, 21, -15, 30, -24];
const LABEL_FLIP_X = 30;
const CANDIDATE_LABEL_DY = -11;

function toAzEl({ e, n, u }) {
  return { azimuth: normalizeAzimuth(Math.atan2(e, n) * DEG), elevation: Math.asin(Math.max(-1, Math.min(1, u))) * DEG };
}

// The ring of directions at an angular distance from a centre direction, as azimuth and elevation.
export function coneOutline(centre, radiusDegrees, points = 72) {
  const c = unitVector(centre.azimuth, centre.elevation);
  let a = { e: -c.n, n: c.e, u: 0 };
  const length = Math.hypot(a.e, a.n);
  a = length < 1e-9 ? { e: 1, n: 0, u: 0 } : { e: a.e / length, n: a.n / length, u: 0 };
  const b = { e: c.n * a.u - c.u * a.n, n: c.u * a.e - c.e * a.u, u: c.e * a.n - c.n * a.e };
  const rho = radiusDegrees * RAD;
  return Array.from({ length: points }, (_, k) => {
    const theta = (2 * Math.PI * k) / points;
    const ca = Math.cos(theta) * Math.sin(rho);
    const cb = Math.sin(theta) * Math.sin(rho);
    return toAzEl({ e: c.e * Math.cos(rho) + a.e * ca + b.e * cb, n: c.n * Math.cos(rho) + a.n * ca + b.n * cb, u: c.u * Math.cos(rho) + a.u * ca + b.u * cb });
  });
}

// Directions to pieces of a polyline on the chart: a point below the horizon ends the piece. `closed` is true when every
// point is above the horizon and the outline is a loop.
export function projectPolyline(points) {
  const segments = [];
  let current = [];
  let hidden = 0;
  for (const p of points) {
    const q = projectSky(p.azimuth, p.elevation);
    if (!q) { hidden += 1; if (current.length) segments.push(current); current = []; } else current.push({ x: round(q.x), y: round(q.y) });
  }
  if (current.length) segments.push(current);
  return { segments, closed: hidden === 0 };
}

export function pathData({ segments, closed }) {
  return segments.map((s) => `M${s.map((p) => `${p.x} ${p.y}`).join(' L')}${closed ? ' Z' : ''}`).join(' ');
}

function sightlineGeometry(observation, instantMs) {
  const centre = sightlineAt(observation, instantMs);
  const { frustum, toleranceDegrees } = observation.direction;
  const outlineAt = (c) => (frustum ? frustumOutline(frustum, c, 8) : coneOutline(c, toleranceDegrees));
  const shapes = [{ at: 'start', centre, ...projectPolyline(outlineAt(centre)) }];
  let track = null;
  if (observation.motion) {
    const end = sightlineAt(observation, observation.motion.endTime.getTime());
    shapes.push({ at: 'end', centre: end, ...projectPolyline(outlineAt(end)) });
    const steps = 24;
    const samples = Array.from({ length: steps + 1 }, (_, k) => sightlineAt(observation, observation.time.getTime() + ((observation.motion.endTime.getTime() - observation.time.getTime()) * k) / steps));
    track = projectPolyline(samples);
  }
  const centreXY = projectSky(centre.azimuth, centre.elevation);
  return {
    kind: frustum ? 'frustum' : 'cone', centre, centreXY: centreXY ? { x: round(centreXY.x), y: round(centreXY.y) } : null,
    shapes: shapes.map((s) => ({ at: s.at, d: pathData(s), centre: s.centre, closed: s.closed, visible: s.segments.length > 0 })),
    trackD: track ? pathData(track) : null,
    belowHorizon: centre.elevation < 0,
  };
}

// The terrain horizon on the chart: the ground that rises above the horizontal, as a shaded band inside the rim (the band
// between the rim and the horizon profile), and the directions where the height field has no data as a dotted arc just
// outside the rim, because "no data" is not "clear". Water and anything at or below the horizontal leave no band.
const OUTSIDE_RIM = 3;
export function horizonGeometry(horizon) {
  if (!horizon) return null;
  const rays = horizon.rays;
  const profile = rays.map((r) => projectSky(r.azimuth, Math.max(0, r.elevation ?? 0)));
  const rim = CHART_RADIUS;
  const circle = `M0 ${-rim} A${rim} ${rim} 0 1 1 0 ${rim} A${rim} ${rim} 0 1 1 0 ${-rim} Z`;
  const polygon = `M${profile.map((p) => `${round(p.x)} ${round(p.y)}`).join(' L')} Z`;
  const arcs = [];
  let run = [];
  const flush = () => { if (run.length) arcs.push(run); run = []; };
  rays.forEach((r) => {
    if (r.complete) { flush(); return; }
    const q = projectSky(r.azimuth, 0, rim + OUTSIDE_RIM);
    run.push(`${round(q.x)} ${round(q.y)}`);
  });
  flush();
  const known = rays.filter((r) => r.elevation !== null);
  const peak = known.reduce((m, r) => (m === null || r.elevation > m.elevation ? r : m), null);
  return {
    maskD: `${circle} ${polygon}`,
    noDataD: arcs.length ? arcs.map((a) => `M${a.join(' L')}`).join(' ') : null,
    noDataRays: rays.filter((r) => !r.complete).length, rays: rays.length,
    peak: peak ? { azimuth: peak.azimuth, elevation: peak.elevation } : null,
    parameters: horizon.parameters,
  };
}

// The chart's content for a run: the sight line, and the objects above the horizon at the reported instant with the nearest
// and every candidate labelled; the objects below the horizon by name.
export function overlayGeometry(observation, reconstruction, candidates = [], horizon = null) {
  const candidateKeys = new Set(candidates.map((c) => `${c.category}|${c.id ?? c.name}`));
  const keyOf = (o) => `${o.category}|${o.id ?? o.name}`;
  const placed = [];
  const below = [];
  for (const o of reconstruction.objects) {
    const p = projectSky(o.azimuth, o.elevation);
    if (!p) { below.push(o); continue; }
    placed.push({ ...o, x: round(p.x), y: round(p.y), candidate: candidateKeys.has(keyOf(o)) });
  }
  placed.sort((a, b) => a.separationFromSightlineDegrees - b.separationFromSightlineDegrees);
  let others = 0;
  for (const o of placed) {
    o.labelled = o.candidate || (o.kind !== 'star' && (others += 1) <= NEAREST_LABELLED);
  }
  // A satellite is named by its short id. A candidate's label sits above its ring, centred; the others sit beside their
  // objects on their own baselines, to the left on the right half of the chart where a label to the right would run off it.
  let slot = 0;
  for (const o of placed) {
    if (!o.labelled) continue;
    o.label = o.category === 'satellite' && o.id ? o.id : o.name;
    if (o.candidate) {
      Object.assign(o, { labelDx: 0, labelDy: CANDIDATE_LABEL_DY, labelAnchor: 'middle' });
    } else {
      Object.assign(o, { labelDx: o.x > LABEL_FLIP_X ? -9 : 9, labelDy: LABEL_BASELINES[slot % LABEL_BASELINES.length], labelAnchor: o.x > LABEL_FLIP_X ? 'end' : 'start' });
      slot += 1;
    }
  }
  return {
    sightline: sightlineGeometry(observation, observation.time.getTime()),
    horizon: horizonGeometry(horizon),
    objects: placed,
    below: below.map((o) => ({ category: o.category, name: o.name, elevation: o.elevation })),
    unavailable: reconstruction.unavailable,
  };
}

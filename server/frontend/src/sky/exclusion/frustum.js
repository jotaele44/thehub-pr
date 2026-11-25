// A camera's field of view as geometry (FDX-039): a rectangular cone about a centre direction, with a horizontal and a
// vertical field of view and a roll. Pure functions. The model is a pinhole camera (no lens distortion is modelled): a
// direction is inside when it is in front of the camera and its horizontal and vertical angles to the optical axis,
// measured in the camera's own frame, are within half the field of view. The sky is seen in azimuth (from north through
// east) and elevation, so every direction here is an {azimuth, elevation} in degrees.
import { angularSeparation, normalizeAzimuth, unitVector } from './geometry.js';

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const dot = (a, b) => a.e * b.e + a.n * b.n + a.u * b.u;
const scale = (v, k) => ({ e: v.e * k, n: v.n * k, u: v.u * k });
const add = (a, b) => ({ e: a.e + b.e, n: a.n + b.n, u: a.u + b.u });

export function validateFrustum(frustum) {
  const horizontal = frustum?.horizontalFovDegrees;
  const vertical = frustum?.verticalFovDegrees;
  if (!finite(horizontal) || horizontal <= 0 || horizontal >= 180) throw new RangeError('The horizontal field of view must be more than 0 and less than 180 degrees.');
  if (!finite(vertical) || vertical <= 0 || vertical >= 180) throw new RangeError('The vertical field of view must be more than 0 and less than 180 degrees.');
  const roll = frustum.rollDegrees === undefined ? 0 : frustum.rollDegrees;
  if (!finite(roll) || roll < -180 || roll > 180) throw new RangeError('Roll must be between -180 and 180 degrees.');
  return Object.freeze({ horizontalFovDegrees: horizontal, verticalFovDegrees: vertical, rollDegrees: roll });
}

// The camera's axes in east-north-up: forward (the optical axis), right and up, rolled about the axis. At roll 0 the
// camera's "up" is the vertical plane's upward direction, so the horizon is level.
function cameraAxes(centre, rollDegrees) {
  const forward = unitVector(centre.azimuth, centre.elevation);
  const az = centre.azimuth * RAD;
  // For a camera looking straight up or down the horizontal axis is undefined; azimuth then names it.
  const right0 = { e: Math.cos(az), n: -Math.sin(az), u: 0 };
  const up0 = { e: -forward.u * Math.sin(az), n: -forward.u * Math.cos(az), u: Math.cos(centre.elevation * RAD) };
  const roll = rollDegrees * RAD;
  const right = add(scale(right0, Math.cos(roll)), scale(up0, Math.sin(roll)));
  const up = add(scale(right0, -Math.sin(roll)), scale(up0, Math.cos(roll)));
  return { forward, right, up };
}

// The direction as angles in the camera's frame, or null if it is behind the camera (no image there).
export function cameraAngles(frustum, centre, azimuth, elevation) {
  const { forward, right, up } = cameraAxes(centre, frustum.rollDegrees);
  const target = unitVector(azimuth, elevation);
  const z = dot(target, forward);
  if (z <= 0) return null;
  return { horizontalDegrees: Math.atan2(dot(target, right), z) * DEG, verticalDegrees: Math.atan2(dot(target, up), z) * DEG };
}

export function frustumContains(frustum, centre, azimuth, elevation) {
  const angles = cameraAngles(frustum, centre, azimuth, elevation);
  return Boolean(angles) && Math.abs(angles.horizontalDegrees) <= frustum.horizontalFovDegrees / 2 && Math.abs(angles.verticalDegrees) <= frustum.verticalFovDegrees / 2;
}

// How far outside the field of view a direction is, in degrees of the larger of its two angular overshoots; 0 or less
// when inside (the negative value is the margin to the nearer edge). null when behind the camera.
export function frustumMargin(frustum, centre, azimuth, elevation) {
  const angles = cameraAngles(frustum, centre, azimuth, elevation);
  if (!angles) return null;
  return Math.max(Math.abs(angles.horizontalDegrees) - frustum.horizontalFovDegrees / 2, Math.abs(angles.verticalDegrees) - frustum.verticalFovDegrees / 2);
}

function toAzEl(v) {
  const length = Math.hypot(v.e, v.n, v.u);
  return { azimuth: normalizeAzimuth(Math.atan2(v.e, v.n) * DEG), elevation: Math.asin(v.u / length) * DEG };
}

// The field of view's edge as a closed polygon of directions (each edge sampled `perEdge` times), for drawing on the chart.
export function frustumOutline(frustum, centre, perEdge = 8) {
  const { forward, right, up } = cameraAxes(centre, frustum.rollDegrees);
  const tx = Math.tan((frustum.horizontalFovDegrees / 2) * RAD);
  const ty = Math.tan((frustum.verticalFovDegrees / 2) * RAD);
  const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
  const points = [];
  for (let side = 0; side < 4; side += 1) {
    const [x0, y0] = corners[side];
    const [x1, y1] = corners[(side + 1) % 4];
    for (let k = 0; k < perEdge; k += 1) {
      const f = k / perEdge;
      const x = (x0 + (x1 - x0) * f) * tx;
      const y = (y0 + (y1 - y0) * f) * ty;
      points.push(toAzEl(add(add(forward, scale(right, x)), scale(up, y))));
    }
  }
  return points;
}

// The angle from the centre to the farthest corner, which bounds every direction inside (a quick pre-filter).
export function frustumRadius(frustum) {
  const centre = { azimuth: 0, elevation: 0 };
  const corner = toAzEl(add(add({ e: 0, n: 1, u: 0 }, { e: Math.tan((frustum.horizontalFovDegrees / 2) * RAD), n: 0, u: 0 }), { e: 0, n: 0, u: Math.tan((frustum.verticalFovDegrees / 2) * RAD) }));
  return angularSeparation(centre.azimuth, centre.elevation, corner.azimuth, corner.elevation);
}

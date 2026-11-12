// Geometry shared by the Sky workspace's "rule out the ordinary" engines (Phase 6, P6-C): directions in the observer's
// sky, angular separation, and look angles from a ground observer to a target given as geodetic latitude, longitude and
// ellipsoidal height. Pure functions, no clock, no network. Everything is geometric: no atmospheric refraction is
// applied here (a caller that needs it says so). Azimuth is from north through east, elevation from the local horizontal.
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

const A = 6378137;
const F = 1 / 298.257223563;
const E2 = F * (2 - F);
export const WGS84 = Object.freeze({ a: A, f: F, e2: E2, b: A * (1 - F) });

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
function requireFinite(name, value) {
  if (!finite(value)) throw new RangeError(`${name} is not a number: ${String(value)}`);
  return value;
}

export const normalizeAzimuth = (degrees) => ((degrees % 360) + 360) % 360;

// East, north and up components of the direction (azimuth from north through east, elevation above the horizontal).
export function unitVector(azimuth, elevation) {
  requireFinite('Azimuth', azimuth);
  requireFinite('Elevation', elevation);
  const az = azimuth * RAD;
  const el = elevation * RAD;
  return { e: Math.cos(el) * Math.sin(az), n: Math.cos(el) * Math.cos(az), u: Math.sin(el) };
}

// The angle between two directions in the sky, in degrees. atan2 of the cross and dot product, so a separation of an
// arc-second is not lost the way acos of a number near 1 loses it.
export function angularSeparation(azimuth1, elevation1, azimuth2, elevation2) {
  const a = unitVector(azimuth1, elevation1);
  const b = unitVector(azimuth2, elevation2);
  const cross = Math.hypot(a.n * b.u - a.u * b.n, a.u * b.e - a.e * b.u, a.e * b.n - a.n * b.e);
  const dot = a.e * b.e + a.n * b.n + a.u * b.u;
  return Math.atan2(cross, dot) * DEG;
}

// An observer on the ground: latitude and longitude in degrees, height in metres above the WGS84 ellipsoid.
export function validateObserver(observer) {
  const lat = requireFinite('Latitude', observer?.lat);
  if (lat < -90 || lat > 90) throw new RangeError('Latitude must be between -90 and 90 degrees.');
  if (!finite(observer?.lon)) throw new RangeError(`Longitude is not a number: ${String(observer?.lon)}`);
  if (observer.lon < -180 || observer.lon > 180) throw new RangeError('Longitude must be between -180 and 180 degrees.');
  const height = observer.height === undefined ? 0 : observer.height;
  if (!finite(height)) throw new RangeError(`Observer height is not a number: ${String(height)}`);
  if (height < -500 || height > 10000) throw new RangeError('Observer height must be between -500 and 10000 metres above the ellipsoid.');
  return Object.freeze({ lat, lon: observer.lon, height });
}

export function geodeticToEcef({ lat, lon, height = 0 }) {
  requireFinite('Latitude', lat);
  requireFinite('Longitude', lon);
  requireFinite('Height', height);
  const phi = lat * RAD;
  const lambda = lon * RAD;
  const sinPhi = Math.sin(phi);
  const cosPhi = Math.cos(phi);
  const n = A / Math.sqrt(1 - E2 * sinPhi * sinPhi);
  return {
    x: (n + height) * cosPhi * Math.cos(lambda),
    y: (n + height) * cosPhi * Math.sin(lambda),
    z: (n * (1 - E2) + height) * sinPhi,
  };
}

// Geodetic coordinates from ECEF by fixed-point iteration (converges to well under a micrometre in a few steps).
export function ecefToGeodetic({ x, y, z }) {
  const p = Math.hypot(x, y);
  const lon = Math.atan2(y, x);
  let lat = Math.atan2(z, p * (1 - E2));
  let height = 0;
  for (let i = 0; i < 12; i += 1) {
    const sinLat = Math.sin(lat);
    const n = A / Math.sqrt(1 - E2 * sinLat * sinLat);
    height = Math.abs(lat) > 1.5 ? z / sinLat - n * (1 - E2) : p / Math.cos(lat) - n;
    lat = Math.atan2(z, p * (1 - (E2 * n) / (n + height)));
  }
  return { lat: lat * DEG, lon: lon * DEG, height };
}

// The ECEF point as east, north and up metres from the observer (a local tangent plane at the observer).
export function ecefToEnu(point, observer) {
  const origin = geodeticToEcef(observer);
  const dx = point.x - origin.x;
  const dy = point.y - origin.y;
  const dz = point.z - origin.z;
  const phi = observer.lat * RAD;
  const lambda = observer.lon * RAD;
  const sinPhi = Math.sin(phi);
  const cosPhi = Math.cos(phi);
  const sinLambda = Math.sin(lambda);
  const cosLambda = Math.cos(lambda);
  return {
    e: -sinLambda * dx + cosLambda * dy,
    n: -sinPhi * cosLambda * dx - sinPhi * sinLambda * dy + cosPhi * dz,
    u: cosPhi * cosLambda * dx + cosPhi * sinLambda * dy + sinPhi * dz,
  };
}

export function enuToEcef({ e, n, u }, observer) {
  const origin = geodeticToEcef(observer);
  const phi = observer.lat * RAD;
  const lambda = observer.lon * RAD;
  const sinPhi = Math.sin(phi);
  const cosPhi = Math.cos(phi);
  const sinLambda = Math.sin(lambda);
  const cosLambda = Math.cos(lambda);
  return {
    x: origin.x - sinLambda * e - sinPhi * cosLambda * n + cosPhi * cosLambda * u,
    y: origin.y + cosLambda * e - sinPhi * sinLambda * n + cosPhi * sinLambda * u,
    z: origin.z + cosPhi * n + sinPhi * u,
  };
}

// Azimuth, elevation (degrees) and range (metres) of an east-north-up vector. A zero vector has no direction.
export function enuToAzEl({ e, n, u }) {
  const range = Math.hypot(e, n, u);
  if (!(range > 0)) throw new RangeError('The target is at the observer, so it has no direction.');
  return { azimuth: normalizeAzimuth(Math.atan2(e, n) * DEG), elevation: Math.asin(Math.max(-1, Math.min(1, u / range))) * DEG, range };
}

// Where a target (geodetic, ellipsoidal height) is in the observer's sky, geometrically.
export function lookTo(observer, target) {
  return enuToAzEl(ecefToEnu(geodeticToEcef(target), observer));
}

// The geodetic position of the point at a given azimuth, elevation and range from the observer.
export function pointAt(observer, azimuth, elevation, range) {
  const v = unitVector(azimuth, elevation);
  requireFinite('Range', range);
  return ecefToGeodetic(enuToEcef({ e: v.e * range, n: v.n * range, u: v.u * range }, observer));
}

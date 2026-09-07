export const SHARED_MAP_PR_CENTER = Object.freeze([-66.4, 18.22]);

function validPoint(point) {
  return typeof point?.lat === 'number'
    && typeof point?.lon === 'number'
    && Number.isFinite(point.lat)
    && Number.isFinite(point.lon);
}

export function buildMultiMarkerParityModel(points = []) {
  const valid = points.filter(validPoint);
  return Object.freeze({
    points: Object.freeze(valid),
    center: Object.freeze(valid.length ? [valid[0].lon, valid[0].lat] : [...SHARED_MAP_PR_CENTER]),
    zoom: 9,
    scrollZoom: true,
  });
}

export function buildSinglePointParityModel(lat, lon, label = '') {
  if (lat === undefined || lat === null || lon === undefined || lon === null) return null;
  const point = Object.freeze({ id: 'single-point', lat: Number(lat), lon: Number(lon), title: label || '' });
  return Object.freeze({
    points: Object.freeze([point]),
    center: Object.freeze([point.lon, point.lat]),
    zoom: 10,
    scrollZoom: false,
  });
}

export function selectOriginalMapRecord(point, callback) {
  if (typeof callback === 'function') callback(point);
  return point;
}

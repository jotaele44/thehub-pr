const EARTH_CIRCUMFERENCE_M = 40075016.68557849;
const MAPLIBRE_WORLD_SIZE_PX = 512;
const CESIUM_DEFAULT_FOV_RAD = Math.PI / 3;
const DEFAULT_VIEWPORT_HEIGHT_PX = 640;

function finite(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${label} must be finite`);
  return number;
}

export function clampLatitude(latitude) {
  return Math.max(-85.05112878, Math.min(85.05112878, finite(latitude, 'latitude')));
}

export function normalizeBearing(bearing) {
  const value = finite(bearing, 'bearing');
  return ((value % 360) + 360) % 360;
}

export function clampMapPitch(pitch) {
  return Math.max(0, Math.min(85, finite(pitch, 'pitch')));
}

export function mapLibreZoomFromGroundResolution(groundResolutionM, latitude) {
  const resolution = finite(groundResolutionM, 'groundResolutionM');
  if (resolution <= 0) throw new Error('groundResolutionM must be > 0');
  const lat = clampLatitude(latitude) * Math.PI / 180;
  const numerator = Math.cos(lat) * EARTH_CIRCUMFERENCE_M;
  return Math.log2(numerator / (MAPLIBRE_WORLD_SIZE_PX * resolution));
}

export function groundResolutionFromMapLibreZoom(zoom, latitude) {
  const z = finite(zoom, 'zoom');
  const lat = clampLatitude(latitude) * Math.PI / 180;
  return Math.cos(lat) * EARTH_CIRCUMFERENCE_M / (MAPLIBRE_WORLD_SIZE_PX * (2 ** z));
}

export function cesiumHeightFromGroundResolution(
  groundResolutionM,
  viewportHeightPx = DEFAULT_VIEWPORT_HEIGHT_PX,
  verticalFovRad = CESIUM_DEFAULT_FOV_RAD,
) {
  const resolution = finite(groundResolutionM, 'groundResolutionM');
  const heightPx = finite(viewportHeightPx, 'viewportHeightPx');
  const fov = finite(verticalFovRad, 'verticalFovRad');
  if (resolution <= 0 || heightPx <= 0 || fov <= 0 || fov >= Math.PI) {
    throw new Error('invalid Cesium resolution/viewport/FOV inputs');
  }
  return resolution * heightPx / (2 * Math.tan(fov / 2));
}

export function groundResolutionFromCesiumHeight(
  cameraHeightM,
  viewportHeightPx = DEFAULT_VIEWPORT_HEIGHT_PX,
  verticalFovRad = CESIUM_DEFAULT_FOV_RAD,
) {
  const height = finite(cameraHeightM, 'cameraHeightM');
  const heightPx = finite(viewportHeightPx, 'viewportHeightPx');
  const fov = finite(verticalFovRad, 'verticalFovRad');
  if (height < 0 || heightPx <= 0 || fov <= 0 || fov >= Math.PI) {
    throw new Error('invalid Cesium height/viewport/FOV inputs');
  }
  return 2 * height * Math.tan(fov / 2) / heightPx;
}

export function mapPitchToCesiumPitchRadians(mapPitchDeg) {
  return (clampMapPitch(mapPitchDeg) - 90) * Math.PI / 180;
}

export function cesiumPitchRadiansToMapPitch(cesiumPitchRad) {
  return clampMapPitch(90 + finite(cesiumPitchRad, 'cesiumPitchRad') * 180 / Math.PI);
}

export function canonicalViewToMapLibre(view) {
  if (!view?.center) throw new Error('canonical view requires center');
  const latitude = clampLatitude(view.center.lat);
  return Object.freeze({
    center: Object.freeze([finite(view.center.lon, 'center.lon'), latitude]),
    zoom: mapLibreZoomFromGroundResolution(view.groundResolutionM, latitude),
    bearing: normalizeBearing(view.bearing || 0),
    pitch: clampMapPitch(view.requestedPitch || 0),
  });
}

export function mapLibreViewToCanonical(mapView) {
  const center = mapView?.center;
  if (!Array.isArray(center) || center.length < 2) throw new Error('MapLibre view requires [lon,lat] center');
  const latitude = clampLatitude(center[1]);
  return Object.freeze({
    center: Object.freeze({ lon: finite(center[0], 'center.lon'), lat: latitude }),
    groundResolutionM: groundResolutionFromMapLibreZoom(mapView.zoom, latitude),
    bearing: normalizeBearing(mapView.bearing || 0),
    requestedPitch: clampMapPitch(mapView.pitch || 0),
  });
}

export function canonicalViewToCesium(view, viewportHeightPx = DEFAULT_VIEWPORT_HEIGHT_PX, verticalFovRad = CESIUM_DEFAULT_FOV_RAD) {
  if (!view?.center) throw new Error('canonical view requires center');
  return Object.freeze({
    longitude: finite(view.center.lon, 'center.lon'),
    latitude: clampLatitude(view.center.lat),
    height: cesiumHeightFromGroundResolution(view.groundResolutionM, viewportHeightPx, verticalFovRad),
    heading: normalizeBearing(view.bearing || 0) * Math.PI / 180,
    pitch: mapPitchToCesiumPitchRadians(view.requestedPitch || 0),
    roll: 0,
  });
}

export function cesiumViewToCanonical(cameraView, viewportHeightPx = DEFAULT_VIEWPORT_HEIGHT_PX, verticalFovRad = CESIUM_DEFAULT_FOV_RAD) {
  return Object.freeze({
    center: Object.freeze({
      lon: finite(cameraView.longitude, 'longitude'),
      lat: clampLatitude(cameraView.latitude),
    }),
    groundResolutionM: groundResolutionFromCesiumHeight(cameraView.height, viewportHeightPx, verticalFovRad),
    bearing: normalizeBearing(finite(cameraView.heading || 0, 'heading') * 180 / Math.PI),
    requestedPitch: cesiumPitchRadiansToMapPitch(cameraView.pitch),
  });
}

export const RENDERER_VIEW_CONSTANTS = Object.freeze({
  earthCircumferenceM: EARTH_CIRCUMFERENCE_M,
  mapLibreWorldSizePx: MAPLIBRE_WORLD_SIZE_PX,
  cesiumDefaultFovRad: CESIUM_DEFAULT_FOV_RAD,
  defaultViewportHeightPx: DEFAULT_VIEWPORT_HEIGHT_PX,
});

// Camera maths for the Federation Constellation. Pure.
//
// A camera is { x, y, zoom }: the world point at the viewport centre and the
// world-to-screen scale. Flights between stages ease in and out and pull back
// in the middle when the hop is long, the way the reference video travels.

export const MIN_ZOOM = 0.06;
export const MAX_ZOOM = 2.6;
export const FLIGHT_MS = 1800;
export const DWELL_MS = 7000;

export const clampZoom = (zoom) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));

export const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

// `inset` reserves screen space (e.g. the caption band) as { top, right, bottom, left }.
export function fitBounds(bounds, viewport, { padding = 48, inset = {}, maxZoom = 1.35 } = {}) {
  if (!bounds) return { x: 0, y: 0, zoom: 0.5 };
  const top = (inset.top || 0) + padding;
  const bottom = (inset.bottom || 0) + padding;
  const left = (inset.left || 0) + padding;
  const right = (inset.right || 0) + padding;
  const availW = Math.max(40, viewport.width - left - right);
  const availH = Math.max(40, viewport.height - top - bottom);
  const bw = Math.max(1, bounds.x1 - bounds.x0);
  const bh = Math.max(1, bounds.y1 - bounds.y0);
  const zoom = clampZoom(Math.min(availW / bw, availH / bh, maxZoom));
  // Centre the bounds inside the inset area, not the whole viewport.
  const cx = (bounds.x0 + bounds.x1) / 2 - ((left - right) / 2) / zoom;
  const cy = (bounds.y0 + bounds.y1) / 2 - ((top - bottom) / 2) / zoom;
  return { x: cx, y: cy, zoom };
}

export const worldToScreen = (cam, viewport, p) => ({
  x: (p.x - cam.x) * cam.zoom + viewport.width / 2,
  y: (p.y - cam.y) * cam.zoom + viewport.height / 2,
});

export const screenToWorld = (cam, viewport, p) => ({
  x: (p.x - viewport.width / 2) / cam.zoom + cam.x,
  y: (p.y - viewport.height / 2) / cam.zoom + cam.y,
});

// Interpolate a flight from a to b at eased progress t in [0, 1]. Zoom moves in
// log space; long hops dip toward a wider view mid-flight.
export function flight(a, b, t, viewport) {
  const e = easeInOutCubic(Math.min(1, Math.max(0, t)));
  const zoom = Math.exp(Math.log(a.zoom) + (Math.log(b.zoom) - Math.log(a.zoom)) * e);
  const dist = Math.hypot(b.x - a.x, b.y - a.y);
  const span = Math.max(viewport.width, viewport.height) / Math.min(a.zoom, b.zoom);
  const dip = Math.min(0.55, dist / (span * 2.5));
  return {
    x: a.x + (b.x - a.x) * e,
    y: a.y + (b.y - a.y) * e,
    zoom: clampZoom(zoom * (1 - dip * Math.sin(Math.PI * e))),
  };
}

// A slow push-in while a stage is on screen; `t` is the fraction of the dwell elapsed.
export function drift(cam, t) {
  const s = Math.min(1, Math.max(0, t));
  return { x: cam.x + Math.sin(s * Math.PI) * 18 / cam.zoom, y: cam.y, zoom: clampZoom(cam.zoom * (1 + 0.06 * s)) };
}

// Zoom by `factor` keeping the world point under `screenPoint` fixed.
export function zoomAt(cam, viewport, screenPoint, factor) {
  const before = screenToWorld(cam, viewport, screenPoint);
  const zoom = clampZoom(cam.zoom * factor);
  const after = screenToWorld({ ...cam, zoom }, viewport, screenPoint);
  return { x: cam.x + (before.x - after.x), y: cam.y + (before.y - after.y), zoom };
}

export const panBy = (cam, dx, dy) => ({ ...cam, x: cam.x - dx / cam.zoom, y: cam.y - dy / cam.zoom });

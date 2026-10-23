// Deep links (FDX-056): URL-addressable search, entity, evidence and map
// positions. Every builder encodes its inputs; every parser validates and
// returns null rather than guessing, so a malformed link is reported, not
// silently "corrected". No credential ever travels in these URLs.

export const SEARCH_TYPES = ['ALL', 'READING', 'FINDING', 'TIMELINE', 'SOURCE', 'ENTITY'];

const MAX_ZOOM = 22;

function finiteNumber(value) {
  if (value === null || value === undefined || String(value).trim() === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function validMapView({ lat, lon, z }) {
  const latitude = finiteNumber(lat);
  const longitude = finiteNumber(lon);
  if (latitude === null || longitude === null) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  const zoom = finiteNumber(z);
  if (z !== undefined && z !== null && String(z).trim() !== '' && (zoom === null || zoom < 0 || zoom > MAX_ZOOM)) {
    return null;
  }
  return { lat: latitude, lon: longitude, z: zoom };
}

// `?lat=18.2&lon=-66.5&z=12` -> { lat, lon, z } | null. Absent lat/lon is "no deep link" (undefined).
export function parseMapView(searchParams) {
  const lat = searchParams.get('lat');
  const lon = searchParams.get('lon');
  if (lat === null && lon === null) return undefined;
  return validMapView({ lat, lon, z: searchParams.get('z') ?? undefined });
}

export function mapViewHref({ lat, lon, z }) {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (z !== null && z !== undefined) params.set('z', String(z));
  return `/gis?${params.toString()}`;
}

// "18.2, -66.5" | "18.2 -66.5 z12" -> { lat, lon, z } | null (lat first, as written in PR).
export function parseCoordinateQuery(text) {
  const match = String(text || '').trim().match(
    /^(-?\d{1,2}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)(?:\s*(?:,|\s)\s*z?\s*(\d{1,2}(?:\.\d+)?))?$/i,
  );
  if (!match) return null;
  return validMapView({ lat: match[1], lon: match[2], z: match[3] });
}

export function searchHref(query, type = 'ALL') {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (type && type !== 'ALL') params.set('type', type);
  const qs = params.toString();
  return qs ? `/search?${qs}` : '/search';
}

export function entityHref(recordId) {
  return `/entity/${encodeURIComponent(String(recordId))}`;
}

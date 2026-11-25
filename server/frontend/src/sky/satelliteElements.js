// The orbital elements behind the Sky workspace's satellites (TWIN-042..046): one request per satellite to
// CelesTrak's GP service (CORS-open, keyless), straight from the browser. The Hub is the acquirer (ADR 0006); no
// producer is called. A satellite whose elements cannot be read is FAILED with the reason and has no element set:
// nothing is guessed, defaulted or filled from an older copy. Every loaded element set keeps the NORAD catalogue
// number the answer carries (checked against the one asked for) and its epoch.
//
// CelesTrak resets connections from addresses that ask too often (about five requests a minute), so this makes
// exactly one request per satellite and never retries; the caller decides when to ask again.
import { SATELLITES, elementAge, gpUrl, parseGp } from './satellites.js';

export const ELEMENT_SOURCE = Object.freeze({
  provider: 'CelesTrak', service: 'GP (general perturbations) JSON', homepage: 'https://celestrak.org/',
  contract: 'CelesTrak GP JSON in the CCSDS OMM field names, mean elements for SGP4',
});
export const ELEMENT_TIMEOUT_MS = 10000;

async function loadOne(satellite, { fetchImpl, now, timeoutMs }) {
  const url = gpUrl(satellite.noradId);
  const base = { id: satellite.id, noradId: satellite.noradId, label: satellite.label, url, retrievedAt: now };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url, { signal: controller.signal, headers: { accept: 'application/json' } });
    if (!response.ok) throw new Error(`CelesTrak answered HTTP ${response.status}`);
    let body;
    try { body = await response.json(); } catch { throw new Error('CelesTrak\'s answer was not JSON'); }
    if (!Array.isArray(body) || body.length === 0) throw new Error(`CelesTrak returned no object for catalogue number ${satellite.noradId}`);
    const matching = body.filter((record) => Number(record?.NORAD_CAT_ID) === satellite.noradId);
    if (matching.length !== 1) throw new Error(`CelesTrak returned ${matching.length} objects for catalogue number ${satellite.noradId}, not 1`);
    const element = parseGp(matching[0]);
    // The record as CelesTrak sent it is kept beside the parsed element set, so what was read can always be shown.
    return Object.freeze({ ...base, state: 'LOADED', error: null, element, record: Object.freeze({ ...matching[0] }), name: element.name, epoch: element.epoch, ageAtRetrieval: elementAge(element, now) });
  } catch (error) {
    const aborted = error?.name === 'AbortError' || controller.signal.aborted;
    const reason = aborted ? `No answer from CelesTrak within ${timeoutMs / 1000} seconds` : (error?.message || String(error));
    return Object.freeze({ ...base, state: 'FAILED', error: reason, element: null, record: null, name: null, epoch: null, ageAtRetrieval: null });
  } finally {
    clearTimeout(timer);
  }
}

export async function loadSatelliteElements({
  fetchImpl = (...args) => globalThis.fetch(...args), now = new Date(), timeoutMs = ELEMENT_TIMEOUT_MS, satellites = SATELLITES,
} = {}) {
  const items = await Promise.all(satellites.map((satellite) => loadOne(satellite, { fetchImpl, now, timeoutMs })));
  return Object.freeze({
    retrievedAt: now, source: ELEMENT_SOURCE, requested: items.length, loaded: items.filter((item) => item.state === 'LOADED').length, items,
  });
}

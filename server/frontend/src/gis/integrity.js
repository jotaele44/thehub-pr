function normalizeForStableJson(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(normalizeForStableJson);
  return Object.keys(value).sort().reduce((acc, key) => {
    acc[key] = normalizeForStableJson(value[key]);
    return acc;
  }, {});
}

export function stableJson(value) {
  return JSON.stringify(normalizeForStableJson(value));
}

export function frameRawTexts(rawTexts = []) {
  const encoder = new TextEncoder();
  return rawTexts.map((text, index) => {
    if (typeof text !== 'string') throw new Error(`rawTexts[${index}] must be a string`);
    return `${encoder.encode(text).byteLength}:${text}`;
  }).join('');
}

function toHex(bytes) {
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export async function sha256Bytes(bytes) {
  if (!globalThis.crypto?.subtle) return null;
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', view);
  return toHex(digest);
}

export async function sha256Text(text) {
  if (typeof text !== 'string') throw new Error('SHA-256 input must be a string');
  return sha256Bytes(new TextEncoder().encode(text));
}

export async function sha256StableJson(value) {
  return sha256Text(stableJson(value));
}

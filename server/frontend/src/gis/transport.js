function proxyUrl(sourceId, target) {
  const params = new URLSearchParams({ source_id: sourceId, target });
  return `/api/gis/proxy?${params.toString()}`;
}

async function readTextResponse(response, url) {
  const rawText = await response.text();
  if (!response.ok) throw new Error(`remote fetch failed ${response.status || 'UNKNOWN'} ${response.statusText || ''} for ${url}${rawText ? `: ${rawText.slice(0, 240)}` : ''}`);
  return Object.freeze({ rawText, response, effectiveUrl: url });
}

export async function fetchSourceText(source, target, options = {}) {
  const injected = options.fetchImpl;
  if (typeof injected === 'function') {
    return readTextResponse(await injected(target, { headers: { Accept: options.accept || 'application/json, application/geo+json, application/xml, text/xml' } }), target);
  }
  const fetchImpl = globalThis.fetch;
  if (typeof fetchImpl !== 'function') throw new Error('online acquisition requires fetch');
  const transport = source.transport || 'direct';
  if (transport === 'proxy-required') {
    const url = proxyUrl(source.sourceId, target);
    return readTextResponse(await fetchImpl(url, { headers: { Accept: options.accept || '*/*' } }), url);
  }
  try {
    return await readTextResponse(await fetchImpl(target, { headers: { Accept: options.accept || '*/*' } }), target);
  } catch (error) {
    if (transport !== 'direct-or-proxy') throw error;
    const url = proxyUrl(source.sourceId, target);
    return readTextResponse(await fetchImpl(url, { headers: { Accept: options.accept || '*/*' } }), url);
  }
}

export async function fetchSourceRange(source, target, range = 'bytes=0-65535', options = {}) {
  const injected = options.fetchImpl;
  const fetchImpl = injected || globalThis.fetch;
  if (typeof fetchImpl !== 'function') throw new Error('raster acquisition requires fetch');
  const useProxy = !injected && (source.transport === 'proxy-required' || source.transport === 'direct-or-proxy');
  const url = useProxy ? `${proxyUrl(source.sourceId, target)}&byte_range=${encodeURIComponent(range)}` : target;
  const headers = useProxy ? { Accept: '*/*' } : { Accept: '*/*', Range: range };
  const response = await fetchImpl(url, { headers });
  if (!response.ok && response.status !== 206) throw new Error(`raster range fetch failed ${response.status || 'UNKNOWN'} for ${url}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  return Object.freeze({
    bytes,
    requestedRange: range,
    contentType: response.headers?.get?.('content-type') || null,
    contentRange: response.headers?.get?.('content-range') || null,
    contentLength: response.headers?.get?.('content-length') || null,
    effectiveUrl: url,
  });
}

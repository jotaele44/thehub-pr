import { describe, expect, it, vi } from 'vitest';

import { fetchSourceRange } from './transport';


function response(status, bytes = [1, 2, 3]) {
  return {
    ok: status >= 200 && status < 300,
    status,
    arrayBuffer: vi.fn(async () => Uint8Array.from(bytes).buffer),
    headers: { get: () => null },
  };
}


describe('bounded raster range transport', () => {
  it('accepts a 206 partial response', async () => {
    const result = await fetchSourceRange(
      { transport: 'direct' },
      'https://example.test/tile.tif',
      'bytes=0-2',
      { fetchImpl: async () => response(206) },
    );

    expect([...result.bytes]).toEqual([1, 2, 3]);
  });

  it('rejects a 200 response before reading the full body', async () => {
    const fullResponse = response(200, new Array(1024).fill(1));

    await expect(fetchSourceRange(
      { transport: 'direct' },
      'https://example.test/tile.tif',
      'bytes=0-2',
      { fetchImpl: async () => fullResponse },
    )).rejects.toThrow(/requires 206 Partial Content/);
    expect(fullResponse.arrayBuffer).not.toHaveBeenCalled();
  });
});

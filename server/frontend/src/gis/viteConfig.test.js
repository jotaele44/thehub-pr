import { describe, expect, it } from 'vitest';
import { CESIUM_CONTENT_TYPES } from '../../vite.config';

describe('Cesium runtime asset MIME bindings', () => {
  it('serves WebAssembly with its required media type', () => {
    expect(CESIUM_CONTENT_TYPES['.wasm']).toBe('application/wasm');
  });
});

import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => ({ setWorkerUrl: vi.fn(), Map: vi.fn() }));

describe('MapLibre entry point', () => {
  it('points MapLibre at the bundled worker before any map is created', async () => {
    const maplibre = await import('maplibre-gl');
    const { maplibregl, workerUrl } = await import('./maplibre');
    expect(workerUrl).toMatch(/maplibre-gl-worker/);
    expect(maplibre.setWorkerUrl).toHaveBeenCalledWith(workerUrl);
    expect(maplibregl.Map).toBe(maplibre.Map);
  });
});

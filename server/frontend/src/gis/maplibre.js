// MapLibre GL 6 finds its web worker relative to its own module URL. A bundle
// rewrites that URL, so the built app asked for /assets/maplibre-gl-worker.mjs,
// which was never emitted: the worker never started and no GeoJSON layer ever
// rendered. Vite bundles the worker (with the shared chunk it imports) and
// returns its URL; every map in the app imports MapLibre through this module so
// the worker URL is set before the first map is created.
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl, workerUrl };

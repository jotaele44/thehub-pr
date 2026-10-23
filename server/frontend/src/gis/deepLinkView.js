import { createCanonicalMapState } from '@/gis/contracts';
import { groundResolutionFromMapLibreZoom } from '@/gis/rendererView';
import { parseMapView } from '@/lib/deepLinks';

export const DEEP_LINK_DEFAULT_ZOOM = 12;

// `/gis?lat&lon&z` (FDX-056): a valid deep link centres the canonical view; a
// malformed one is reported and the default view is kept, never "corrected".
export function initialMapState(searchParams, defaultState) {
  const view = parseMapView(searchParams);
  if (view === undefined) return { state: defaultState, notice: null };
  if (view === null) {
    return { state: defaultState, notice: 'The map link has an invalid lat, lon or z, so the default view is shown.' };
  }
  const zoom = view.z ?? DEEP_LINK_DEFAULT_ZOOM;
  return {
    state: createCanonicalMapState({
      ...defaultState,
      view: {
        ...defaultState.view,
        center: { lon: view.lon, lat: view.lat },
        groundResolutionM: groundResolutionFromMapLibreZoom(zoom, view.lat),
      },
    }),
    notice: `Centred on ${view.lat}, ${view.lon} at zoom ${zoom} from the page link.`,
  };
}

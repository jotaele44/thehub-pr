export const MUNICIPIOS_STYLE = Object.freeze({
  color: "#475569",
  weight: 1,
  fillColor: "#1e293b",
  fillOpacity: 0.6,
});

let cachedPromise = null;

// Renderer-agnostic loader for the committed Puerto Rico municipality fallback.
// The asset remains resolved against document.baseURI so it works in the normal
// Vite build and in the single-file/offline desktop export.
export function loadMunicipiosGeoJSON() {
  if (cachedPromise) return cachedPromise;
  const url = new URL("geo/pr_municipios.geojson", document.baseURI).href;
  cachedPromise = fetch(url)
    .then((response) => {
      if (!response.ok) throw new Error(`municipios fallback fetch failed: HTTP ${response.status}`);
      return response.json();
    })
    .catch((error) => {
      cachedPromise = null;
      throw error;
    });
  return cachedPromise;
}

// Compatibility export retained while consumers migrate to the shared MapLibre
// component. Rendering ownership no longer lives in this module.
export default function MunicipiosLayer() {
  return null;
}

import { useEffect, useState } from "react";
import { GeoJSON, Pane } from "react-leaflet";

// Puerto Rico municipality outlines, drawn in a pane beneath the tile layer so
// the geography is still visible when the online basemap tiles can't load
// (i.e. offline). Served from public/geo/ (resolved against the document base
// so it works in the normal build and the single-file offline export).
const STYLE = { color: "#475569", weight: 1, fillColor: "#1e293b", fillOpacity: 0.6 };

export default function MunicipiosLayer() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    const url = new URL("geo/pr_municipios.geojson", document.baseURI).href;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive) setData(d);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!data) return null;
  return (
    <Pane name="municipios" style={{ zIndex: 150 }}>
      <GeoJSON data={data} style={STYLE} interactive={false} />
    </Pane>
  );
}

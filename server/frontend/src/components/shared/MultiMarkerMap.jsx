import React from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import MunicipiosLayer from "./MunicipiosLayer";

const icon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41],
});

// Puerto Rico default center.
const PR_CENTER = [18.22, -66.4];

// Renders many geolocated records as pins.
// points: [{ id, lat, lon, title, subtitle }]
export default function MultiMarkerMap({ points = [], height = 480 }) {
  const valid = points.filter(
    (p) => typeof p.lat === "number" && typeof p.lon === "number" && !Number.isNaN(p.lat) && !Number.isNaN(p.lon)
  );
  const center = valid.length ? [valid[0].lat, valid[0].lon] : PR_CENTER;

  return (
    <div className="rounded-lg overflow-hidden border border-border" style={{ height }}>
      <MapContainer center={center} zoom={9} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          opacity={0.85}
          attribution="&copy; OpenStreetMap, &copy; CARTO"
        />
        <MunicipiosLayer />
        {valid.map((p) => (
          <Marker key={p.id} position={[p.lat, p.lon]} icon={icon}>
            <Popup>
              <div className="text-sm font-medium">{p.title}</div>
              {p.subtitle && <div className="text-xs text-muted-foreground mt-0.5">{p.subtitle}</div>}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
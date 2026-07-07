import { HUB_REPO } from "@/lib/federation";

// Generic, provenance-preserving export utilities for federation ledgers.
// All exports inject source_repo = thehub-pr and keep IDs, module, evidence tier,
// confidence, and review status when those fields exist on the record.

const esc = (v) => {
  if (v === null || v === undefined) return "";
  const s = Array.isArray(v) ? v.join("; ") : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function download(content, fileName, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

const stamp = () => new Date().toISOString().slice(0, 10);

// Build a flat row from an entity record (data lives at top level after .list()).
const flatten = (rec) => ({ ...(rec.data || rec), id: rec.id || rec.data?.id });

// CSV export. `columns` is an ordered array of field keys. source_repo is always appended.
export function exportLedgerCsv(records, { columns, fileNameBase, module }) {
  const cols = columns.includes("source_repo") ? columns : [...columns, "source_repo"];
  const rows = records.map(flatten);
  const header = cols.join(",");
  const body = rows
    .map((r) => cols.map((c) => esc(c === "source_repo" ? (r.source_repo || HUB_REPO) : r[c])).join(","))
    .join("\n");
  const fileName = `${fileNameBase}-${stamp()}.csv`;
  download(`${header}\n${body}`, fileName, "text/csv;charset=utf-8;");
  return { fileName, count: rows.length, module };
}

// GeoJSON export for geospatial ledgers. Only records with numeric lat/long are emitted.
// All non-geometry fields are preserved as feature properties (provenance-safe).
export function exportLedgerGeoJson(records, { fileNameBase, module }) {
  const rows = records.map(flatten);
  const features = rows
    .filter((r) => typeof r.latitude === "number" && typeof r.longitude === "number")
    .map((r) => {
      const { latitude, longitude, ...props } = r;
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [longitude, latitude] },
        properties: { ...props, source_repo: props.source_repo || HUB_REPO },
      };
    });
  const fc = {
    type: "FeatureCollection",
    metadata: { module, source_repo: HUB_REPO, exported_at: new Date().toISOString(), feature_count: features.length },
    features,
  };
  const fileName = `${fileNameBase}-${stamp()}.geojson`;
  download(JSON.stringify(fc, null, 2), fileName, "application/geo+json;charset=utf-8;");
  return { fileName, count: features.length, module };
}

// Count records that carry usable geometry.
export const geoCount = (records) =>
  records.map(flatten).filter((r) => typeof r.latitude === "number" && typeof r.longitude === "number").length;
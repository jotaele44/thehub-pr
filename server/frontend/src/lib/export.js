// Provenance-preserving client-side export helpers (CSV + GeoJSON).

const unwrap = (row) => (row && row.data ? { ...row.data, id: row.id ?? row.data.id } : row);

const csvEscape = (value) => {
  if (value === undefined || value === null) return "";
  let s = value;
  if (typeof s === "object") s = JSON.stringify(s);
  s = String(s);
  if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
};

export function toCsv(rows, columns) {
  const records = rows.map(unwrap);
  const cols = columns && columns.length
    ? columns
    : Array.from(records.reduce((set, r) => {
        Object.keys(r || {}).forEach((k) => set.add(k));
        return set;
      }, new Set()));
  const header = cols.map(csvEscape).join(",");
  const lines = records.map((r) => cols.map((c) => csvEscape(r?.[c])).join(","));
  return [header, ...lines].join("\n");
}

export function downloadFile(content, fileName, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const hasGeo = (r) => num(r?.latitude) !== null && num(r?.longitude) !== null;

// Count of records that carry a mappable latitude/longitude pair.
export function geoCount(records = []) {
  return records.map(unwrap).filter(hasGeo).length;
}

// Export a ledger to CSV; returns { fileName, count } for the audit trail.
export function exportLedgerCsv(records = [], { columns, fileNameBase = "ledger" } = {}) {
  const rows = records.map(unwrap);
  const fileName = `${fileNameBase}-${new Date().toISOString().slice(0, 10)}.csv`;
  downloadFile(toCsv(rows, columns), fileName, "text/csv;charset=utf-8");
  return { fileName, count: rows.length };
}

// Export mappable rows of a ledger as a GeoJSON FeatureCollection;
// returns { fileName, count } for the audit trail.
export function exportLedgerGeoJson(records = [], { fileNameBase = "ledger", module } = {}) {
  const rows = records.map(unwrap).filter(hasGeo);
  const collection = {
    type: "FeatureCollection",
    features: rows.map((r) => {
      const { latitude, longitude, ...properties } = r;
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [num(longitude), num(latitude)] },
        properties: { ...properties, module: module || properties.module },
      };
    }),
  };
  const fileName = `${fileNameBase}-${new Date().toISOString().slice(0, 10)}.geojson`;
  downloadFile(JSON.stringify(collection, null, 2), fileName, "application/geo+json");
  return { fileName, count: rows.length };
}

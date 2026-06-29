const toCsvCell = (value) => {
  if (value === null || value === undefined) return '';
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function geoCount(rows = []) {
  return rows.filter((r) => Number.isFinite(Number(r.latitude)) && Number.isFinite(Number(r.longitude))).length;
}

export function exportLedgerCsv(rows = [], fileName = 'ledger.csv') {
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r || {}))));
  const csv = [keys.join(','), ...rows.map((r) => keys.map((k) => toCsvCell(r[k])).join(','))].join('\n');
  downloadText(csv, fileName, 'text/csv');
  return { fileName, recordCount: rows.length };
}

export function exportLedgerGeoJson(rows = [], fileName = 'ledger.geojson') {
  const features = rows.filter((r) => r.latitude && r.longitude).map((r) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [Number(r.longitude), Number(r.latitude)] }, properties: { ...r } }));
  const geojson = JSON.stringify({ type: 'FeatureCollection', features }, null, 2);
  downloadText(geojson, fileName, 'application/geo+json');
  return { fileName, recordCount: features.length };
}

function downloadText(text, fileName, type) {
  if (typeof window === 'undefined') return;
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

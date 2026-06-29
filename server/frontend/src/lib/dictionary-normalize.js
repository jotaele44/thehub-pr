export function normalizeTerm(value) {
  return (value || '').toString().trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
}

export function buildDictionaryIndex(rows = []) {
  const index = new Map();
  for (const row of rows) {
    const key = normalizeTerm(row.term || row.name || row.label || row.title);
    if (key) index.set(key, row);
  }
  return index;
}

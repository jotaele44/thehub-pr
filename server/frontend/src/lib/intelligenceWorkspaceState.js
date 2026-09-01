export const INTELLIGENCE_TIME_WINDOWS = Object.freeze({
  all: null,
  '6h': 6 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
});

export function normalizeSearchText(value) {
  return String(value ?? '').trim().toLowerCase();
}

export function parseTimestampMs(value) {
  if (value === undefined || value === null || value === '') return null;
  if (value instanceof Date) {
    const ms = value.getTime();
    return Number.isFinite(ms) ? ms : null;
  }
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const ms = Date.parse(String(value));
  return Number.isFinite(ms) ? ms : null;
}

export function readExplicitState(row, keys, fallback) {
  for (const key of keys) {
    const raw = row?.[key];
    if (raw !== undefined && raw !== null && String(raw).trim() !== '') {
      return String(raw).trim().toUpperCase();
    }
  }
  return fallback;
}

export function coerceContradictions(row) {
  const raw = row?.contradictions ?? row?._contradictions ?? row?.conflicts;
  if (raw === undefined || raw === null || raw === '') return [];
  const values = Array.isArray(raw) ? raw : [raw];
  return values.map((item) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object') {
      return item.summary || item.description || item.type || JSON.stringify(item);
    }
    return String(item);
  });
}

export function uniqueNonEmpty(values) {
  return [...new Set(values.flatMap((value) => Array.isArray(value) ? value : [value])
    .map((value) => String(value ?? '').trim())
    .filter(Boolean))];
}

export function filterIntelligenceRows(rows, adapter, filters = {}, nowMs = Date.now()) {
  const sourceRows = Array.isArray(rows) ? rows : [];
  const query = normalizeSearchText(filters.query);
  const category = filters.category && filters.category !== 'all' ? String(filters.category) : null;
  const timeWindow = filters.timeWindow || 'all';
  const windowMs = INTELLIGENCE_TIME_WINDOWS[timeWindow];
  if (windowMs === undefined) throw new Error(`Unknown intelligence time window: ${timeWindow}`);

  let undatedCount = 0;
  let undatedRetainedCount = 0;
  let undatedExcludedCount = 0;
  let futureTimestampCount = 0;

  const visible = sourceRows.filter((row) => {
    if (query) {
      const haystack = adapter.getSearchValues(row).map(normalizeSearchText).join('\n');
      if (!haystack.includes(query)) return false;
    }

    if (category && String(adapter.getCategory(row) ?? '') !== category) return false;

    const timestampMs = parseTimestampMs(adapter.getTimestamp?.(row));
    if (timestampMs === null) undatedCount += 1;
    else if (timestampMs > nowMs) futureTimestampCount += 1;

    if (windowMs === null) return true;

    if (timestampMs === null) {
      if (adapter.temporalPolicy === 'retain-undated') {
        undatedRetainedCount += 1;
        return true;
      }
      undatedExcludedCount += 1;
      return false;
    }

    if (timestampMs > nowMs) return false;
    return timestampMs >= nowMs - windowMs;
  });

  // Diagnostics describe the loaded denominator rather than only the visible
  // search/category slice. Temporal retained/excluded counts remain scoped to
  // rows that reached the temporal gate.
  if (query || category) {
    undatedCount = sourceRows.filter((row) => parseTimestampMs(adapter.getTimestamp?.(row)) === null).length;
    futureTimestampCount = sourceRows.filter((row) => {
      const timestampMs = parseTimestampMs(adapter.getTimestamp?.(row));
      return timestampMs !== null && timestampMs > nowMs;
    }).length;
  }

  const sourceCount = sourceRows.length;
  const visibleCount = visible.length;
  const excludedCount = sourceCount - visibleCount;
  if (sourceCount !== visibleCount + excludedCount) {
    throw new Error('Intelligence workspace denominator failed to close');
  }

  return {
    visible,
    metrics: {
      sourceCount,
      visibleCount,
      excludedCount,
      undatedCount,
      undatedRetainedCount,
      undatedExcludedCount,
      futureTimestampCount,
    },
  };
}

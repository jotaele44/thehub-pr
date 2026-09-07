export function toStacBoundary(value, endOfDay = false) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T${endOfDay ? '23:59:59' : '00:00:00'}Z`;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error(`invalid STAC datetime boundary: ${value}`);
  return parsed.toISOString();
}

export function toStacInterval(start, end) {
  const normalizedStart = toStacBoundary(start, false);
  const normalizedEnd = toStacBoundary(end, true);
  return Object.freeze({
    requestedStart: start || null,
    requestedEnd: end || null,
    start: normalizedStart,
    end: normalizedEnd,
    datetime: normalizedStart || normalizedEnd ? `${normalizedStart || '..'}/${normalizedEnd || '..'}` : null,
  });
}

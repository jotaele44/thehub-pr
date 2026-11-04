// How the Sky workspace writes times, angles and offsets, shared by its panels so one reading never differs from another.
import { formatClock } from '@/sky/astronomy';

export const button = 'min-h-[44px] rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-50';
export const field = 'min-h-[44px] w-full rounded-md border border-border bg-background px-2 text-sm';

export const isoOf = (date) => date.toISOString().replace('.000Z', 'Z');
export const degrees = (value) => `${value.toFixed(1)}°`;
export const offsetLabel = (tz) => (tz === 0 ? 'UTC' : `UTC${tz > 0 ? '+' : '-'}${Math.abs(tz)}`);
export const eventText = (date, tz) => `${formatClock(date, tz)} ${offsetLabel(tz)} (${formatClock(date, 0)} UTC)`;

// To the second, for events a few minutes long (a satellite pass), at the observer's offset and in UTC.
const secondsClock = (date, tz) => new Date(date.getTime() + tz * 3600e3).toISOString().slice(11, 19);
export const preciseEventText = (date, tz) => `${secondsClock(date, tz)} ${offsetLabel(tz)} (${secondsClock(date, 0)} UTC)`;

export function duration(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${String(seconds % 60).padStart(2, '0')} s`;
}

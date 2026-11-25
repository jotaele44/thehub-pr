// Multi-sensor clock alignment (FDX-038): putting events from several sources (an aircraft track, a witness report, a
// camera, a sensor) on one UTC timeline, so a reconstruction can say which sources cover the observation window.
// It mirrors the protocol of the Skywatcher replay (skywatcher-multisensor-replay-v1): the timeline is the union of the
// event timestamps, there is no interpolation, a gap is declared with a reason and never inferred, overlapping gaps for
// one source are refused, and every time is normalised to UTC from an explicit zone.
//
// What this does NOT do, on purpose: it never estimates a clock offset. An offset is something a person knows about a
// device (an NTP check, a camera that was 3.2 s fast) and declares with its basis; guessing it from the content of the
// events would make the answer depend on the guess. An offset that is not declared is zero, said so in the result.
import { sha256StableJson } from '../../gis/integrity.js';
import { parseInstant } from './aircraftTracks.js';

export const CLOCK_ALIGNMENT_CONTRACT = 'sky-clock-alignment-v1';
export const MIRRORED_PROTOCOL = Object.freeze({
  protocol: 'skywatcher-multisensor-replay-v1', timeline_policy: 'union_observation_timestamps', interpolation: 'none',
});
export const SENSOR_TYPES = Object.freeze(['aircraft_track', 'observer_report', 'camera_frame', 'sensor_series']);
export const MAX_SOURCES = 20;
export const MAX_EVENTS = 100000;
const MAX_TIMELINE_ROWS = 2000;
const MAX_OFFSET_SECONDS = 86400;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const iso = (ms) => new Date(ms).toISOString();

function normaliseGaps(source, gaps) {
  if (gaps === undefined) return [];
  if (!Array.isArray(gaps)) throw new RangeError(`Source ${source}: gaps must be a list.`);
  const out = gaps.map((gap, i) => {
    if (!gap || typeof gap.reason !== 'string' || !gap.reason.trim()) throw new RangeError(`Source ${source}: gap ${i + 1} needs a reason: a gap is declared with its cause and never inferred.`);
    const start = parseInstant(gap.startUtc);
    const end = parseInstant(gap.endUtc);
    if (start.error || end.error) throw new RangeError(`Source ${source}: gap ${i + 1} needs a start and an end in UTC with a zone (${start.error ?? end.error}).`);
    if (!(start.ms < end.ms)) throw new RangeError(`Source ${source}: gap ${i + 1} must start before it ends.`);
    return { sourceId: source, startMs: start.ms, endMs: end.ms, reason: gap.reason.trim() };
  }).sort((a, b) => a.startMs - b.startMs || a.endMs - b.endMs);
  for (let i = 1; i < out.length; i += 1) {
    if (out[i].startMs < out[i - 1].endMs) throw new RangeError(`Source ${source}: two declared gaps overlap.`);
  }
  return out;
}

export function alignSources(input) {
  if (!Array.isArray(input) || input.length === 0) throw new RangeError('Give at least one source.');
  if (input.length > MAX_SOURCES) throw new RangeError(`At most ${MAX_SOURCES} sources are aligned together.`);
  const ids = new Set();
  const sources = [];
  const events = [];
  const gaps = [];
  const warnings = [];
  const notes = [];
  let total = 0;
  for (const raw of input) {
    const sourceId = typeof raw?.sourceId === 'string' ? raw.sourceId.trim() : '';
    if (!sourceId) throw new RangeError('Every source needs a sourceId.');
    if (ids.has(sourceId)) throw new RangeError(`Two sources are called ${sourceId}.`);
    ids.add(sourceId);
    if (!SENSOR_TYPES.includes(raw.sensorType)) throw new RangeError(`Source ${sourceId}: the sensor type must be one of ${SENSOR_TYPES.join(', ')}.`);
    let offset = 0;
    let basis = null;
    const declared = raw.clockOffsetSeconds !== undefined;
    if (declared) {
      offset = raw.clockOffsetSeconds;
      if (!finite(offset) || Math.abs(offset) > MAX_OFFSET_SECONDS) throw new RangeError(`Source ${sourceId}: the clock offset must be a number of seconds within a day (the amount to add to this source's times to reach UTC).`);
      if (offset !== 0) {
        basis = typeof raw.clockOffsetBasis === 'string' ? raw.clockOffsetBasis.trim() : '';
        if (!basis) throw new RangeError(`Source ${sourceId}: a clock offset needs its basis (how it is known). An offset is declared, never inferred or guessed.`);
      }
    } else {
      notes.push(`Source ${sourceId} declared no clock offset; its times are taken as UTC as written.`);
    }
    if (!Array.isArray(raw.events)) throw new RangeError(`Source ${sourceId}: events must be a list.`);
    total += raw.events.length;
    if (total > MAX_EVENTS) throw new RangeError(`More than ${MAX_EVENTS} events in all; this does not align that many.`);
    const format = raw.timeFormat ?? 'ISO';
    const seen = new Set();
    const mine = raw.events.map((event, i) => {
      const id = typeof event?.id === 'string' && event.id.trim() ? event.id.trim() : `${sourceId}#${i + 1}`;
      if (seen.has(id)) throw new RangeError(`Source ${sourceId}: two events are called ${id}.`);
      seen.add(id);
      const t = parseInstant(event?.time, format);
      if (t.error) throw new RangeError(`Source ${sourceId}: event ${id}: ${t.error}.`);
      return { sourceId, id, sensorType: raw.sensorType, rawMs: t.ms, alignedMs: t.ms + Math.round(offset * 1000), offsetSeconds: offset, detail: event.detail ?? null };
    });
    const sourceGaps = normaliseGaps(sourceId, raw.gaps);
    gaps.push(...sourceGaps);
    for (const e of mine) {
      const inside = sourceGaps.find((g) => e.alignedMs >= g.startMs && e.alignedMs < g.endMs);
      if (inside) warnings.push({ sourceId, eventId: e.id, message: `Event ${e.id} of ${sourceId} is inside a gap the same source declared (${inside.reason}); one of the two is wrong.` });
    }
    events.push(...mine);
    const times = mine.map((e) => e.alignedMs).sort((a, b) => a - b);
    let longest = null;
    for (let i = 1; i < times.length; i += 1) longest = Math.max(longest ?? 0, (times[i] - times[i - 1]) / 1000);
    sources.push(Object.freeze({
      sourceId, label: raw.label ?? null, sensorType: raw.sensorType, events: mine.length,
      clockOffsetSeconds: offset, clockOffsetDeclared: declared, clockOffsetBasis: basis,
      first: times.length ? iso(times[0]) : null, last: times.length ? iso(times[times.length - 1]) : null, longestIntervalSeconds: longest,
      gaps: sourceGaps.length,
    }));
  }
  events.sort((a, b) => a.alignedMs - b.alignedMs || (a.sourceId < b.sourceId ? -1 : (a.sourceId > b.sourceId ? 1 : 0)) || (a.id < b.id ? -1 : 1));
  gaps.sort((a, b) => a.startMs - b.startMs || (a.sourceId < b.sourceId ? -1 : 1));
  const stamps = [...new Set(events.map((e) => e.alignedMs))];
  const reports = new Map();
  for (const e of events) {
    if (!reports.has(e.alignedMs)) reports.set(e.alignedMs, new Set());
    reports.get(e.alignedMs).add(e.sourceId);
  }
  const timeline = stamps.slice(0, MAX_TIMELINE_ROWS).map((ms) => ({
    time: iso(ms),
    sources: Object.fromEntries(sources.map((s) => {
      if (reports.get(ms).has(s.sourceId)) return [s.sourceId, 'REPORTED'];
      if (gaps.some((g) => g.sourceId === s.sourceId && ms >= g.startMs && ms < g.endMs)) return [s.sourceId, 'DECLARED_GAP'];
      return [s.sourceId, 'NO_REPORT'];
    })),
  }));
  return Object.freeze({
    contract: CLOCK_ALIGNMENT_CONTRACT, mirrors: MIRRORED_PROTOCOL,
    sources: Object.freeze(sources),
    events: Object.freeze(events.map((e) => Object.freeze({
      sourceId: e.sourceId, id: e.id, sensorType: e.sensorType, rawTime: iso(e.rawMs), offsetAppliedSeconds: e.offsetSeconds, time: iso(e.alignedMs),
    }))),
    timestampsUtc: Object.freeze(stamps.map(iso)),
    timeline: Object.freeze(timeline), timelineTruncated: stamps.length > MAX_TIMELINE_ROWS,
    gaps: Object.freeze(gaps.map((g) => Object.freeze({ sourceId: g.sourceId, startUtc: iso(g.startMs), endUtc: iso(g.endMs), reason: g.reason }))),
    warnings: Object.freeze(warnings), notes: Object.freeze(notes),
    counts: Object.freeze({ sources: sources.length, events: events.length, timestamps: stamps.length, gaps: gaps.length }),
    limits: Object.freeze([
      'Clock offsets are declared by the person who knows the device and are never inferred from the events; an offset not declared is zero.',
      'There is no interpolation: a source with no report at a timestamp is NO_REPORT, which is missing data and not a value of zero, and a gap exists only where one was declared.',
      'Event times keep millisecond precision (Skywatcher\'s replay keeps microseconds); declared gap times are true UTC and are not shifted by any clock offset.',
    ]),
  });
}

// Which sources have anything to say about a window: how many events fall inside it, the nearest report on either side,
// and the declared gaps that overlap it. A source with no events inside is not "quiet": it is missing data.
export function windowCoverage(alignment, window) {
  const start = window.start instanceof Date ? window.start.getTime() : window.start;
  const end = window.end instanceof Date ? window.end.getTime() : window.end;
  if (!finite(start) || !finite(end) || end < start) throw new RangeError('The window needs a start and an end, the end not before the start.');
  return Object.freeze(alignment.sources.map((s) => {
    const mine = alignment.events.filter((e) => e.sourceId === s.sourceId).map((e) => Date.parse(e.time));
    const inside = mine.filter((t) => t >= start && t <= end);
    const before = mine.filter((t) => t < start);
    const after = mine.filter((t) => t > end);
    const overlapping = alignment.gaps.filter((g) => g.sourceId === s.sourceId && Date.parse(g.startUtc) < end && Date.parse(g.endUtc) > start);
    return Object.freeze({
      sourceId: s.sourceId, sensorType: s.sensorType, eventsInWindow: inside.length,
      nearestBefore: before.length ? iso(Math.max(...before)) : null, nearestAfter: after.length ? iso(Math.min(...after)) : null,
      declaredGapsOverlapping: Object.freeze(overlapping.map((g) => ({ startUtc: g.startUtc, endUtc: g.endUtc, reason: g.reason }))),
      state: inside.length > 0 ? 'HAS_EVENTS' : 'NO_EVENTS_IN_WINDOW',
    });
  }));
}

// The alignment's own digest, over stable JSON (sorted keys, compact). It is a record of this computation, not the
// digest Skywatcher's replay would give for the same inputs: the two are not interchangeable.
export async function alignmentDigest(alignment) {
  return sha256StableJson({ ...alignment, timeline: undefined });
}

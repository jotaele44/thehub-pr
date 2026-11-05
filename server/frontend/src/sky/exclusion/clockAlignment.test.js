import { describe, expect, it } from 'vitest';
import {
  CLOCK_ALIGNMENT_CONTRACT, MAX_SOURCES, MIRRORED_PROTOCOL, SENSOR_TYPES, alignSources, alignmentDigest, windowCoverage,
} from './clockAlignment';

// Date.UTC drops fractional seconds, so add them as milliseconds
const at = (s) => new Date(Date.UTC(2026, 10, 4, 12, 0, 0) + Math.round(s * 1000)).toISOString();
const track = { sourceId: 'adsb', sensorType: 'aircraft_track', events: [{ id: 'p1', time: at(0) }, { id: 'p2', time: at(10) }, { id: 'p3', time: at(20) }] };
const camera = { sourceId: 'cam', sensorType: 'camera_frame', clockOffsetSeconds: -3.2, clockOffsetBasis: 'camera clock read 3.2 s fast against NTP at 11:58Z', events: [{ id: 'f1', time: at(13.2) }, { id: 'f2', time: at(33.2) }] };

describe('mirroring the Skywatcher replay protocol', () => {
  it('uses the union of the event timestamps, no interpolation, and says it mirrors skywatcher-multisensor-replay-v1', () => {
    const a = alignSources([track, camera]);
    expect(a.contract).toBe(CLOCK_ALIGNMENT_CONTRACT);
    expect(a.mirrors).toEqual({ protocol: 'skywatcher-multisensor-replay-v1', timeline_policy: 'union_observation_timestamps', interpolation: 'none' });
    expect(MIRRORED_PROTOCOL.interpolation).toBe('none');
    // the camera frames at 13.2 and 33.2 s on its fast clock are 10 and 30 s: the track's 10 s report and the camera's first frame share a timestamp
    expect(a.timestampsUtc).toEqual([at(0), at(10), at(20), at(30)]);
    expect(a.counts).toEqual({ sources: 2, events: 5, timestamps: 4, gaps: 0 });
  });

  it('shifts a source by its declared offset, keeps the raw time beside the aligned one, and records the basis', () => {
    const a = alignSources([track, camera]);
    const f1 = a.events.find((e) => e.id === 'f1');
    expect(f1).toMatchObject({ rawTime: at(13.2), offsetAppliedSeconds: -3.2, time: at(10) });
    const cam = a.sources.find((s) => s.sourceId === 'cam');
    expect(cam).toMatchObject({ clockOffsetSeconds: -3.2, clockOffsetDeclared: true });
    expect(cam.clockOffsetBasis).toMatch(/NTP/);
    // the aligned camera frame coincides with the track's second report: one timestamp, reported by both
    const row = a.timeline.find((r) => r.time === at(10));
    expect(row.sources).toEqual({ adsb: 'REPORTED', cam: 'REPORTED' });
  });

  it('marks a source with nothing at a timestamp NO_REPORT, which is missing data and not zero', () => {
    const a = alignSources([track, camera]);
    expect(a.timeline.find((r) => r.time === at(0)).sources).toEqual({ adsb: 'REPORTED', cam: 'NO_REPORT' });
    expect(a.limits.join(' ')).toMatch(/NO_REPORT, which is missing data and not a value of zero/);
  });

  it('sorts events by aligned time, then source, then id, however the sources listed them', () => {
    const a = alignSources([camera, track]);
    const order = a.events.map((e) => `${e.time}|${e.sourceId}|${e.id}`);
    expect(order).toEqual([...order].sort());
  });
});

describe('clock offsets are declared, never inferred', () => {
  it('takes an undeclared offset as zero and says so', () => {
    const a = alignSources([track]);
    expect(a.sources[0]).toMatchObject({ clockOffsetSeconds: 0, clockOffsetDeclared: false, clockOffsetBasis: null });
    expect(a.notes.join(' ')).toMatch(/adsb declared no clock offset; its times are taken as UTC as written/);
  });

  it('refuses a non-zero offset with no basis, and an offset that is not a believable number', () => {
    expect(() => alignSources([{ ...track, clockOffsetSeconds: 2 }])).toThrow(/needs its basis.*never inferred or guessed/);
    expect(() => alignSources([{ ...track, clockOffsetSeconds: 2, clockOffsetBasis: '   ' }])).toThrow(/needs its basis/);
    expect(() => alignSources([{ ...track, clockOffsetSeconds: 90000, clockOffsetBasis: 'x' }])).toThrow(/within a day/);
    expect(() => alignSources([{ ...track, clockOffsetSeconds: Number.NaN, clockOffsetBasis: 'x' }])).toThrow(/within a day/);
    // a declared offset of exactly zero needs no basis: nothing was changed
    expect(alignSources([{ ...track, clockOffsetSeconds: 0 }]).sources[0].clockOffsetDeclared).toBe(true);
  });

  it('exports no way to estimate an offset', async () => {
    const mod = await import('./clockAlignment');
    expect(Object.keys(mod).filter((k) => /estimate|infer|guess|detect|sync/i.test(k))).toEqual([]);
  });
});

describe('declared gaps', () => {
  const gapped = { ...track, gaps: [{ startUtc: at(11), endUtc: at(19), reason: 'receiver out of range behind the hill' }] };

  it('keeps a gap with its reason, in true UTC, and shows it in the timeline only where the source has no report', () => {
    const a = alignSources([gapped, camera]);
    expect(a.gaps).toEqual([{ sourceId: 'adsb', startUtc: at(11), endUtc: at(19), reason: 'receiver out of range behind the hill' }]);
    expect(a.counts.gaps).toBe(1);
    // a timestamp inside the gap that only the camera reported: the track is in a DECLARED_GAP there, not simply silent
    const inside = alignSources([gapped, { ...camera, events: [{ id: 'f1', time: at(16.2) }] }]);
    expect(inside.timeline.find((r) => r.time === at(13)).sources.adsb).toBe('DECLARED_GAP');
  });

  it('is never shifted by a clock offset: a gap is declared in true UTC', () => {
    const a = alignSources([{ ...camera, gaps: [{ startUtc: at(14), endUtc: at(20), reason: 'lens covered' }] }]);
    expect(a.gaps[0]).toMatchObject({ startUtc: at(14), endUtc: at(20) });
  });

  it('refuses a gap with no reason, with no zone, backwards, or overlapping another of the same source', () => {
    const g = (extra) => alignSources([{ ...track, gaps: [{ startUtc: at(1), endUtc: at(2), reason: 'r', ...extra }] }]);
    expect(() => g({ reason: '' })).toThrow(/needs a reason/);
    expect(() => g({ reason: undefined })).toThrow(/declared with its cause and never inferred/);
    expect(() => g({ startUtc: '2026-11-04T12:00:01' })).toThrow(/UTC with a zone/);
    expect(() => g({ endUtc: at(0) })).toThrow(/must start before it ends/);
    expect(() => alignSources([{ ...track, gaps: [{ startUtc: at(1), endUtc: at(5), reason: 'a' }, { startUtc: at(4), endUtc: at(8), reason: 'b' }] }])).toThrow(/two declared gaps overlap/);
    expect(() => alignSources([{ ...track, gaps: 'no' }])).toThrow(/gaps must be a list/);
    // the same span on two different sources is fine
    expect(alignSources([{ ...track, gaps: [{ startUtc: at(1), endUtc: at(5), reason: 'a' }] }, { ...camera, gaps: [{ startUtc: at(1), endUtc: at(5), reason: 'b' }] }]).counts.gaps).toBe(2);
  });

  it('warns, without choosing, when a source reports inside a gap it declared itself', () => {
    const a = alignSources([{ ...track, gaps: [{ startUtc: at(5), endUtc: at(15), reason: 'dropout' }] }]);
    expect(a.warnings).toHaveLength(1);
    expect(a.warnings[0]).toMatchObject({ sourceId: 'adsb', eventId: 'p2' });
    expect(a.warnings[0].message).toMatch(/one of the two is wrong/);
  });
});

describe('what it refuses', () => {
  it('refuses no sources, too many, duplicate ids, unknown sensor types and events it cannot read', () => {
    expect(() => alignSources([])).toThrow(/at least one source/);
    expect(() => alignSources(Array.from({ length: MAX_SOURCES + 1 }, (_, i) => ({ ...track, sourceId: `s${i}` })))).toThrow(/At most 20 sources/);
    expect(() => alignSources([track, track])).toThrow(/Two sources are called adsb/);
    expect(() => alignSources([{ ...track, sensorType: 'radar' }])).toThrow(new RegExp(`one of ${SENSOR_TYPES.join(', ')}`));
    expect(() => alignSources([{ ...track, sourceId: '' }])).toThrow(/needs a sourceId/);
    expect(() => alignSources([{ ...track, events: 'x' }])).toThrow(/events must be a list/);
    expect(() => alignSources([{ ...track, events: [{ id: 'a', time: '2026-11-04T12:00:00' }] }])).toThrow(/UTC designator|ISO 8601 with a UTC designator/);
    expect(() => alignSources([{ ...track, events: [{ id: 'a', time: at(0) }, { id: 'a', time: at(1) }] }])).toThrow(/two events are called a/);
  });

  it('numbers events that arrive without an id, and reads epoch seconds only when told to', () => {
    const a = alignSources([{ sourceId: 'w', sensorType: 'observer_report', timeFormat: 'EPOCH_SECONDS', events: [{ time: 1793448000 }, { time: '1793448010' }] }]);
    expect(a.events.map((e) => e.id)).toEqual(['w#1', 'w#2']);
    expect(a.events[0].time).toBe('2026-10-31T12:00:00.000Z');
    expect(() => alignSources([{ sourceId: 'w', sensorType: 'observer_report', events: [{ time: 1793448000 }] }])).toThrow(/not text/);
  });
});

describe('windowCoverage: who has anything to say about the window', () => {
  const a = alignSources([
    { ...track, gaps: [{ startUtc: at(22), endUtc: at(40), reason: 'out of range' }] },
    camera,
    { sourceId: 'witness', sensorType: 'observer_report', events: [{ id: 'w', time: at(600) }] },
  ]);

  it('counts events inside, the nearest report each side, and the declared gaps that overlap', () => {
    const cover = windowCoverage(a, { start: new Date(at(5)), end: new Date(at(25)) });
    const adsb = cover.find((c) => c.sourceId === 'adsb');
    expect(adsb).toMatchObject({ state: 'HAS_EVENTS', eventsInWindow: 2, nearestBefore: at(0), nearestAfter: null });
    expect(adsb.declaredGapsOverlapping).toEqual([{ startUtc: at(22), endUtc: at(40), reason: 'out of range' }]);
    expect(cover.find((c) => c.sourceId === 'cam')).toMatchObject({ state: 'HAS_EVENTS', eventsInWindow: 1 });
  });

  it('calls a source with no event in the window NO_EVENTS_IN_WINDOW, with how far its nearest report is, never "quiet"', () => {
    const w = windowCoverage(a, { start: new Date(at(100)), end: new Date(at(110)) }).find((c) => c.sourceId === 'witness');
    expect(w).toMatchObject({ state: 'NO_EVENTS_IN_WINDOW', eventsInWindow: 0, nearestBefore: null, nearestAfter: at(600) });
  });

  it('refuses a window that ends before it starts', () => {
    expect(() => windowCoverage(a, { start: new Date(at(10)), end: new Date(at(5)) })).toThrow(/end not before the start/);
    expect(() => windowCoverage(a, { start: Number.NaN, end: 1 })).toThrow(/needs a start and an end/);
  });
});

describe('the digest', () => {
  it('is the same for the same inputs and different for different ones, and is not a Skywatcher replay digest', async () => {
    const one = await alignmentDigest(alignSources([track, camera]));
    const again = await alignmentDigest(alignSources([track, camera]));
    const other = await alignmentDigest(alignSources([track, { ...camera, clockOffsetSeconds: -3.1 }]));
    expect(one).toMatch(/^[0-9a-f]{64}$/);
    expect(again).toBe(one);
    expect(other).not.toBe(one);
  });

  it('is frozen all the way down to the sources', () => {
    const a = alignSources([track]);
    expect(Object.isFrozen(a)).toBe(true);
    expect(Object.isFrozen(a.sources[0])).toBe(true);
    expect(Object.isFrozen(a.events[0])).toBe(true);
  });
});

// What the served Hub store is, from the `store` member of GET /api/spatial/features
// (written by the build beside the database). Counts and densities over a bounded
// sample are never Puerto Rico totals, and a store that does not say how it was
// built is never assumed complete.
const UNKNOWN = 'The Hub store does not record how it was built, so these counts are not known to be totals.';

export function describeStore(store) {
  const kind = store?.kind;
  if (kind === 'bounded-sample') {
    const cap = store.cap_per_stream ? ` (at most ${store.cap_per_stream} records per stream)` : '';
    const streams = Object.entries(store.streams || {}).map(([name, counts]) => `${name} ${counts.sampled} of ${counts.actual}`).join(', ');
    return {
      kind,
      sample: true,
      text: `The Hub store is a bounded sample${cap}${streams ? `: ${streams}` : ''}. `
        + 'Counts and densities describe this sample, not Puerto Rico; how representative it is has not been established.',
    };
  }
  if (!kind || kind === 'not_recorded' || kind === 'unreadable') return { kind: kind || 'not_recorded', sample: null, text: UNKNOWN };
  return { kind, sample: null, text: `The Hub store declares itself "${kind}"; these counts are not asserted to be totals.` };
}

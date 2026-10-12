import { describe, expect, it } from 'vitest';
import { describeStore } from './storeBasis';

describe('what the served store is', () => {
  it('says a bounded sample is a sample, with what was kept of what a full run produced', () => {
    const store = {
      kind: 'bounded-sample', cap_per_stream: 400,
      streams: { alerts: { sampled: 400, actual: 4399 }, entities: { sampled: 825, actual: 48224, closure_added: 425 } },
    };
    const described = describeStore(store);
    expect(described.sample).toBe(true);
    expect(described.text).toBe(
      'The Hub store is a bounded sample (at most 400 records per stream): alerts 400 of 4399, entities 825 of 48224. '
      + 'Counts and densities describe this sample, not Puerto Rico; how representative it is has not been established.',
    );
  });

  it('never calls a store of unknown basis complete', () => {
    for (const store of [undefined, null, {}, { kind: 'not_recorded' }, { kind: 'unreadable', basis: 'x' }]) {
      const described = describeStore(store);
      expect(described.sample).toBeNull();
      expect(described.text).toBe('The Hub store does not record how it was built, so these counts are not known to be totals.');
    }
  });

  it('names a kind it does not know without asserting totals', () => {
    const described = describeStore({ kind: 'snapshot-2026', streams: {} });
    expect(described.sample).toBeNull();
    expect(described.text).toBe('The Hub store declares itself "snapshot-2026"; these counts are not asserted to be totals.');
  });
});

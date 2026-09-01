import { describe, it, expect } from 'vitest';
import { filterIntelligenceRows, readExplicitState } from '@/lib/intelligenceWorkspaceState';
import { INTELLIGENCE_ADAPTERS } from '@/lib/intelligenceAdapters';

const NOW = Date.parse('2026-08-25T02:03:00Z');

describe('intelligence workspace state', () => {
  it('closes the loaded-row denominator exactly', () => {
    const adapter = INTELLIGENCE_ADAPTERS.skywatcher;
    const result = filterIntelligenceRows([
      { event_id: 'a', title: 'A', event_type: 'Aviation', event_date: '2026-08-25T01:00:00Z' },
      { event_id: 'b', title: 'B', event_type: 'Drone', event_date: null },
      { event_id: 'c', title: 'C', event_type: 'Aviation', event_date: '2026-08-23T01:00:00Z' },
    ], adapter, { timeWindow: '24h' }, NOW);

    expect(result.metrics.sourceCount).toBe(3);
    expect(result.metrics.visibleCount).toBe(1);
    expect(result.metrics.excludedCount).toBe(2);
    expect(result.metrics.sourceCount).toBe(result.metrics.visibleCount + result.metrics.excludedCount);
    expect(result.metrics.undatedCount).toBe(1);
    expect(result.metrics.undatedExcludedCount).toBe(1);
  });

  it('retains timeless spatial assets when a bounded window is requested', () => {
    const adapter = INTELLIGENCE_ADAPTERS.aguayluz;
    const result = filterIntelligenceRows([
      { asset_id: 'a1', name: 'Reservoir A', asset_type: 'Reservoir' },
      { asset_id: 'a2', name: 'Pump B', asset_type: 'PumpStation' },
    ], adapter, { timeWindow: '6h' }, NOW);

    expect(result.metrics.visibleCount).toBe(2);
    expect(result.metrics.undatedRetainedCount).toBe(2);
  });

  it('does not turn missing explicit forensic state into a positive claim', () => {
    expect(readExplicitState({}, ['identity_state'], 'UNRESOLVED')).toBe('UNRESOLVED');
    expect(readExplicitState({}, ['certification_state'], 'OPEN')).toBe('OPEN');
    expect(readExplicitState({}, ['epistemic_class'], 'UNKNOWN')).toBe('UNKNOWN');
  });

  it('rejects unknown time-window identifiers instead of silently broadening scope', () => {
    expect(() => filterIntelligenceRows([], INTELLIGENCE_ADAPTERS.skywatcher, { timeWindow: 'forever' }, NOW)).toThrow(/Unknown intelligence time window/);
  });
});

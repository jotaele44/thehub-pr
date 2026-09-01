import { describe, it, expect } from 'vitest';
import { INTELLIGENCE_ADAPTERS } from '@/lib/intelligenceAdapters';

describe('intelligence domain adapters', () => {
  it('keeps the three domain contracts independent', () => {
    const adapters = Object.values(INTELLIGENCE_ADAPTERS);
    expect(adapters).toHaveLength(3);
    expect(new Set(adapters.map((adapter) => adapter.primaryEntity)).size).toBe(3);
    expect(new Set(adapters.map((adapter) => adapter.relatedEntity)).size).toBe(3);
  });

  it('fails closed when identity, certification, or epistemic fields are absent', () => {
    for (const adapter of Object.values(INTELLIGENCE_ADAPTERS)) {
      expect(adapter.getForensicAxes({})).toMatchObject({
        identity: 'UNRESOLVED',
        certification: 'OPEN',
        epistemic: 'UNKNOWN',
      });
    }
  });

  it('preserves explicit forensic state rather than deriving it from confidence or proximity', () => {
    const axes = INTELLIGENCE_ADAPTERS.skywatcher.getForensicAxes({
      confidence: 'High',
      identity_state: '0:1',
      certification_state: 'PROVISIONAL',
      epistemic_class: 'INFERENCE',
    });
    expect(axes.identity).toBe('0:1');
    expect(axes.certification).toBe('PROVISIONAL');
    expect(axes.epistemic).toBe('INFERENCE');
  });

  it('selects related records without promoting them to identity', () => {
    const adapter = INTELLIGENCE_ADAPTERS.spiderweb;
    const related = adapter.getRelated([
      { edge_id: 'e1', source_node_id: 'n1', target_node_id: 'n2', relationship_type: 'LocatedAt' },
      { edge_id: 'e2', source_node_id: 'n3', target_node_id: 'n4', relationship_type: 'RelatedTo' },
    ], { node_id: 'n1' });

    expect(related.map((row) => row.edge_id)).toEqual(['e1']);
    expect(adapter.relatedDisclaimer).toMatch(/do not establish canonical identity/i);
  });

  it('does not derive source freshness from Hub query recency', () => {
    const axes = INTELLIGENCE_ADAPTERS.aguayluz.getForensicAxes({ updated_date: '2026-08-25T02:00:00Z' });
    expect(axes.freshness).toBe('unknown');
  });
});

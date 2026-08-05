import { describe, it, expect } from 'vitest';
import { chipClass, SEVERITY, REVIEW_STATUS, GENERIC_STATUS, SENSITIVITY } from '@/lib/chips';

describe('chips', () => {
  it('resolves every value in a status map to a non-empty class string', () => {
    for (const map of [SEVERITY, REVIEW_STATUS, GENERIC_STATUS, SENSITIVITY]) {
      for (const value of Object.keys(map)) {
        expect(chipClass(map, value)).toBeTypeOf('string');
        expect(chipClass(map, value).length).toBeGreaterThan(0);
      }
    }
  });

  it('emits semantic status tokens, not raw palette classes', () => {
    // e.g. SEVERITY.Critical -> danger token
    expect(SEVERITY.Critical).toContain('status-danger');
    expect(SEVERITY.Critical).not.toMatch(/(red|emerald|amber|sky)-\d/);
  });

  it('falls back to a neutral chip for unknown/empty values', () => {
    expect(chipClass(SEVERITY, 'Nonexistent')).toContain('text-muted-foreground');
    expect(chipClass(null, undefined)).toContain('text-muted-foreground');
  });
});

import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, isNavActive } from '@/lib/nav';

const items = NAV_GROUPS.flatMap((g) => g.items);

describe('nav config', () => {
  it('has non-empty groups, each item with a label and an absolute path', () => {
    expect(NAV_GROUPS.length).toBeGreaterThan(0);
    for (const item of items) {
      expect(item.label).toBeTruthy();
      expect(item.path.startsWith('/')).toBe(true);
    }
  });

  it('has no duplicate paths across groups', () => {
    const paths = items.map((i) => i.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('matches active routes correctly', () => {
    expect(isNavActive('/', '/')).toBe(true);
    expect(isNavActive('/activity', '/')).toBe(true);
    expect(isNavActive('/programs', '/')).toBe(false);
    expect(isNavActive('/crossover', '/crossover')).toBe(true);
    expect(isNavActive('/crossover/x', '/crossover')).toBe(true);
    expect(isNavActive('/moneysweep', '/money')).toBe(false);
  });
});

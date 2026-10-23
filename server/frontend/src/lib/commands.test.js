import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '@/lib/nav';
import { MAX_COMMANDS, buildCommands, filterCommands, navigationCommands, queryCommands } from './commands';

describe('command palette model', () => {
  it('derives navigation from NAV_GROUPS with no duplicate or dead destinations', () => {
    const commands = navigationCommands();
    const paths = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.path));
    expect(commands.map((c) => c.href)).toEqual([...new Set(paths)]);
    expect(new Set(commands.map((c) => c.id)).size).toBe(commands.length);
    expect(commands.every((c) => c.href.startsWith('/'))).toBe(true);
  });

  it('collapses a destination listed twice', () => {
    const groups = [{ label: 'A', items: [{ label: 'One', path: '/x' }] }, { label: 'B', items: [{ label: 'Dup', path: '/x' }] }];
    expect(navigationCommands(groups)).toHaveLength(1);
  });

  it('filters with AND semantics, ignoring accents and case', () => {
    const commands = [{ label: 'GIS Workspace', group: 'Tools' }, { label: 'Crossover', group: 'Federación' }];
    expect(filterCommands(commands, 'gis tools')).toHaveLength(1);
    expect(filterCommands(commands, 'gis federacion')).toHaveLength(0);
    expect(filterCommands(commands, 'FEDERACION')).toEqual([commands[1]]);
  });

  it('offers query commands only when the query parses', () => {
    expect(queryCommands('')).toEqual([]);
    const ids = (q) => queryCommands(q).map((c) => c.id);
    expect(ids('laguna')).toEqual(['search']);
    expect(ids('18.2, -66.5')).toEqual(['search', 'coordinates']);
    expect(ids('Entities/ent_1')).toEqual(['search', 'evidence']);
    expect(ids('ent_abc123')).toEqual(['search', 'entity']);
    expect(ids('Tweets/1')).toEqual(['search']);
    const coordinates = queryCommands('18.2 -66.5 z12').find((c) => c.id === 'coordinates');
    expect(coordinates.href).toBe('/gis?lat=18.2&lon=-66.5&z=12');
    expect(queryCommands('Entities/ent_1')[1].href).toBe('/evidence/Entities/ent_1');
  });

  it('puts query commands first and stays bounded', () => {
    const commands = buildCommands('search');
    expect(commands[0].id).toBe('search');
    expect(commands.some((c) => c.href === '/search' && c.kind === 'navigate')).toBe(true);
    expect(buildCommands('').length).toBeLessThanOrEqual(MAX_COMMANDS);
  });
});

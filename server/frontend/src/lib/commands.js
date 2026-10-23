// Command palette model (FDX-055 / TWIN-095). Navigation commands are derived
// from NAV_GROUPS, the app's single source of navigation truth, so the palette
// can never list a destination the sidebar does not have (no duplicates, no dead
// commands). Query-driven commands only appear when the query parses: free text
// searches the Federation, "lat, lon [z]" jumps the map, "Collection/id" opens a
// provenance record and an "ent_…" id opens the entity composition. Every
// command is a navigation; the palette performs no writes.
import { NAV_GROUPS } from '@/lib/nav';
import { evidenceHref } from '@/lib/evidenceState';
import { entityHref, mapViewHref, parseCoordinateQuery, searchHref } from '@/lib/deepLinks';

export const EVIDENCE_COLLECTIONS = ['Sources', 'Entities', 'Observations', 'Alerts', 'Relationships', 'Correlations'];
const EVIDENCE_REF = new RegExp(`^(${EVIDENCE_COLLECTIONS.join('|')})/(\\S+)$`);
const ENTITY_ID = /^ent_[A-Za-z0-9]+$/;
export const MAX_COMMANDS = 50;

export function fold(text) {
  return String(text || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

export function navigationCommands(groups = NAV_GROUPS) {
  const seen = new Set();
  const commands = [];
  for (const group of groups) {
    for (const item of group.items) {
      if (seen.has(item.path)) continue;
      seen.add(item.path);
      commands.push({ id: `nav:${item.path}`, label: item.label, group: group.label, href: item.path, kind: 'navigate' });
    }
  }
  return commands;
}

export function queryCommands(query) {
  const text = String(query || '').trim();
  if (!text) return [];
  const commands = [{ id: 'search', label: `Search the Federation for “${text}”`, group: 'Search', href: searchHref(text), kind: 'search' }];
  const coordinates = parseCoordinateQuery(text);
  if (coordinates) {
    const zoom = coordinates.z === null ? '' : ` at zoom ${coordinates.z}`;
    commands.push({
      id: 'coordinates', label: `Jump the map to ${coordinates.lat}, ${coordinates.lon}${zoom}`, group: 'Map',
      href: mapViewHref(coordinates), kind: 'map',
    });
  }
  const evidence = text.match(EVIDENCE_REF);
  if (evidence) {
    commands.push({
      id: 'evidence', label: `Open provenance for ${evidence[1]}/${evidence[2]}`, group: 'Records',
      href: evidenceHref(evidence[1], evidence[2]), kind: 'evidence',
    });
  }
  if (ENTITY_ID.test(text)) {
    commands.push({ id: 'entity', label: `Open entity ${text}`, group: 'Records', href: entityHref(text), kind: 'entity' });
  }
  return commands;
}

// Every query word must appear (AND), accent- and case-insensitively.
export function filterCommands(commands, query) {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return commands;
  return commands.filter((command) => {
    const haystack = fold(`${command.label} ${command.group}`);
    return words.every((word) => haystack.includes(word));
  });
}

export function buildCommands(query, groups = NAV_GROUPS) {
  return [...queryCommands(query), ...filterCommands(navigationCommands(groups), query)].slice(0, MAX_COMMANDS);
}

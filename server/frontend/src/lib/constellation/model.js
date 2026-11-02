// Federation Constellation view-model: the /api/constellation payload indexed
// for drawing and navigation. Pure — no DOM, no canvas — so it is unit-tested
// directly. Both lenses share the app anchors ("app:<id>"), so toggling lenses
// keeps those nodes in place and morphs everything else around them.

export const LENSES = ['code', 'content'];

const indexLens = (lens) => {
  const nodes = new Map(lens.nodes.map((n) => [n.id, n]));
  const edges = lens.edges.filter((e) => nodes.has(e.from) && nodes.has(e.to));
  const neighbors = new Map(lens.nodes.map((n) => [n.id, new Set()]));
  for (const e of edges) {
    if (e.kind === 'member') continue;
    neighbors.get(e.from).add(e.to);
    neighbors.get(e.to).add(e.from);
  }
  return { nodes, edges, neighbors, legend: lens.legend || [] };
};

export function buildModel(payload) {
  const lenses = {
    code: indexLens(payload.lenses.code),
    content: indexLens(payload.lenses.content),
  };
  const codeToContent = new Map();
  const contentToCode = new Map();
  for (const { code, content } of payload.links || []) {
    if (!codeToContent.has(code)) codeToContent.set(code, content);
    if (!contentToCode.has(content)) contentToCode.set(content, code);
  }
  return {
    stages: payload.stages,
    apps: new Map(payload.apps.map((a) => [a.id, a])),
    lenses,
    links: { code: codeToContent, content: contentToCode },
    linksAll: payload.links || [],
    storeStatus: payload.store_status,
    totals: payload.totals || {},
  };
}

export const otherLens = (lens) => (lens === 'code' ? 'content' : 'code');

// The node to keep selected when switching lenses: app anchors are shared, other
// nodes map through lineage links; anything unlinked drops the selection.
export function counterpartOf(model, lens, id) {
  if (!id) return null;
  if (id.startsWith('app:')) return id;
  return model.links[lens].get(id) ?? null;
}

// Every node in the other lens linked to `id` (a component can produce several streams).
export function linkedNodes(model, lens, id) {
  const target = otherLens(lens);
  const ids = model.linksAll.filter((l) => l[lens] === id).map((l) => l[target]);
  return ids.map((i) => model.lenses[target].nodes.get(i)).filter(Boolean);
}

export function stageFocus(model, lens, stageIndex) {
  const stage = model.stages[stageIndex];
  return stage ? stage.focus[lens].filter((id) => model.lenses[lens].nodes.has(id)) : [];
}

// The index of the first (non-overview) stage whose focus contains the node.
export function stageOfNode(model, lens, id) {
  const index = model.stages.findIndex((s) => !s.overview && s.focus[lens].includes(id));
  return index === -1 ? null : index;
}

export const stageIndexById = (model, id) => model.stages.findIndex((s) => s.id === id);

export const stageTitle = (stage) => `${stage.title.lead} ${stage.title.accent}`;

const KIND_LABELS = {
  app: 'App', command: 'Command', config: 'Config', module: 'Module', script: 'Script', function: 'Function',
  artifact: 'Artifact', route: 'API route', ui: 'User interface', stream: 'Producer stream',
  hub_stream: 'Hub stream', correlation: 'Correlation strategy', collection: 'UI collection', seam: 'Declared seam',
};

export const kindLabel = (kind) => KIND_LABELS[kind] || kind;

const formatter = new Intl.NumberFormat('en-US');
export const formatCount = (value) => (value === null || value === undefined ? '—' : formatter.format(value));

// One line a screen reader (and the outline list) can use in place of the canvas.
export function describeNode(node) {
  const parts = [node.label, kindLabel(node.kind), node.sublabel];
  if (node.total !== undefined && node.total !== null) parts.push(`${formatCount(node.total)} exported`);
  if (node.stored !== undefined && node.stored !== null) parts.push(`${formatCount(node.stored)} in store`);
  return parts.filter(Boolean).join(' · ');
}

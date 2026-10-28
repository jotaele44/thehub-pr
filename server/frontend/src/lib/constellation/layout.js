// Deterministic world layout for the Federation Constellation. Pure.
//
// Stage centres sit on a meandering path in tour order. Each app's anchor sits at
// its home stage (the first stage that names it) and is shared by both lenses,
// so later stages reach back to it with the long crossing lines of the reference
// video. Every other node is seeded on a golden-angle spiral around its app's
// cluster centre in its own stage, then a fixed number of relaxation passes push
// overlapping label boxes apart. Same payload in, same picture out.

import { LENSES } from './model';

export const STAGE_GAP = 1500;
export const MEANDER = 520;
const APP_RING = 440;
const FOREIGN_RING = 420;
const SPIRAL_BASE = 150;
const SPIRAL_STEP = 72;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const SETTLE_ITERATIONS = 160;
const RESOLVE_ITERATIONS = 400;

// Label metrics in world units (the canvas draws labels at these sizes x zoom).
export const LABEL_FONT = 11;
export const SUBLABEL_FONT = 8.5;
const CHAR_W = 6.7;
const SUB_CHAR_W = 5.2;
export const LABEL_PAD = 8;
export const LABEL_H = 34;
export const LABEL_GAP = 10;

export function hashString(value) {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// mulberry32: a tiny seeded PRNG, so jitter is identical on every run.
export function seededRandom(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function labelBox(node) {
  const w = Math.max((node.label || '').length * CHAR_W, (node.sublabel || '').length * SUB_CHAR_W) + LABEL_PAD * 2;
  return { w, h: LABEL_H };
}

// The node's footprint: its dot plus the label box drawn to its right.
export function footprint(pos, box) {
  return { x0: pos.x - 12, x1: pos.x + LABEL_GAP + box.w + 6, y0: pos.y - box.h / 2 - 6, y1: pos.y + box.h / 2 + 6 };
}

function stageCenters(stages) {
  const centers = new Map();
  const tour = stages.filter((s) => !s.overview);
  tour.forEach((stage, i) => {
    centers.set(stage.id, { x: i * STAGE_GAP, y: Math.round(Math.sin(i * 1.2) * MEANDER) });
  });
  const xs = [...centers.values()];
  const mid = xs.length ? { x: (xs[0].x + xs[xs.length - 1].x) / 2, y: 0 } : { x: 0, y: 0 };
  stages.filter((s) => s.overview).forEach((s) => centers.set(s.id, mid));
  return centers;
}

function appAnchors(model, centers) {
  const anchors = new Map();
  const byStage = new Map();
  for (const app of model.apps.values()) {
    const home = app.home_stage;
    if (!byStage.has(home)) byStage.set(home, []);
    byStage.get(home).push(app.id);
  }
  for (const [stageId, apps] of byStage) {
    const c = centers.get(stageId) || { x: 0, y: 0 };
    apps.forEach((appId, k) => {
      if (apps.length === 1) {
        anchors.set(`app:${appId}`, { x: c.x - 220, y: c.y });
        return;
      }
      const angle = -Math.PI / 2 + (2 * Math.PI * k) / apps.length;
      anchors.set(`app:${appId}`, { x: c.x + APP_RING * Math.cos(angle), y: c.y + APP_RING * Math.sin(angle) });
    });
  }
  return anchors;
}

function overlap(a, b) {
  const dx = Math.min(a.x1 - b.x0, b.x1 - a.x0);
  const dy = Math.min(a.y1 - b.y0, b.y1 - a.y0);
  return dx > 0 && dy > 0 ? { dx, dy } : null;
}

// One collision pass; returns whether anything still overlapped.
function collide(items, strength) {
  let any = false;
  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) {
      const a = items[i];
      const b = items[j];
      if (a.fixed && b.fixed) continue;
      const o = overlap(footprint(a.pos, a.box), footprint(b.pos, b.box));
      if (!o) continue;
      any = true;
      // Labels are wide and short, so separating vertically is usually cheaper.
      const axis = o.dy < o.dx * 1.6 ? 'y' : 'x';
      const sign = Math.sign(b.pos[axis] - a.pos[axis]) || ((i + j) % 2 ? 1 : -1);
      const push = ((axis === 'y' ? o.dy : o.dx) + 1) * strength;
      if (a.fixed) b.pos[axis] += sign * push;
      else if (b.fixed) a.pos[axis] -= sign * push;
      else { a.pos[axis] -= (sign * push) / 2; b.pos[axis] += (sign * push) / 2; }
    }
  }
  return any;
}

function relax(items, edges) {
  const movable = items.filter((it) => !it.fixed);
  const index = new Map(items.map((it) => [it.id, it]));
  const springs = edges.filter((e) => e.kind !== 'member' && index.has(e.from) && index.has(e.to));
  // Settle: collisions against a gentle pull home and along edges.
  for (let iter = 0; iter < SETTLE_ITERATIONS; iter += 1) {
    collide(items, 0.5);
    for (const it of movable) {
      it.pos.x += (it.home.x - it.pos.x) * 0.01;
      it.pos.y += (it.home.y - it.pos.y) * 0.01;
    }
    for (const e of springs) {
      const a = index.get(e.from);
      const b = index.get(e.to);
      const dx = b.pos.x - a.pos.x;
      const dy = b.pos.y - a.pos.y;
      if (Math.hypot(dx, dy) < 360) continue;
      if (!a.fixed) { a.pos.x += dx * 0.003; a.pos.y += dy * 0.003; }
      if (!b.fixed) { b.pos.x -= dx * 0.003; b.pos.y -= dy * 0.003; }
    }
  }
  // Resolve: collisions only, until no label box overlaps another.
  for (let iter = 0; iter < RESOLVE_ITERATIONS; iter += 1) {
    if (!collide(items, 1)) break;
  }
}

function layoutLens(model, lensName, centers, anchors) {
  const lens = model.lenses[lensName];
  const positions = new Map([...anchors].map(([id, p]) => [id, { ...p }]));
  const byStage = new Map();
  for (const node of lens.nodes.values()) {
    if (node.kind === 'app') continue;
    if (!byStage.has(node.stage)) byStage.set(node.stage, []);
    byStage.get(node.stage).push(node);
  }
  for (const [stageId, nodes] of byStage) {
    const center = centers.get(stageId) || { x: 0, y: 0 };
    const apps = [...new Set(nodes.map((n) => n.app))];
    const homeApps = apps.filter((a) => model.apps.get(a)?.home_stage === stageId);
    const foreign = apps.filter((a) => !homeApps.includes(a));
    const clusterCenter = new Map();
    for (const app of homeApps) clusterCenter.set(app, anchors.get(`app:${app}`));
    foreign.forEach((app, k) => {
      if (foreign.length === 1 && homeApps.length === 0) {
        clusterCenter.set(app, { x: center.x, y: center.y });
        return;
      }
      const angle = Math.PI / 2 + (2 * Math.PI * k) / foreign.length + (homeApps.length ? Math.PI / foreign.length : 0);
      clusterCenter.set(app, { x: center.x + FOREIGN_RING * Math.cos(angle), y: center.y + FOREIGN_RING * Math.sin(angle) });
    });
    const items = [];
    const counters = new Map();
    for (const node of nodes) {
      const cc = clusterCenter.get(node.app);
      const k = counters.get(node.app) || 0;
      counters.set(node.app, k + 1);
      const rand = seededRandom(hashString(`${lensName}:${node.id}`));
      const r = SPIRAL_BASE + SPIRAL_STEP * Math.sqrt(k) + rand() * 30;
      const theta = k * GOLDEN_ANGLE + (hashString(node.app) % 628) / 100;
      const pos = { x: cc.x + r * Math.cos(theta) * 1.5, y: cc.y + r * Math.sin(theta) * 0.9 };
      items.push({ id: node.id, pos, home: { ...cc }, box: labelBox(node), fixed: false });
    }
    for (const app of homeApps) {
      const id = `app:${app}`;
      items.push({ id, pos: positions.get(id), home: positions.get(id), box: labelBox(lens.nodes.get(id)), fixed: true });
    }
    relax(items, lens.edges);
    for (const it of items) positions.set(it.id, { x: Math.round(it.pos.x), y: Math.round(it.pos.y) });
  }
  return positions;
}

export function computeLayout(model) {
  const centers = stageCenters(model.stages);
  const anchors = appAnchors(model, centers);
  const positions = {};
  const boxes = {};
  for (const lens of LENSES) {
    positions[lens] = layoutLens(model, lens, centers, anchors);
    boxes[lens] = new Map([...model.lenses[lens].nodes.values()].map((n) => [n.id, labelBox(n)]));
  }
  return { centers, positions, boxes };
}

// World-space bounds of a set of nodes, label boxes included.
export function boundsOf(layout, lens, ids) {
  let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
  for (const id of ids) {
    const p = layout.positions[lens].get(id);
    const box = layout.boxes[lens].get(id);
    if (!p || !box) continue;
    const f = footprint(p, box);
    x0 = Math.min(x0, f.x0); y0 = Math.min(y0, f.y0); x1 = Math.max(x1, f.x1); y1 = Math.max(y1, f.y1);
  }
  return Number.isFinite(x0) ? { x0, y0, x1, y1 } : null;
}

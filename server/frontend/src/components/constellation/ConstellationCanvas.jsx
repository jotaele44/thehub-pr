import React, { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import { boundsOf, hashString, LABEL_FONT, LABEL_GAP, LABEL_PAD, seededRandom, SUBLABEL_FONT } from '@/lib/constellation/layout';
import { drift, DWELL_MS, fitBounds, flight, FLIGHT_MS, panBy, zoomAt } from '@/lib/constellation/camera';
import { stageFocus } from '@/lib/constellation/model';

// Canvas renderer for the Federation Constellation: a starfield, ring-dot nodes
// with two-line monospace labels, edges keyed by kind with light pulses
// travelling along them, and (in the content lens) real sample records drifting
// along the record flows. All colours come from CSS tokens: the --constellation-*
// tokens in index.css and each app's --fd-accent from the federation design
// layer, read through hidden [data-repo] probes.
//
// Mutable renderer state lives in one stable object (`rt`) rather than refs so
// the animation loop reads the latest props without re-subscribing.

const TOKENS = ['bg', 'bg-glow', 'star', 'grain', 'edge-1', 'edge-2', 'edge-3', 'label-bg', 'label-border', 'label-fg', 'label-muted', 'highlight'];
const MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace';
const LENS_FADE_MS = 450;
const PULSE_MS = 2600;
const PARTICLE_MS = 6400;
const MAX_PARTICLES = 28;
const TILE = 768;
// Label floors: in-focus labels never draw smaller than `focus` x their world size,
// anchors never smaller than `anchor`/`anchorOff`, and below `far` zoom only anchors
// (and the selection) keep labels while records ride as dots. Phones get lower floors.
const FLOORS = {
  wide: { focus: 0.74, anchor: 1, anchorOff: 0.85, far: 0.3 },
  narrow: { focus: 0.6, anchor: 0.75, anchorOff: 0.65, far: 0.16 },
};
const floorsFor = (width) => (width < 640 ? FLOORS.narrow : FLOORS.wide);

const hsl = (channels, alpha = 1) => `hsl(${channels} / ${alpha})`;

function hexAlpha(hex, alpha) {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function readPalette(container) {
  const style = getComputedStyle(container);
  const palette = {};
  for (const token of TOKENS) palette[token] = style.getPropertyValue(`--constellation-${token}`).trim() || '220 10% 60%';
  palette.accents = {};
  container.querySelectorAll('[data-repo]').forEach((el) => {
    palette.accents[el.dataset.repo] = getComputedStyle(el).getPropertyValue('--fd-accent').trim();
  });
  return palette;
}

function starTile(palette, dpr) {
  const tile = document.createElement('canvas');
  tile.width = TILE * dpr;
  tile.height = TILE * dpr;
  const ctx = tile.getContext('2d');
  if (!ctx) return null;
  ctx.scale(dpr, dpr);
  const rand = seededRandom(20261027);
  for (let i = 0; i < 70; i += 1) {
    // Faint warm scratches, like film grain on the reference footage.
    const x = rand() * TILE; const y = rand() * TILE; const len = 20 + rand() * 120; const a = rand() * Math.PI;
    ctx.strokeStyle = hsl(palette.grain, 0.03 + rand() * 0.05);
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
    ctx.stroke();
  }
  for (let i = 0; i < 520; i += 1) {
    const r = rand() < 0.94 ? 0.5 + rand() * 0.6 : 1 + rand() * 0.9;
    ctx.fillStyle = hsl(palette.star, 0.08 + rand() * (r > 1 ? 0.5 : 0.28));
    ctx.beginPath();
    ctx.arc(rand() * TILE, rand() * TILE, r, 0, Math.PI * 2);
    ctx.fill();
  }
  return tile;
}

const truncate = (text, max) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

function programOf(model, appId) {
  return model.apps.get(appId)?.program_id;
}

function drawBackground(rt) {
  const { ctx, width, height, palette, cam } = rt;
  ctx.fillStyle = hsl(palette.bg);
  ctx.fillRect(0, 0, width, height);
  const glow = ctx.createRadialGradient(width * 0.5, height * 0.42, 0, width * 0.5, height * 0.42, Math.max(width, height) * 0.75);
  glow.addColorStop(0, hsl(palette['bg-glow'], 0.95));
  glow.addColorStop(1, hsl(palette.bg, 0));
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);
  if (rt.stars) {
    const pattern = ctx.createPattern(rt.stars, 'repeat');
    if (pattern) {
      const ox = (-cam.x * cam.zoom * 0.05) % TILE;
      const oy = (-cam.y * cam.zoom * 0.05) % TILE;
      if (pattern.setTransform && typeof DOMMatrix !== 'undefined') {
        pattern.setTransform(new DOMMatrix().translateSelf(ox, oy).scaleSelf(1 / rt.dpr, 1 / rt.dpr));
      }
      ctx.fillStyle = pattern;
      ctx.fillRect(0, 0, width, height);
    }
  }
}

function drawVignette(rt) {
  const { ctx, width, height, palette } = rt;
  const v = ctx.createRadialGradient(width / 2, height / 2, Math.min(width, height) * 0.35, width / 2, height / 2, Math.max(width, height) * 0.75);
  v.addColorStop(0, hsl(palette.bg, 0));
  v.addColorStop(1, hsl(palette.bg, 0.78));
  ctx.fillStyle = v;
  ctx.fillRect(0, 0, width, height);
}

function toScreen(rt, p) {
  const { cam, width, height } = rt;
  return { x: (p.x - cam.x) * cam.zoom + width / 2, y: (p.y - cam.y) * cam.zoom + height / 2 };
}

function onScreen(rt, a, b, margin = 80) {
  const x0 = Math.min(a.x, b.x); const x1 = Math.max(a.x, b.x);
  const y0 = Math.min(a.y, b.y); const y1 = Math.max(a.y, b.y);
  return x1 > -margin && x0 < rt.width + margin && y1 > -margin && y0 < rt.height + margin;
}

function drawLens(rt, lensName, alpha, now) {
  const { ctx, palette, cam } = rt;
  const { model, layout, stageIndex, selectedId, animate, exploring } = rt.props;
  const floors = floorsFor(rt.width);
  const lens = model.lenses[lensName];
  const positions = layout.positions[lensName];
  const boxes = layout.boxes[lensName];
  const focus = new Set(stageFocus(model, lensName, stageIndex));
  const tones = Object.fromEntries(lens.legend.map((l) => [l.kind, l.tone]));
  const active = selectedId && lens.nodes.has(selectedId) ? selectedId : (rt.hoverId && lens.nodes.has(rt.hoverId) ? rt.hoverId : null);
  const near = active ? lens.neighbors.get(active) : null;
  const screen = new Map();
  for (const [id, p] of positions) {
    if (lens.nodes.has(id)) screen.set(id, toScreen(rt, p));
  }
  ctx.save();
  ctx.globalAlpha = alpha;

  // Edges, member lines first so typed edges draw over them.
  const ordered = [...lens.edges].sort((a, b) => (a.kind === 'member' ? 0 : 1) - (b.kind === 'member' ? 0 : 1));
  const flows = [];
  for (const e of ordered) {
    const a = screen.get(e.from); const b = screen.get(e.to);
    if (!a || !b || !onScreen(rt, a, b)) continue;
    const member = e.kind === 'member';
    const inFocus = focus.has(e.from) || focus.has(e.to);
    const touches = active && (e.from === active || e.to === active);
    let opacity = member ? (inFocus ? 0.11 : 0.045) : (inFocus ? 0.46 : 0.12);
    if (touches) opacity = 0.95;
    else if (active && !member) opacity *= 0.45;
    const tone = member ? null : palette[`edge-${tones[e.kind] || 1}`];
    const weightWidth = e.weight ? 0.7 + Math.log10(e.weight + 1) * 0.55 : 1;
    ctx.strokeStyle = member ? hsl(palette['label-muted'], opacity) : hsl(tone, opacity);
    ctx.lineWidth = member ? 0.6 : weightWidth * (touches ? 1.7 : 1);
    ctx.setLineDash(e.status ? [5, 5] : []);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    if (member || !animate || !(inFocus || touches)) continue;
    // A short bright pulse travelling from source to target.
    const seed = (hashString(e.id) % 1000) / 1000;
    const t = ((now / PULSE_MS) + seed) % 1;
    const tail = Math.max(0, t - 0.08);
    const px = a.x + (b.x - a.x) * t; const py = a.y + (b.y - a.y) * t;
    const grad = ctx.createLinearGradient(a.x + (b.x - a.x) * tail, a.y + (b.y - a.y) * tail, px, py);
    grad.addColorStop(0, hsl(tone, 0));
    grad.addColorStop(1, hsl(tone, Math.min(1, opacity + 0.45)));
    ctx.setLineDash([]);
    ctx.strokeStyle = grad;
    ctx.lineWidth = ctx.lineWidth + 1.2;
    ctx.beginPath();
    ctx.moveTo(a.x + (b.x - a.x) * tail, a.y + (b.y - a.y) * tail);
    ctx.lineTo(px, py);
    ctx.stroke();
    if (e.kind === 'flow' && inFocus) flows.push({ e, a, b, seed });
  }
  ctx.setLineDash([]);

  // Content lens: real sample records riding the record flows.
  if (lensName === 'content' && animate) {
    let drawn = 0;
    const size = Math.min(10, 9 * Math.max(0.75, cam.zoom));
    ctx.font = `${size}px ${MONO}`;
    for (const { e, a, b, seed } of flows) {
      const source = lens.nodes.get(e.from);
      const target = lens.nodes.get(e.to);
      const samples = (source?.samples?.length ? source.samples : target?.samples) || [];
      if (!samples.length) continue;
      for (let k = 0; k < 2 && drawn < MAX_PARTICLES; k += 1) {
        const phase = (now / PARTICLE_MS) + seed + k * 0.5;
        const t = phase % 1;
        const sample = samples[Math.floor(phase) % samples.length];
        const x = a.x + (b.x - a.x) * t; const y = a.y + (b.y - a.y) * t;
        if (x < -40 || y < -20 || x > rt.width + 40 || y > rt.height + 20) continue;
        const fade = Math.sin(Math.PI * t);
        ctx.fillStyle = hsl(palette.highlight, 0.9 * fade);
        ctx.beginPath();
        ctx.arc(x, y, 2.2, 0, Math.PI * 2);
        ctx.fill();
        if (cam.zoom >= floors.far) {
          ctx.fillStyle = hsl(palette['label-fg'], 0.78 * fade);
          ctx.fillText(truncate(sample.label || sample.id, 34), x + 6, y - 5);
        }
        drawn += 1;
      }
    }
  }

  // Nodes first, then labels in priority order, skipping any label that would
  // land on one already placed (so zoomed-out views never pile labels up).
  const hits = [];
  const candidates = [];
  for (const node of lens.nodes.values()) {
    const s = screen.get(node.id);
    if (!s || s.x < -400 || s.y < -60 || s.x > rt.width + 60 || s.y > rt.height + 60) continue;
    const anchor = node.kind === 'app';
    const inFocus = focus.has(node.id);
    const isActive = node.id === active;
    const isSelected = node.id === selectedId;
    let opacity = inFocus || anchor ? 1 : 0.3;
    if (active && !isActive && !near?.has(node.id)) opacity *= 0.45;
    const accent = palette.accents[programOf(model, node.app)];
    const ring = anchor ? (hexAlpha(accent, opacity) || hsl(palette['label-fg'], opacity)) : hsl(palette['label-fg'], 0.85 * opacity);
    const radius = anchor ? 8 : 4 * Math.min(1.4, Math.max(0.7, cam.zoom));
    if (anchor && accent) {
      const glow = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, 26);
      glow.addColorStop(0, hexAlpha(accent, 0.45 * opacity));
      glow.addColorStop(1, hexAlpha(accent, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(s.x, s.y, 26, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = ring;
    ctx.lineWidth = anchor ? 1.8 : 1.1;
    ctx.beginPath();
    ctx.arc(s.x, s.y, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = ring;
    ctx.beginPath();
    ctx.arc(s.x, s.y, radius * 0.38, 0, Math.PI * 2);
    ctx.fill();
    if (isSelected || isActive) {
      const pulse = animate ? 3 * Math.sin(now / 280) : 0;
      ctx.strokeStyle = hsl(palette.highlight, 0.9);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(s.x, s.y, radius + 7 + pulse, 0, Math.PI * 2);
      ctx.stroke();
    }
    hits.push({ id: node.id, x0: s.x - 12, y0: s.y - 12, x1: s.x + 12, y1: s.y + 12 });

    // In-focus labels keep a readable floor; anchors keep a larger one.
    let scale = cam.zoom;
    if (inFocus || isActive || isSelected) scale = Math.max(scale, floors.focus);
    if (anchor) scale = Math.max(scale, inFocus ? floors.anchor : floors.anchorOff);
    const far = cam.zoom < floors.far;
    const visible = anchor || isActive || isSelected || (inFocus && !far) || (exploring && LABEL_FONT * scale >= 8.5);
    if (!visible || alpha < 0.05) continue;
    const compact = anchor && !inFocus && cam.zoom < 0.5;
    const priority = isSelected ? 6 : isActive ? 5 : anchor && inFocus ? 4 : inFocus ? 3 : anchor ? 2 : 1;
    candidates.push({ node, s, scale, opacity, accent, compact, anchor, isSelected, priority });
  }

  const placed = [];
  candidates.sort((a, b) => b.priority - a.priority);
  for (const c of candidates) {
    const box = boxes.get(c.node.id);
    const w = c.compact ? (c.node.label.length * 6.9 + LABEL_PAD * 2) * c.scale : box.w * c.scale;
    const h = c.compact ? 20 * c.scale : box.h * c.scale;
    // Try the label right of its dot, then left, above and below; the first spot
    // clear of labels already placed wins (the selection always gets the first).
    const gap = LABEL_GAP * c.scale;
    const spots = [
      [c.s.x + gap, c.s.y - h / 2], [c.s.x - gap - w, c.s.y - h / 2],
      [c.s.x - w / 2, c.s.y - gap - h], [c.s.x - w / 2, c.s.y + gap],
    ];
    const clear = (sx, sy) => !placed.some((r) => r.x0 < sx + w + 2 && sx - 2 < r.x1 && r.y0 < sy + h + 2 && sy - 2 < r.y1);
    const inside = (sx, sy) => sx >= 0 && sy >= 0 && sx + w <= rt.width && sy + h <= rt.height;
    const spot = c.priority >= 5 ? spots[0]
      : spots.find(([sx, sy]) => clear(sx, sy) && inside(sx, sy)) || spots.find(([sx, sy]) => clear(sx, sy));
    if (!spot) continue;
    const [x, y] = spot;
    placed.push({ x0: x - 2, y0: y - 2, x1: x + w + 2, y1: y + h + 2 });
    ctx.fillStyle = hsl(palette['label-bg'], 0.86 * c.opacity);
    ctx.strokeStyle = c.isSelected ? hsl(palette.highlight, 0.9) : hsl(palette['label-border'], 0.9 * c.opacity);
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, 3 * c.scale); else ctx.rect(x, y, w, h);
    ctx.fill();
    ctx.stroke();
    if (c.accent) {
      ctx.fillStyle = hexAlpha(c.accent, 0.9 * c.opacity);
      ctx.fillRect(x, y + 3 * c.scale, 2, h - 6 * c.scale);
    }
    ctx.fillStyle = hsl(palette['label-fg'], c.opacity);
    ctx.font = `${c.anchor ? 600 : 400} ${LABEL_FONT * c.scale}px ${MONO}`;
    ctx.fillText(c.node.label, x + LABEL_PAD * c.scale, y + 14 * c.scale);
    if (!c.compact) {
      ctx.fillStyle = hsl(palette['label-muted'], c.opacity);
      ctx.font = `${SUBLABEL_FONT * c.scale}px ${MONO}`;
      ctx.fillText(c.node.sublabel || '', x + LABEL_PAD * c.scale, y + 27 * c.scale);
    }
    hits.push({ id: c.node.id, x0: x, y0: y, x1: x + w, y1: y + h });
  }
  ctx.restore();
  return hits;
}

function draw(rt, now) {
  if (!rt.ctx || !rt.props || !rt.palette) return;
  rt.ctx.setTransform(rt.dpr, 0, 0, rt.dpr, 0, 0);
  drawBackground(rt);
  const lens = rt.props.lens;
  const fade = rt.fade && now - rt.fade.start < LENS_FADE_MS ? (now - rt.fade.start) / LENS_FADE_MS : null;
  if (fade !== null && rt.fade.from !== lens) drawLens(rt, rt.fade.from, 1 - fade, now);
  rt.hits = drawLens(rt, lens, fade === null ? 1 : fade, now);
  drawVignette(rt);
}

function stageTarget(rt) {
  const { model, layout, lens, stageIndex, insetBottom } = rt.props;
  const ids = stageFocus(model, lens, stageIndex);
  const viewport = { width: rt.width, height: rt.height };
  const options = { padding: 28, inset: { top: 44, bottom: insetBottom }, maxZoom: 1.3 };
  let cam = fitBounds(boundsOf(layout, lens, ids), viewport, options);
  // Focus labels keep a readable floor, so a tight fit must make room for them.
  const floors = floorsFor(rt.width);
  for (let i = 0; i < 2 && cam.zoom < floors.focus && cam.zoom >= floors.far; i += 1) {
    cam = fitBounds(boundsOf(layout, lens, ids, floors.focus / cam.zoom), viewport, options);
  }
  return cam;
}

const ConstellationCanvas = forwardRef(function ConstellationCanvas(props, handle) {
  const { label, describedBy, onSelect, onHover, onUserInteract } = props;
  const [rt] = useState(() => ({
    container: null, canvas: null, ctx: null, width: 0, height: 0, dpr: 1, cam: null, flight: null, arrivedAt: 0,
    userCam: false, palette: null, stars: null, fade: null, hoverId: null, hits: [], pointers: new Map(),
    drag: null, pinch: null, raf: 0, props: null, seen: {},
  }));
  rt.props = props;
  rt.callbacks = { onSelect, onHover, onUserInteract };

  const requestFrame = () => {
    if (rt.raf || typeof window === 'undefined' || !window.requestAnimationFrame) return;
    rt.raf = window.requestAnimationFrame(tick);
  };

  function retarget(animate, duration = FLIGHT_MS) {
    if (!rt.width || !rt.props) return;
    const target = stageTarget(rt);
    const now = performance.now();
    rt.userCam = false;
    if (!animate || !rt.cam || !rt.props.animate) {
      rt.cam = target;
      rt.flight = null;
    } else {
      rt.flight = { from: rt.cam, to: target, start: now, duration };
    }
    rt.target = target;
    rt.arrivedAt = rt.flight ? now + duration : now;
    requestFrame();
  }

  function tick(now) {
    rt.raf = 0;
    if (!rt.ctx) return;
    if (rt.flight) {
      const t = (now - rt.flight.start) / rt.flight.duration;
      rt.cam = flight(rt.flight.from, rt.flight.to, t, { width: rt.width, height: rt.height });
      if (t >= 1) { rt.cam = rt.flight.to; rt.flight = null; rt.arrivedAt = now; }
    } else if (rt.props.playing && !rt.userCam && rt.props.animate && rt.target) {
      rt.cam = drift(rt.target, (now - rt.arrivedAt) / DWELL_MS);
    }
    draw(rt, now);
    if (rt.props.animate || rt.flight || (rt.fade && now - rt.fade.start < LENS_FADE_MS)) requestFrame();
  }

  function userInteract() {
    rt.flight = null;
    if (!rt.userCam) {
      rt.userCam = true;
      rt.callbacks.onUserInteract?.();
    }
  }

  function hitAt(x, y) {
    for (let i = rt.hits.length - 1; i >= 0; i -= 1) {
      const h = rt.hits[i];
      if (x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1) return h.id;
    }
    return null;
  }

  useImperativeHandle(handle, () => ({
    zoomBy(factor) {
      if (!rt.cam) return;
      userInteract();
      rt.cam = zoomAt(rt.cam, { width: rt.width, height: rt.height }, { x: rt.width / 2, y: rt.height / 2 }, factor);
      requestFrame();
    },
    panBy(dx, dy) {
      if (!rt.cam) return;
      userInteract();
      rt.cam = panBy(rt.cam, dx, dy);
      requestFrame();
    },
    fit() { retarget(true, 900); },
    // The handle only touches rt, so it is built once; a fresh object per render
    // would re-run the parent's ref setter on every render.
  }), []);

  // Mount: size, palette, starfield, input listeners and the frame loop.
  useEffect(() => {
    const { container, canvas } = rt;
    if (!container || !canvas) return undefined;
    rt.ctx = canvas.getContext?.('2d') || null;
    if (!rt.ctx) return undefined;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      rt.dpr = Math.min(2, window.devicePixelRatio || 1);
      rt.width = Math.max(1, Math.round(rect.width));
      rt.height = Math.max(1, Math.round(rect.height));
      canvas.width = rt.width * rt.dpr;
      canvas.height = rt.height * rt.dpr;
      canvas.style.width = `${rt.width}px`;
      canvas.style.height = `${rt.height}px`;
      if (!rt.stars || rt.stars.dpr !== rt.dpr) {
        rt.stars = starTile(rt.palette, rt.dpr);
        if (rt.stars) rt.stars.dpr = rt.dpr;
      }
      if (!rt.cam || !rt.userCam) retarget(false); else requestFrame();
    };
    rt.palette = readPalette(container);
    resize();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resize);
    observer?.observe(container);
    const themeWatch = typeof MutationObserver === 'undefined' ? null : new MutationObserver(() => {
      rt.palette = readPalette(container);
      rt.stars = starTile(rt.palette, rt.dpr);
      requestFrame();
    });
    themeWatch?.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    document.fonts?.load?.(`11px ${MONO}`).then(requestFrame, () => {});

    const local = (event) => {
      const rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };
    const onPointerDown = (event) => {
      canvas.setPointerCapture?.(event.pointerId);
      rt.pointers.set(event.pointerId, local(event));
      if (rt.pointers.size === 1) rt.drag = { ...local(event), moved: false };
      if (rt.pointers.size === 2) {
        const [p, q] = [...rt.pointers.values()];
        rt.pinch = Math.hypot(p.x - q.x, p.y - q.y);
      }
    };
    const onPointerMove = (event) => {
      const point = local(event);
      if (rt.pointers.has(event.pointerId)) {
        rt.pointers.set(event.pointerId, point);
        if (rt.pointers.size === 2 && rt.pinch) {
          const [p, q] = [...rt.pointers.values()];
          const dist = Math.hypot(p.x - q.x, p.y - q.y);
          userInteract();
          rt.cam = zoomAt(rt.cam, { width: rt.width, height: rt.height }, { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 }, dist / rt.pinch);
          rt.pinch = dist;
          if (rt.drag) rt.drag.moved = true;
          requestFrame();
          return;
        }
        if (rt.drag) {
          const dx = point.x - rt.drag.x; const dy = point.y - rt.drag.y;
          if (!rt.drag.moved && Math.hypot(dx, dy) < 4) return;
          rt.drag.moved = true;
          userInteract();
          rt.cam = panBy(rt.cam, dx, dy);
          rt.drag.x = point.x; rt.drag.y = point.y;
          canvas.style.cursor = 'grabbing';
          requestFrame();
        }
        return;
      }
      const hover = hitAt(point.x, point.y);
      if (hover !== rt.hoverId) {
        rt.hoverId = hover;
        canvas.style.cursor = hover ? 'pointer' : 'grab';
        rt.callbacks.onHover?.(hover);
        requestFrame();
      }
    };
    const onPointerUp = (event) => {
      const point = local(event);
      rt.pointers.delete(event.pointerId);
      if (rt.pointers.size < 2) rt.pinch = null;
      if (rt.drag && !rt.drag.moved && rt.pointers.size === 0) rt.callbacks.onSelect?.(hitAt(point.x, point.y));
      if (rt.pointers.size === 0) rt.drag = null;
      canvas.style.cursor = rt.hoverId ? 'pointer' : 'grab';
    };
    const onWheel = (event) => {
      event.preventDefault();
      userInteract();
      rt.cam = zoomAt(rt.cam, { width: rt.width, height: rt.height }, local(event), Math.exp(-event.deltaY * 0.0015));
      requestFrame();
    };
    const onDoubleClick = () => retarget(true, 900);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    canvas.addEventListener('dblclick', onDoubleClick);
    canvas.style.cursor = 'grab';
    return () => {
      observer?.disconnect();
      themeWatch?.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('dblclick', onDoubleClick);
      if (rt.raf) window.cancelAnimationFrame?.(rt.raf);
      rt.raf = 0;
      rt.ctx = null;
    };
    // The loop reads props through rt, so it mounts once.
  }, []);

  // React to the tour: a new stage flies the camera; a new lens crossfades and
  // keeps an explored camera where the viewer left it.
  const { stageIndex, lens, selectedId, model, layout, playing, animate, insetBottom } = props;
  useEffect(() => {
    const seen = rt.seen;
    const stageChanged = seen.stageIndex !== stageIndex || seen.model !== model;
    const lensChanged = seen.lens !== undefined && seen.lens !== lens;
    if (lensChanged) rt.fade = { from: seen.lens, start: performance.now() };
    if (stageChanged) retarget(seen.stageIndex !== undefined);
    else if (lensChanged && !rt.userCam) retarget(true, 900);
    else if (seen.insetBottom !== insetBottom && !rt.userCam) retarget(false);
    if (selectedId && selectedId !== seen.selectedId && rt.cam && rt.width) {
      const p = layout.positions[lens].get(selectedId);
      const s = p ? { x: (p.x - rt.cam.x) * rt.cam.zoom + rt.width / 2, y: (p.y - rt.cam.y) * rt.cam.zoom + rt.height / 2 } : null;
      const visible = s && s.x > 40 && s.y > 60 && s.x < rt.width - 160 && s.y < rt.height - insetBottom;
      if (p && !visible) {
        const ids = [selectedId, ...(model.lenses[lens].neighbors.get(selectedId) || [])];
        const target = fitBounds(boundsOf(layout, lens, ids), { width: rt.width, height: rt.height }, {
          padding: 48, inset: { top: 52, bottom: insetBottom }, maxZoom: 1.2,
        });
        rt.userCam = true;
        rt.flight = animate ? { from: rt.cam, to: target, start: performance.now(), duration: 1100 } : null;
        if (!animate) rt.cam = target;
      }
    }
    if (playing && !seen.playing && rt.userCam) retarget(true, 1100);
    rt.seen = { stageIndex, lens, selectedId, model, playing, insetBottom };
    requestFrame();
  });

  return (
    <div ref={(el) => { rt.container = el; }} className="absolute inset-0">
      <canvas
        ref={(el) => { rt.canvas = el; }}
        role="img"
        aria-label={label}
        aria-describedby={describedBy}
        className="block h-full w-full touch-none"
      />
      <div hidden aria-hidden="true">
        {[...model.apps.values()].map((app) => <span key={app.id} data-repo={app.program_id} />)}
      </div>
    </div>
  );
});

export default ConstellationCanvas;

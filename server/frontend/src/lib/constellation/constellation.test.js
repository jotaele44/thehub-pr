import { describe, it, expect } from 'vitest';
import { constellationPayload } from '@/test/constellationPayload';
import {
  buildModel, counterpartOf, describeNode, formatCount, linkedNodes, otherLens, stageFocus, stageIndexById,
  stageOfNode, stageTitle,
} from '@/lib/constellation/model';
import { boundsOf, computeLayout, footprint, hashString, labelBox, seededRandom } from '@/lib/constellation/layout';
import {
  clampZoom, drift, easeInOutCubic, fitBounds, flight, MAX_ZOOM, MIN_ZOOM, panBy, screenToWorld, worldToScreen, zoomAt,
} from '@/lib/constellation/camera';
import { initialTour, tourReducer } from '@/lib/constellation/tour';

const model = buildModel(constellationPayload);
const viewport = { width: 1200, height: 700 };

describe('constellation model', () => {
  it('indexes both lenses and drops edges whose ends are missing', () => {
    expect(model.lenses.code.nodes.size).toBe(7);
    expect(model.lenses.content.nodes.size).toBe(6);
    const broken = buildModel({
      ...constellationPayload,
      lenses: { ...constellationPayload.lenses, code: { ...constellationPayload.lenses.code, edges: [{ id: 'x', kind: 'call', from: 'nope', to: 'thehub.fetch' }] } },
    });
    expect(broken.lenses.code.edges).toEqual([]);
  });

  it('keeps member edges out of the neighbour sets', () => {
    expect([...model.lenses.code.neighbors.get('centinelas.poll')]).toEqual(['centinelas.dispatch']);
    expect(model.lenses.code.neighbors.get('app:centinelas').size).toBe(0);
  });

  it('maps a selection across lenses through links, and keeps shared anchors', () => {
    expect(counterpartOf(model, 'code', 'centinelas.export')).toBe('content:centinelas:observations');
    expect(counterpartOf(model, 'content', 'content:thehub:stream:observations')).toBe('thehub.aggregate');
    expect(counterpartOf(model, 'code', 'app:thehub')).toBe('app:thehub');
    expect(counterpartOf(model, 'code', 'centinelas.poll')).toBeNull();
    expect(counterpartOf(model, 'code', null)).toBeNull();
    expect(linkedNodes(model, 'code', 'centinelas.export').map((n) => n.id)).toEqual(['content:centinelas:observations']);
    expect(otherLens('code')).toBe('content');
  });

  it('answers stage questions', () => {
    expect(stageFocus(model, 'content', 0)).toEqual(['app:centinelas', 'content:centinelas:observations', 'content:seam:intake-drops']);
    expect(stageFocus(model, 'code', 9)).toEqual([]);
    expect(stageOfNode(model, 'code', 'thehub.fetch')).toBe(1);
    expect(stageOfNode(model, 'code', 'missing')).toBeNull();
    expect(stageIndexById(model, 'federation')).toBe(2);
    expect(stageTitle(model.stages[1])).toBe('HUB AGGREGATE');
  });

  it('describes a node in one line with real counts', () => {
    const node = model.lenses.content.nodes.get('content:thehub:stream:observations');
    expect(describeNode(node)).toBe('observations · Hub stream · thehub-pr · data/aggregate/observations.jsonl · 572 exported · 400 in store');
    expect(formatCount(48224)).toBe('48,224');
    expect(formatCount(null)).toBe('—');
  });
});

describe('constellation layout', () => {
  const layout = computeLayout(model);

  it('is deterministic', () => {
    const again = computeLayout(buildModel(constellationPayload));
    expect([...again.positions.code]).toEqual([...layout.positions.code]);
    expect([...again.positions.content]).toEqual([...layout.positions.content]);
    expect(seededRandom(7)()).toBe(seededRandom(7)());
    expect(hashString('a')).not.toBe(hashString('b'));
  });

  it('shares app anchors between lenses and places every node', () => {
    expect(layout.positions.code.get('app:thehub')).toEqual(layout.positions.content.get('app:thehub'));
    for (const lens of ['code', 'content']) {
      for (const id of model.lenses[lens].nodes.keys()) expect(layout.positions[lens].has(id)).toBe(true);
    }
  });

  it('separates label boxes inside a stage', () => {
    const ids = ['centinelas.poll', 'centinelas.dispatch', 'app:centinelas'];
    const rects = ids.map((id) => footprint(layout.positions.code.get(id), layout.boxes.code.get(id)));
    for (let i = 0; i < rects.length; i += 1) {
      for (let j = i + 1; j < rects.length; j += 1) {
        const a = rects[i]; const b = rects[j];
        const overlapping = a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
        expect(overlapping).toBe(false);
      }
    }
  });

  it('sizes label boxes from the longer line and bounds a set of nodes', () => {
    expect(labelBox({ label: 'ab', sublabel: '' }).w).toBeLessThan(labelBox({ label: 'ab', sublabel: 'a much longer sublabel' }).w);
    const b = boundsOf(layout, 'code', ['centinelas.poll', 'thehub.fetch']);
    expect(b.x1).toBeGreaterThan(b.x0);
    expect(boundsOf(layout, 'code', ['missing'])).toBeNull();
    const wide = boundsOf(layout, 'code', ['centinelas.poll', 'thehub.fetch'], 2);
    expect(wide.x1 - wide.x0).toBeGreaterThan(b.x1 - b.x0);
  });
});

describe('constellation camera', () => {
  it('fits bounds inside the viewport and respects the inset', () => {
    const cam = fitBounds({ x0: 0, y0: 0, x1: 1000, y1: 500 }, viewport, { padding: 0 });
    expect(cam.zoom).toBeCloseTo(1.2);
    const inset = fitBounds({ x0: 0, y0: 0, x1: 1000, y1: 500 }, viewport, { padding: 0, inset: { bottom: 200 } });
    expect(inset.zoom).toBeCloseTo(1);
    expect(inset.y).toBeGreaterThan(cam.y);
    expect(fitBounds(null, viewport)).toEqual({ x: 0, y: 0, zoom: 0.5 });
  });

  it('round-trips screen and world coordinates', () => {
    const cam = { x: 40, y: -20, zoom: 0.8 };
    const p = { x: 123, y: 456 };
    const back = screenToWorld(cam, viewport, worldToScreen(cam, viewport, p));
    expect(back.x).toBeCloseTo(p.x);
    expect(back.y).toBeCloseTo(p.y);
  });

  it('flies with eased ends and a mid-flight pull-back on long hops', () => {
    const a = { x: 0, y: 0, zoom: 1 };
    const b = { x: 6000, y: 0, zoom: 1 };
    expect(flight(a, b, 0, viewport)).toEqual(a);
    expect(flight(a, b, 1, viewport).x).toBeCloseTo(6000);
    expect(flight(a, b, 0.5, viewport).zoom).toBeLessThan(1);
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5);
  });

  it('zooms about a fixed point, pans and clamps', () => {
    const cam = { x: 0, y: 0, zoom: 1 };
    const pivot = { x: 900, y: 100 };
    const zoomed = zoomAt(cam, viewport, pivot, 2);
    const before = screenToWorld(cam, viewport, pivot);
    const after = screenToWorld(zoomed, viewport, pivot);
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
    expect(panBy(cam, 100, 0).x).toBe(-100);
    expect(clampZoom(100)).toBe(MAX_ZOOM);
    expect(clampZoom(0)).toBe(MIN_ZOOM);
    expect(drift(cam, 1).zoom).toBeGreaterThan(cam.zoom);
  });
});

describe('constellation tour', () => {
  const start = initialTour({ stageCount: 3 });

  it('starts playing on the first stage', () => {
    expect(start).toEqual({ stageCount: 3, stageIndex: 0, lens: 'code', selectedId: null, playing: true });
    expect(initialTour({ stageCount: 1 }).playing).toBe(false);
    expect(initialTour({ stageCount: 3, stageIndex: 9 }).stageIndex).toBe(2);
  });

  it('advances only while playing and loops after the overview', () => {
    const s1 = tourReducer(start, { type: 'ADVANCE' });
    expect(s1.stageIndex).toBe(1);
    expect(tourReducer({ ...start, stageIndex: 2 }, { type: 'ADVANCE' }).stageIndex).toBe(0);
    const paused = tourReducer(s1, { type: 'PAUSE' });
    expect(tourReducer(paused, { type: 'ADVANCE' })).toBe(paused);
  });

  it('steps and jumps manually, clearing the selection', () => {
    const selected = { ...start, selectedId: 'thehub.fetch' };
    expect(tourReducer(selected, { type: 'NEXT' })).toMatchObject({ stageIndex: 1, selectedId: null });
    expect(tourReducer(start, { type: 'PREV' }).stageIndex).toBe(2);
    expect(tourReducer(start, { type: 'GOTO', index: 2 }).stageIndex).toBe(2);
    expect(tourReducer(start, { type: 'GOTO', index: 0 })).toBe(start);
  });

  it('pauses on interaction and selection, and restarts from the overview', () => {
    expect(tourReducer(start, { type: 'USER_INTERACT' }).playing).toBe(false);
    expect(tourReducer(start, { type: 'SELECT', id: 'thehub.fetch', stageIndex: 1 })).toMatchObject({ playing: false, selectedId: 'thehub.fetch', stageIndex: 1 });
    const end = { ...start, playing: false, stageIndex: 2 };
    expect(tourReducer(end, { type: 'PLAY' })).toMatchObject({ playing: true, stageIndex: 0 });
    expect(tourReducer(start, { type: 'TOGGLE_PLAY' }).playing).toBe(false);
  });

  it('switches lens carrying the counterpart selection', () => {
    const s = tourReducer({ ...start, selectedId: 'centinelas.export' }, { type: 'SET_LENS', lens: 'content', selectedId: 'content:centinelas:observations' });
    expect(s).toMatchObject({ lens: 'content', selectedId: 'content:centinelas:observations' });
    expect(tourReducer(s, { type: 'SET_LENS', lens: 'content' })).toBe(s);
    expect(tourReducer(s, { type: 'CLEAR_SELECTION' }).selectedId).toBeNull();
    expect(tourReducer(s, { type: 'UNKNOWN' })).toBe(s);
  });
});

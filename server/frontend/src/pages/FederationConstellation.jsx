import React, { useEffect, useMemo, useReducer, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Orbit } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import ConstellationCanvas from '@/components/constellation/ConstellationCanvas';
import ConstellationControls from '@/components/constellation/ConstellationControls';
import ConstellationLegend from '@/components/constellation/ConstellationLegend';
import NodeDetails from '@/components/constellation/NodeDetails';
import StageCaption from '@/components/constellation/StageCaption';
import StageOutline from '@/components/constellation/StageOutline';
import { buildModel, counterpartOf, formatCount, LENSES, otherLens, stageFocus, stageIndexById, stageOfNode, stageTitle } from '@/lib/constellation/model';
import { computeLayout } from '@/lib/constellation/layout';
import { DWELL_MS, FLIGHT_MS } from '@/lib/constellation/camera';
import { initialTour, tourReducer } from '@/lib/constellation/tour';

// The Federation Apps as one graph, after the "code constellation" flythrough
// videos: the tour flies stage by stage through the pipeline (Centinelas intake
// to Hub ingest) under a two-tone caption, and pausing hands the camera to the
// viewer. The Code lens draws each app's components; the Content lens draws the
// records they move, with real counts and sample rows from the Hub store.

const OUTLINE_ID = 'constellation-outline';

function useMediaQuery(query) {
  const read = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(read);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    list.addEventListener?.('change', onChange);
    return () => list.removeEventListener?.('change', onChange);
  }, [query]);
  return matches;
}

function readTour(searchParams, model, reducedMotion) {
  const lens = LENSES.includes(searchParams.get('lens')) ? searchParams.get('lens') : 'code';
  const stageParam = searchParams.get('stage');
  const stageIndex = stageParam ? Math.max(0, stageIndexById(model, stageParam)) : 0;
  const node = searchParams.get('node');
  const selectedId = node && model.lenses[lens].nodes.has(node) ? node : null;
  return initialTour({
    stageCount: model.stages.length, stageIndex, lens, selectedId,
    playing: !reducedMotion && !stageParam && !selectedId,
  });
}

function ConstellationView({ model, layout, reducedMotion }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tour, dispatch] = useReducer(tourReducer, null, () => readTour(searchParams, model, reducedMotion));
  const [canvas, setCanvas] = useState(null);
  const wide = useMediaQuery('(min-width: 640px)');
  const { stageIndex, lens, selectedId, playing } = tour;
  const stage = model.stages[stageIndex];
  const node = selectedId ? model.lenses[lens].nodes.get(selectedId) : null;
  const singleApp = stage.apps.length === 1 ? model.apps.get(stage.apps[0]) : null;

  // The flythrough: hold each stage for its flight plus a dwell, then move on.
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => dispatch({ type: 'ADVANCE' }), (reducedMotion ? 0 : FLIGHT_MS) + DWELL_MS);
    return () => clearTimeout(timer);
  }, [playing, stageIndex, reducedMotion]);

  // Keep the URL a deep link to what is on screen.
  useEffect(() => {
    const next = new URLSearchParams();
    next.set('lens', lens);
    next.set('stage', stage.id);
    if (selectedId) next.set('node', selectedId);
    if (next.toString() !== searchParams.toString()) setSearchParams(next, { replace: true });
  }, [lens, stage.id, selectedId, searchParams, setSearchParams]);

  const setLens = (next) => dispatch({ type: 'SET_LENS', lens: next, selectedId: counterpartOf(model, lens, selectedId) });
  const select = (id) => (id ? dispatch({ type: 'SELECT', id }) : dispatch({ type: 'CLEAR_SELECTION' }));
  const showIn = (targetLens, id) => {
    const inStage = stageFocus(model, targetLens, stageIndex).includes(id);
    dispatch({ type: 'SET_LENS', lens: targetLens, selectedId: id });
    dispatch({ type: 'SELECT', id, stageIndex: inStage ? stageIndex : (stageOfNode(model, targetLens, id) ?? stageIndex) });
  };

  const onKeyDown = (event) => {
    const keys = {
      ' ': () => dispatch({ type: 'TOGGLE_PLAY' }),
      ArrowRight: () => dispatch({ type: 'NEXT' }),
      ArrowLeft: () => dispatch({ type: 'PREV' }),
      l: () => setLens(otherLens(lens)),
      L: () => setLens(otherLens(lens)),
      '+': () => canvas?.zoomBy(1.25),
      '=': () => canvas?.zoomBy(1.25),
      '-': () => canvas?.zoomBy(0.8),
      f: () => canvas?.fit(),
      Escape: () => dispatch({ type: 'CLEAR_SELECTION' }),
    };
    const run = keys[event.key];
    if (!run || event.target !== event.currentTarget) return;
    event.preventDefault();
    run();
  };

  const focusCount = stageFocus(model, lens, stageIndex).length;
  const canvasLabel = `Federation constellation, ${lens} lens. Stage ${stageIndex + 1} of ${model.stages.length}: `
    + `${stageTitle(stage)}, ${focusCount} nodes in view. The list of nodes in this stage follows the controls.`;

  return (
    <div className="space-y-4">
      {model.storeStatus === 'EMPTY' ? (
        <div role="status" className="rounded-xl border border-border bg-card p-4 text-sm text-foreground" data-constellation-store="EMPTY">
          The Hub store holds no records yet, so the Content lens shows only the declared streams and seams. Run
          {' '}<code className="font-mono">make ingest</code> to load the committed sample.
        </div>
      ) : null}

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-3">
          <div
            tabIndex={0}
            role="region"
            aria-label="Constellation stage. Space plays or pauses, the arrow keys change stage, L switches lens, plus and minus zoom."
            onKeyDown={onKeyDown}
            className="relative h-[68vh] min-h-[420px] max-h-[880px] overflow-hidden rounded-xl border border-border bg-[hsl(var(--constellation-bg))] focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
            data-constellation-stage={stage.id}
            data-constellation-lens={lens}
          >
            <ConstellationCanvas
              ref={setCanvas}
              model={model}
              layout={layout}
              lens={lens}
              stageIndex={stageIndex}
              selectedId={selectedId}
              playing={playing}
              exploring={!playing}
              animate={!reducedMotion}
              insetBottom={wide ? 112 : 88}
              label={canvasLabel}
              describedBy={OUTLINE_ID}
              onSelect={select}
              onUserInteract={() => dispatch({ type: 'USER_INTERACT' })}
            />
            <ConstellationLegend legend={model.lenses[lens].legend} lens={lens} />
            <StageCaption stage={stage} index={stageIndex} count={model.stages.length} program={singleApp?.program_id} />
          </div>

          <ConstellationControls
            stages={model.stages}
            stageIndex={stageIndex}
            playing={playing}
            lens={lens}
            onPrev={() => dispatch({ type: 'PREV' })}
            onNext={() => dispatch({ type: 'NEXT' })}
            onTogglePlay={() => dispatch({ type: 'TOGGLE_PLAY' })}
            onGoto={(index) => dispatch({ type: 'GOTO', index })}
            onLens={setLens}
            onFit={() => canvas?.fit()}
            onZoom={(factor) => canvas?.zoomBy(factor)}
          />
          <p className="text-xs text-muted-foreground" role="status" data-constellation-mode={playing ? 'tour' : 'explore'}>
            {playing
              ? `Touring: stage ${stageIndex + 1} of ${model.stages.length}. Drag, scroll or select a node to explore.`
              : 'Exploring: drag to pan, scroll or pinch to zoom, select a node for details. Play resumes the tour.'}
          </p>
        </div>

        <aside className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-2 2xl:grid-cols-1 2xl:content-start" aria-label="Details">
          <NodeDetails
            model={model}
            lens={lens}
            node={node}
            stage={stage}
            stageIndex={stageIndex}
            onSelect={select}
            onShowIn={showIn}
            onClose={() => dispatch({ type: 'CLEAR_SELECTION' })}
          />
          <StageOutline id={OUTLINE_ID} model={model} lens={lens} stageIndex={stageIndex} selectedId={selectedId} onSelect={select} />
        </aside>
      </div>

      <p className="text-xs text-muted-foreground">
        Code lens: <code className="font-mono">registry/constellation.v1.json</code>, checked against the repo by its tests.
        Content lens: the Hub store ({formatCount(model.totals.stored)} rows held of {formatCount(model.totals.exported)} exported).
        Cross-app hops are file or package handoffs; the federation forbids runtime RPC between producers.
      </p>
    </div>
  );
}

export default function FederationConstellation() {
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['constellation'],
    queryFn: () => federation.constellation.get(),
    staleTime: 60_000,
  });
  const model = useMemo(() => (data ? buildModel(data) : null), [data]);
  const layout = useMemo(() => (model ? computeLayout(model) : null), [model]);

  return (
    <div className="space-y-4 p-4 md:p-8">
      <PageHeader
        icon={Orbit}
        title="Federation Constellation"
        description="The seven federation apps as one graph. Switch between the program code and the content it moves; the tour flies through the pipeline, and pausing lets you explore."
      />
      {isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading the constellation…</p> : null}
      {isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The constellation is unavailable: {String(error?.message || error)}
        </div>
      ) : null}
      {model && layout ? <ConstellationView model={model} layout={layout} reducedMotion={reducedMotion} /> : null}
    </div>
  );
}

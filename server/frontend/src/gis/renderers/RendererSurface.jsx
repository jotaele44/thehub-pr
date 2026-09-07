import React, { Suspense, lazy } from 'react';

const MapLibreRenderer = lazy(() => import('./MapLibreRenderer'));
const CesiumRenderer = lazy(() => import('./CesiumRenderer'));

function LoadingRenderer({ mode }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-muted/20 text-sm text-muted-foreground">
      Loading {mode === '3d' ? 'Cesium 3D' : 'MapLibre 2D'} renderer…
    </div>
  );
}

export default function RendererSurface(props) {
  const Renderer = props.canonicalState.mode === '3d' ? CesiumRenderer : MapLibreRenderer;
  return (
    <Suspense fallback={<LoadingRenderer mode={props.canonicalState.mode} />}>
      <Renderer {...props} />
    </Suspense>
  );
}

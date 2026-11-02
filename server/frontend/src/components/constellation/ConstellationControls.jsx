import React from 'react';
import { ChevronLeft, ChevronRight, Code2, Database, Maximize, Pause, Play, ZoomIn, ZoomOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { stageTitle } from '@/lib/constellation/model';

const base = 'inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium';
const tone = (active) => cn(
  base,
  active ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-foreground hover:bg-muted',
);

// The tour's transport and lens controls. Every control has a visible or
// screen-reader name and is at least 44px tall.
export default function ConstellationControls({
  stages, stageIndex, playing, lens, onPrev, onNext, onTogglePlay, onGoto, onLens, onFit, onZoom,
}) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-constellation-controls>
      <div className="flex items-center gap-2" role="group" aria-label="Tour">
        <button type="button" className={tone(false)} onClick={onPrev} aria-label="Previous stage">
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </button>
        <button type="button" className={tone(playing)} onClick={onTogglePlay} aria-pressed={playing}>
          {playing ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
          {playing ? 'Pause' : 'Play tour'}
        </button>
        <button type="button" className={tone(false)} onClick={onNext} aria-label="Next stage">
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Stages">
        {stages.map((stage, index) => (
          <button
            key={stage.id}
            type="button"
            onClick={() => onGoto(index)}
            aria-pressed={index === stageIndex}
            aria-label={`Stage ${index + 1} of ${stages.length}: ${stageTitle(stage)}`}
            className={cn(
              'inline-flex min-h-[44px] min-w-[36px] items-center justify-center rounded-md border px-2 font-mono text-xs font-semibold',
              index === stageIndex
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-card text-muted-foreground hover:bg-muted',
            )}
          >
            {index + 1}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1" role="group" aria-label="Lens">
        <button type="button" className={tone(lens === 'code')} aria-pressed={lens === 'code'} onClick={() => onLens('code')}>
          <Code2 className="h-4 w-4" aria-hidden="true" /> Code
        </button>
        <button type="button" className={tone(lens === 'content')} aria-pressed={lens === 'content'} onClick={() => onLens('content')}>
          <Database className="h-4 w-4" aria-hidden="true" /> Content
        </button>
      </div>

      <div className="flex items-center gap-1" role="group" aria-label="View">
        <button type="button" className={tone(false)} onClick={() => onZoom(1.25)} aria-label="Zoom in">
          <ZoomIn className="h-4 w-4" aria-hidden="true" />
        </button>
        <button type="button" className={tone(false)} onClick={() => onZoom(0.8)} aria-label="Zoom out">
          <ZoomOut className="h-4 w-4" aria-hidden="true" />
        </button>
        <button type="button" className={tone(false)} onClick={onFit} aria-label="Fit the stage in view">
          <Maximize className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

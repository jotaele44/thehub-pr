import React from 'react';
import { cn } from '@/lib/utils';

// The stage title over the constellation: a two-tone English title with one word
// highlighted and a Spanish subtitle. A single-app stage takes that app's accent
// (through its [data-repo] --fd-accent); shared stages take the gold highlight.
export default function StageCaption({ stage, index, count, program }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center px-3 sm:bottom-6">
      <div
        data-repo={program || undefined}
        data-stage-caption={stage.id}
        className="relative max-w-full rounded-md border border-[hsl(var(--constellation-label-border))] bg-[hsl(var(--constellation-label-bg)/0.84)] px-4 pb-2 pt-2.5 text-center shadow-lg sm:px-7 sm:pb-3 sm:pt-3.5"
      >
        <span
          aria-hidden="true"
          className={cn(
            'absolute left-1/2 top-0 h-[3px] w-20 -translate-x-1/2 -translate-y-1/2 rounded-full',
            program ? 'bg-[var(--fd-accent)]' : 'bg-[hsl(var(--constellation-highlight))]',
          )}
        />
        <p className="font-heading text-2xl font-extrabold uppercase leading-none tracking-tight sm:text-4xl xl:text-5xl" data-stage-title>
          <span className="text-[hsl(var(--constellation-caption))]">{stage.title.lead}</span>{' '}
          <span
            className={cn(
              'inline-block rounded-sm px-1.5 py-0.5',
              program
                ? 'bg-[var(--fd-accent)] text-[hsl(var(--constellation-label-fg))]'
                : 'bg-[hsl(var(--constellation-highlight))] text-[hsl(var(--constellation-bg))]',
            )}
          >
            {stage.title.accent}
          </span>
        </p>
        <p lang="es" className="mt-1.5 text-sm text-[hsl(var(--constellation-label-fg))] sm:text-lg">{stage.subtitle_es}</p>
        <p className="sr-only" aria-live="polite">
          {`Stage ${index + 1} of ${count}: ${stage.title.lead} ${stage.title.accent}. ${stage.summary}`}
        </p>
      </div>
    </div>
  );
}

import React from 'react';

const TONE_DOT = {
  1: 'bg-[hsl(var(--constellation-edge-1))]',
  2: 'bg-[hsl(var(--constellation-edge-2))]',
  3: 'bg-[hsl(var(--constellation-edge-3))]',
};

// The legend in the stage's top-left corner, as in the reference video. It
// names the edge kinds of the lens on screen; each entry's meaning is read out
// to assistive technology.
export default function ConstellationLegend({ legend, lens }) {
  return (
    <div className="pointer-events-none absolute left-3 right-3 top-3 sm:left-4 sm:top-4" data-constellation-legend={lens}>
      <ul
        aria-label={`Edge legend, ${lens} lens`}
        className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] font-semibold uppercase tracking-wide text-[hsl(var(--constellation-label-muted))]"
      >
        {legend.map((item) => (
          <li key={item.kind} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`h-2 w-2 rounded-full ${TONE_DOT[item.tone] || TONE_DOT[1]}`} />
            {item.label}
            <span className="sr-only">: {item.meaning}</span>
          </li>
        ))}
        <li className="flex items-center gap-1.5 normal-case tracking-normal">
          <span aria-hidden="true" className="w-4 border-t border-dashed border-[hsl(var(--constellation-label-muted))]" />
          dormant or manual seam
        </li>
      </ul>
    </div>
  );
}

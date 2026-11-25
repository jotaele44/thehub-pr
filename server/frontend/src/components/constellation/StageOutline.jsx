import React from 'react';
import { cn } from '@/lib/utils';
import { kindLabel, stageFocus } from '@/lib/constellation/model';

// The nodes the stage frames, as a keyboard-navigable list: the non-visual
// equivalent of the canvas, and a quick way to jump to any of them.
export default function StageOutline({ id, model, lens, stageIndex, selectedId, onSelect }) {
  const nodes = stageFocus(model, lens, stageIndex).map((nodeId) => model.lenses[lens].nodes.get(nodeId));
  return (
    <section id={id} aria-label="Nodes in this stage" className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        In this stage · {nodes.length} {lens} nodes
      </h3>
      <ul className="max-h-[22rem] space-y-1 overflow-y-auto pr-1">
        {nodes.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              aria-pressed={node.id === selectedId}
              onClick={() => onSelect(node.id)}
              className={cn(
                'flex min-h-[44px] w-full flex-col items-start justify-center rounded-md border px-3 py-1.5 text-left',
                node.id === selectedId ? 'border-primary bg-primary/10' : 'border-border bg-card hover:bg-muted',
              )}
            >
              <span className="font-mono text-sm text-foreground">{node.label}</span>
              <span className="text-[11px] text-muted-foreground">{kindLabel(node.kind)} · {node.sublabel}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

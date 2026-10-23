import React from 'react';
import { cn } from '@/lib/utils';
import { EVIDENCE_AXES, SYNTHETIC_TONE, axisValue } from '@/lib/evidenceState';

// One labelled chip per independent evidence-state axis. The chip text carries
// the meaning; colour only reinforces it. The basis is exposed as the chip's
// accessible description.
export default function EvidenceStateStrip({ evidence, className }) {
  return (
    <ul aria-label="Evidence state" className={cn('flex flex-wrap gap-2', className)}>
      {evidence?.synthetic ? (
        <li>
          <span
            className={cn('inline-flex items-center rounded-md border px-2 py-1 text-[11px] font-semibold', SYNTHETIC_TONE)}
            data-evidence-axis="synthetic"
            data-evidence-value="SYNTHETIC"
          >
            Synthetic / test row
          </span>
        </li>
      ) : null}
      {EVIDENCE_AXES.map((axis) => {
        const shown = axisValue(axis, evidence?.[axis.key]);
        const basis = axis.basisKey ? evidence?.[axis.basisKey] : null;
        const description = basis || shown.description || undefined;
        return (
          <li key={axis.key}>
            <span
              className={cn('inline-flex items-center rounded-md border px-2 py-1 text-[11px] font-semibold', shown.tone)}
              data-evidence-axis={axis.key}
              data-evidence-value={shown.value}
              title={description}
            >
              <span className="mr-1 font-normal opacity-80">{axis.label}:</span>
              {shown.label}
              {description ? <span className="sr-only"> ({description})</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

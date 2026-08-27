import React from 'react';

export default function ForensicStateBadge({ axis, value }) {
  const display = String(value || 'UNKNOWN').trim().toUpperCase();
  return (
    <span
      className="inline-flex items-center rounded-md border border-border bg-muted px-2 py-1 text-[11px] font-semibold text-foreground"
      data-forensic-axis={axis}
      data-forensic-value={display}
    >
      <span className="mr-1 text-muted-foreground">{axis}:</span>{display}
    </span>
  );
}

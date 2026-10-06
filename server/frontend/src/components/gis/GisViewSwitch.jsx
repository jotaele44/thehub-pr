import React from 'react';

// `/gis?view=property-map` opens the Property Map and `/gis?view=digital-twin` the
// Digital Twin (Phase 5); the workbench stays the default view, so existing /gis
// links keep working.
export const GIS_VIEWS = Object.freeze([
  Object.freeze({ id: 'workbench', label: 'Workbench' }),
  Object.freeze({ id: 'property-map', label: 'Property Map' }),
  Object.freeze({ id: 'digital-twin', label: 'Digital Twin' }),
]);

export function gisViewFrom(searchParams) {
  const view = searchParams.get('view');
  return GIS_VIEWS.some((item) => item.id === view) ? view : 'workbench';
}

export default function GisViewSwitch({ view, setSearchParams }) {
  return (
    <div role="group" aria-label="GIS view" className="inline-flex gap-1 rounded-md border border-border bg-muted/30 p-1">
      {GIS_VIEWS.map((item) => (
        <button
          key={item.id} type="button" aria-pressed={view === item.id}
          className={`min-h-[44px] rounded px-3 text-sm ${view === item.id ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`}
          onClick={() => setSearchParams((previous) => {
            const next = new URLSearchParams(previous);
            if (item.id === 'workbench') next.delete('view'); else next.set('view', item.id);
            next.delete('panel');
            return next;
          })}
        >{item.label}</button>
      ))}
    </div>
  );
}

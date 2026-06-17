import React, { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import MultiMarkerMap from "@/components/shared/MultiMarkerMap";
import { MapPin } from "lucide-react";

// Map tab for a module entity that has latitude/longitude fields.
// buildPoint(row) -> { id, lat, lon, title, subtitle }
export default function ModuleMapTab({ entityName, buildPoint }) {
  const { rows, isLoading } = useEntityData(entityName);

  const points = useMemo(() => rows.map(buildPoint), [rows, buildPoint]);
  const mapped = points.filter((p) => typeof p.lat === "number" && typeof p.lon === "number");

  if (isLoading) {
    return <div className="h-[480px] rounded-lg border border-border bg-card animate-pulse" />;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 text-[11px] text-muted-foreground">
        <MapPin className="h-3.5 w-3.5" />
        {mapped.length} of {rows.length} records have coordinates and are shown on the map.
      </div>
      {mapped.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No records with latitude/longitude yet. Add coordinates to records to plot them here.
          </p>
        </div>
      ) : (
        <MultiMarkerMap points={mapped} />
      )}
    </div>
  );
}
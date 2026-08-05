import React from "react";
import { cn } from "@/lib/utils";

// Shared page header. Two visual modes:
//  - default: neutral square icon tile (secondary bg) + title/description.
//  - accented: pass `accent` (a domainAccent() object) to tint the icon tile,
//    and optionally `badge` for a small pill next to the title.
// ModulePageHeader is a thin preset over this — the markup lives in one place.
export default function PageHeader({ title, description, icon: Icon, actions, accent, badge }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div className="flex items-start gap-3">
        {Icon && (
          <div className={cn(
            "mt-0.5 h-10 w-10 rounded-lg flex items-center justify-center shrink-0 border",
            accent ? cn(accent.bg, accent.border) : "bg-secondary border-border"
          )}>
            <Icon className={cn("h-5 w-5", accent ? accent.text : "text-foreground")} />
          </div>
        )}
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
            {badge && (
              <span className={cn(
                "px-1.5 py-0.5 rounded border text-[11px]",
                accent ? cn(accent.bg, accent.text, accent.border) : "bg-secondary text-muted-foreground border-border"
              )}>{badge}</span>
            )}
          </div>
          {description && <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

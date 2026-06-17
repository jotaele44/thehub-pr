import React from "react";
import { Link } from "react-router-dom";
import { MODULES, domainAccent } from "@/lib/federation";
import { cn } from "@/lib/utils";
import { Network, Radar, Droplets, Banknote, Plane, ArrowRight } from "lucide-react";

const ICONS = {
  "Spiderweb-PR": Network, "Ovnis-PR": Radar, "AguaYLuz-PR": Droplets,
  "MoneySweep-PR": Banknote, "Skywatcher-PR": Plane,
};

export default function ModuleGrid({ programs }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {MODULES.map((m) => {
        const accent = domainAccent(m.domain);
        const Icon = ICONS[m.name];
        const program = programs.find((p) => p.name === m.name);
        return (
          <Link key={m.path} to={m.path}
            className={cn("group rounded-xl border bg-card p-4 transition-all hover:bg-secondary/40", accent.border)}>
            <div className="flex items-start justify-between">
              <div className={cn("h-10 w-10 rounded-lg flex items-center justify-center border", accent.bg, accent.border)}>
                <Icon className={cn("h-5 w-5", accent.text)} />
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
            </div>
            <div className="mt-3">
              <div className="text-sm font-semibold text-foreground">{m.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{m.blurb}</div>
            </div>
            <div className="mt-3 flex items-center gap-2 text-[11px]">
              <span className={cn("px-1.5 py-0.5 rounded border", accent.bg, accent.text, accent.border)}>{m.domain}</span>
              <span className="text-muted-foreground">{program?.status || "Planned"}</span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
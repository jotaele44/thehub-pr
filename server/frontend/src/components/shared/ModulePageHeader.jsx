import React from "react";
import { cn } from "@/lib/utils";
import { domainAccent } from "@/lib/federation";

export default function ModulePageHeader({ module, icon: Icon }) {
  const accent = domainAccent(module.domain);
  return (
    <div className="flex items-start gap-3 mb-6">
      <div className={cn("h-11 w-11 rounded-lg flex items-center justify-center border shrink-0", accent.bg, accent.border)}>
        <Icon className={cn("h-5 w-5", accent.text)} />
      </div>
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{module.name}</h1>
          <span className={cn("px-1.5 py-0.5 rounded border text-[11px]", accent.bg, accent.text, accent.border)}>{module.domain}</span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">{module.blurb} · legacy: <span className="font-mono-id">{module.oldName}</span></p>
      </div>
    </div>
  );
}
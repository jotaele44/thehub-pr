import React from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import CrossoverCard from "@/components/crossover/CrossoverCard";
import EmptyState from "@/components/shared/EmptyState";
import { PAIR_PANELS, pairKey } from "@/lib/crossover-config";
import { Layers } from "lucide-react";

// Renders panels A–K, each scoped to a module pair, as expandable sections.
export default function PairPanel({ crossovers }) {
  return (
    <Accordion type="multiple" className="space-y-2">
      {PAIR_PANELS.map((p) => {
        const key = pairKey(p.pair[0], p.pair[1]);
        const rows = crossovers.filter((c) => pairKey(c.source_module, c.target_module) === key);
        return (
          <AccordionItem key={p.id} value={p.id} className="rounded-xl border border-border bg-card px-4">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center gap-3 text-left">
                <span className="h-6 w-6 rounded-md bg-secondary border border-border flex items-center justify-center text-xs font-mono-id">{p.id}</span>
                <span className="text-sm font-medium">{p.title}</span>
                <span className="text-xs text-muted-foreground">({rows.length})</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              {rows.length === 0 ? (
                <EmptyState
                  icon={Layers}
                  title="No crossovers in this pair yet"
                  description="No explicit links or candidate matches were found between these modules. Add records with shared municipality, agency, vendor, source, or graph linkage to surface candidates."
                />
              ) : (
                <div className="grid md:grid-cols-2 gap-3 pb-2">
                  {rows.map((c) => <CrossoverCard key={c.crossover_id} c={c} />)}
                </div>
              )}
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
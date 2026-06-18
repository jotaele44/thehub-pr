import React from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import GroupHeaderMetrics from "../GroupHeaderMetrics";
import TaskCard from "../TaskCard";

export default function GroupedView({ grouped, role, onEdit, onStatusChange }) {
  const defaultOpen = grouped.filter((g) => g.tasks.length > 0).map((g) => g.key);

  return (
    <Accordion type="multiple" defaultValue={defaultOpen} className="space-y-3">
      {grouped.map((group) => (
        <AccordionItem
          key={group.key}
          value={group.key}
          className="border border-border rounded-xl bg-card/50 overflow-hidden"
        >
          <AccordionTrigger className="px-4 py-3 hover:no-underline hover:bg-secondary/30">
            <GroupHeaderMetrics label={group.label} domain={group.domain} metrics={group.metrics} />
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            {group.tasks.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">No tasks match the current filters for this module.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {group.tasks.map((t) => (
                  <TaskCard key={t.id} task={t} role={role} onEdit={onEdit} onStatusChange={onStatusChange} />
                ))}
              </div>
            )}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
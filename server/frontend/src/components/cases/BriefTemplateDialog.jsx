import React, { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { BRIEF_TEMPLATE_LIST, DEFAULT_TEMPLATE_ID } from "@/lib/case-brief-templates";
import { generateCaseBriefPdf } from "@/lib/case-brief-pdf";
import { FileDown, Check } from "lucide-react";

// Lets leadership pick an output style before generating a case-brief PDF.
export default function BriefTemplateDialog({ open, onOpenChange, caseRow, sources, anomalies }) {
  const [selected, setSelected] = useState(DEFAULT_TEMPLATE_ID);

  const handleGenerate = () => {
    if (!caseRow) return;
    generateCaseBriefPdf(caseRow, sources, anomalies, selected);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Choose a brief template</DialogTitle>
          <DialogDescription>
            Select an output style for {caseRow?.case_code || caseRow?.title || "this case"}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-1">
          {BRIEF_TEMPLATE_LIST.map((t) => {
            const active = selected === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelected(t.id)}
                className={`w-full text-left rounded-lg border p-3 transition-colors ${
                  active ? "border-sky-500/60 bg-sky-500/10" : "border-border bg-secondary/40 hover:bg-secondary"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{t.label}</span>
                  {active && <Check className="h-4 w-4 text-sky-300 ml-auto" />}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
              </button>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleGenerate}>
            <FileDown className="h-4 w-4 mr-2" />Generate PDF
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
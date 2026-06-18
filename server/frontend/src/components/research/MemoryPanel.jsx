import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import { format } from "date-fns";
import { Brain, RefreshCw, Loader2, X } from "lucide-react";

// Displays the distilled "Important Information (Memory)" for a module session:
// a cleaned, organized summary of the transcript with the filler removed.
export default function MemoryPanel({ memory, distilling, onRegenerate, onClose, disabled }) {
  return (
    <Card className="border-blue-500/30 bg-blue-500/5">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 text-xs font-medium text-blue-200">
          <Brain className="h-3.5 w-3.5" />
          <span>Important Information (Memory)</span>
          {memory?.distilled_at && (
            <span className="text-muted-foreground font-normal">
              · {format(new Date(memory.distilled_at), "MMM d, HH:mm")}
              {typeof memory.message_count === "number" ? ` · ${memory.message_count} msgs` : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            disabled={distilling || disabled}
            className="h-7 text-xs"
          >
            {distilling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            {memory ? "Refresh" : "Distill"}
          </Button>
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7">
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
      <div className="px-4 py-3 max-h-64 overflow-y-auto">
        {distilling && !memory ? (
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Distilling transcript…
          </p>
        ) : memory?.content ? (
          <ReactMarkdown className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_a]:text-blue-300">
            {memory.content}
          </ReactMarkdown>
        ) : (
          <p className="text-sm text-muted-foreground">
            No memory yet. Distill the transcript to extract durable leads, entities, sources, and open questions.
          </p>
        )}
      </div>
    </Card>
  );
}
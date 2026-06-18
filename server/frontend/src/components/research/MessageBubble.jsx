import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { CheckCircle2, AlertCircle, Loader2, ChevronRight, Wrench } from "lucide-react";

// Compact tool-call display for an agent message (entity ops, file/Drive reads).
function ToolCall({ toolCall }) {
  const [open, setOpen] = useState(false);
  const name = (toolCall?.name || "tool").split(".").reverse().join(" ").toLowerCase();
  const status = toolCall?.status || "completed";
  const results = toolCall?.results;
  const running = status === "running" || status === "pending" || status === "in_progress";
  const failed = status === "failed" || status === "error" ||
    (typeof results === "string" && /error|failed/i.test(results));
  const Icon = running ? Loader2 : failed ? AlertCircle : CheckCircle2;

  const pretty = (val) => {
    if (val == null) return "";
    try { return JSON.stringify(typeof val === "string" ? JSON.parse(val) : val, null, 2); }
    catch { return String(val); }
  };

  return (
    <div className="mt-1.5 text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex items-center gap-2 px-2.5 py-1 rounded-md border transition-colors",
          open ? "bg-secondary border-border" : "bg-card border-border hover:bg-secondary/60"
        )}
      >
        <Wrench className="h-3 w-3 text-muted-foreground" />
        <span className="text-foreground/90">{name}</span>
        <Icon className={cn("h-3 w-3", running && "animate-spin text-blue-300", failed ? "text-red-300" : !running && "text-emerald-300")} />
        {(toolCall?.arguments_string || results) && !running && (
          <ChevronRight className={cn("h-3 w-3 text-muted-foreground transition-transform", open && "rotate-90")} />
        )}
      </button>
      {open && !running && (
        <div className="mt-1.5 ml-2 pl-3 border-l-2 border-border space-y-2">
          {toolCall?.arguments_string && (
            <div>
              <div className="text-muted-foreground mb-1">Parameters</div>
              <pre className="bg-secondary/50 rounded-md p-2 whitespace-pre-wrap text-foreground/80">{pretty(toolCall.arguments_string)}</pre>
            </div>
          )}
          {results && (
            <div>
              <div className="text-muted-foreground mb-1">Result</div>
              <pre className="bg-secondary/50 rounded-md p-2 whitespace-pre-wrap max-h-48 overflow-auto text-foreground/80">{pretty(results)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%]", isUser && "items-end")}>
        {message.content && (
          <div className={cn(
            "rounded-2xl px-4 py-2.5 text-sm",
            isUser ? "bg-secondary text-secondary-foreground" : "bg-card border border-border"
          )}>
            {isUser ? (
              <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
            ) : (
              <ReactMarkdown className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_a]:text-blue-300">
                {message.content}
              </ReactMarkdown>
            )}
          </div>
        )}
        {message.tool_calls?.length > 0 && (
          <div className="space-y-1">
            {message.tool_calls.map((tc, i) => <ToolCall key={i} toolCall={tc} />)}
          </div>
        )}
      </div>
    </div>
  );
}
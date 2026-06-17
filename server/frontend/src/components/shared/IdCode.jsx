import React from "react";
import { cn } from "@/lib/utils";

export default function IdCode({ children, className }) {
  if (!children) return <span className="text-muted-foreground">—</span>;
  return <span className={cn("font-mono-id text-xs text-foreground/90", className)}>{children}</span>;
}
import React from "react";
import { Lock } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import { INTEGRATION_STATUS } from "@/lib/chips";

export default function SyncBlockCard({ github }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-red-300">
          <Lock className="h-3.5 w-3.5" /> GitHub Sync Readiness
        </span>
        <StatusChip map={INTEGRATION_STATUS} value={github?.status || "Blocked"} />
      </div>
      <p className="text-sm text-foreground">
        {github?.blocking_reason || "GitHub sync remains blocked until thehub-pr transition parity gates pass."}
      </p>
      {github?.next_action && (
        <p className="text-xs text-muted-foreground mt-2">Next action: {github.next_action}</p>
      )}
    </div>
  );
}
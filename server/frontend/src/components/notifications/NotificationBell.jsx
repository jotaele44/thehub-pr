import React, { useState } from "react";
import { Bell, AlertTriangle } from "lucide-react";
import { useNotifications } from "@/hooks/useNotifications";

// Header notification center: a bell with a badge counting what's new since the
// user last looked (red when any are life-safety critical), and a dropdown listing
// the ranked digest. Opening it marks everything read (advances the cursor).
export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { count, criticalCount, items, markAllRead } = useNotifications();

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && count > 0) markAllRead();
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label={`Notifications: ${count} new`}
        className="relative inline-flex items-center justify-center h-9 w-9 rounded-md hover:bg-muted transition-colors"
      >
        <Bell className="h-5 w-5" />
        {count > 0 && (
          <span
            className={`absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-semibold text-white flex items-center justify-center ${
              criticalCount > 0 ? "bg-red-600" : "bg-blue-600"
            }`}
          >
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-80 max-h-[70vh] overflow-y-auto rounded-lg border bg-popover shadow-lg z-50">
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <span className="font-semibold text-sm">Notifications</span>
              <span className="text-xs text-muted-foreground">
                {count} new{criticalCount > 0 ? ` · ${criticalCount} critical` : ""}
              </span>
            </div>
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                You're all caught up.
              </div>
            ) : (
              <ul className="divide-y">
                {items.slice(0, 50).map((a, i) => (
                  <li key={a.record_id || a.id || i} className="px-4 py-3 flex gap-2">
                    {a.is_critical && (
                      <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
                    )}
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">
                        {a.module || "Alert"}
                        {a.severity != null && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            (sev {a.severity})
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {a.summary || a.alert_type || ""}
                      </div>
                      {a.occurred_at && (
                        <div className="text-[11px] text-muted-foreground mt-0.5">
                          {new Date(a.occurred_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

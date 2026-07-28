import React, { useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SECRET_PRESENCE } from "@/lib/chips";

// Credential controls that can set a value but never show one.
//
// There is no "reveal" affordance, and no masked preview either: a masked
// prefix or a character count is still a disclosure, and showing four dots
// where a 40-character key lives teaches an operator nothing except that
// something is stored -- which the presence chip already says.
export default function SecretPresencePanel({ presence = [], onSet, onDelete, busy = false }) {
  const [drafts, setDrafts] = useState({});

  if (!presence.length) {
    return (
      <p className="text-sm text-muted-foreground">
        This application declares no credentials for the operations in scope.
      </p>
    );
  }

  return (
    <ul className="space-y-3" data-testid="secret-panel">
      {presence.map((entry) => (
        <li key={entry.secret_id} className="rounded-lg border border-border p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <span className="text-sm font-mono flex items-center gap-1.5">
              <KeyRound className="h-3.5 w-3.5 text-muted-foreground" />
              {entry.secret_id}
            </span>
            <StatusChip map={SECRET_PRESENCE} value={entry.status} />
          </div>

          {entry.detail && <p className="text-xs text-muted-foreground mb-2">{entry.detail}</p>}

          <div className="flex items-center gap-2">
            <Input
              type="password"
              autoComplete="off"
              aria-label={`New value for ${entry.secret_id}`}
              placeholder={entry.status === "present" ? "Replace stored value…" : "Enter value…"}
              value={drafts[entry.secret_id] ?? ""}
              disabled={busy}
              onChange={(event) =>
                setDrafts((current) => ({ ...current, [entry.secret_id]: event.target.value }))
              }
            />
            <Button
              type="button"
              size="sm"
              disabled={busy || !drafts[entry.secret_id]}
              onClick={() => {
                onSet?.(entry.secret_id, drafts[entry.secret_id]);
                // Drop the draft immediately; there is no reason for a secret
                // to outlive the request in component state.
                setDrafts((current) => ({ ...current, [entry.secret_id]: "" }));
              }}
            >
              Store
            </Button>
            {entry.status === "present" && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                aria-label={`Remove ${entry.secret_id}`}
                onClick={() => onDelete?.(entry.secret_id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>

          <p className="text-[11px] text-muted-foreground mt-1.5">
            Stored in the operating system credential store. The value is never sent back to this
            page, written to a log, or recorded in a receipt.
          </p>
        </li>
      ))}
    </ul>
  );
}

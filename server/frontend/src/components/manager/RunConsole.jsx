import React from "react";
import { CircleStop, ScrollText, ShieldCheck } from "lucide-react";
import StatusChip from "@/components/shared/StatusChip";
import { Button } from "@/components/ui/button";
import { RUN_STATUS } from "@/lib/chips";

// Plan preview, streamed log, and receipt for a single run.
//
// The plan is shown as an argv *list*, not a joined command line. That is not
// cosmetic: argv is what actually runs, and rendering it space-joined would
// invite an operator to copy it into a terminal, where the quoting rules are
// different and a filename containing a space would silently become two
// arguments.
export default function RunConsole({ plan, run, lines = [], receipt, onCancel, onClose }) {
  return (
    <div className="space-y-4" data-testid="run-console">
      {plan && !run && (
        <section aria-labelledby="plan-heading" className="rounded-lg border border-border p-3">
          <h4 id="plan-heading" className="text-sm font-medium mb-2">
            Dry run — nothing has been executed
          </h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3">
            <dt className="text-muted-foreground">Write scope</dt>
            <dd>{plan.writeScope}</dd>
            <dt className="text-muted-foreground">Network</dt>
            <dd>{plan.networkPolicy}</dd>
            <dt className="text-muted-foreground">Rollback</dt>
            <dd>{plan.rollbackStrategy}</dd>
            {plan.expectedOutputs?.length > 0 && (
              <>
                <dt className="text-muted-foreground">Expected outputs</dt>
                <dd>{plan.expectedOutputs.join(", ")}</dd>
              </>
            )}
          </dl>

          <p className="text-xs text-muted-foreground mb-1">Arguments, in order:</p>
          <ol className="text-xs font-mono bg-secondary rounded-md p-2 space-y-0.5 overflow-x-auto">
            {plan.argvPreview.map((token, index) => (
              <li key={`${token}-${index}`} className="whitespace-pre">
                <span className="text-muted-foreground mr-2">{String(index).padStart(2, "0")}</span>
                {token}
              </li>
            ))}
          </ol>

          {plan.missingSecrets?.length > 0 && (
            <p className="text-xs text-status-warning-fg mt-2">
              Missing credentials: {plan.missingSecrets.join(", ")}
            </p>
          )}
          {plan.warnings?.map((warning) => (
            <p key={warning} className="text-xs text-status-warning-fg mt-2">
              {warning}
            </p>
          ))}
        </section>
      )}

      {run && (
        <section aria-labelledby="log-heading" className="rounded-lg border border-border p-3">
          <div className="flex items-center justify-between mb-2">
            <h4 id="log-heading" className="text-sm font-medium flex items-center gap-1.5">
              <ScrollText className="h-4 w-4" />
              Output
            </h4>
            <div className="flex items-center gap-2">
              <StatusChip map={RUN_STATUS} value={run.status} />
              {run.status === "running" && (
                <Button type="button" variant="outline" size="sm" onClick={onCancel}>
                  <CircleStop className="h-3.5 w-3.5 mr-1.5" />
                  Cancel
                </Button>
              )}
            </div>
          </div>
          <pre
            className="text-xs font-mono bg-secondary rounded-md p-2 max-h-64 overflow-auto whitespace-pre-wrap"
            role="log"
            aria-live="polite"
            aria-label="Operation output"
          >
            {lines.length ? lines.join("") : "Waiting for output…"}
          </pre>
          <p className="text-[11px] text-muted-foreground mt-1">
            Credential values are removed before this output is streamed, stored, or hashed.
          </p>
        </section>
      )}

      {receipt && (
        <section aria-labelledby="receipt-heading" className="rounded-lg border border-border p-3">
          <h4 id="receipt-heading" className="text-sm font-medium flex items-center gap-1.5 mb-2">
            <ShieldCheck className="h-4 w-4" />
            Signed receipt
          </h4>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Run</dt>
            <dd className="font-mono truncate">{receipt.receipt.run_id}</dd>
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <StatusChip map={RUN_STATUS} value={receipt.receipt.status} />
            </dd>
            <dt className="text-muted-foreground">Exit code</dt>
            <dd>{String(receipt.receipt.exit_code)}</dd>
            <dt className="text-muted-foreground">Transaction</dt>
            <dd>
              {receipt.receipt.transaction.phase_reached} · rollback{" "}
              {receipt.receipt.transaction.rollback_state}
            </dd>
            <dt className="text-muted-foreground">Log digest</dt>
            <dd className="font-mono truncate">{receipt.receipt.log.sha256.slice(0, 16)}…</dd>
            <dt className="text-muted-foreground">Signature</dt>
            <dd className="font-mono truncate">
              {receipt.signature.algorithm} · {receipt.signature.payload_sha256.slice(0, 16)}…
            </dd>
          </dl>

          {receipt.receipt.validators?.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs">
              {receipt.receipt.validators.map((validator) => (
                <li key={validator.name} className="flex items-center gap-2">
                  <span
                    className={
                      validator.status === "passed"
                        ? "text-status-success-fg"
                        : "text-status-danger-fg"
                    }
                  >
                    {validator.status === "passed" ? "✓" : "✕"}
                  </span>
                  <span className="text-muted-foreground">{validator.name}</span>
                  {validator.detail && <span>{validator.detail}</span>}
                </li>
              ))}
            </ul>
          )}

          {receipt.receipt.transaction.unexpected_writes?.length > 0 && (
            <p className="text-xs text-status-danger-fg mt-2">
              Quarantined: wrote outside its declared scope —{" "}
              {receipt.receipt.transaction.unexpected_writes.join(", ")}
            </p>
          )}
          {receipt.receipt.transaction.rollback_state === "failed" && (
            <p className="text-xs text-status-danger-fg mt-2">
              Rollback failed: {receipt.receipt.transaction.rollback_detail}. Do not re-run until
              this is resolved by hand.
            </p>
          )}

          {onClose && (
            <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={onClose}>
              Dismiss
            </Button>
          )}
        </section>
      )}
    </div>
  );
}

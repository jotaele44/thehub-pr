import React from "react";
import { Button } from "@/components/ui/button";

const ACTIONS = [
  ["fetch", "Fetch"],
  ["export", "Export"],
  ["audit", "Audit"],
  ["repair", "Repair"],
];

function stateLabel(state) {
  switch (state) {
    case "ACTIVE_ARTIFACT":
      return "ACTIVE";
    case "CONNECTED_NO_ACTIVE_ARTIFACT":
      return "CONNECTED · NO ACTIVE ARTIFACT";
    case "ARTIFACT_ERROR":
      return "ARTIFACT ERROR";
    case "UNAVAILABLE":
      return "UNAVAILABLE";
    default:
      return state || "UNKNOWN";
  }
}

export default function RepositoryDataHealthPanel({ repositories = [], operations = [], onSelect }) {
  const byId = new Map(operations.map((operation) => [operation.operationId, operation]));

  if (!repositories.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No verified repository health records are available from the native manager.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {repositories.map((repo) => (
        <div key={repo.repo} className="rounded-lg border border-border p-3 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-mono text-sm truncate">{repo.repo}</p>
              <p className="text-xs text-muted-foreground truncate">
                {repo.repositoryFullName || repo.bindingError || "repository identity unavailable"}
              </p>
            </div>
            <span className="text-[11px] font-medium text-muted-foreground whitespace-nowrap">
              {stateLabel(repo.state)}
            </span>
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              Operations: {repo.enabledOperations}/{repo.declaredOperations} enabled
            </p>
            {repo.activeArtifact ? (
              <p className="font-mono truncate">
                ACTIVE {repo.activeArtifact.artifact_id} · {repo.activeArtifact.sha256?.slice(0, 12)}…
              </p>
            ) : (
              <p>ACTIVE artifact: none registered</p>
            )}
            {repo.lastReceipt && (
              <p className="truncate">
                Last run: {repo.lastReceipt.operationId} · {repo.lastReceipt.status}
              </p>
            )}
          </div>

          {(repo.bindingError || repo.artifactError) && (
            <p className="text-xs text-status-warning-fg">
              {repo.bindingError || repo.artifactError}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {ACTIONS.map(([key, label]) => {
              const operationId = repo.quickActions?.[key];
              const operation = operationId ? byId.get(operationId) : null;
              const disabled = !operation || !operation.enabled;
              const reason = !operation
                ? `No ${label.toLowerCase()} operation is declared for this repository.`
                : operation.enablementReason || "Operation is policy-disabled.";
              return (
                <Button
                  key={key}
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  title={disabled ? reason : operation.operationId}
                  onClick={() => operation && !disabled && onSelect(operation)}
                >
                  {label}
                </Button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

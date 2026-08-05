import React from "react";
import { CircleAlert, CircleCheck, CircleDashed } from "lucide-react";

// Machine-detected prerequisites with an actionable remediation for each.
//
// Every unmet item carries a specific next step rather than a bare red mark.
// "Python 3.10 or newer is required" tells an operator nothing they can act on;
// naming what was found and what to do about it does.
const ICONS = {
  met: CircleCheck,
  unmet: CircleAlert,
  unknown: CircleDashed,
};

const TONE = {
  met: "text-status-success-fg",
  unmet: "text-status-warning-fg",
  unknown: "text-muted-foreground",
};

export default function PrerequisitePanel({ prerequisites = [] }) {
  if (!prerequisites.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No prerequisites have been evaluated for this application yet.
      </p>
    );
  }

  const unmet = prerequisites.filter((item) => item.status === "unmet");

  return (
    <div className="space-y-2" data-testid="prerequisite-panel">
      {unmet.length > 0 && (
        <p className="text-xs text-status-warning-fg">
          {unmet.length} prerequisite{unmet.length === 1 ? "" : "s"} unmet. Operations that depend on
          them stay disabled until they are resolved.
        </p>
      )}
      <ul className="space-y-1.5">
        {prerequisites.map((item) => {
          const Icon = ICONS[item.status] || CircleDashed;
          return (
            <li
              key={item.name}
              className="flex items-start gap-2 text-sm"
              data-prerequisite={item.name}
              data-status={item.status}
            >
              <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${TONE[item.status] || ""}`} />
              <div className="min-w-0">
                <p>{item.name}</p>
                {item.detail && <p className="text-xs text-muted-foreground">{item.detail}</p>}
                {item.status !== "met" && item.remediation && (
                  <p className="text-xs text-status-warning-fg mt-0.5">{item.remediation}</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

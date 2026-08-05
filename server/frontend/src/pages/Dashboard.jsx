import React from "react";
import { useEntityData } from "@/hooks/useEntityData";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import ModuleGrid from "@/components/dashboard/ModuleGrid";
import TaskRollup from "@/components/dashboard/TaskRollup";
import ProgramTaskChart from "@/components/dashboard/ProgramTaskChart";
import VerificationGatePanel from "@/components/dashboard/VerificationGatePanel";
import ConfidenceTrendChart from "@/components/dashboard/ConfidenceTrendChart";
import CaseEvidenceTimeline from "@/components/dashboard/CaseEvidenceTimeline";
import ImmediateReviewQueue from "@/components/dashboard/ImmediateReviewQueue";
import GovernanceAlertsPanel from "@/components/dashboard/GovernanceAlertsPanel";
import RiskHeatmap from "@/components/dashboard/RiskHeatmap";
import StatusChip from "@/components/shared/StatusChip";
import { GATE_STATUS } from "@/lib/chips";
import { isTaskOpen } from "@/lib/task-utils";
import { LayoutDashboard, FileStack, BookOpen, ListChecks, ShieldCheck, GitBranch, Lock } from "lucide-react";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const { rows: programs } = useEntityData("Programs");
  const { rows: cases } = useEntityData("UnifiedCases");
  const { rows: sources } = useEntityData("UnifiedSources");
  const { rows: tasks } = useEntityData("FederationTasks");
  const { rows: gates } = useEntityData("ValidationGates");

  const openTasks = tasks.filter((t) => isTaskOpen(t.status)).length;
  const passedGates = gates.filter((g) => g.status === "Passed").length;
  const blockingOpen = gates.filter((g) => g.blocking && g.status !== "Passed").length;
  const syncReady = programs.filter((p) => p.github_sync_status === "Ready" || p.github_sync_status === "Connected").length;

  return (
    <div>
      <PageHeader
        icon={LayoutDashboard}
        title="Command Dashboard"
        description="Federation control plane for the Puerto Rico research modules. Sanitized analytical metadata only — GitHub sync remains gated until validation passes."
      />

      <div className="mb-6">
        <ConfidenceTrendChart />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Unified Cases" value={cases.length} icon={FileStack} />
        <StatCard label="Sources" value={sources.length} icon={BookOpen} />
        <StatCard label="Open Tasks" value={openTasks} icon={ListChecks} />
        <StatCard label="Gates Passed" value={`${passedGates}/${gates.length || 0}`} icon={ShieldCheck} accent="text-status-success-fg" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center gap-2 mb-1">
            <Lock className="h-4 w-4 text-status-warning-fg" />
            <h3 className="text-sm font-semibold">GitHub-Readiness</h3>
          </div>
          <p className="text-xs text-muted-foreground mb-4">Repository sync stays blocked until all blocking validation gates pass for a program.</p>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-2xl font-semibold font-mono-id text-foreground">{blockingOpen}</div>
              <div className="text-xs text-muted-foreground">Blocking gates open</div>
            </div>
            <div>
              <div className="text-2xl font-semibold font-mono-id text-foreground">{syncReady}</div>
              <div className="text-xs text-muted-foreground">Programs sync-ready</div>
            </div>
            <Link to="/gates" className="ml-auto text-xs text-status-info-fg hover:underline flex items-center gap-1">
              <GitBranch className="h-3.5 w-3.5" /> Review gates
            </Link>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold mb-3">Recent Gates</h3>
          <div className="space-y-2">
            {gates.slice(0, 4).map((g) => (
              <div key={g.id} className="flex items-center justify-between text-xs">
                <span className="truncate text-muted-foreground mr-2">{g.gate_name}</span>
                <StatusChip map={GATE_STATUS} value={g.status} />
              </div>
            ))}
            {!gates.length && <p className="text-xs text-muted-foreground">No gates defined yet.</p>}
          </div>
        </div>
      </div>

      <div className="mb-8">
        <ImmediateReviewQueue />
      </div>

      <div className="mb-8">
        <GovernanceAlertsPanel />
      </div>

      <div className="mb-8">
        <RiskHeatmap />
      </div>

      <VerificationGatePanel />

      <h2 className="text-sm font-semibold text-foreground mb-3 uppercase tracking-wide">Case Evidence Timeline</h2>
      <div className="mb-8">
        <CaseEvidenceTimeline />
      </div>

      <h2 className="text-sm font-semibold text-foreground mb-3 uppercase tracking-wide">Task Control Plane</h2>
      <div className="mb-6">
        <ProgramTaskChart />
      </div>
      <div className="mb-8">
        <TaskRollup />
      </div>

      <h2 className="text-sm font-semibold text-foreground mb-3 uppercase tracking-wide">Federation Modules</h2>
      <ModuleGrid programs={programs} />
    </div>
  );
}
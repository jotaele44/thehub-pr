import React from "react";
import { useQuery } from "@tanstack/react-query";
import { federation } from "@/api/federationClient";
import { GitCompareArrows, FileStack, BookOpen, ListChecks, Network, Share2 } from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import LineageBanner from "@/components/audit/LineageBanner";
import ModuleParityList from "@/components/audit/ModuleParityList";
import GateChecklist from "@/components/audit/GateChecklist";
import EvidenceStandardsCard from "@/components/audit/EvidenceStandardsCard";
import SyncBlockCard from "@/components/audit/SyncBlockCard";

const useList = (name, sort) =>
  useQuery({ queryKey: [name], queryFn: () => federation.entities[name].list(sort), initialData: [] });

export default function TransitionAudit() {
  const { data: programs } = useList("Programs");
  const { data: gates } = useList("ValidationGates");
  const { data: standards } = useList("EvidenceStandards");
  const { data: integrations } = useList("IntegrationStatus");
  const { data: cases } = useList("UnifiedCases");
  const { data: sources } = useList("UnifiedSources");
  const { data: tasks } = useList("FederationTasks");
  const { data: nodes } = useList("GraphNodes");
  const { data: edges } = useList("GraphEdges");

  const control = programs.find((p) => p.program_id === "prog-control");
  const controlGates = gates.filter((g) => g.program_id === "prog-control");
  const github = integrations.find((i) => i.integration_name === "GitHub" && i.program_id === "prog-control");

  return (
    <div className="p-5 lg:p-8 max-w-[100rem] mx-auto">
      <PageHeader
        title="Transition Audit"
        description="Confirms whether INTSYS-PR faithfully preserves, upgrades, and operationalizes the thehub-pr research ecosystem."
        icon={GitCompareArrows}
      />

      <div className="space-y-5">
        <LineageBanner program={control} />

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <StatCard label="Cases" value={cases.length} icon={FileStack} />
          <StatCard label="Sources" value={sources.length} icon={BookOpen} />
          <StatCard label="Tasks" value={tasks.length} icon={ListChecks} />
          <StatCard label="Graph Nodes" value={nodes.length} icon={Network} />
          <StatCard label="Graph Edges" value={edges.length} icon={Share2} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ModuleParityList />
          <GateChecklist gates={controlGates} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <EvidenceStandardsCard standards={standards} />
          <SyncBlockCard github={github} />
        </div>
      </div>
    </div>
  );
}
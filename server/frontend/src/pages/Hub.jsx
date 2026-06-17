import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Dashboard from "@/pages/Dashboard";
import FederationCrossoverWorkspace from "@/pages/FederationCrossoverWorkspace";
import AnomalyOverlap from "@/pages/AnomalyOverlap";
import TransitionAudit from "@/pages/TransitionAudit";
import ResearchAssistant from "@/pages/ResearchAssistant";
import ControlLedgers from "@/pages/ControlLedgers";

const TABS = [
  { value: "dashboard", label: "Command Dashboard", Component: Dashboard },
  { value: "crossover", label: "Crossover Workspace", Component: FederationCrossoverWorkspace },
  { value: "anomaly-overlap", label: "Anomaly Overlap", Component: AnomalyOverlap },
  { value: "transition", label: "Transition Audit", Component: TransitionAudit },
  { value: "research", label: "Research Assistant", Component: ResearchAssistant },
  { value: "control", label: "Control Ledgers", Component: ControlLedgers },
];

export default function Hub() {
  const navigate = useNavigate();
  const { search } = useLocation();
  const tabParam = new URLSearchParams(search).get("tab");
  const active = TABS.some((t) => t.value === tabParam) ? tabParam : "dashboard";
  const Active = TABS.find((t) => t.value === active).Component;

  return (
    <div>
      <Tabs value={active} onValueChange={(v) => navigate(`/hub?tab=${v}`)} className="mb-6">
        <TabsList className="flex-wrap h-auto justify-start">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Active embedded />
    </div>
  );
}
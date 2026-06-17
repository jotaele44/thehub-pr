import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import PageHeader from "@/components/shared/PageHeader";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Boxes } from "lucide-react";
import Programs from "@/pages/Programs";
import Cases from "@/pages/Cases";
import Sources from "@/pages/Sources";
import Dictionary from "@/pages/Dictionary";
import Tasks from "@/pages/Tasks";
import Gates from "@/pages/Gates";
import Integrations from "@/pages/Integrations";
import ExportsPage from "@/pages/Exports";
import ModuleReadiness from "@/pages/ModuleReadiness";
import Manifest from "@/pages/Manifest";

const TABS = [
  { value: "programs", label: "Programs", Component: Programs },
  { value: "cases", label: "Unified Cases", Component: Cases },
  { value: "sources", label: "Unified Sources", Component: Sources },
  { value: "dictionary", label: "Dictionary", Component: Dictionary },
  { value: "tasks", label: "Federation Tasks", Component: Tasks },
  { value: "gates", label: "Validation Gates", Component: Gates },
  { value: "integrations", label: "Integrations", Component: Integrations },
  { value: "exports", label: "Exports", Component: ExportsPage },
  { value: "readiness", label: "Module Readiness", Component: ModuleReadiness },
  { value: "manifest", label: "Manifest", Component: Manifest },
];

export default function ControlLedgers({ embedded = false }) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const tabParam = new URLSearchParams(search).get("tab");
  const initial = TABS.some((t) => t.value === tabParam) ? tabParam : "programs";
  // When embedded inside the Hub shell, keep tab state internal so sub-tab
  // navigation never escapes to /control. Standalone keeps URL-synced tabs.
  const [embeddedTab, setEmbeddedTab] = useState(initial);
  const active = embedded ? embeddedTab : initial;
  const Active = TABS.find((t) => t.value === active).Component;

  const onTabChange = (v) => {
    if (embedded) setEmbeddedTab(v);
    else navigate(`/control?tab=${v}`);
  };

  return (
    <div>
      {!embedded && (
        <PageHeader
          icon={Boxes}
          title="Control Ledgers"
          description="Parent control-plane ledgers and federation governance surfaces."
        />
      )}
      <Tabs value={active} onValueChange={onTabChange} className="mb-6">
        <TabsList className="flex-wrap h-auto justify-start">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Active />
    </div>
  );
}
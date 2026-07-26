import React, { useEffect, useState } from "react";
import { Boxes, ChevronDown, ChevronUp, LockKeyhole } from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const APP_CENTER_APPS = [
  { appId: "thehub", name: "TheHub", profile: "Core", lifecycle: "Ready" },
  { appId: "ovnis", name: "OVNIS", profile: "One-click", lifecycle: "Available" },
  { appId: "centinelas", name: "Centinelas", profile: "Guided", lifecycle: "Available" },
  { appId: "skywatcher", name: "Skywatcher", profile: "Guided", lifecycle: "Available" },
  { appId: "aguayluz", name: "AguaYLuz", profile: "Guided", lifecycle: "Available" },
  { appId: "spiderweb", name: "Spiderweb", profile: "One-click Basic", lifecycle: "Available" },
  { appId: "moneysweep", name: "MoneySweep", profile: "Multistage", lifecycle: "Available" },
];

const DIMENSIONS = ["Install", "Configuration", "Data", "Federation", "Production"];

function AppTile({ app }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card data-app-id={app.appId} aria-label={`${app.name} application`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 rounded-xl border bg-muted flex items-center justify-center font-semibold"
              aria-hidden="true"
            >
              {app.name.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <CardTitle className="text-base">{app.name}</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">{app.profile} profile</p>
            </div>
          </div>
          <span className="text-xs rounded-md border px-2 py-1">{app.lifecycle}</span>
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
          {DIMENSIONS.map((dimension) => (
            <div key={dimension} className="rounded-md bg-muted/60 p-2">
              <dt className="text-muted-foreground">{dimension}</dt>
              <dd className="font-medium mt-1">
                {app.appId === "thehub" && dimension !== "Production" ? "Ready" : "Not assessed"}
              </dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2 mt-4">
          <Button disabled aria-disabled="true">
            {app.appId === "thehub" ? "Open" : "Install"}
          </Button>
          <Button disabled variant="outline" aria-disabled="true">Validate</Button>
          <Button
            variant="ghost"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            Technical details
            {expanded ? <ChevronUp className="h-4 w-4 ml-2" /> : <ChevronDown className="h-4 w-4 ml-2" />}
          </Button>
        </div>
        {expanded && (
          <div className="mt-3 rounded-md border p-3 text-xs" role="region" aria-label={`${app.name} technical details`}>
            <p>Application ID: <code>{app.appId}</code></p>
            <p className="mt-1">Lifecycle actions are unavailable in the Phase 1 read-only foundation.</p>
            <p className="mt-1 flex items-center gap-1"><LockKeyhole className="h-3 w-3" /> Secret values are never exposed.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AppCenter() {
  const [apps, setApps] = useState(APP_CENTER_APPS);

  useEffect(() => {
    // Native sessions are intentionally unavailable in ordinary browser mode.
    // When the native manager supplies a session, a later phase will hydrate
    // this read-only view from /api/federation-manager/apps.
    setApps(APP_CENTER_APPS);
  }, []);

  return (
    <div>
      <PageHeader
        icon={Boxes}
        title="App Center"
        description="Read-only foundation for the seven federation applications. Installation and lifecycle actions are not enabled in this phase."
        actions={<Button disabled aria-disabled="true">Install all recommended</Button>}
      />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {apps.map((app) => <AppTile key={app.appId} app={app} />)}
      </div>
    </div>
  );
}

import React, { useEffect, useState } from "react";
import {
  Banknote,
  Boxes,
  ChevronDown,
  ChevronUp,
  Droplets,
  Hexagon,
  LockKeyhole,
  Network,
  Plane,
  Radar,
  Radio,
} from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const APP_CENTER_APPS = [
  { appId: "thehub", name: "TheHub", profile: "Core", lifecycle: "Ready", readiness: {} },
  { appId: "ovnis", name: "OVNIS", profile: "One-click", lifecycle: "Available", readiness: {} },
  { appId: "centinelas", name: "Centinelas", profile: "Guided", lifecycle: "Available", readiness: {} },
  { appId: "skywatcher", name: "Skywatcher", profile: "Guided", lifecycle: "Available", readiness: {} },
  { appId: "aguayluz", name: "AguaYLuz", profile: "Guided", lifecycle: "Available", readiness: {} },
  { appId: "spiderweb", name: "Spiderweb", profile: "One-click Basic", lifecycle: "Available", readiness: {} },
  { appId: "moneysweep", name: "MoneySweep", profile: "Multistage", lifecycle: "Available", readiness: {} },
];

const DIMENSIONS = ["Install", "Configuration", "Data", "Federation", "Production"];
const ICONS = {
  thehub: Hexagon,
  ovnis: Radar,
  centinelas: Radio,
  skywatcher: Plane,
  aguayluz: Droplets,
  spiderweb: Network,
  moneysweep: Banknote,
};

export class ManagerUnavailableError extends Error {}

function titleCase(value) {
  return String(value || "not_assessed")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export async function loadAppInventory({
  fetchImpl = globalThis.fetch,
  storage = globalThis.sessionStorage,
} = {}) {
  const token = storage?.getItem("prii.manager.session");
  if (!token) throw new ManagerUnavailableError("Native manager session is unavailable.");
  const response = await fetchImpl("/api/federation-manager/apps", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ManagerUnavailableError("Native manager inventory is unavailable.");
  const inventory = await response.json();
  if (!Array.isArray(inventory) || inventory.length !== APP_CENTER_APPS.length) {
    throw new ManagerUnavailableError("Native manager returned an invalid inventory.");
  }
  const expected = new Set(APP_CENTER_APPS.map((app) => app.appId));
  if (new Set(inventory.map((app) => app.appId)).size !== expected.size
      || inventory.some((app) => !expected.has(app.appId))) {
    throw new ManagerUnavailableError("Native manager returned an invalid app identity.");
  }
  return inventory.map((app) => ({
    appId: app.appId,
    name: app.displayName,
    profile: titleCase(app.profile),
    lifecycle: titleCase(app.lifecycle),
    readiness: app.readiness,
  }));
}

function AppTile({ app }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICONS[app.appId];
  return (
    <Card data-app-id={app.appId} aria-label={`${app.name} application`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 rounded-xl border bg-muted flex items-center justify-center font-semibold"
              role="img"
              aria-label={`${app.name} icon`}
              data-native-icon={app.appId}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
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
                {app.readiness[dimension.toLowerCase()]
                  ? titleCase(app.readiness[dimension.toLowerCase()])
                  : app.appId === "thehub" && dimension !== "Production" ? "Ready" : "Not assessed"}
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

export default function AppCenter({ inventoryLoader = loadAppInventory }) {
  const [apps, setApps] = useState(APP_CENTER_APPS);
  const [managerState, setManagerState] = useState("loading");

  useEffect(() => {
    let active = true;
    inventoryLoader()
      .then((inventory) => {
        if (active) {
          setApps(inventory);
          setManagerState("connected");
        }
      })
      .catch(() => {
        if (active) setManagerState("unavailable");
      });
    return () => {
      active = false;
    };
  }, [inventoryLoader]);

  return (
    <div>
      <PageHeader
        icon={Boxes}
        title="App Center"
        description="Read-only foundation for the seven federation applications. Installation and lifecycle actions are not enabled in this phase."
        actions={<Button disabled aria-disabled="true">Install all recommended</Button>}
      />
      <p className="mb-4 text-sm text-muted-foreground" role="status">
        {managerState === "connected"
          ? "Native manager inventory connected (read-only)."
          : managerState === "unavailable"
            ? "Native manager unavailable. Showing the safe read-only catalog."
            : "Checking native manager inventory…"}
      </p>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {apps.map((app) => <AppTile key={app.appId} app={app} />)}
      </div>
    </div>
  );
}

import React from "react";
import {
  AlertTriangle,
  Boxes,
  GitBranch,
  LockKeyhole,
  Plane,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MODULES, HUB_REPO, programIconUrl } from "@/lib/federation";
import readiness from "@/data/iosStartReadiness.json";

const STATUS_CLASS = {
  PASS: "border-status-success/30 bg-status-success/10 text-status-success-fg",
  OPEN: "border-status-info/30 bg-status-info/10 text-status-info-fg",
  BLOCKED: "border-status-danger/30 bg-status-danger/10 text-status-danger-fg",
  PROVISIONAL: "border-status-warning/30 bg-status-warning/10 text-status-warning-fg",
  UNRESOLVED: "border-status-neutral/30 bg-status-neutral/10 text-status-neutral-fg",
};

const IOS_CLASS = {
  READY_FOR_FIRST_SURFACE: "border-status-info/30 bg-status-info/10 text-status-info-fg",
  FIRST_SURFACE_STARTED: "border-status-success/30 bg-status-success/10 text-status-success-fg",
  BLOCKED_BY_DESKTOP_GAP: "border-status-danger/30 bg-status-danger/10 text-status-danger-fg",
  PROVISIONAL_DESKTOP_BASE: "border-status-warning/30 bg-status-warning/10 text-status-warning-fg",
  UNRESOLVED: "border-status-neutral/30 bg-status-neutral/10 text-status-neutral-fg",
};

const APP_META = new Map([
  [HUB_REPO, { domain: "ControlPlane", icon: programIconUrl(HUB_REPO) }],
  ...MODULES.map((module) => [
    module.repo_name,
    { domain: module.domain, icon: programIconUrl(module.repo_name) },
  ]),
]);

function classFor(map, value) {
  return map[value] || "border-border bg-secondary text-muted-foreground";
}

function shortSha(value) {
  return value ? value.slice(0, 12) : "unverified";
}

function label(value) {
  return String(value || "UNRESOLVED").replaceAll("_", " ");
}

function Pill({ value, map }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-[11px] font-medium ${classFor(map, value)}`}>
      {label(value)}
    </span>
  );
}

function ArithmeticPanel() {
  const counts = readiness.blocker_arithmetic;
  const classified =
    counts.PASS + counts.OPEN + counts.BLOCKED + counts.PROVISIONAL + counts.UNRESOLVED;
  const closes = classified === counts.total && readiness.records.length === counts.total;
  return (
    <section className="grid grid-cols-2 gap-3 md:grid-cols-6" aria-label="Certification arithmetic">
      {["PASS", "OPEN", "BLOCKED", "PROVISIONAL", "UNRESOLVED"].map((key) => (
        <div key={key} className="rounded-lg border border-border bg-card p-3">
          <p className="text-[11px] font-medium uppercase text-muted-foreground">{key}</p>
          <p className="mt-1 text-2xl font-semibold">{counts[key]}</p>
        </div>
      ))}
      <div className={`rounded-lg border p-3 ${closes ? "border-status-success/30 bg-status-success/10" : "border-status-danger/30 bg-status-danger/10"}`}>
        <p className="text-[11px] font-medium uppercase text-muted-foreground">Arithmetic</p>
        <p className="mt-1 text-2xl font-semibold">{classified}={counts.total}</p>
      </div>
    </section>
  );
}

function AppReadinessCard({ record }) {
  const meta = APP_META.get(record.repo_id);
  const hasRemoteDrift = record.observed_remote_main_sha
    && record.observed_remote_main_sha !== record.desktop_main_sha;
  return (
    <Card data-repo-id={record.repo_id} aria-label={`${record.app_name} iOS readiness`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src={meta?.icon || programIconUrl(record.repo_id)}
              alt=""
              className="h-10 w-10 shrink-0 rounded-lg border border-border bg-muted p-1"
            />
            <div className="min-w-0">
              <CardTitle className="truncate text-base">{record.app_name}</CardTitle>
              <p className="mt-1 truncate text-xs text-muted-foreground">{record.repo_id}</p>
            </div>
          </div>
          <Pill value={record.desktop_certification_state} map={STATUS_CLASS} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
          <div className="rounded-md bg-muted/60 p-2">
            <p className="text-muted-foreground">Desktop SHA</p>
            <p className="mt-1 font-mono">{shortSha(record.desktop_main_sha)}</p>
          </div>
          <div className="rounded-md bg-muted/60 p-2">
            <p className="text-muted-foreground">iOS State</p>
            <p className="mt-1"><Pill value={record.ios_start_state} map={IOS_CLASS} /></p>
          </div>
        </div>

        {hasRemoteDrift && (
          <div className="rounded-md border border-status-warning/30 bg-status-warning/10 p-3 text-xs text-status-warning-fg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Remote main drift observed: <span className="font-mono">{shortSha(record.observed_remote_main_sha)}</span>.
                Recertification must refresh this producer before mobile consumes it as current.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Receipts</p>
          <div className="flex flex-wrap gap-2">
            {record.canonical_receipts.map((receipt) => (
              <span key={receipt} className="rounded-md border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
                {receipt}
              </span>
            ))}
          </div>
        </div>

        {record.noncanonical_references.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">ZIP references</p>
            <div className="flex flex-wrap gap-2">
              {record.noncanonical_references.map((reference) => (
                <span key={reference.path} className="rounded-md border border-status-neutral/30 bg-status-neutral/10 px-2 py-1 text-[11px] text-status-neutral-fg">
                  {reference.state}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="text-sm text-muted-foreground">{record.notes}</p>
      </CardContent>
    </Card>
  );
}

export default function IosStart() {
  return (
    <div className="p-4 sm:p-5 lg:p-8 max-w-[100rem] mx-auto">
      <PageHeader
        icon={Smartphone}
        title="iOS Start"
        badge={readiness.baseline.state}
        description="Read-only mobile start surface for the bounded desktop federation state. ZIP archives are reference material only."
      />

      <div className="space-y-5">
        <section className="rounded-lg border border-border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="flex items-start gap-3">
              <GitBranch className="mt-0.5 h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs font-medium uppercase text-muted-foreground">Branch</p>
                <p className="mt-1 font-mono text-sm">{readiness.baseline.branch}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs font-medium uppercase text-muted-foreground">TheHub base</p>
                <p className="mt-1 font-mono text-sm">{shortSha(readiness.baseline.thehub_start_sha)}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Boxes className="mt-0.5 h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs font-medium uppercase text-muted-foreground">ZIP policy</p>
                <p className="mt-1 text-sm">{readiness.baseline.zip_policy}</p>
              </div>
            </div>
          </div>
        </section>

        <ArithmeticPanel />

        <section className="rounded-lg border border-status-warning/30 bg-status-warning/10 p-4 text-sm text-status-warning-fg">
          <div className="flex items-start gap-3">
            <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Bounded certification guard</p>
              <p className="mt-1">
                This is a provisional desktop baseline. A remote SHA drift was detected after the previous all-main
                pickup, and Lumen semantic search is recorded as unavailable for this run.
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-status-info/30 bg-status-info/10 p-4 text-sm text-status-info-fg">
          <div className="flex items-start gap-3">
            <Plane className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Skywatcher mobile semantics</p>
              <p className="mt-1">
                FR24 screenshot observations remain ICON_DERIVED_APPROX, APPROXIMATE, SCREENSHOT_BBOX_DERIVED,
                and REVIEW_BOUND_IDENTITY. They are not exact aircraft coordinates.
              </p>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-2" aria-label="Seven app iOS readiness">
          {readiness.records.map((record) => (
            <AppReadinessCard key={record.repo_id} record={record} />
          ))}
        </section>
      </div>
    </div>
  );
}

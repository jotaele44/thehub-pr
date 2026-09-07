import React, { useCallback, useEffect, useMemo, useState } from "react";
import { federation } from "@/api/federationClient";
import PageHeader from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Bell, CheckCircle2, FileUp, Loader2, PlugZap, RefreshCw, Settings, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export const OPERATOR_CONNECTORS = [
  { name: "Federation", label: "Federation" },
  { name: "GitHub", label: "GitHub" },
  { name: "CSVExport", label: "CSV export" },
  { name: "GeoJSONExport", label: "GeoJSON export" },
  { name: "GoogleDrive", label: "Google Drive" },
  { name: "ManualImport", label: "Manual import" },
];

const fallbackPreference = { channels: [], timing: "asap" };
const normalizePreference = (value) => ({
  channels: Array.isArray(value?.channels) ? value.channels : [],
  timing: value?.timing || "asap",
});
const channelLabel = (channel) => channel === "sms" ? "SMS" : channel.charAt(0).toUpperCase() + channel.slice(1);
const statusLabel = (status) => String(status || "unknown").replaceAll("_", " ");

function SectionState({ kind, children }) {
  const Icon = kind === "error" ? TriangleAlert : kind === "success" ? CheckCircle2 : Loader2;
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
        kind === "error" && "border-destructive/40 bg-destructive/10 text-destructive",
        kind === "success" && "border-status-success/40 bg-status-success/10 text-status-success-fg",
        kind === "loading" && "bg-secondary text-muted-foreground",
      )}
    >
      <Icon className={cn("h-4 w-4 shrink-0", kind === "loading" && "animate-spin")} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

function UploadPanel({ api }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const upload = async (event) => {
    event.preventDefault();
    if (!file) {
      setError("Choose a file before uploading.");
      return;
    }
    setUploading(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.uploadFile({ file }));
    } catch (err) {
      setError(err?.message || "The file could not be uploaded.");
    } finally {
      setUploading(false);
    }
  };

  const reference = result?.file_url || result?.url || result?.file_id || result?.id;
  const unavailable = result?.available === false || result?.implemented === false || !reference;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileUp className="h-5 w-5" aria-hidden="true" />
          <CardTitle>File upload</CardTitle>
        </div>
        <CardDescription>Send an operator-selected file to the configured federation upload service.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={upload} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="operator-file">File</Label>
            <Input
              id="operator-file"
              type="file"
              onChange={(event) => {
                setFile(event.target.files?.[0] || null);
                setError("");
                setResult(null);
              }}
              disabled={uploading}
            />
            <p className="text-xs text-muted-foreground">
              The selected file is sent only after you choose Upload file.
            </p>
          </div>
          <Button type="submit" disabled={!file || uploading}>
            {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {uploading ? "Uploading…" : "Upload file"}
          </Button>
          {error && <SectionState kind="error">{error}</SectionState>}
          {result && (
            <SectionState kind={unavailable ? "error" : "success"}>
              {unavailable
                ? result.reason || result.message || "The upload endpoint did not return a usable file reference."
                : `Uploaded ${file?.name || "file"}${reference ? ` · Reference: ${reference}` : ""}`}
            </SectionState>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

function ConnectionsPanel({ api }) {
  const [states, setStates] = useState({});
  const [checkingAll, setCheckingAll] = useState(true);

  const check = useCallback(async (connector) => {
    setStates((current) => ({ ...current, [connector.name]: { loading: true } }));
    try {
      const data = await api.getConnection(connector.name);
      setStates((current) => ({ ...current, [connector.name]: { data, loading: false } }));
    } catch (error) {
      setStates((current) => ({ ...current, [connector.name]: { error: error?.message || "Connection check failed.", loading: false } }));
    }
  }, [api]);

  const checkAll = useCallback(async () => {
    setCheckingAll(true);
    await Promise.all(OPERATOR_CONNECTORS.map(check));
    setCheckingAll(false);
  }, [check]);

  useEffect(() => {
    checkAll();
  }, [checkAll]);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <PlugZap className="h-5 w-5" aria-hidden="true" />
              <CardTitle>Connections</CardTitle>
            </div>
            <CardDescription className="mt-1.5">Check the live connection contract for operator-facing services.</CardDescription>
          </div>
          <Button type="button" variant="secondary" onClick={checkAll} disabled={checkingAll}>
            <RefreshCw className={cn("mr-2 h-4 w-4", checkingAll && "animate-spin")} aria-hidden="true" />
            {checkingAll ? "Checking…" : "Check all"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {OPERATOR_CONNECTORS.length === 0 ? (
          <p className="text-sm text-muted-foreground">No operator connections are configured.</p>
        ) : (
          <ul className="divide-y divide-border" aria-label="Connection status">
            {OPERATOR_CONNECTORS.map((connector) => {
              const state = states[connector.name] || {};
              const status = state.data?.status;
              const connected = ["connected", "ready", "ok", "available"].includes(String(status).toLowerCase());
              return (
                <li key={connector.name} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{connector.label}</p>
                    {state.loading ? (
                      <p role="status" className="mt-1 text-xs text-muted-foreground">Checking connection…</p>
                    ) : state.error ? (
                      <p role="alert" className="mt-1 text-xs text-destructive">{state.error}</p>
                    ) : state.data ? (
                      <p className={cn("mt-1 text-xs capitalize", connected ? "text-status-success-fg" : "text-muted-foreground")}>
                        {statusLabel(status)}
                        {state.data.message ? ` · ${state.data.message}` : ""}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-muted-foreground">Not checked.</p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label={`Check ${connector.label} connection`}
                    onClick={() => check(connector)}
                    disabled={state.loading}
                  >
                    Check
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function PreferenceControls({ scope, value, channels, timing, onChange, disabled = false }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <fieldset disabled={disabled}>
        <legend className="mb-2 text-sm font-medium">Outbound channels</legend>
        <div className="flex flex-wrap gap-4">
          {channels.map((channel) => {
            const id = `${scope}-${channel}`;
            return (
              <label key={channel} htmlFor={id} className="flex items-center gap-2 text-sm">
                <input
                  id={id}
                  type="checkbox"
                  checked={value.channels.includes(channel)}
                  onChange={(event) => {
                    const next = event.target.checked
                      ? [...value.channels, channel]
                      : value.channels.filter((item) => item !== channel);
                    onChange({ ...value, channels: next });
                  }}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                {channelLabel(channel)}
              </label>
            );
          })}
        </div>
        {!channels.length && <p className="text-xs text-muted-foreground">No outbound channels are available.</p>}
      </fieldset>
      <div className="space-y-2">
        <Label htmlFor={`${scope}-timing`}>Delivery timing</Label>
        <select
          id={`${scope}-timing`}
          value={value.timing}
          disabled={disabled}
          onChange={(event) => onChange({ ...value, timing: event.target.value })}
          className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
        >
          {timing.map((item) => (
            <option key={item} value={item}>{item === "brief" ? "Scheduled brief" : "As soon as possible"}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

function NotificationsPanel({ api }) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState(null);
  const [model, setModel] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await api.getPreferences();
      setModel({
        prefs: data?.prefs || {},
        targets: data?.targets || {},
        domains: Array.isArray(data?.domains) ? data.domains : [],
        channels: Array.isArray(data?.channels) ? data.channels : [],
        timing: Array.isArray(data?.timing) && data.timing.length ? data.timing : ["asap", "brief"],
      });
    } catch (error) {
      setLoadError(error?.message || "Notification preferences could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  const globalPreference = normalizePreference(model?.prefs?.all || fallbackPreference);
  const setPreference = (key, value) => {
    setSaveState(null);
    setModel((current) => ({ ...current, prefs: { ...current.prefs, [key]: value } }));
  };
  const removePreference = (key) => {
    setSaveState(null);
    setModel((current) => {
      const prefs = { ...current.prefs };
      delete prefs[key];
      return { ...current, prefs };
    });
  };
  const setTarget = (channel, value) => {
    setSaveState(null);
    setModel((current) => ({ ...current, targets: { ...current.targets, [channel]: value } }));
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setSaveState(null);
    try {
      const prefs = { ...model.prefs, all: globalPreference };
      await api.setPreferences(prefs, model.targets);
      setModel((current) => ({ ...current, prefs }));
      setSaveState({ kind: "success", message: "Notification preferences saved." });
    } catch (error) {
      setSaveState({ kind: "error", message: error?.message || "Notification preferences could not be saved." });
    } finally {
      setSaving(false);
    }
  };

  const targetChannels = useMemo(
    () => (model?.channels || []).filter((channel) => channel === "push" || channel === "sms"),
    [model?.channels],
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5" aria-hidden="true" />
          <CardTitle>Notification preferences</CardTitle>
        </div>
        <CardDescription>In-app notifications remain available. Choose optional outbound channels globally or by domain.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <SectionState kind="loading">Loading notification preferences…</SectionState>
        ) : loadError ? (
          <div className="space-y-3">
            <SectionState kind="error">{loadError}</SectionState>
            <Button type="button" variant="secondary" onClick={load}>Try again</Button>
          </div>
        ) : !model ? (
          <p className="text-sm text-muted-foreground">No preference data is available.</p>
        ) : (
          <form onSubmit={save} className="space-y-6">
            <section aria-labelledby="global-delivery-heading" className="space-y-3">
              <div>
                <h2 id="global-delivery-heading" className="text-sm font-semibold">Default delivery</h2>
                <p className="text-xs text-muted-foreground">Applies to every domain without a custom override.</p>
              </div>
              <PreferenceControls
                scope="all"
                value={globalPreference}
                channels={model.channels}
                timing={model.timing}
                onChange={(value) => setPreference("all", value)}
              />
            </section>

            <section aria-labelledby="delivery-targets-heading" className="space-y-3">
              <div>
                <h2 id="delivery-targets-heading" className="text-sm font-semibold">Delivery targets</h2>
                <p className="text-xs text-muted-foreground">Targets are stored by the existing notification preferences service.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {targetChannels.map((channel) => (
                  <div key={channel} className="space-y-2">
                    <Label htmlFor={`target-${channel}`}>{channel === "sms" ? "SMS number" : "Push endpoint"}</Label>
                    <Input
                      id={`target-${channel}`}
                      type={channel === "sms" ? "tel" : "url"}
                      value={model.targets[channel] || ""}
                      onChange={(event) => setTarget(channel, event.target.value)}
                      placeholder={channel === "sms" ? "+1 787 555 0123" : "https://push.example/subscription"}
                    />
                  </div>
                ))}
              </div>
              {!targetChannels.length && <p className="text-sm text-muted-foreground">No outbound delivery targets are available.</p>}
            </section>

            <section aria-labelledby="domain-overrides-heading" className="space-y-3">
              <div>
                <h2 id="domain-overrides-heading" className="text-sm font-semibold">Domain overrides</h2>
                <p className="text-xs text-muted-foreground">Enable an override only where delivery should differ from the default.</p>
              </div>
              {!model.domains.length ? (
                <p className="text-sm text-muted-foreground">No notification domains are available.</p>
              ) : (
                <div className="space-y-4">
                  {model.domains.map((domain) => {
                    const custom = Object.hasOwn(model.prefs, domain);
                    const value = normalizePreference(model.prefs[domain] || globalPreference);
                    return (
                      <div key={domain} className="rounded-lg border border-border p-4">
                        <label className="mb-4 flex items-center gap-2 text-sm font-medium">
                          <input
                            type="checkbox"
                            checked={custom}
                            onChange={(event) => event.target.checked
                              ? setPreference(domain, { channels: [...value.channels], timing: value.timing })
                              : removePreference(domain)}
                            className="h-4 w-4 rounded border-input accent-primary"
                          />
                          Custom delivery for {domain}
                        </label>
                        <PreferenceControls
                          scope={domain}
                          value={value}
                          channels={model.channels}
                          timing={model.timing}
                          disabled={!custom}
                          onChange={(next) => setPreference(domain, next)}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
                {saving ? "Saving…" : "Save preferences"}
              </Button>
              {saveState && <SectionState kind={saveState.kind}>{saveState.message}</SectionState>}
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

const defaultApi = {
  uploadFile: (payload) => federation.integrations.Core.UploadFile(payload),
  getConnection: (name) => federation.connectors.getConnection(name),
  getPreferences: () => federation.notifications.getPreferences(),
  setPreferences: (prefs, targets) => federation.notifications.setPreferences(prefs, targets),
};

export default function OperatorSettings({ api = defaultApi }) {
  return (
    <div>
      <PageHeader
        icon={Settings}
        title="Operator Settings"
        description="Operator-facing file transfer, connection checks, and notification delivery settings."
      />
      <div className="grid gap-5 xl:grid-cols-2">
        <UploadPanel api={api} />
        <ConnectionsPanel api={api} />
        <div className="xl:col-span-2">
          <NotificationsPanel api={api} />
        </div>
      </div>
    </div>
  );
}

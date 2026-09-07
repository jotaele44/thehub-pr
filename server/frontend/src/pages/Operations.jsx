import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Ban, Play, TerminalSquare } from "lucide-react";
import EmptyState from "@/components/shared/EmptyState";
import PageHeader from "@/components/shared/PageHeader";
import StatusChip from "@/components/shared/StatusChip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import GateStatusPanel from "@/components/manager/GateStatusPanel";
import OperationForm from "@/components/manager/OperationForm";
import PrerequisitePanel from "@/components/manager/PrerequisitePanel";
import RepositoryDataHealthPanel from "@/components/manager/RepositoryDataHealthPanel";
import RunConsole from "@/components/manager/RunConsole";
import SecretPresencePanel from "@/components/manager/SecretPresencePanel";
import {
  ManagerUnavailableError,
  cleanValues,
  formFields,
  initialValues,
  managerApi,
  subscribeToRunLogs,
  tokenFields,
} from "@/components/manager/managerClient";
import { RISK_CLASS } from "@/lib/chips";

function OperationRow({ operation, selected, onSelect }) {
  const disabled = !operation.enabled;
  return (
    <li>
      <button
        type="button"
        onClick={() => !disabled && onSelect(operation)}
        disabled={disabled}
        aria-disabled={disabled}
        data-operation-id={operation.operationId}
        className={[
          "w-full text-left p-3 rounded-lg border transition-colors",
          selected ? "border-primary bg-secondary" : "border-border",
          disabled ? "opacity-60 cursor-not-allowed" : "hover:bg-secondary",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-mono truncate">{operation.operationId}</span>
          <StatusChip map={RISK_CLASS} value={operation.riskClass} />
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {operation.category} · writes {operation.writeScope}
        </p>
        {disabled && (
          <p className="text-xs text-status-warning-fg mt-1 flex items-start gap-1">
            <Ban className="h-3 w-3 mt-0.5 shrink-0" />
            <span>{operation.enablementReason}</span>
          </p>
        )}
      </button>
    </li>
  );
}

export default function Operations({ api = managerApi, subscribe = subscribeToRunLogs }) {
  const [state, setState] = useState("loading");
  const [operations, setOperations] = useState([]);
  const [repositories, setRepositories] = useState([]);
  const [accounting, setAccounting] = useState(null);
  const [gates, setGates] = useState(null);
  const [selected, setSelected] = useState(null);
  const [values, setValues] = useState({});
  const [tokens, setTokens] = useState({});
  const [plan, setPlan] = useState(null);
  const [run, setRun] = useState(null);
  const [lines, setLines] = useState([]);
  const [receipt, setReceipt] = useState(null);
  const [presence, setPresence] = useState([]);
  const [prerequisites, setPrerequisites] = useState([]);
  const [error, setError] = useState("");
  const unsubscribe = useRef(null);

  useEffect(() => {
    let active = true;
    const repositoryRequest =
      typeof api.repositories === "function" ? api.repositories() : Promise.resolve([]);
    Promise.all([api.listOperations(), repositoryRequest, api.accounting(), api.gates()])
      .then(([ops, repos, counts, evidence]) => {
        if (!active) return;
        setOperations(ops);
        setRepositories(repos);
        setAccounting(counts);
        setGates(evidence);
        setState("connected");
      })
      .catch((cause) => {
        if (!active) return;
        setState(cause instanceof ManagerUnavailableError ? "unavailable" : "error");
        setError(cause?.message || "The operations plane could not be reached.");
      });
    return () => {
      active = false;
      unsubscribe.current?.();
    };
  }, [api]);

  const fields = useMemo(() => (selected ? formFields(selected.parameters) : []), [selected]);
  const slots = useMemo(() => (selected ? tokenFields(selected.parameters) : []), [selected]);

  const select = useCallback(
    (operation) => {
      unsubscribe.current?.();
      setSelected(operation);
      setValues(initialValues(operation.parameters));
      setTokens({});
      setPlan(null);
      setRun(null);
      setLines([]);
      setReceipt(null);
      setError("");
      if (operation.secretRefs?.length) {
        api
          .secretPresence(operation.appId, operation.secretRefs)
          .then(setPresence)
          .catch(() => setPresence([]));
      } else {
        setPresence([]);
      }
      api
        .prerequisites(operation.appId)
        .then(setPrerequisites)
        .catch(() => setPrerequisites([]));
    },
    [api],
  );

  const doPlan = useCallback(async () => {
    if (!selected) return;
    setError("");
    try {
      setPlan(await api.plan(selected.operationId, cleanValues(fields, values)));
    } catch (cause) {
      setPlan(null);
      setError(cause?.detail || cause?.message || "The plan could not be produced.");
    }
  }, [api, fields, selected, values]);

  const doRun = useCallback(async () => {
    if (!selected) return;
    setError("");
    setReceipt(null);
    setLines([]);
    setRun({ status: "running" });
    try {
      const document = await api.run(selected.operationId, {
        parameters: cleanValues(fields, values),
        fileTokens: tokens,
        acknowledged: Boolean(plan),
      });
      setReceipt(document);
      setRun({ status: document.receipt.status, runId: document.receipt.run_id });
      const snapshot = await api.logSnapshot(document.receipt.run_id).catch(() => null);
      if (snapshot?.lines?.length) {
        setLines((current) => (current.length ? current : snapshot.lines));
      }
      api.gates().then(setGates).catch(() => {});
      if (typeof api.repositories === "function") {
        api.repositories().then(setRepositories).catch(() => {});
      }
    } catch (cause) {
      setRun({ status: "failed" });
      setError(cause?.detail || cause?.message || "The operation could not be started.");
    }
  }, [api, fields, plan, selected, tokens, values]);

  const doCancel = useCallback(() => {
    if (run?.runId) api.cancel(run.runId).catch(() => {});
  }, [api, run]);

  useEffect(() => {
    if (!run?.runId || run.status !== "running") return undefined;
    unsubscribe.current = subscribe(run.runId, {
      onLine: (line) => setLines((current) => [...current, line]),
      onDone: (status) => setRun((current) => ({ ...current, status })),
      onError: () => {},
    });
    return () => unsubscribe.current?.();
  }, [run?.runId, run?.status, subscribe]);

  if (state === "loading") {
    return (
      <div className="p-6 space-y-4">
        <PageHeader title="Operations" icon={TerminalSquare} />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (state !== "connected") {
    return (
      <div className="p-6">
        <PageHeader title="Operations" icon={TerminalSquare} />
        <EmptyState
          icon={TerminalSquare}
          title="The operations plane is unavailable"
          description={
            state === "unavailable"
              ? "This page requires the native manager session. Open TheHub through the desktop application."
              : error
          }
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Operations"
        icon={TerminalSquare}
        description={
          accounting
            ? `${accounting.enabled} of ${accounting.total} declared operations are enabled. Policy sequence ${accounting.sequence}.`
            : undefined
        }
      />

      {error && (
        <p role="alert" className="text-sm text-status-danger-fg">
          {error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Repository data health</CardTitle>
        </CardHeader>
        <CardContent>
          <RepositoryDataHealthPanel
            repositories={repositories}
            operations={operations}
            onSelect={select}
          />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Declared operations</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 max-h-[32rem] overflow-auto pr-1">
              {operations.map((operation) => (
                <OperationRow
                  key={operation.operationId}
                  operation={operation}
                  selected={selected?.operationId === operation.operationId}
                  onSelect={select}
                />
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">
              {selected ? selected.operationId : "Select an operation"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!selected && (
              <p className="text-sm text-muted-foreground">
                Choose an enabled operation to review what it would do before running it.
              </p>
            )}

            {selected && (
              <>
                {prerequisites.length > 0 && (
                  <details className="rounded-lg border border-border p-3">
                    <summary className="text-sm font-medium cursor-pointer">
                      Prerequisites
                      {prerequisites.some((item) => item.status === "unmet") && (
                        <span className="text-status-warning-fg ml-2 text-xs">
                          {prerequisites.filter((item) => item.status === "unmet").length} unmet
                        </span>
                      )}
                    </summary>
                    <div className="mt-3">
                      <PrerequisitePanel prerequisites={prerequisites} />
                    </div>
                  </details>
                )}

                <OperationForm
                  fields={fields}
                  values={values}
                  tokenSlots={slots}
                  tokens={tokens}
                  disabled={run?.status === "running"}
                  onChange={(name, value) =>
                    setValues((current) => ({ ...current, [name]: value }))
                  }
                  onPickFile={(slot) =>
                    setError(
                      `Selecting a file for "${slot.name}" requires the native picker, which is available when TheHub runs as a desktop application.`,
                    )
                  }
                />

                {presence.length > 0 && (
                  <SecretPresencePanel
                    presence={presence}
                    busy={run?.status === "running"}
                    onSet={(secretId, value) =>
                      api
                        .setSecret(selected.appId, secretId, value)
                        .then(() => api.secretPresence(selected.appId, selected.secretRefs))
                        .then(setPresence)
                        .catch((cause) => setError(cause?.detail || cause?.message))
                    }
                    onDelete={(secretId) =>
                      api
                        .deleteSecret(selected.appId, secretId)
                        .then(() => api.secretPresence(selected.appId, selected.secretRefs))
                        .then(setPresence)
                        .catch((cause) => setError(cause?.detail || cause?.message))
                    }
                  />
                )}

                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" onClick={doPlan}>
                    Dry run
                  </Button>
                  <Button
                    type="button"
                    onClick={doRun}
                    disabled={!plan || run?.status === "running"}
                  >
                    <Play className="h-3.5 w-3.5 mr-1.5" />
                    Run
                  </Button>
                  {!plan && (
                    <span className="text-xs text-muted-foreground">
                      Review the dry run first — it shows exactly what will be executed.
                    </span>
                  )}
                </div>

                <RunConsole
                  plan={plan}
                  run={run}
                  lines={lines}
                  receipt={receipt}
                  onCancel={doCancel}
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Readiness gates</CardTitle>
        </CardHeader>
        <CardContent>
          <GateStatusPanel evidence={gates} />
        </CardContent>
      </Card>
    </div>
  );
}

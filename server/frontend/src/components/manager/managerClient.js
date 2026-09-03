// Client for the loopback-only Federation Manager operations API.
//
// Deliberately not routed through `federationClient`: that client targets the
// SPA's own API with its localStorage token and `credentials: 'include'`, while
// the manager API is a separate loopback surface authorised by a short-lived
// native session token held in sessionStorage. Sharing one client would mean
// one of the two surfaces silently sending the wrong credential.
//
// Nothing here ever receives a secret value. Secrets go in; only presence
// comes back.

const BASE = "/api/federation-manager";
const SESSION_KEY = "prii.manager.session";

export class ManagerUnavailableError extends Error {}
export class ManagerRequestError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function readSessionToken(storage = globalThis.sessionStorage) {
  return storage?.getItem(SESSION_KEY) || null;
}

async function request(
  path,
  { method = "GET", body, fetchImpl = globalThis.fetch, storage = globalThis.sessionStorage } = {},
) {
  const token = readSessionToken(storage);
  if (!token) throw new ManagerUnavailableError("Native manager session is unavailable.");

  const response = await fetchImpl(`${BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

  if (response.status === 401) {
    throw new ManagerUnavailableError("Native manager session expired.");
  }
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json())?.detail || "";
    } catch {
      detail = response.statusText;
    }
    throw new ManagerRequestError(detail || "Manager request failed.", response.status, detail);
  }
  return response.status === 204 ? null : response.json();
}

export const managerApi = {
  listOperations: (opts) => request("/operations", opts),
  repositories: (opts) => request("/repositories", opts),
  prerequisites: (appId, opts) =>
    request(`/apps/${encodeURIComponent(appId)}/prerequisites`, opts),
  accounting: (opts) => request("/operations/accounting", opts),
  plan: (operationId, parameters, opts) =>
    request(`/operations/${encodeURIComponent(operationId)}/plan`, {
      ...opts,
      method: "POST",
      body: { parameters },
    }),
  run: (operationId, { parameters, fileTokens, acknowledged } = {}, opts) =>
    request(`/operations/${encodeURIComponent(operationId)}/run`, {
      ...opts,
      method: "POST",
      body: { parameters, file_tokens: fileTokens, acknowledged: Boolean(acknowledged) },
    }),
  cancel: (runId, opts) =>
    request(`/runs/${encodeURIComponent(runId)}/cancel`, { ...opts, method: "POST" }),
  receipt: (runId, opts) => request(`/runs/${encodeURIComponent(runId)}/receipt`, opts),
  receipts: (opts) => request("/receipts", opts),
  gates: (opts) => request("/gates", opts),
  logSnapshot: (runId, opts) => request(`/runs/${encodeURIComponent(runId)}/logs`, opts),
  logTicket: (runId, opts) =>
    request(`/runs/${encodeURIComponent(runId)}/log-ticket`, { ...opts, method: "POST" }),
  secretPresence: (appId, secretIds, opts) =>
    request("/secrets/presence", {
      ...opts,
      method: "POST",
      body: { app_id: appId, secret_ids: secretIds },
    }),
  setSecret: (appId, secretId, value, opts) =>
    request("/secrets", {
      ...opts,
      method: "POST",
      body: { app_id: appId, secret_id: secretId, value },
    }),
  deleteSecret: (appId, secretId, opts) =>
    request(`/secrets/${encodeURIComponent(appId)}/${encodeURIComponent(secretId)}`, {
      ...opts,
      method: "DELETE",
    }),
};

export function subscribeToRunLogs(
  runId,
  { onLine, onDone, onError, EventSourceImpl = globalThis.EventSource, ...opts } = {},
) {
  let source = null;
  let cancelled = false;

  managerApi
    .logTicket(runId, opts)
    .then(({ ticket }) => {
      if (cancelled || typeof EventSourceImpl !== "function") {
        if (typeof EventSourceImpl !== "function") onError?.(new Error("Streaming is unavailable."));
        return;
      }
      source = new EventSourceImpl(`${BASE}/runs/${encodeURIComponent(runId)}/logs/${ticket}`);
      source.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.done) {
            onDone?.(payload.status);
            source.close();
          } else if (payload.line !== undefined) {
            onLine?.(payload.line);
          }
        } catch {
          onLine?.(String(event.data));
        }
      };
      source.onerror = () => {
        source.close();
        onError?.(new Error("Log stream interrupted."));
      };
    })
    .catch((error) => onError?.(error));

  return () => {
    cancelled = true;
    source?.close();
  };
}

export function formFields(parameters = {}) {
  return Object.entries(parameters)
    .filter(([, spec]) => spec.type !== "fixed")
    .map(([name, spec]) => ({
      name,
      label: name.replace(/_/g, " "),
      type: spec.type,
      required: Boolean(spec.required),
      defaultValue: spec.default,
      values: spec.values || [],
      extensions: spec.extensions || [],
      minimum: spec.minimum,
      maximum: spec.maximum,
    }));
}

export function initialValues(parameters = {}) {
  const values = {};
  for (const [name, spec] of Object.entries(parameters)) {
    if (spec.type === "fixed") continue;
    values[name] = spec.default !== undefined ? spec.default : spec.type === "boolean" ? false : "";
  }
  return values;
}

export function cleanValues(fields, values) {
  const payload = {};
  for (const field of fields) {
    const value = values[field.name];
    if (field.type === "boolean") {
      payload[field.name] = Boolean(value);
      continue;
    }
    if (value === "" || value === undefined || value === null) continue;
    if (field.type === "integer") payload[field.name] = Number.parseInt(value, 10);
    else if (field.type === "number") payload[field.name] = Number(value);
    else payload[field.name] = value;
  }
  return payload;
}

export function tokenFields(parameters = {}) {
  return Object.entries(parameters)
    .filter(([, spec]) => spec.type === "file_token" || spec.type === "file_set_token")
    .map(([name, spec]) => ({ name, extensions: spec.extensions || [], family: spec.family }));
}

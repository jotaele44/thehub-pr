import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Operations from "./Operations";

const CANARY = "prii-canary-secret-ui-77af";

const OPERATIONS = [
  {
    operationId: "hub.list",
    appId: "thehub",
    repo: "thehub-pr",
    category: "inspect",
    enabled: true,
    enablementReason: "",
    riskClass: "R0_READ_ONLY",
    approvalPolicy: "none",
    networkPolicy: "none",
    writeScope: "none",
    rollbackStrategy: "none",
    targetKind: "console_script",
    parameters: { registry: { type: "fixed", value: "registry/producers.yaml" } },
    secretRefs: [],
    expectedOutputs: [],
  },
  {
    operationId: "hub.correlate",
    appId: "thehub",
    repo: "thehub-pr",
    category: "derive",
    enabled: true,
    enablementReason: "",
    riskClass: "R1_DERIVED_WRITE",
    approvalPolicy: "none",
    networkPolicy: "none",
    writeScope: "aggregate correlations output",
    rollbackStrategy: "stage_validate_atomic_promote",
    targetKind: "console_script",
    parameters: {
      in_dir: { type: "directory", required: true },
      out: { type: "managed_output_directory", required: true },
      window_days: { type: "integer", default: 7, minimum: 0, maximum: 3650 },
    },
    secretRefs: [],
    expectedOutputs: ["correlations.jsonl"],
  },
  {
    operationId: "hub.validate_manifest",
    appId: "thehub",
    repo: "thehub-pr",
    category: "validate",
    enabled: true,
    enablementReason: "",
    riskClass: "R0_READ_ONLY",
    approvalPolicy: "none",
    networkPolicy: "none",
    writeScope: "none",
    rollbackStrategy: "none",
    targetKind: "console_script",
    parameters: { path: { type: "file_token", required: true, extensions: [".json"] } },
    secretRefs: [],
    expectedOutputs: [],
  },
  {
    operationId: "hub.fetch",
    appId: "thehub",
    repo: "thehub-pr",
    category: "acquire",
    enabled: false,
    enablementReason: "Repository acquisition is an R3 lifecycle operation; gate G09 is not certified.",
    riskClass: "R3_LIFECYCLE",
    approvalPolicy: "confirm_network_and_disk_write",
    networkPolicy: "github.com only",
    writeScope: "managed app/workspace roots only",
    rollbackStrategy: "delete staging checkout",
    targetKind: "internal_builtin",
    parameters: {},
    secretRefs: [],
    expectedOutputs: [],
  },
  {
    operationId: "centinelas.classify",
    appId: "centinelas",
    repo: "centinelas-pr",
    category: "classify",
    enabled: false,
    enablementReason: "Producer operation. Declared and classified for accounting, but not enabled.",
    riskClass: "R2_NETWORK_INGEST",
    approvalPolicy: "confirm_external_api",
    networkPolicy: "Anthropic API only",
    writeScope: ".centinelas classified",
    rollbackStrategy: "run_partition_restore",
    targetKind: "console_script",
    parameters: {},
    secretRefs: ["ANTHROPIC_API_KEY"],
    expectedOutputs: [],
  },
];

const ACCOUNTING = { total: 68, enabled: 12, declared_not_enabled: 56, unclassified: [], sequence: 1 };

const GATES = {
  gates: [
    {
      gate_id: "G04_OPERATION_ACCOUNTING",
      requirement: "All 68 accounted",
      blocking: true,
      status: "passed",
      derived_from: [{ run_id: "a".repeat(32), receipt_sha256: "b".repeat(64), signature_verified: true }],
    },
    {
      gate_id: "G07_NATIVE_SECRETS",
      requirement: "macOS Keychain certified",
      blocking: true,
      status: "blocked_not_certified",
      status_reason: "No macOS host is available in this environment.",
      derived_from: [],
      annotations: [
        { author: "operator", note: "I checked this by hand", recorded_at: "2026-07-27T00:00:00Z" },
      ],
    },
  ],
};

const RECEIPT = {
  receipt: {
    run_id: "c".repeat(32),
    operation_id: "hub.list",
    app_id: "thehub",
    status: "succeeded",
    exit_code: 0,
    argv_redacted: ["hub", "list", "--registry", "registry/producers.yaml"],
    log: { sha256: "d".repeat(64), bytes: 42, truncated: false, redactions: 0 },
    transaction: { strategy: "none", phase_reached: "RECEIPT", rollback_state: "not_required" },
    validators: [{ name: "exit_code", status: "passed", detail: "exit 0" }],
  },
  signature: { algorithm: "Ed25519", payload_sha256: "e".repeat(64), key_id: "m", value: "sig" },
};

function makeApi(overrides = {}) {
  return {
    listOperations: vi.fn().mockResolvedValue(OPERATIONS),
    accounting: vi.fn().mockResolvedValue(ACCOUNTING),
    gates: vi.fn().mockResolvedValue(GATES),
    plan: vi.fn().mockResolvedValue({
      operationId: "hub.list",
      argvPreview: ["hub", "list", "--registry", "registry/producers.yaml"],
      writeScope: "none",
      networkPolicy: "none",
      rollbackStrategy: "none",
      expectedOutputs: [],
      missingSecrets: [],
      warnings: [],
    }),
    run: vi.fn().mockResolvedValue(RECEIPT),
    cancel: vi.fn().mockResolvedValue({}),
    logSnapshot: vi.fn().mockResolvedValue({ lines: ["# thehub-pr — 6 producers\n"], done: true }),
    secretPresence: vi.fn().mockResolvedValue([
      { secret_id: "ANTHROPIC_API_KEY", status: "absent", detail: "not set in the OS credential store" },
    ]),
    prerequisites: vi.fn().mockResolvedValue([
      { name: "Signed operations policy", status: "met", detail: "sequence 1", remediation: "" },
      {
        name: "Console script: hub",
        status: "unmet",
        detail: "not found on PATH",
        remediation: "Install the thehub application environment so `hub` is on PATH.",
      },
    ]),
    setSecret: vi.fn().mockResolvedValue({ status: "present" }),
    deleteSecret: vi.fn().mockResolvedValue({ status: "absent" }),
    ...overrides,
  };
}

const noSubscribe = () => () => {};

describe("Operations", () => {
  it("lists every declared operation, including the disabled ones", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    expect(screen.getByText("hub.fetch")).toBeInTheDocument();
    expect(screen.getByText("centinelas.classify")).toBeInTheDocument();
  });

  it("shows why a disabled operation is disabled and refuses to select it", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.fetch");

    expect(screen.getByText(/gate G09 is not certified/)).toBeInTheDocument();

    const button = screen.getByText("hub.fetch").closest("button");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-disabled", "true");

    fireEvent.click(button);
    expect(screen.getByText("Select an operation")).toBeInTheDocument();
  });

  it("reports the accounting honestly in the header", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    expect(await screen.findByText(/12 of 68 declared operations are enabled/)).toBeInTheDocument();
  });

  it("generates form fields from the typed parameter schema", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.correlate");
    fireEvent.click(screen.getByText("hub.correlate").closest("button"));

    expect(screen.getByLabelText(/in dir/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/window days/i)).toHaveAttribute("type", "number");
  });

  it("does not render a control for a fixed policy parameter", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));

    expect(screen.queryByLabelText(/registry/i)).not.toBeInTheDocument();
    expect(screen.getByText(/takes no operator-supplied parameters/i)).toBeInTheDocument();
  });

  it("renders a native file slot rather than a file input", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.validate_manifest");
    fireEvent.click(screen.getByText("hub.validate_manifest").closest("button"));

    expect(screen.getByRole("button", { name: /choose file/i })).toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(screen.getByText(/never receives the file path/i)).toBeInTheDocument();
  });

  it("requires a dry run before the run button becomes available", async () => {
    const api = makeApi();
    render(<Operations api={api} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));

    expect(screen.getByRole("button", { name: /^run$/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /dry run/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^run$/i })).toBeEnabled());
    expect(api.run).not.toHaveBeenCalled();
  });

  it("shows the plan as an ordered argv list, not a command line", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));
    fireEvent.click(screen.getByRole("button", { name: /dry run/i }));

    const runConsole = await screen.findByTestId("run-console");

    // Each argument is its own list item, so an operator cannot copy a
    // space-joined line into a terminal where the quoting rules differ.
    const items = within(runConsole).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "00hub",
      "01list",
      "02--registry",
      "03registry/producers.yaml",
    ]);
    expect(within(runConsole).queryByText("hub list --registry registry/producers.yaml")).toBeNull();
    expect(within(runConsole).getByText(/nothing has been executed/i)).toBeInTheDocument();
  });

  it("runs and shows the signed receipt", async () => {
    const api = makeApi();
    render(<Operations api={api} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));
    fireEvent.click(screen.getByRole("button", { name: /dry run/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^run$/i })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    expect(await screen.findByText("Signed receipt")).toBeInTheDocument();
    expect(screen.getByText(/Ed25519/)).toBeInTheDocument();
    expect(api.run).toHaveBeenCalledWith("hub.list", expect.objectContaining({ acknowledged: true }));
  });

  it("surfaces a refusal from the server instead of failing silently", async () => {
    const api = makeApi({
      plan: vi.fn().mockRejectedValue({ detail: "hub.correlate.window_days must be >= 0" }),
    });
    render(<Operations api={api} subscribe={noSubscribe} />);
    await screen.findByText("hub.correlate");
    fireEvent.click(screen.getByText("hub.correlate").closest("button"));
    fireEvent.click(screen.getByRole("button", { name: /dry run/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/must be >= 0/);
  });

  it("renders gate status derived from receipts and marks a note as advisory", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    const panel = await screen.findByTestId("gate-panel");

    expect(within(panel).getByText("G04_OPERATION_ACCOUNTING")).toBeInTheDocument();
    expect(within(panel).getByText("passed")).toBeInTheDocument();
    expect(within(panel).getByText("blocked_not_certified")).toBeInTheDocument();
    expect(within(panel).getByText(/No macOS host is available/)).toBeInTheDocument();
    expect(within(panel).getByText(/note, not evidence/)).toBeInTheDocument();
    expect(within(panel).getByText(/cannot change a status/)).toBeInTheDocument();
  });

  it("offers no control that could mark a gate passed", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    const panel = await screen.findByTestId("gate-panel");
    expect(within(panel).queryAllByRole("button")).toHaveLength(0);
    expect(within(panel).queryAllByRole("checkbox")).toHaveLength(0);
  });

  it("shows credential presence without any reveal affordance", async () => {
    const api = makeApi({
      listOperations: vi.fn().mockResolvedValue([{ ...OPERATIONS[4], enabled: true }]),
    });
    render(<Operations api={api} subscribe={noSubscribe} />);
    await screen.findByText("centinelas.classify");
    fireEvent.click(screen.getByText("centinelas.classify").closest("button"));

    const panel = await screen.findByTestId("secret-panel");
    expect(within(panel).getByText("ANTHROPIC_API_KEY")).toBeInTheDocument();
    expect(within(panel).getByText("absent")).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: /reveal|show/i })).toBeNull();
    expect(within(panel).getByLabelText(/New value for ANTHROPIC_API_KEY/)).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("never echoes a stored credential back into the page", async () => {
    const api = makeApi({
      listOperations: vi.fn().mockResolvedValue([{ ...OPERATIONS[4], enabled: true }]),
    });
    render(<Operations api={api} subscribe={noSubscribe} />);
    await screen.findByText("centinelas.classify");
    fireEvent.click(screen.getByText("centinelas.classify").closest("button"));

    const input = await screen.findByLabelText(/New value for ANTHROPIC_API_KEY/);
    fireEvent.change(input, { target: { value: CANARY } });
    fireEvent.click(screen.getByRole("button", { name: /store/i }));

    await waitFor(() => expect(api.setSecret).toHaveBeenCalled());
    expect(document.body.textContent).not.toContain(CANARY);
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("falls back to a clear message when the native session is absent", async () => {
    const { ManagerUnavailableError } = await import("@/components/manager/managerClient");
    const api = makeApi({
      listOperations: vi.fn().mockRejectedValue(new ManagerUnavailableError("no session")),
    });
    render(<Operations api={api} subscribe={noSubscribe} />);
    expect(await screen.findByText(/operations plane is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/desktop application/i)).toBeInTheDocument();
  });

  it("streams log lines into the console", async () => {
    const api = makeApi({
      run: vi.fn().mockResolvedValue({
        ...RECEIPT,
        receipt: { ...RECEIPT.receipt, status: "running" },
      }),
      logSnapshot: vi.fn().mockResolvedValue({ lines: [], done: false }),
    });
    const subscribe = vi.fn((runId, { onLine, onDone }) => {
      onLine("streamed line one\n");
      onDone("succeeded");
      return () => {};
    });

    render(<Operations api={api} subscribe={subscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));
    fireEvent.click(screen.getByRole("button", { name: /dry run/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^run$/i })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    expect(await screen.findByText(/streamed line one/)).toBeInTheDocument();
    expect(subscribe).toHaveBeenCalled();
  });

  it("shows machine-detected prerequisites with an actionable remediation", async () => {
    render(<Operations api={makeApi()} subscribe={noSubscribe} />);
    await screen.findByText("hub.list");
    fireEvent.click(screen.getByText("hub.list").closest("button"));

    const panel = await screen.findByTestId("prerequisite-panel");
    expect(within(panel).getByText(/not found on PATH/)).toBeInTheDocument();
    expect(within(panel).getByText(/Install the thehub application environment/)).toBeInTheDocument();
    expect(screen.getByText(/1 unmet/)).toBeInTheDocument();
  });
});

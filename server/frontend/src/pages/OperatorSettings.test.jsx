import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OperatorSettings, { OPERATOR_CONNECTORS } from "./OperatorSettings";

const writeTokenMocks = vi.hoisted(() => ({
  get: vi.fn(() => null),
  set: vi.fn(),
}));
vi.mock("@/api/federationClient", () => ({
  federation: {},
  getWriteToken: writeTokenMocks.get,
  setWriteToken: writeTokenMocks.set,
}));

beforeEach(() => {
  writeTokenMocks.get.mockReturnValue(null);
  writeTokenMocks.set.mockClear();
});

function makeApi(overrides = {}) {
  return {
    uploadFile: vi.fn().mockResolvedValue({ file_id: "file-123" }),
    getConnection: vi.fn().mockImplementation(async (name) => ({ name, status: name === "GitHub" ? "connected" : "not_connected" })),
    getPreferences: vi.fn().mockResolvedValue({
      prefs: { all: { channels: ["push"], timing: "asap" } },
      targets: { push: "https://push.example/subscription" },
      domains: ["seismic", "water"],
      channels: ["push", "sms"],
      timing: ["asap", "brief"],
    }),
    setPreferences: vi.fn().mockResolvedValue({}),
    ...overrides,
  };
}

describe("OperatorSettings", () => {
  it("stores a write token without displaying it and allows clearing it", async () => {
    const secret = "operator-write-secret";
    render(<OperatorSettings api={makeApi()} />);
    const input = screen.getByLabelText("Write token");

    fireEvent.change(input, { target: { value: secret } });
    fireEvent.click(screen.getByRole("button", { name: "Save write token" }));

    expect(writeTokenMocks.set).toHaveBeenCalledWith(secret);
    expect(await screen.findByText(/write token saved for this tab session/i)).toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(screen.queryByText(secret)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear write token" }));

    expect(writeTokenMocks.set).toHaveBeenLastCalledWith(null);
    expect(await screen.findByText(/write token removed from this browser/i)).toBeInTheDocument();
  });

  it("does not reveal an existing write token in the password field", async () => {
    writeTokenMocks.get.mockReturnValue("existing-secret");
    const api = makeApi();
    render(<OperatorSettings api={api} />);

    expect(screen.getByLabelText("Write token")).toHaveValue("");
    expect(screen.queryByText("existing-secret")).not.toBeInTheDocument();
    await screen.findByRole("button", { name: "Save preferences" });
    await waitFor(() => expect(api.getConnection).toHaveBeenCalledTimes(OPERATOR_CONNECTORS.length));
    writeTokenMocks.get.mockReturnValue(null);
  });

  it("checks each operator connection on load and supports individual retries", async () => {
    const api = makeApi();
    render(<OperatorSettings api={api} />);

    await waitFor(() => expect(api.getConnection).toHaveBeenCalledTimes(OPERATOR_CONNECTORS.length));
    expect(await screen.findByText("connected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /check github connection/i }));
    await waitFor(() => expect(api.getConnection).toHaveBeenCalledTimes(OPERATOR_CONNECTORS.length + 1));
    expect(api.getConnection).toHaveBeenLastCalledWith("GitHub");
  });

  it("uploads the selected file and reports its server reference", async () => {
    const api = makeApi();
    render(<OperatorSettings api={api} />);
    const file = new File(["evidence"], "evidence.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/^file$/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload file/i }));

    await waitFor(() => expect(api.uploadFile).toHaveBeenCalledWith({ file }));
    expect(await screen.findByText(/uploaded evidence\.csv.*file-123/i)).toBeInTheDocument();
  });

  it("reports the real diagnostic upload response as unavailable, not uploaded", async () => {
    const reason = "Binary file storage is not provisioned in diagnostic mode; this hub build retains no upload backend.";
    const api = makeApi({
      uploadFile: vi.fn().mockResolvedValue({
        status: "not_implemented",
        mode: "diagnostic",
        implemented: false,
        feature: "files",
        reason,
        message: "files not implemented in diagnostic mode",
        file_id: "compat-file-id",
      }),
    });
    render(<OperatorSettings api={api} />);
    const file = new File(["evidence"], "evidence.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/^file$/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload file/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(reason);
    expect(screen.queryByText(/uploaded evidence\.csv/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/compat-file-id/i)).not.toBeInTheDocument();
  });

  it.each([
    [{ available: false, reason: "Storage unavailable" }, /storage unavailable/i],
    [{ implemented: true }, /did not return a usable file reference/i],
  ])("rejects incomplete upload success responses", async (response, message) => {
    const api = makeApi({ uploadFile: vi.fn().mockResolvedValue(response) });
    render(<OperatorSettings api={api} />);
    const file = new File(["evidence"], "evidence.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/^file$/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload file/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText(/^file$/i).files[0]).toBe(file);
  });

  it("loads, edits, and saves global and per-domain notification preferences", async () => {
    const api = makeApi();
    render(<OperatorSettings api={api} />);

    const formButton = await screen.findByRole("button", { name: /save preferences/i });
    fireEvent.change(screen.getByLabelText(/sms number/i), { target: { value: "+17875550123" } });
    fireEvent.click(screen.getByLabelText(/custom delivery for water/i));

    const waterPanel = screen.getByLabelText(/custom delivery for water/i).closest("div");
    fireEvent.click(within(waterPanel).getByLabelText("SMS"));
    fireEvent.change(within(waterPanel).getByLabelText(/delivery timing/i), { target: { value: "brief" } });
    fireEvent.click(formButton);

    await waitFor(() => expect(api.setPreferences).toHaveBeenCalledOnce());
    expect(api.setPreferences).toHaveBeenCalledWith(
      expect.objectContaining({
        all: { channels: ["push"], timing: "asap" },
        water: expect.objectContaining({ channels: expect.arrayContaining(["push", "sms"]), timing: "brief" }),
      }),
      expect.objectContaining({ sms: "+17875550123" }),
    );
    expect(await screen.findByText(/preferences saved/i)).toBeInTheDocument();
  });

  it("renders load and connection failures accessibly", async () => {
    const api = makeApi({
      getConnection: vi.fn().mockRejectedValue(new Error("Connector offline")),
      getPreferences: vi.fn().mockRejectedValue(new Error("Preferences offline")),
    });
    const { container } = render(<OperatorSettings api={api} />);

    expect(await screen.findByText("Preferences offline")).toBeInTheDocument();
    expect((await screen.findAllByText("Connector offline")).length).toBe(OPERATOR_CONNECTORS.length);
    expect(await axe(container)).toHaveNoViolations();
  });
});

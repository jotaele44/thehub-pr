import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { federation } from "@/api/federationClient";
import SourceMonitorDetail from "./SourceMonitorDetail";

vi.mock("@/api/federationClient", () => ({
  federation: { entities: { MonitoredSources: { get: vi.fn() } } },
}));

const ROW = {
  id: "spiderweb-pr:namus", monitor_id: "spiderweb-pr:namus", producer: "spiderweb-pr", source_id: "namus",
  name: "NIJ", producer_family: "missing_persons", evidence_tier: null, cadence: "quarterly",
  cadence_raw: "90 days", cadence_window_seconds: 7776000, status: "active", status_raw: "harvester_landed",
  url: "https://namus.nij.ojp.gov", producer_last_package_at: null,
  raw: { stratum: "A", classes: ["missing_juvenile"] },
  lineage: { registry_path: "configs/missing_persons_sources.yaml", adapter: "source_monitor_v1" },
  observed_at: "2026-11-08T00:00:00Z",
};

function renderAt(url, state) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[state ? { pathname: url, state } : url]}>
        <Routes><Route path="/source-monitor/:monitorId" element={<SourceMonitorDetail />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SourceMonitorDetail", () => {
  beforeEach(() => {
    // mockClear, not mockReset: resetting before a Promise.reject implementation
    // surfaces the rejection as unhandled under vitest 4.
    vi.mocked(federation.entities.MonitoredSources.get).mockClear();
  });

  it("decodes the route id and renders normalized, raw and lineage fields read-only", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockResolvedValue(ROW);
    const { container } = renderAt("/source-monitor/spiderweb-pr%3Anamus");
    expect(await screen.findByRole("heading", { name: "NIJ" })).toBeInTheDocument();
    expect(federation.entities.MonitoredSources.get).toHaveBeenCalledWith("spiderweb-pr:namus");
    expect(screen.getByText("registry: harvester_landed")).toBeInTheDocument();
    expect(screen.getByText("no export package found")).toBeInTheDocument();
    expect(screen.getByText('["missing_juvenile"]')).toBeInTheDocument();
    expect(screen.getByText("configs/missing_persons_sources.yaml")).toBeInTheDocument();
    // The producer links to its page with the Monitor tab selected.
    expect(screen.getByRole("link", { name: "spiderweb-pr" })).toHaveAttribute("href", "/spiderweb?tab=sources");
    expect(screen.getByRole("link", { name: "Back to Source Monitor" })).toHaveAttribute("href", "/source-monitor");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("explains a missing row instead of failing", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockImplementation(
      () => Promise.reject(Object.assign(new Error("not found"), { status: 404 })),
    );
    renderAt("/source-monitor/ovnis-pr%3AGONE");
    expect(await screen.findByText("Monitored source not found")).toBeInTheDocument();
  });
});


describe("SourceMonitorDetail for a stream row", () => {
  beforeEach(() => vi.mocked(federation.entities.MonitoredSources.get).mockClear());

  it("shows the reported last success, its basis, the last attempt and the stream origin", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockResolvedValue({
      ...ROW, id: "aguayluz-pr:nwps_gauges", monitor_id: "aguayluz-pr:nwps_gauges", producer: "aguayluz-pr",
      source_id: "nwps_gauges", name: "NWPS river gauges", origin: "stream",
      last_success_basis: "RUN_RECEIPT", last_success_at: "2026-11-08T15:47:31Z",
      last_attempt_at: "2026-11-09T15:47:31Z", last_attempt_status: "failure",
      producer_last_package_at: "2026-11-10T00:00:00Z",
    });
    renderAt("/source-monitor/aguayluz-pr%3Anwps_gauges");
    expect(await screen.findByRole("heading", { name: "NWPS river gauges" })).toBeInTheDocument();
    expect(screen.getByText("(run receipt)")).toBeInTheDocument();
    expect(screen.getByText("(failure)")).toBeInTheDocument();
    expect(screen.getByText("source_monitors stream")).toBeInTheDocument();
    expect(screen.getByText(/from the last success$/)).toBeInTheDocument();
  });
});


describe("SourceMonitorDetail back link", () => {
  // A block body: a function returned from beforeEach runs as its teardown, and
  // mockClear returns the mock, which would call it once more after each test.
  beforeEach(() => {
    vi.mocked(federation.entities.MonitoredSources.get).mockClear();
  });

  it("returns to the producer Monitor tab the row was opened from", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockResolvedValue(ROW);
    const { container } = renderAt("/source-monitor/spiderweb-pr%3Anamus", { fromProducer: "spiderweb-pr" });
    // The way back is there before the row has loaded.
    expect(screen.getByRole("status")).toHaveTextContent("Loading source…");
    expect(screen.getByRole("link", { name: "Back to the Spiderweb-PR Monitor tab" }))
      .toHaveAttribute("href", "/spiderweb?tab=sources");
    expect(await screen.findByRole("heading", { name: "NIJ" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the Spiderweb-PR Monitor tab" }))
      .toHaveAttribute("href", "/spiderweb?tab=sources");
    expect(screen.queryByRole("link", { name: /Back to Source Monitor/ })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses Skywatcher's view parameter", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockResolvedValue({ ...ROW, producer: "skywatcher-pr" });
    renderAt("/source-monitor/skywatcher-pr%3Anamus", { fromProducer: "skywatcher-pr" });
    expect(await screen.findByRole("heading", { name: "NIJ" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the Skywatcher-PR Monitor tab" }))
      .toHaveAttribute("href", "/skywatcher?view=sources");
    expect(screen.getByRole("link", { name: "skywatcher-pr" })).toHaveAttribute("href", "/skywatcher?view=sources");
  });

  it("keeps the producer way back when the row is not found", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockImplementation(
      () => Promise.reject(Object.assign(new Error("not found"), { status: 404 })),
    );
    renderAt("/source-monitor/ovnis-pr%3AGONE", { fromProducer: "ovnis-pr" });
    expect(await screen.findByText("Monitored source not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the Ovnis-PR Monitor tab" }))
      .toHaveAttribute("href", "/ovnis?tab=sources");
  });

  it("falls back to the federation view for an unknown producer", async () => {
    vi.mocked(federation.entities.MonitoredSources.get).mockResolvedValue(ROW);
    renderAt("/source-monitor/spiderweb-pr%3Anamus", { fromProducer: "not-a-producer" });
    expect(await screen.findByRole("heading", { name: "NIJ" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Source Monitor" })).toHaveAttribute("href", "/source-monitor");
  });
});

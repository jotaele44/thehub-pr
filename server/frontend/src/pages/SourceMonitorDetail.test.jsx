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

function renderAt(url) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
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
    expect(screen.getByRole("link", { name: "spiderweb-pr" })).toHaveAttribute("href", "/spiderweb");
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

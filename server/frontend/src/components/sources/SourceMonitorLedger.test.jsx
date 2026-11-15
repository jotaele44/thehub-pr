import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { useEntityData } from "@/hooks/useEntityData";
import SourceMonitorLedger from "./SourceMonitorLedger";

vi.mock("@/hooks/useEntityData", () => ({ useEntityData: vi.fn() }));

const NOW = Date.parse("2026-11-08T00:00:00Z");
const ago = (days) => new Date(NOW - days * 86400000).toISOString();

const ROWS = [
  {
    id: "ovnis-pr:SRC-0001", monitor_id: "ovnis-pr:SRC-0001", producer: "ovnis-pr", source_id: "SRC-0001",
    name: "AARO Case Archive", producer_family: "USAF", evidence_tier: "T1", cadence: "yearly",
    cadence_window_seconds: 366 * 86400, status: "active", producer_last_package_at: ago(10),
  },
  {
    id: "moneysweep-pr:usaspending_prime", monitor_id: "moneysweep-pr:usaspending_prime", producer: "moneysweep-pr",
    source_id: "usaspending_prime", name: "usaspending_prime", producer_family: "federal", evidence_tier: null,
    cadence: "weekly", cadence_window_seconds: 7 * 86400, status: "not_active", producer_last_package_at: ago(30),
  },
  {
    id: "aguayluz-pr:nwps_gauges", monitor_id: "aguayluz-pr:nwps_gauges", producer: "aguayluz-pr",
    source_id: "nwps_gauges", name: "NWPS river gauges", producer_family: "HYDROMETEOROLOGY", evidence_tier: null,
    cadence: "realtime", cadence_window_seconds: 7200, status: "unknown", producer_last_package_at: ago(30),
    last_success_basis: "OUTPUT_DERIVED", last_success_at: new Date(NOW - 3600 * 1000).toISOString(), origin: "stream",
  },
];

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname}</div>;
}

function renderLedger(props = {}) {
  return render(
    <MemoryRouter initialEntries={["/source-monitor"]}>
      <Routes>
        <Route path="/source-monitor" element={<SourceMonitorLedger now={NOW} {...props} />} />
        <Route path="/source-monitor/:monitorId" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SourceMonitorLedger", () => {
  let create;
  let update;
  beforeEach(() => {
    create = vi.fn();
    update = vi.fn();
    vi.mocked(useEntityData).mockReturnValue({ rows: ROWS, create, update, saving: false, isLoading: false });
  });

  it("reads the MonitoredSources collection and offers no create or edit affordance", () => {
    renderLedger();
    expect(useEntityData).toHaveBeenCalledWith("MonitoredSources");
    expect(screen.queryByRole("button", { name: /new/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("lists every producer federation-wide, stalest first", () => {
    renderLedger();
    const body = screen.getAllByRole("rowgroup")[1];
    const rows = within(body).getAllByRole("row");
    expect(rows).toHaveLength(3);
    // moneysweep: weekly window, 30 days old -> Stale; ovnis: yearly, 10 days -> Fresh.
    expect(within(rows[0]).getByText("moneysweep-pr")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Stale")).toBeInTheDocument();
    expect(within(rows[0]).getByText("not active")).toBeInTheDocument();
    expect(rows.slice(1).every((r) => within(r).queryByText("Fresh"))).toBe(true);
    expect(screen.getByRole("columnheader", { name: /producer$/i })).toBeInTheDocument();
  });

  it("scopes to one producer and drops the producer column on a producer tab", () => {
    renderLedger({ producer: "ovnis-pr" });
    const body = screen.getAllByRole("rowgroup")[1];
    expect(within(body).getAllByRole("row")).toHaveLength(1);
    expect(screen.getByText("AARO Case Archive")).toBeInTheDocument();
    expect(screen.queryByText("usaspending_prime")).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /^producer$/i })).not.toBeInTheDocument();
  });

  it("opens the read-only detail route on row click, never the edit sheet", () => {
    renderLedger();
    fireEvent.click(screen.getByText("AARO Case Archive"));
    expect(screen.getByTestId("where")).toHaveTextContent("/source-monitor/ovnis-pr%3ASRC-0001");
    expect(update).not.toHaveBeenCalled();
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = renderLedger();
    expect(await axe(container)).toHaveNoViolations();
  });
});


describe("SourceMonitorLedger per-source freshness", () => {
  beforeEach(() => {
    vi.mocked(useEntityData).mockReturnValue({ rows: ROWS, create: vi.fn(), update: vi.fn(), saving: false, isLoading: false });
  });

  it("measures a stream row from its own last success and says so", () => {
    renderLedger({ producer: "aguayluz-pr" });
    const body = screen.getAllByRole("rowgroup")[1];
    const [row] = within(body).getAllByRole("row");
    // The package is 30 days old, but the source succeeded an hour ago.
    expect(within(row).getByText("Fresh")).toBeInTheDocument();
    expect(within(row).getByText("last success · from outputs")).toBeInTheDocument();
  });

  it("labels registry-reader rows as measured from the producer export", () => {
    renderLedger({ producer: "moneysweep-pr" });
    const body = screen.getAllByRole("rowgroup")[1];
    const [row] = within(body).getAllByRole("row");
    expect(within(row).getByText("producer export")).toBeInTheDocument();
  });
});

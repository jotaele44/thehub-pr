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
    last_success_basis: "NOT_RECORDED", last_success_at: null, origin: "stream",
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
  return (
    <>
      <div data-testid="where">{loc.pathname}</div>
      <div data-testid="state">{JSON.stringify(loc.state)}</div>
    </>
  );
}

function tree(props = {}) {
  return (
    <MemoryRouter initialEntries={["/source-monitor"]}>
      <Routes>
        <Route path="/source-monitor" element={<SourceMonitorLedger now={NOW} {...props} />} />
        <Route path="/source-monitor/:monitorId" element={<Where />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderLedger(props = {}) {
  return render(tree(props));
}

// useEntityData answers by collection name: the monitor rows, or the summary.
// `fetching` is the monitor rows' isFetching (the summary is never fetching here).
function serve({ rows = ROWS, summaries = [], fetching = false } = {}) {
  const result = (data, isFetching) => ({
    rows: data, create: vi.fn(), update: vi.fn(), saving: false, isLoading: false, isFetching,
  });
  vi.mocked(useEntityData).mockImplementation((name) => (
    name === "SourceMonitorSummary" ? result(summaries, false) : result(rows, fetching)
  ));
}

const bodyRows = () => within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");

describe("SourceMonitorLedger", () => {
  let create;
  let update;
  beforeEach(() => {
    create = vi.fn();
    update = vi.fn();
    vi.mocked(useEntityData).mockReset();
    vi.mocked(useEntityData).mockImplementation((name) => ({
      rows: name === "MonitoredSources" ? ROWS : [], create, update, saving: false, isLoading: false,
    }));
  });

  it("reads the MonitoredSources collection and offers no create or edit affordance", () => {
    renderLedger();
    expect(useEntityData).toHaveBeenCalledWith("MonitoredSources");
    // EntityLedger and the facet both call it with the collection name alone, so
    // they share one react-query key and one request.
    const calls = vi.mocked(useEntityData).mock.calls.filter(([name]) => name === "MonitoredSources");
    expect(calls.length).toBeGreaterThan(1);
    expect(calls.every((call) => call.length === 1)).toBe(true);
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
    expect(screen.getByTestId("state")).toHaveTextContent("null");
    expect(update).not.toHaveBeenCalled();
  });

  it("tells the detail page which producer tab it was opened from", () => {
    renderLedger({ producer: "ovnis-pr" });
    fireEvent.click(screen.getByText("AARO Case Archive"));
    expect(screen.getByTestId("where")).toHaveTextContent("/source-monitor/ovnis-pr%3ASRC-0001");
    expect(JSON.parse(screen.getByTestId("state").textContent)).toEqual({ fromProducer: "ovnis-pr" });
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = renderLedger();
    expect(await axe(container)).toHaveNoViolations();
  });
});


describe("SourceMonitorLedger per-source freshness", () => {
  beforeEach(() => serve());

  it("measures a stream row from its own last success and says so", () => {
    renderLedger({ producer: "aguayluz-pr" });
    const body = screen.getAllByRole("rowgroup")[1];
    const [row] = within(body).getAllByRole("row");
    // The package is 30 days old, but the source succeeded an hour ago.
    expect(within(row).getByText("Fresh")).toBeInTheDocument();
    expect(within(row).getByText("last success · from outputs")).toBeInTheDocument();
  });

  it("labels rows with no recorded success as measured from the producer export", () => {
    renderLedger({ producer: "moneysweep-pr" });
    const body = screen.getAllByRole("rowgroup")[1];
    const [row] = within(body).getAllByRole("row");
    expect(within(row).getByText("producer export")).toBeInTheDocument();
  });
});


describe("SourceMonitorLedger Family filter", () => {
  beforeEach(() => serve());

  it("offers a Family filter federation-wide and on a producer tab", () => {
    const { unmount } = renderLedger();
    expect(screen.getByRole("combobox", { name: "Family" })).toBeInTheDocument();
    unmount();
    renderLedger({ producer: "ovnis-pr" });
    expect(screen.getByRole("combobox", { name: "Family" })).toBeInTheDocument();
  });

  it("keeps rows that load after the first render visible", () => {
    // The first render has no rows yet, so the filter has no options; it must
    // still exist then, or its state would start undefined and hide every row.
    serve({ rows: [] });
    const { rerender } = renderLedger();
    expect(screen.getByRole("combobox", { name: "Family" })).toBeInTheDocument();
    serve();
    rerender(tree());
    expect(bodyRows()).toHaveLength(3);
  });
});


describe("SourceMonitorLedger list-limit notice", () => {
  const summary = (total) => ({
    id: "source_monitor_summary", total,
    producers: { "ovnis-pr": { count: 40 }, "moneysweep-pr": { count: 1 }, "aguayluz-pr": { count: 1 } },
  });

  it("warns on a producer tab cut short while the hub holds more than the list loads", () => {
    serve({ summaries: [summary(501)] });
    renderLedger({ producer: "ovnis-pr" });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The hub holds 40 sources from ovnis-pr but this tab shows 1: the table loads the first 500 of 501",
    );
  });

  it("stays quiet at the limit, for a producer with every row loaded, and federation-wide", () => {
    serve({ summaries: [summary(500)] });
    const { unmount } = renderLedger({ producer: "ovnis-pr" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    unmount();

    serve({ summaries: [summary(501)] });
    const second = renderLedger({ producer: "moneysweep-pr" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    second.unmount();

    // The Source Monitor page shows its own notice; the federation table adds none.
    vi.mocked(useEntityData).mockClear();
    renderLedger();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(useEntityData).not.toHaveBeenCalledWith("SourceMonitorSummary");
  });

  it("waits for the first rows before comparing them with the summary", () => {
    // The summary can arrive before the rows; until they do, every producer would
    // look cut short. The summary is still requested alongside the rows.
    vi.mocked(useEntityData).mockClear();
    serve({ rows: [], summaries: [summary(501)], fetching: true });
    const { rerender } = renderLedger({ producer: "ovnis-pr" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(useEntityData).toHaveBeenCalledWith("SourceMonitorSummary");

    // A refetch with rows already loaded keeps the notice.
    serve({ summaries: [summary(501)], fetching: true });
    rerender(tree({ producer: "ovnis-pr" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The hub holds 40 sources from ovnis-pr but this tab shows 1");
  });

  it("reads the summary row by its id", () => {
    serve({ summaries: [{ ...summary(501), id: "something_else" }] });
    renderLedger({ producer: "ovnis-pr" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("has no detectable accessibility violations with the notice shown", async () => {
    serve({ summaries: [summary(501)] });
    const { container } = renderLedger({ producer: "ovnis-pr" });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});

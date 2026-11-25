import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import { MemoryRouter } from "react-router-dom";
import { useEntityData } from "@/hooks/useEntityData";
import SourceMonitor from "./SourceMonitor";

vi.mock("@/hooks/useEntityData", () => ({ useEntityData: vi.fn() }));

const ROWS = [
  {
    id: "aguayluz-pr:nwps_gauges", monitor_id: "aguayluz-pr:nwps_gauges", producer: "aguayluz-pr",
    source_id: "nwps_gauges", name: "NWPS river gauges", producer_family: "HYDROMETEOROLOGY", evidence_tier: null,
    cadence: "realtime", cadence_window_seconds: 7200, status: "unknown", origin: "stream",
    producer_last_package_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "moneysweep-pr:usaspending_prime", monitor_id: "moneysweep-pr:usaspending_prime", producer: "moneysweep-pr",
    source_id: "usaspending_prime", name: "usaspending_prime", producer_family: "federal", evidence_tier: null,
    cadence: "weekly", cadence_window_seconds: 7 * 86400, status: "partial", origin: "stream",
    last_success_basis: "NOT_RECORDED", last_success_at: null,
    producer_last_package_at: "2026-10-01T00:00:00Z",
  },
];

function summary(overrides = {}) {
  return {
    id: "source_monitor_summary", schema_version: "prii_source_monitor_v1", generated_at: "2026-11-08T00:00:00Z",
    total: 3, error_count: 1, stream_producers: ["aguayluz-pr", "moneysweep-pr", "skywatcher-pr"],
    producers: {
      "aguayluz-pr": {
        origin: "stream", count: 1, package_created_at: "2026-11-01T00:00:00Z",
        registries: ["config/hydromet_sources.v1.json"], excluded: {}, errors: [],
      },
      "moneysweep-pr": {
        origin: "stream", count: 1, package_created_at: "2026-10-01T00:00:00Z",
        registries: ["reports/source_registry_status.csv"], excluded: {}, errors: [],
      },
      // An expected producer with no stream rows in this aggregate (no package, so
      // no export timestamp either): ingest flags the gap instead of dropping it.
      "centinelas-pr": {
        origin: "stream", count: 0, package_created_at: null,
        registries: [], excluded: {},
        errors: ["reports through the source_monitors stream, but this aggregate has no rows from it"],
      },
      "skywatcher-pr": {
        origin: "stream", count: 1, package_created_at: "2026-11-02T00:00:00Z",
        registries: ["registry/source_registry.yaml"], excluded: {}, errors: [],
      },
      // Not a registered producer, from a legacy summary with no origin: listed,
      // but there is no page to link to.
      "retired-pr": { count: 0, package_created_at: "2026-09-01T00:00:00Z", registries: [], excluded: {}, errors: [] },
    },
    ...overrides,
  };
}

// useEntityData answers by collection name: the summary, or the monitor rows.
function serve({ summaries = [summary()], rows = ROWS } = {}) {
  vi.mocked(useEntityData).mockImplementation((name) => ({
    rows: name === "SourceMonitorSummary" ? summaries : name === "MonitoredSources" ? rows : [],
    create: vi.fn(), update: vi.fn(), saving: false, isLoading: false,
  }));
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/source-monitor"]}>
      <SourceMonitor />
    </MemoryRouter>,
  );
}

// A StatCard: its label and value share the card's root element.
const statCard = (label) => screen.getByText(label).parentElement.parentElement;
const producerTable = () => screen.getAllByRole("table")[0];
const producerRow = (pid) => within(producerTable()).getByText(pid).closest("tr");

describe("SourceMonitor page", () => {
  beforeEach(() => {
    vi.mocked(useEntityData).mockReset();
    serve();
  });

  it("summarizes sources, producers, producer errors and missing export timestamps", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Source Monitor" })).toBeInTheDocument();
    expect(statCard("Monitored sources")).toHaveTextContent("3");
    expect(statCard("Producers")).toHaveTextContent("5");
    expect(statCard("Producer errors")).toHaveTextContent("1");
    expect(statCard("Producer errors")).toHaveTextContent("1 producer(s) affected");
    expect(statCard("No export timestamp")).toHaveTextContent("1");
    expect(within(producerRow("centinelas-pr"))
      .getByText("reports through the source_monitors stream, but this aggregate has no rows from it"))
      .toBeInTheDocument();
    expect(within(producerRow("moneysweep-pr")).getByText("—")).toBeInTheDocument();
    expect(screen.getByText((_, el) => el?.tagName === "P"
      && /by hub ingest from the source_monitors stream\.$/.test(el.textContent))).toBeInTheDocument();
    expect(screen.queryByText(/hub source-monitor/)).not.toBeInTheDocument();
  });

  it("reads every producer from its stream and labels a legacy summary entry", () => {
    renderPage();
    for (const pid of ["aguayluz-pr", "moneysweep-pr", "centinelas-pr", "skywatcher-pr"]) {
      expect(within(producerRow(pid)).getByText("source_monitors stream")).toHaveAttribute("data-origin", "stream");
    }
    // A summary entry without an origin predates ADR 0013's completion.
    expect(within(producerRow("retired-pr")).getByText("legacy registry reader"))
      .toHaveAttribute("data-origin", "hub_adapter");
  });

  it("links each registered producer to its page's Monitor tab", () => {
    renderPage();
    expect(screen.getByRole("link", { name: "aguayluz-pr" })).toHaveAttribute("href", "/aguayluz?tab=sources");
    expect(screen.getByRole("link", { name: "moneysweep-pr" })).toHaveAttribute("href", "/moneysweep?tab=sources");
    expect(screen.getByRole("link", { name: "centinelas-pr" })).toHaveAttribute("href", "/centinelas?tab=sources");
    // Skywatcher keeps its tab in ?view=.
    expect(screen.getByRole("link", { name: "skywatcher-pr" })).toHaveAttribute("href", "/skywatcher?view=sources");
    expect(screen.queryByRole("link", { name: "retired-pr" })).not.toBeInTheDocument();
    expect(producerRow("retired-pr")).toBeInTheDocument();
  });

  it("warns when the hub holds more sources than the table loads", () => {
    serve({ summaries: [summary({ total: 501 })] });
    renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The hub holds 501 monitored sources but this table loads the first 500.",
    );
  });

  it("does not warn at the limit", () => {
    serve({ summaries: [summary({ total: 500 })] });
    renderPage();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders only the table until a summary exists", () => {
    serve({ summaries: [] });
    renderPage();
    expect(screen.queryByText("Monitored sources")).not.toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByText("NWPS river gauges")).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    serve({ summaries: [summary({ total: 501 })] });
    const { container } = renderPage();
    expect(await axe(container)).toHaveNoViolations();
  });
});

import React from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import IosStart from "./IosStart";
import readiness from "@/data/iosStartReadiness.json";

describe("IosStart", () => {
  it("renders exactly seven federation apps from the bounded readiness receipt", () => {
    render(<IosStart />);
    expect(readiness.records).toHaveLength(7);
    for (const record of readiness.records) {
      expect(screen.getByLabelText(`${record.app_name} iOS readiness`)).toBeInTheDocument();
    }
  });

  it("keeps ZIP archives classified as noncanonical references", () => {
    render(<IosStart />);
    expect(screen.getAllByText("NONCANONICAL_REFERENCE").length).toBeGreaterThan(0);
    expect(screen.getByText(/ZIP archives are reference material only/i)).toBeInTheDocument();
    expect(screen.queryByText(/canonical baseline from zip/i)).not.toBeInTheDocument();
  });

  it("surfaces blocker states without collapsing the provisional desktop base", () => {
    render(<IosStart />);
    const aguayluz = screen.getByLabelText("AguaYLuz iOS readiness");
    expect(within(aguayluz).getByText("PROVISIONAL")).toBeInTheDocument();
    expect(within(aguayluz).getByText("PROVISIONAL DESKTOP BASE")).toBeInTheDocument();
    expect(within(aguayluz).getByText(/Remote main drift observed/i)).toBeInTheDocument();
  });

  it("preserves Skywatcher approximate screenshot semantics and rejects exact-coordinate wording", () => {
    render(<IosStart />);
    expect(screen.getAllByText(/ICON_DERIVED_APPROX/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/SCREENSHOT_BBOX_DERIVED/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not exact aircraft coordinates/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/exact ADS-B position/i)).not.toBeInTheDocument();
  });

  it("keeps blocker arithmetic closed", () => {
    const counts = readiness.blocker_arithmetic;
    const classified = counts.PASS + counts.OPEN + counts.BLOCKED + counts.PROVISIONAL + counts.UNRESOLVED;
    expect(classified).toBe(counts.total);
    expect(readiness.records).toHaveLength(counts.total);
  });
});

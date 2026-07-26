import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AppCenter, { APP_CENTER_APPS } from "./AppCenter";

describe("AppCenter", () => {
  it("renders exactly seven native application names without repository suffixes", () => {
    render(<AppCenter />);
    expect(APP_CENTER_APPS).toHaveLength(7);
    for (const app of APP_CENTER_APPS) {
      expect(screen.getByText(app.name)).toBeInTheDocument();
    }
    expect(screen.queryByText(/-pr/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/PRII-/i)).not.toBeInTheDocument();
  });

  it("keeps all lifecycle mutations disabled and shows five readiness dimensions", () => {
    render(<AppCenter />);
    expect(screen.getByRole("button", { name: /install all recommended/i })).toBeDisabled();
    expect(screen.getAllByRole("button", { name: /^(install|open)$/i })).toHaveLength(7);
    for (const button of screen.getAllByRole("button", { name: /^(install|open)$/i })) {
      expect(button).toBeDisabled();
    }
    for (const label of ["Install", "Configuration", "Data", "Federation", "Production"]) {
      expect(screen.getAllByText(label, { selector: "dt" })).toHaveLength(7);
    }
  });
});

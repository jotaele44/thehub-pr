import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AppCenter, { APP_CENTER_APPS, loadAppInventory } from "./AppCenter";

const API_INVENTORY = APP_CENTER_APPS.map((app) => ({
  appId: app.appId,
  displayName: app.name,
  profile: app.profile.toLowerCase().replaceAll("-", "_").replaceAll(" ", "_"),
  lifecycle: app.lifecycle.toLowerCase(),
  readiness: {
    install: app.appId === "thehub" ? "installed" : "absent",
    configuration: "incomplete",
    data: "empty",
    federation: "unknown",
    production: "not_assessed",
  },
}));
const PENDING_LOADER = () => new Promise(() => {});

describe("AppCenter", () => {
  it("renders exactly seven native application names without repository suffixes", () => {
    render(<AppCenter inventoryLoader={PENDING_LOADER} />);
    expect(APP_CENTER_APPS).toHaveLength(7);
    for (const app of APP_CENTER_APPS) {
      expect(screen.getByText(app.name)).toBeInTheDocument();
      expect(screen.getByRole("img", { name: `${app.name} icon` }))
        .toHaveAttribute("data-native-icon", app.appId);
    }
    expect(screen.queryByText(/-pr/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/PRII-/i)).not.toBeInTheDocument();
  });

  it("keeps all lifecycle mutations disabled and shows five readiness dimensions", () => {
    render(<AppCenter inventoryLoader={PENDING_LOADER} />);
    expect(screen.getByRole("button", { name: /install all recommended/i })).toBeDisabled();
    expect(screen.getAllByRole("button", { name: /^(install|open)$/i })).toHaveLength(7);
    for (const button of screen.getAllByRole("button", { name: /^(install|open)$/i })) {
      expect(button).toBeDisabled();
    }
    for (const label of ["Install", "Configuration", "Data", "Federation", "Production"]) {
      expect(screen.getAllByText(label, { selector: "dt" })).toHaveLength(7);
    }
  });

  it("hydrates from the authenticated read-only inventory contract", async () => {
    const loader = vi.fn().mockResolvedValue(
      await loadAppInventory({
        storage: { getItem: () => "native-session" },
        fetchImpl: vi.fn().mockResolvedValue({
          ok: true,
          json: async () => API_INVENTORY,
        }),
      }),
    );
    render(<AppCenter inventoryLoader={loader} />);
    expect(await screen.findByRole("status")).toHaveTextContent(/connected.*read-only/i);
    expect(loader).toHaveBeenCalledOnce();
    expect(screen.getAllByText("Installed")).toHaveLength(1);
  });

  it("falls back safely when the native manager is unavailable", async () => {
    render(<AppCenter inventoryLoader={() => Promise.reject(new Error("offline"))} />);
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/unavailable.*safe read-only/i);
    });
    expect(screen.getByRole("button", { name: /install all recommended/i })).toBeDisabled();
    expect(APP_CENTER_APPS).toHaveLength(7);
  });
});

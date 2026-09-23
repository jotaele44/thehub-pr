import { describe, expect, it } from "vitest";
import {
  GIS_INTERACTION_CAPABILITIES,
  assertInteractionCapability,
  assertInteractionEvidence,
  deriveMapReadiness,
} from "./interactionCapabilities";

describe("GIS interaction capability contract", () => {
  it("preserves the seven recording-observed capability families", () => {
    const observed = Object.values(GIS_INTERACTION_CAPABILITIES).filter((item) => item.evidence === "OBSERVED");
    expect(new Set(observed.map((item) => item.family))).toEqual(
      new Set(["map", "basemap", "layers", "search", "draw", "measure", "print"]),
    );
  });

  it("fails closed for unknown capabilities and evidence classes", () => {
    expect(() => assertInteractionCapability("unknown")).toThrow(/Unknown GIS interaction capability/);
    expect(() => assertInteractionEvidence("INFERRED")).toThrow(/Unknown GIS interaction evidence/);
  });

  it("keeps overlay readiness independent from basemap readiness", () => {
    expect(deriveMapReadiness({ basemapStatus: "READY", overlayStatuses: ["READY"] })).toMatchObject({
      ready: true,
      degraded: false,
      overlaysReady: true,
    });
    expect(deriveMapReadiness({ basemapStatus: "ERROR", overlayStatuses: ["READY"] })).toMatchObject({
      ready: true,
      degraded: true,
      overlaysReady: true,
    });
  });

  it("does not promote failed overlays merely because the basemap is ready", () => {
    expect(deriveMapReadiness({ basemapStatus: "READY", overlayStatuses: ["ERROR"] })).toMatchObject({
      ready: false,
      degraded: false,
      overlaysReady: false,
    });
  });
});

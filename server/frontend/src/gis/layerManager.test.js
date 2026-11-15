import { describe, expect, it } from "vitest";
import { normalizeLayerDisplayState, normalizeLayerState, removeActiveLayer, reorderActiveLayers } from "./layerManager";

const base = {
  mode: "2d",
  view: { center: { lon: -66.4, lat: 18.22 }, groundResolutionM: 25 },
  activeLayerIds: ["layer-a", "layer-b"],
  layerState: {
    "layer-a": { visible: true, opacity: 1 },
    "layer-b": { visible: false, opacity: 0.4 },
  },
};

describe("canonical layer manager", () => {
  it("normalizes valid display state without synthesizing identity", () => {
    expect(normalizeLayerDisplayState({ visible: true, opacity: "0.5", label: "Parcels" })).toEqual({
      visible: true,
      opacity: 0.5,
      label: "Parcels",
    });
  });

  it("fails closed on invalid visibility and opacity", () => {
    expect(() => normalizeLayerDisplayState({ visible: "true", opacity: 0.5 })).toThrow(/visible must be boolean/);
    expect(() => normalizeLayerDisplayState({ visible: true, opacity: Number.NaN })).toThrow(/opacity must be finite/);
    expect(() => normalizeLayerDisplayState({ visible: true, opacity: -0.01 })).toThrow(/within \[0,1\]/);
    expect(() => normalizeLayerDisplayState({ visible: true, opacity: 1.01 })).toThrow(/within \[0,1\]/);
  });

  it("rejects state for inactive layers", () => {
    expect(() => normalizeLayerState(["layer-a"], { "layer-b": { visible: true, opacity: 1 } })).toThrow(/inactive layerId/);
  });

  it("reorders only an exact permutation of the active stable IDs", () => {
    expect(reorderActiveLayers(base, ["layer-b", "layer-a"]).activeLayerIds).toEqual(["layer-b", "layer-a"]);
    expect(() => reorderActiveLayers(base, ["layer-a", "layer-a"])).toThrow(/duplicate stable IDs/);
    expect(() => reorderActiveLayers(base, ["layer-a"])).toThrow(/preserve active layer count/);
    expect(() => reorderActiveLayers(base, ["layer-a", "layer-c"])).toThrow(/foreign or missing stable IDs/);
  });

  it("removes a whole layer and its state without disturbing retained layers", () => {
    const next = removeActiveLayer(base, "layer-a");
    expect(next.activeLayerIds).toEqual(["layer-b"]);
    expect(next.layerState).toEqual({ "layer-b": { visible: false, opacity: 0.4 } });
    expect(() => removeActiveLayer(next, "layer-a")).toThrow(/inactive layerId/);
  });

  it("does not treat duplicate display names as duplicate identity", () => {
    const states = normalizeLayerState(["parcel-a", "parcel-b"], {
      "parcel-a": { visible: true, opacity: 1, title: "Parcels" },
      "parcel-b": { visible: true, opacity: 1, title: "Parcels" },
    });
    expect(Object.keys(states)).toEqual(["parcel-a", "parcel-b"]);
  });
});

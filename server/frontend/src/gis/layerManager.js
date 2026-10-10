import { createCanonicalMapState } from "./contracts";

function assertLayerId(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    throw new Error("layerId requires a non-empty stable identifier");
  }
  return String(value);
}

export function normalizeLayerDisplayState(input = {}) {
  if (typeof input.visible !== "boolean") throw new Error("layer visible must be boolean");
  const opacity = Number(input.opacity);
  if (!Number.isFinite(opacity)) throw new Error("layer opacity must be finite");
  if (opacity < 0 || opacity > 1) throw new Error("layer opacity must be within [0,1]");
  return Object.freeze({ ...input, visible: input.visible, opacity });
}

export function normalizeLayerState(activeLayerIds = [], layerState = {}) {
  const active = new Set(activeLayerIds);
  const normalized = {};
  for (const [layerId, state] of Object.entries(layerState)) {
    if (!active.has(layerId)) throw new Error(`layerState references inactive layerId: ${layerId}`);
    normalized[layerId] = normalizeLayerDisplayState(state);
  }
  return Object.freeze(normalized);
}

export function reorderActiveLayers(stateInput, nextOrder) {
  const state = createCanonicalMapState(stateInput);
  const current = state.activeLayerIds;
  const next = (nextOrder || []).map(assertLayerId);
  if (new Set(next).size !== next.length) throw new Error("layer reorder contains duplicate stable IDs");
  if (next.length !== current.length) throw new Error("layer reorder must preserve active layer count");
  const currentSet = new Set(current);
  if (next.some((id) => !currentSet.has(id))) throw new Error("layer reorder contains foreign or missing stable IDs");
  return createCanonicalMapState({ ...state, activeLayerIds: next });
}

export function removeActiveLayer(stateInput, layerIdInput) {
  const state = createCanonicalMapState(stateInput);
  const layerId = assertLayerId(layerIdInput);
  if (!state.activeLayerIds.includes(layerId)) throw new Error(`cannot remove inactive layerId: ${layerId}`);
  const activeLayerIds = state.activeLayerIds.filter((id) => id !== layerId);
  const layerState = Object.fromEntries(Object.entries(state.layerState).filter(([id]) => id !== layerId));
  return createCanonicalMapState({ ...state, activeLayerIds, layerState });
}

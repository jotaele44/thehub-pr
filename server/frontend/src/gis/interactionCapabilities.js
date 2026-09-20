export const GIS_INTERACTION_EVIDENCE = Object.freeze(["OBSERVED", "SUPPORTED_EXTENSION", "PROGRAM_SPECIFIC"]);

export const GIS_INTERACTION_CAPABILITIES = Object.freeze({
  "map.navigation": { family: "map", evidence: "OBSERVED" },
  "basemap.select": { family: "basemap", evidence: "OBSERVED" },
  "layers.manage": { family: "layers", evidence: "OBSERVED" },
  "search.multi_mode": { family: "search", evidence: "OBSERVED" },
  "draw.geometry": { family: "draw", evidence: "OBSERVED" },
  "measure.geometry": { family: "measure", evidence: "OBSERVED" },
  "print.layout": { family: "print", evidence: "OBSERVED" },
  "map.3d": { family: "map", evidence: "SUPPORTED_EXTENSION" },
  "workspace.customize": { family: "workspace", evidence: "SUPPORTED_EXTENSION" },
});

export function assertInteractionCapability(id) {
  const capability = GIS_INTERACTION_CAPABILITIES[id];
  if (!capability) throw new Error(`Unknown GIS interaction capability: ${id}`);
  return capability;
}

export function assertInteractionEvidence(evidence) {
  if (!GIS_INTERACTION_EVIDENCE.includes(evidence)) {
    throw new Error(`Unknown GIS interaction evidence: ${evidence}`);
  }
  return evidence;
}

export function deriveMapReadiness({ basemapStatus, overlayStatuses = [] }) {
  const overlaysReady = overlayStatuses.every((status) => status === "READY");
  return Object.freeze({
    basemapStatus,
    overlayStatuses: [...overlayStatuses],
    overlaysReady,
    ready: overlaysReady,
    degraded: basemapStatus !== "READY" && overlaysReady,
  });
}

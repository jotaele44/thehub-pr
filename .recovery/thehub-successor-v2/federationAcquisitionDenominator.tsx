export type DenominatorStatus = "PASS" | "NOT_APPLICABLE";
export type AcquisitionStatus = "PASS" | "OPEN" | "BLOCKED" | "NOT_APPLICABLE";

export interface FederationAcquisitionRow {
  app: "Spiderweb" | "MoneySweep" | "AguaYLuz" | "Skywatcher" | "OVNIS" | "Centinelas" | "TheHub";
  denominatorKind: string;
  denominatorCount: number | null;
  denominatorStatus: DenominatorStatus;
  terminalCount: number | null;
  acquisitionStatus: AcquisitionStatus;
  credentialDeferredCount: number;
  renderedRunId: number;
  renderedHead: string;
  renderedArtifactSha256: string;
  renderedDesktop393430: "PASS";
  facts: Record<string, number | string | boolean | null>;
  note: string;
}

export const FEDERATION_ACQUISITION_ROWS: FederationAcquisitionRow[] = [
  {
    app: "Spiderweb",
    denominatorKind: "LOCATION_QUERY_PROVIDER_LANES",
    denominatorCount: 16,
    denominatorStatus: "PASS",
    terminalCount: 16,
    acquisitionStatus: "OPEN",
    credentialDeferredCount: 2,
    renderedRunId: 37658188295,
    renderedHead: "ef4be84765525fae3aaee40d473029aa88d1c4b9",
    renderedArtifactSha256: "e22c419d67de161f525e3519abc9db4b7e5ed8fea9b3418d07686815b381ef3a",
    renderedDesktop393430: "PASS",
    facts: {
      ready: 3,
      providerBindingOpen: 1,
      readyWithCredentials: 2,
      readySpecialized: 6,
      resolverOnly: 4,
      registrySourceCommit: "71a345fb9bebaa411761f6d61e6e736cca499b80",
      providerRegistryBlob: "8741fe151b3887a9ef5ba1d8819f7a9480b3de01",
      sourceBindingsBlob: "78839a5fa15554c85ed48fb50bf3a02fa279fa53",
    },
    note: "The 16-lane denominator is closed; credential, resolver-only, and provider-binding residue remains acquisition-open.",
  },
  {
    app: "MoneySweep",
    denominatorKind: "SOURCE_REGISTRY_HISTORICAL_BASELINE",
    denominatorCount: 167,
    denominatorStatus: "PASS",
    terminalCount: null,
    acquisitionStatus: "OPEN",
    credentialDeferredCount: 0,
    renderedRunId: 37658844467,
    renderedHead: "a46566ad3b80a1c3890685252af72dd2bc76ad85",
    renderedArtifactSha256: "474dd0af3cbb16a2001997b6e371ff73cf5b065e2010c51d3c6982aebf13ac0c",
    renderedDesktop393430: "PASS",
    facts: {
      rawNormalizedCanonical: true,
      sourceProvenanceRequired: true,
      terminalManifestationClassificationRecovered: false,
    },
    note: "The 167-source historical registry denominator is retained; complete terminal manifestation acquisition has not been reconstructed.",
  },
  {
    app: "AguaYLuz",
    denominatorKind: "SOURCE_VECTORS_HISTORICAL_SNAPSHOT",
    denominatorCount: 8,
    denominatorStatus: "PASS",
    terminalCount: 8,
    acquisitionStatus: "OPEN",
    credentialDeferredCount: 0,
    renderedRunId: 37659465324,
    renderedHead: "d143dd218b52dbfc32c91876583441865edea10c",
    renderedArtifactSha256: "baf50944924b2478c544210eb5862d4b8c893f316f9f4f50904d0c1bcea5cbd7",
    renderedDesktop393430: "PASS",
    facts: {
      historicalLoaded: 7,
      historicalEmpty: 1,
      currentRefreshRequired: true,
      historicalToCurrentSubstitution: "DENY",
    },
    note: "Historical 8-vector arithmetic is closed, but current authoritative reacquisition/freshness remains open.",
  },
  {
    app: "Skywatcher",
    denominatorKind: "ACQUISITION_PROVIDER_FAMILIES",
    denominatorCount: 6,
    denominatorStatus: "PASS",
    terminalCount: null,
    acquisitionStatus: "OPEN",
    credentialDeferredCount: 1,
    renderedRunId: 37660263966,
    renderedHead: "5fbeb64f8ff5b41a2a8e2162624429ceee7f04ba",
    renderedArtifactSha256: "b8b6209a83872599f6fa5cc598ccb9f680fb587b70738bda9fd688109886799b",
    renderedDesktop393430: "PASS",
    facts: {
      cneos: true,
      horizons: true,
      spaceTrack: true,
      nasaJsc: true,
      noaa: true,
      aircraft: true,
      rlsmSeparatePackageResidue: 1,
      proximityIdentity: "DENY",
    },
    note: "Six provider families are enumerated; live acquisition and RLSM remain open, with Space-Track credentials deferred.",
  },
  {
    app: "OVNIS",
    denominatorKind: "ARTIFACT_REFERENCES",
    denominatorCount: 244,
    denominatorStatus: "PASS",
    terminalCount: 0,
    acquisitionStatus: "OPEN",
    credentialDeferredCount: 0,
    renderedRunId: 37659504996,
    renderedHead: "ae4c9d36a46968f21b2bb4cb429de9e5c077684c",
    renderedArtifactSha256: "c2fb8fc3f14f1af95437400e853029c9c502657eed450094c8a20f3ae7b9c8a6",
    renderedDesktop393430: "PASS",
    facts: {
      artifactReferences: 244,
      verifiedByteArtifacts: 0,
      promotionRule: "HASH_SIZE_TIME_AUTHORITY_REQUIRED",
    },
    note: "Reference denominator is closed; byte acquisition/verification remains fully open.",
  },
  {
    app: "Centinelas",
    denominatorKind: "CONFIGURED_FEEDS",
    denominatorCount: 60,
    denominatorStatus: "PASS",
    terminalCount: 60,
    acquisitionStatus: "BLOCKED",
    credentialDeferredCount: 0,
    renderedRunId: 37660348727,
    renderedHead: "8a9b9041ba0628227b27fe67026146af4418b34b",
    renderedArtifactSha256: "096bc30a804cf5ed30af54272b46356050790e009f576230cc87ccf621187d82",
    renderedDesktop393430: "PASS",
    facts: {
      success: 54,
      empty: 1,
      externalFailure: 5,
      recoveredSourceIdentities: 87,
      historicalDatabase: "UNAVAILABLE_NO_DUMP",
    },
    note: "All 60 feed attempts are terminally classified, but five external failures block acquisition certification.",
  },
  {
    app: "TheHub",
    denominatorKind: "PRODUCER_ACQUISITION",
    denominatorCount: null,
    denominatorStatus: "NOT_APPLICABLE",
    terminalCount: null,
    acquisitionStatus: "NOT_APPLICABLE",
    credentialDeferredCount: 0,
    renderedRunId: 37659519663,
    renderedHead: "c96797d27258615434d6f1a8658a7f870f353d7a",
    renderedArtifactSha256: "7b800fe7a1f5f4e71b506b66f0834c13934e7d933f4fda929f0cad39fce8a305",
    renderedDesktop393430: "PASS",
    facts: {
      producerTruthAuthority: false,
      receiptConsumerOnly: true,
    },
    note: "TheHub has no producer-acquisition authority; it consumes exact producer receipts.",
  },
];

const SHA256 = /^[0-9a-f]{64}$/;
const HEAD = /^[0-9a-f]{40}$/;

export function evaluateFederationAcquisition(rows = FEDERATION_ACQUISITION_ROWS) {
  const residue: string[] = [];
  if (rows.length !== 7 || new Set(rows.map(row => row.app)).size !== 7) {
    residue.push("SEVEN_APP_DENOMINATOR_INVALID");
  }
  for (const row of rows) {
    if (row.denominatorStatus === "PASS" && (!row.denominatorCount || row.denominatorCount <= 0)) {
      residue.push(`${row.app}:DENOMINATOR_COUNT_INVALID`);
    }
    if (row.terminalCount !== null && row.denominatorCount !== null && row.terminalCount > row.denominatorCount) {
      residue.push(`${row.app}:TERMINAL_COUNT_EXCEEDS_DENOMINATOR`);
    }
    if (!Number.isInteger(row.renderedRunId) || row.renderedRunId <= 0) residue.push(`${row.app}:RENDER_RUN_INVALID`);
    if (!HEAD.test(row.renderedHead)) residue.push(`${row.app}:RENDER_HEAD_INVALID`);
    if (!SHA256.test(row.renderedArtifactSha256)) residue.push(`${row.app}:RENDER_HASH_INVALID`);
    if (row.renderedDesktop393430 !== "PASS") residue.push(`${row.app}:RENDER_OPEN`);
  }
  const denominatorClosed = rows.every(row => row.denominatorStatus === "PASS" || row.denominatorStatus === "NOT_APPLICABLE");
  const renderedClosed = rows.every(row => row.renderedDesktop393430 === "PASS");
  const acquisitionCertified = rows.every(row => row.acquisitionStatus === "PASS" || row.acquisitionStatus === "NOT_APPLICABLE");
  return {
    rowCount: rows.length,
    denominatorClosed,
    renderedClosed,
    acquisitionCertified,
    infrastructureMigrationEligible: denominatorClosed && renderedClosed && acquisitionCertified && residue.length === 0,
    residue,
    openApps: rows.filter(row => row.acquisitionStatus === "OPEN").map(row => row.app),
    blockedApps: rows.filter(row => row.acquisitionStatus === "BLOCKED").map(row => row.app),
    credentialDeferredCount: rows.reduce((sum,row)=>sum+row.credentialDeferredCount,0),
  };
}

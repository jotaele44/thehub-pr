export const IOS_READY_STATES = {
  READY_FOR_FIRST_SURFACE: "READY_FOR_FIRST_SURFACE",
  FIRST_SURFACE_STARTED: "FIRST_SURFACE_STARTED",
  BLOCKED_BY_DESKTOP_GAP: "BLOCKED_BY_DESKTOP_GAP",
  PROVISIONAL_DESKTOP_BASE: "PROVISIONAL_DESKTOP_BASE",
  UNRESOLVED: "UNRESOLVED",
};

export const IOS_REFERENCE_STATES = {
  NONCANONICAL_REFERENCE: "NONCANONICAL_REFERENCE",
  REFERENCE_ONLY: "REFERENCE_ONLY",
  PORTABLE_UI_PATTERN: "PORTABLE_UI_PATTERN",
  STALE: "STALE",
  CONFLICTING: "CONFLICTING",
  REJECTED: "REJECTED",
};

export const MONEY_SWEEP_CONTINUATION_RECEIPT = {
  runId: "20260901T022813Z_moneysweep_prasa_contract_closure",
  receiptPath:
    "reports/moneysweep-live-readiness/20260901T022813Z_moneysweep_prasa_contract_closure/thehub_moneysweep_prasa_contract_closure_pickup_receipt.json",
  moneysweepReceiptPath:
    "../moneysweep-pr/reports/live-readiness/20260901T022813Z_moneysweep_prasa_contract_closure/moneysweep_prasa_contract_closure_receipt.json",
  packageId: "pkg_9642c2a411343e9c0c20891ac84f4f08",
  resultState: "HUB_AGGREGATE_PASS_FEDERATION_LIVE_READINESS_PROVISIONAL",
  moneysweepResultState: "PROVISIONAL_LIVE_READINESS_PRASA_CLOSED_HUD_DRGR_PRESERVED",
  verifiedAtUtc: "2026-09-01T02:28:13Z",
  blockerCounts: {
    pass: 0,
    open: 0,
    blocked: 0,
    provisional: 1,
    unresolved: 1,
  },
  closedEvidence: [
    {
      sourceId: "prasa",
      label: "PRASA contract evidence",
      state: "FOUND_STRUCTURED_FROM_AUTHORITY_TRANSITION_PDF",
      rows: 642,
      reason:
        "ACT agency 163 PRASA transition contract PDF parsed into 642 contract rows and 309 vendor master rows.",
    },
  ],
  partialBlockers: [
    {
      sourceId: "hud_drgr_authorized",
      label: "HUD authorized DRGR export",
      state: "PARTIAL_UNRESOLVED",
      reviewedArtifactCount: 3,
      reason:
        "No non-empty authorized DRGR export was found; HUD HCV rows and public CDBG files are not authorized DRGR exports.",
    },
  ],
};

const BASE_IOS_READINESS = {
  thehub: {
    iosStartState: IOS_READY_STATES.FIRST_SURFACE_STARTED,
    certificationState: "PROVISIONAL",
    canonicalReceipts: ["reports/ios_start_scope_20260829.md"],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 1, open: 0, blocked: 0, provisional: 1, unresolved: 0 },
    blockers: [],
  },
  ovnis: {
    iosStartState: IOS_READY_STATES.READY_FOR_FIRST_SURFACE,
    certificationState: "PROVISIONAL",
    canonicalReceipts: [],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 0, open: 0, blocked: 0, provisional: 1, unresolved: 0 },
    blockers: [],
  },
  centinelas: {
    iosStartState: IOS_READY_STATES.READY_FOR_FIRST_SURFACE,
    certificationState: "PASS",
    canonicalReceipts: [],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 1, open: 0, blocked: 0, provisional: 0, unresolved: 0 },
    blockers: [],
  },
  skywatcher: {
    iosStartState: IOS_READY_STATES.BLOCKED_BY_DESKTOP_GAP,
    certificationState: "PROVISIONAL",
    canonicalReceipts: [],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 0, open: 0, blocked: 1, provisional: 1, unresolved: 1 },
    blockers: [
      {
        sourceId: "fr24_approximate_geometry",
        label: "FR24 approximate geometry",
        state: "PROVISIONAL",
        reason:
          "Skywatcher positions remain ICON_DERIVED_APPROX, APPROXIMATE, SCREENSHOT_BBOX_DERIVED, and REVIEW_BOUND_IDENTITY; they are not exact ADS-B coordinates.",
      },
    ],
  },
  aguayluz: {
    iosStartState: IOS_READY_STATES.PROVISIONAL_DESKTOP_BASE,
    certificationState: "PROVISIONAL",
    canonicalReceipts: [],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 0, open: 0, blocked: 0, provisional: 1, unresolved: 0 },
    blockers: [],
  },
  spiderweb: {
    iosStartState: IOS_READY_STATES.READY_FOR_FIRST_SURFACE,
    certificationState: "PASS",
    canonicalReceipts: [],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: { pass: 1, open: 0, blocked: 0, provisional: 0, unresolved: 0 },
    blockers: [],
  },
};

export const IOS_READINESS_BY_APP = {
  ...BASE_IOS_READINESS,
  moneysweep: {
    iosStartState: IOS_READY_STATES.BLOCKED_BY_DESKTOP_GAP,
    certificationState: "PROVISIONAL",
    canonicalReceipts: [
      MONEY_SWEEP_CONTINUATION_RECEIPT.receiptPath,
      MONEY_SWEEP_CONTINUATION_RECEIPT.moneysweepReceiptPath,
    ],
    noncanonicalReferences: [IOS_REFERENCE_STATES.NONCANONICAL_REFERENCE],
    blockerCounts: MONEY_SWEEP_CONTINUATION_RECEIPT.blockerCounts,
    blockers: MONEY_SWEEP_CONTINUATION_RECEIPT.partialBlockers,
    closedEvidence: MONEY_SWEEP_CONTINUATION_RECEIPT.closedEvidence,
    receipt: MONEY_SWEEP_CONTINUATION_RECEIPT,
  },
};

export function withIosReadiness(apps) {
  return apps.map((app) => ({
    ...app,
    iosReadiness: IOS_READINESS_BY_APP[app.appId] || {
      iosStartState: IOS_READY_STATES.UNRESOLVED,
      certificationState: "UNRESOLVED",
      canonicalReceipts: [],
      noncanonicalReferences: [],
      blockerCounts: { pass: 0, open: 0, blocked: 0, provisional: 0, unresolved: 1 },
      blockers: [],
    },
  }));
}

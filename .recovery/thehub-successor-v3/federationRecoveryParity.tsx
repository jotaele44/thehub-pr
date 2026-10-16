export type ParityState = "PASS" | "NOT_APPLICABLE" | "OPEN";
export type HistoricalRowsState = "PASS" | "UNAVAILABLE_NO_DUMP" | "NOT_PROVEN" | "NOT_APPLICABLE_NO_SERVER_DB";
export type RenderedByteIdentityState = "PASS";

export interface FederationRecoveryParityRow {
  app: "Spiderweb" | "MoneySweep" | "AguaYLuz" | "Skywatcher" | "OVNIS" | "Centinelas" | "TheHub";
  producerRunId: number;
  producerHead: string;
  artifactSha256: string;
  testsPassed: number;
  auth: ParityState;
  acl: ParityState;
  dbSchema: ParityState;
  dbSchemaTables: number | null;
  historicalRows: HistoricalRowsState;
  sourceContract: ParityState;
  authoritativeAcquisition: ParityState;
  renderedDesktop393430: ParityState;
  renderedRunId: number;
  renderedHead: string;
  renderedArtifactSha256: string;
  renderedApplicationByteIdentity: RenderedByteIdentityState;
  note: string;
}

const SHA = /^[0-9a-f]{64}$/;
const HEAD = /^[0-9a-f]{40}$/;

export const FEDERATION_RECOVERY_PARITY_ROWS: FederationRecoveryParityRow[] = [
  {
    app: "Spiderweb",
    producerRunId: 37662519149,
    producerHead: "8496b394ce692ed355bbb5c510ed3d80d02488f5",
    artifactSha256: "a963ba1fdd8215cdf6f48728588d2d2edeac36a4077a114cc859748c4869fb05",
    testsPassed: 154,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 9,
    historicalRows: "NOT_PROVEN",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 37662519149,
    renderedHead: "8496b394ce692ed355bbb5c510ed3d80d02488f5",
    renderedArtifactSha256: "a963ba1fdd8215cdf6f48728588d2d2edeac36a4077a114cc859748c4869fb05",
    renderedApplicationByteIdentity: "PASS",
    note: "Eight protected non-auth mutation vectors; ACL/read/owner/admin guards; exact nine-table schema; source-equivalence and rendered QA closed.",
  },
  {
    app: "MoneySweep",
    producerRunId: 38948159159,
    producerHead: "646982f0299be5aeb0cd96153f54782ca3ff8dfe",
    artifactSha256: "e92c7b11602ede553202340cbfcfdf14d0aaf5e4179d4ba840d56db950859b64",
    testsPassed: 90,
    auth: "NOT_APPLICABLE",
    acl: "NOT_APPLICABLE",
    dbSchema: "PASS",
    dbSchemaTables: 5,
    historicalRows: "NOT_PROVEN",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 38948159159,
    renderedHead: "646982f0299be5aeb0cd96153f54782ca3ff8dfe",
    renderedArtifactSha256: "e92c7b11602ede553202340cbfcfdf14d0aaf5e4179d4ba840d56db950859b64",
    renderedApplicationByteIdentity: "PASS",
    note: "Exactly five recovered GET handlers and zero mutation handlers; write auth/ACL is explicitly not applicable; rendered QA is bound into successor v3.",
  },
  {
    app: "AguaYLuz",
    producerRunId: 37540391891,
    producerHead: "84cdadebbbcc3a8a28925b37499292056acba496",
    artifactSha256: "d08a5f4d95137b14b74f98e4d89c90233ae710bb7f1eee5fa13470959ad1caac",
    testsPassed: 152,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 44,
    historicalRows: "NOT_PROVEN",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 37659465324,
    renderedHead: "d143dd218b52dbfc32c91876583441865edea10c",
    renderedArtifactSha256: "baf50944924b2478c544210eb5862d4b8c893f316f9f4f50904d0c1bcea5cbd7",
    renderedApplicationByteIdentity: "PASS",
    note: "Protected water mutations enforce auth, role, ownership and idempotency; render head differs only by the QA workflow while recovered application bytes are unchanged.",
  },
  {
    app: "Skywatcher",
    producerRunId: 37540399007,
    producerHead: "1f9e589f5adbb9ca14b4142e2457bc7f1adc0320",
    artifactSha256: "5c07b7397d9172554383a103b9711195f8741db89c37450457dbf3d28f0ea624",
    testsPassed: 146,
    auth: "PASS",
    acl: "NOT_APPLICABLE",
    dbSchema: "NOT_APPLICABLE",
    dbSchemaTables: null,
    historicalRows: "NOT_APPLICABLE_NO_SERVER_DB",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 37660263966,
    renderedHead: "5fbeb64f8ff5b41a2a8e2162624429ceee7f04ba",
    renderedArtifactSha256: "b8b6209a83872599f6fa5cc598ccb9f680fb587b70738bda9fd688109886799b",
    renderedApplicationByteIdentity: "PASS",
    note: "Credential/authorization boundaries fail closed; no recovered server DB schema; acquisition/RLSM remains separately open; rendered bytes are unchanged from the semantic baseline.",
  },
  {
    app: "OVNIS",
    producerRunId: 37540408170,
    producerHead: "582324707df80e3204bb6623bae751b2983ef9d1",
    artifactSha256: "3828a9805af2d6abdc51a5821b0486a65915b08e047a6484f888734755240f03",
    testsPassed: 262,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 31,
    historicalRows: "NOT_PROVEN",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 37659504996,
    renderedHead: "ae4c9d36a46968f21b2bb4cb429de9e5c077684c",
    renderedArtifactSha256: "c2fb8fc3f14f1af95437400e853029c9c502657eed450094c8a20f3ae7b9c8a6",
    renderedApplicationByteIdentity: "PASS",
    note: "Workspace authorization and protected endpoints pass; 244 references remain distinct from 0 verified byte artifacts; later render head changes only QA workflow state.",
  },
  {
    app: "Centinelas",
    producerRunId: 37660348727,
    producerHead: "8a9b9041ba0628227b27fe67026146af4418b34b",
    artifactSha256: "096bc30a804cf5ed30af54272b46356050790e009f576230cc87ccf621187d82",
    testsPassed: 35,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 22,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    renderedRunId: 37660348727,
    renderedHead: "8a9b9041ba0628227b27fe67026146af4418b34b",
    renderedArtifactSha256: "096bc30a804cf5ed30af54272b46356050790e009f576230cc87ccf621187d82",
    renderedApplicationByteIdentity: "PASS",
    note: "Execution guards cover auth, roles, stale-head, revocation and idempotency; mobile containment and rendered QA close; historical database remains unavailable.",
  },
  {
    app: "TheHub",
    producerRunId: 38901463947,
    producerHead: "0e865cf357a72d670ba4cc166d9af7396dbe8a7f",
    artifactSha256: "d9d6ce4bf7f3ac29fb3927644feef04a2cc9a3949d2c832d4b1bb9c07b08b720",
    testsPassed: 162,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 21,
    historicalRows: "NOT_PROVEN",
    sourceContract: "PASS",
    authoritativeAcquisition: "NOT_APPLICABLE",
    renderedDesktop393430: "PASS",
    renderedRunId: 37659519663,
    renderedHead: "c96797d27258615434d6f1a8658a7f870f353d7a",
    renderedArtifactSha256: "7b800fe7a1f5f4e71b506b66f0834c13934e7d933f4fda929f0cad39fce8a305",
    renderedApplicationByteIdentity: "PASS",
    note: "Consumer receipts and control-plane boundaries pass; later successor changes affect recovery parity/acquisition helpers only, not the exact recovered application/UI bytes.",
  },
];

export interface FederationRecoveryParityEvaluation {
  rowCount: number;
  credentialFreeContractParityClosed: boolean;
  historicalRowsRecovered: boolean;
  renderedClosed: boolean;
  authoritativeAcquisitionClosed: boolean;
  infrastructureMigrationEligible: boolean;
  residue: string[];
}

export function evaluateFederationRecoveryParity(rows = FEDERATION_RECOVERY_PARITY_ROWS): FederationRecoveryParityEvaluation {
  const residue: string[] = [];
  const names = rows.map(row => row.app);
  if (rows.length !== 7 || new Set(names).size !== 7) residue.push("SEVEN_APP_DENOMINATOR_NOT_CLOSED");

  for (const row of rows) {
    if (!HEAD.test(row.producerHead)) residue.push(`${row.app}:INVALID_HEAD`);
    if (!SHA.test(row.artifactSha256)) residue.push(`${row.app}:INVALID_ARTIFACT_HASH`);
    if (!Number.isInteger(row.producerRunId) || row.producerRunId <= 0) residue.push(`${row.app}:INVALID_RUN_ID`);
    if (!Number.isInteger(row.testsPassed) || row.testsPassed <= 0) residue.push(`${row.app}:INVALID_TEST_DENOMINATOR`);
    if (row.auth === "OPEN") residue.push(`${row.app}:AUTH_OPEN`);
    if (row.acl === "OPEN") residue.push(`${row.app}:ACL_OPEN`);
    if (row.dbSchema === "OPEN") residue.push(`${row.app}:DB_SCHEMA_OPEN`);
    if (row.sourceContract !== "PASS") residue.push(`${row.app}:SOURCE_CONTRACT_OPEN`);
    if (!["PASS", "UNAVAILABLE_NO_DUMP", "NOT_PROVEN", "NOT_APPLICABLE_NO_SERVER_DB"].includes(row.historicalRows)) {
      residue.push(`${row.app}:INVALID_HISTORICAL_ROWS_STATE`);
    }
    if (row.dbSchema === "PASS" && (!row.dbSchemaTables || row.dbSchemaTables <= 0)) {
      residue.push(`${row.app}:DB_TABLE_DENOMINATOR_MISSING`);
    }
    if (row.dbSchema === "NOT_APPLICABLE" && row.dbSchemaTables !== null) {
      residue.push(`${row.app}:DB_NOT_APPLICABLE_WITH_TABLES`);
    }

    if (row.renderedDesktop393430 === "PASS") {
      if (!Number.isInteger(row.renderedRunId) || row.renderedRunId <= 0) residue.push(`${row.app}:INVALID_RENDERED_RUN_ID`);
      if (!HEAD.test(row.renderedHead)) residue.push(`${row.app}:INVALID_RENDERED_HEAD`);
      if (!SHA.test(row.renderedArtifactSha256)) residue.push(`${row.app}:INVALID_RENDERED_ARTIFACT_HASH`);
      if (row.renderedApplicationByteIdentity !== "PASS") residue.push(`${row.app}:RENDERED_BYTE_IDENTITY_OPEN`);
    }
  }

  const credentialFreeContractParityClosed = !residue.some(item =>
    /AUTH_OPEN|ACL_OPEN|DB_SCHEMA_OPEN|SOURCE_CONTRACT_OPEN|DB_TABLE_DENOMINATOR|INVALID_(HEAD|ARTIFACT_HASH|RUN_ID|TEST_DENOMINATOR|HISTORICAL_ROWS_STATE)|SEVEN_APP_DENOMINATOR/.test(item),
  );
  const historicalRowsRecovered = rows.every(row =>
    row.historicalRows === "PASS" || row.historicalRows === "NOT_APPLICABLE_NO_SERVER_DB",
  );
  const renderedClosed =
    rows.every(row => row.renderedDesktop393430 === "PASS") &&
    !residue.some(item => /RENDERED_/.test(item));
  const authoritativeAcquisitionClosed = rows.every(row =>
    row.authoritativeAcquisition === "PASS" || row.authoritativeAcquisition === "NOT_APPLICABLE",
  );
  const infrastructureMigrationEligible =
    credentialFreeContractParityClosed && renderedClosed && authoritativeAcquisitionClosed;

  return {
    rowCount: rows.length,
    credentialFreeContractParityClosed,
    historicalRowsRecovered,
    renderedClosed,
    authoritativeAcquisitionClosed,
    infrastructureMigrationEligible,
    residue,
  };
}

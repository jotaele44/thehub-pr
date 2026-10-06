export type ParityState = "PASS" | "NOT_APPLICABLE" | "OPEN";
export type HistoricalRowsState = "UNAVAILABLE_NO_DUMP" | "NOT_APPLICABLE_NO_SERVER_DB";

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
  note: string;
}

const SHA = /^[0-9a-f]{64}$/;
const HEAD = /^[0-9a-f]{40}$/;

export const FEDERATION_RECOVERY_PARITY_ROWS: FederationRecoveryParityRow[] = [
  {
    app: "Spiderweb",
    producerRunId: 37538781611,
    producerHead: "48e0e916ea379a67b751199d4e84f61eb6f39e98",
    artifactSha256: "2a588ec06c5988611ee25c4c5e10d34dbd6987b044e8d5ebe4d8df529a8c3cd8",
    testsPassed: 154,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 9,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "PASS",
    note: "Eight protected non-auth mutation vectors; ACL/read/owner/admin guards; exact nine-table schema; source-equivalence and rendered QA closed.",
  },
  {
    app: "MoneySweep",
    producerRunId: 37539577351,
    producerHead: "d0ef0eef7d2679501e6a99914a763cd015abe540",
    artifactSha256: "cc45fcbc0da23633ef9c8e26084f7b11ce20b4659603f0ce2a4c3472578c7fab",
    testsPassed: 90,
    auth: "NOT_APPLICABLE",
    acl: "NOT_APPLICABLE",
    dbSchema: "PASS",
    dbSchemaTables: 5,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "OPEN",
    note: "Recovered API surface is exactly five GET handlers and zero mutation handlers; write auth/ACL is explicitly not applicable.",
  },
  {
    app: "AguaYLuz",
    producerRunId: 37530961477,
    producerHead: "3a9fe443579dd8338861187d7c70841fa3c33ed2",
    artifactSha256: "68f5fedbc910b1e439963d13bd68e3507a5d06d01a3ac019ff0d32d15149792e",
    testsPassed: 152,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 44,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "OPEN",
    note: "Protected water mutations enforce auth, role, ownership and idempotency; current/empty/stale/error source states remain distinct.",
  },
  {
    app: "Skywatcher",
    producerRunId: 37531308529,
    producerHead: "9ae2ba27c522734a9dcf3e4b135fd3b84dd5efa7",
    artifactSha256: "70ab4f3de96a5469ec997f844a6e67fec12af48af571030b8ba7ace51be32e2f",
    testsPassed: 146,
    auth: "PASS",
    acl: "NOT_APPLICABLE",
    dbSchema: "NOT_APPLICABLE",
    dbSchemaTables: null,
    historicalRows: "NOT_APPLICABLE_NO_SERVER_DB",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "OPEN",
    note: "Credential/authorization boundaries fail closed; recovered snapshot has no Kysely server DB schema; acquisition/RLSM remain separately open.",
  },
  {
    app: "OVNIS",
    producerRunId: 37531652743,
    producerHead: "532a26575429000e575d60d7a7f466540e32516a",
    artifactSha256: "2701993d8c47d0e6966b6152a39433e4c18d72b4f365eca2fba3c72f9bb278aa",
    testsPassed: 262,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 31,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "OPEN",
    note: "Workspace authorization and protected endpoints pass; 244 references remain distinct from 0 verified byte artifacts.",
  },
  {
    app: "Centinelas",
    producerRunId: 37532054570,
    producerHead: "8c6ca3384afaa5f21aef120bdef1b995b87cb676",
    artifactSha256: "29badcbd967af58cf68143d21cf1156b14a72e49466954a5c757fe2fe3c42610",
    testsPassed: 33,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 22,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "OPEN",
    renderedDesktop393430: "OPEN",
    note: "Execution guards cover auth, roles, stale-head, revocation and idempotency; historical database remains unavailable.",
  },
  {
    app: "TheHub",
    producerRunId: 37532340842,
    producerHead: "7a40132dd5fd639b8f6391f71e95e8a01b0d91e1",
    artifactSha256: "9b8be7a7b355f56843f59fb824b788003088c1da9a337b644f7970b10f7d3370",
    testsPassed: 145,
    auth: "PASS",
    acl: "PASS",
    dbSchema: "PASS",
    dbSchemaTables: 21,
    historicalRows: "UNAVAILABLE_NO_DUMP",
    sourceContract: "PASS",
    authoritativeAcquisition: "NOT_APPLICABLE",
    renderedDesktop393430: "OPEN",
    note: "Consumer receipts, bearer-negative tests and control-plane authority boundaries pass; TheHub is not a producer acquisition authority.",
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
    if (row.historicalRows !== "UNAVAILABLE_NO_DUMP" && row.historicalRows !== "NOT_APPLICABLE_NO_SERVER_DB") {
      residue.push(`${row.app}:INVALID_HISTORICAL_ROWS_STATE`);
    }
    if (row.dbSchema === "PASS" && (!row.dbSchemaTables || row.dbSchemaTables <= 0)) {
      residue.push(`${row.app}:DB_TABLE_DENOMINATOR_MISSING`);
    }
    if (row.dbSchema === "NOT_APPLICABLE" && row.dbSchemaTables !== null) {
      residue.push(`${row.app}:DB_NOT_APPLICABLE_WITH_TABLES`);
    }
  }

  const credentialFreeContractParityClosed = !residue.some(item =>
    /AUTH_OPEN|ACL_OPEN|DB_SCHEMA_OPEN|SOURCE_CONTRACT_OPEN|DENOMINATOR|INVALID_/.test(item),
  );
  const historicalRowsRecovered = rows.every(row => row.historicalRows !== "UNAVAILABLE_NO_DUMP");
  const renderedClosed = rows.every(row => row.renderedDesktop393430 === "PASS");
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

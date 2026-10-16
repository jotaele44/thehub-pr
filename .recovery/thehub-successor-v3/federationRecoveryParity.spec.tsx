import {
  FEDERATION_RECOVERY_PARITY_ROWS,
  evaluateFederationRecoveryParity,
} from "./federationRecoveryParity";

describe("Federation recovered cross-cutting parity matrix v3", () => {
  it("freezes exactly seven unique federation applications", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.rowCount).toBe(7);
    expect(new Set(FEDERATION_RECOVERY_PARITY_ROWS.map(row => row.app)).size).toBe(7);
  });

  it("closes credential-free auth ACL schema and source-contract parity without credentials", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.credentialFreeContractParityClosed).toBeTrue();
    expect(result.residue).toEqual([]);
  });

  it("binds rendered desktop 393 and 430 PASS to run head artifact evidence for all seven apps", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.renderedClosed).toBeTrue();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.every(row => row.renderedDesktop393430 === "PASS")).toBeTrue();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.every(row => row.renderedRunId > 0)).toBeTrue();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.every(row => /^[0-9a-f]{40}$/.test(row.renderedHead))).toBeTrue();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.every(row => /^[0-9a-f]{64}$/.test(row.renderedArtifactSha256))).toBeTrue();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.every(row => row.renderedApplicationByteIdentity === "PASS")).toBeTrue();
  });

  it("preserves MoneySweep write auth and ACL as explicitly not applicable on its GET-only surface", () => {
    const row = FEDERATION_RECOVERY_PARITY_ROWS.find(row => row.app === "MoneySweep")!;
    expect(row.auth).toBe("NOT_APPLICABLE");
    expect(row.acl).toBe("NOT_APPLICABLE");
    expect(row.dbSchemaTables).toBe(5);
    expect(row.testsPassed).toBe(90);
  });

  it("preserves Skywatcher server DB as not applicable instead of inventing a schema", () => {
    const row = FEDERATION_RECOVERY_PARITY_ROWS.find(row => row.app === "Skywatcher")!;
    expect(row.dbSchema).toBe("NOT_APPLICABLE");
    expect(row.dbSchemaTables).toBeNull();
    expect(row.historicalRows).toBe("NOT_APPLICABLE_NO_SERVER_DB");
  });

  it("never converts missing historical database dumps into zero-row PASS", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.historicalRowsRecovered).toBeFalse();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.historicalRows === "UNAVAILABLE_NO_DUMP").map(row => row.app)).toEqual(["Centinelas"]);
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.historicalRows === "NOT_PROVEN").length).toBe(5);
  });

  it("keeps authoritative acquisition separate from source-contract and rendered parity", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.authoritativeAcquisitionClosed).toBeFalse();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.authoritativeAcquisition === "OPEN").length).toBe(6);
    expect(result.renderedClosed).toBeTrue();
  });

  it("keeps infrastructure migration blocked even after rendered closure while acquisition residue remains", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.credentialFreeContractParityClosed).toBeTrue();
    expect(result.renderedClosed).toBeTrue();
    expect(result.authoritativeAcquisitionClosed).toBeFalse();
    expect(result.infrastructureMigrationEligible).toBeFalse();
  });
});

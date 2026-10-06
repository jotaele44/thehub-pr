import {
  FEDERATION_RECOVERY_PARITY_ROWS,
  evaluateFederationRecoveryParity,
} from "./federationRecoveryParity";

describe("Federation recovered cross-cutting parity matrix", () => {
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

  it("preserves MoneySweep write auth and ACL as explicitly not applicable on its GET-only surface", () => {
    const row = FEDERATION_RECOVERY_PARITY_ROWS.find(row => row.app === "MoneySweep")!;
    expect(row.auth).toBe("NOT_APPLICABLE");
    expect(row.acl).toBe("NOT_APPLICABLE");
    expect(row.dbSchemaTables).toBe(5);
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
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.historicalRows === "UNAVAILABLE_NO_DUMP").length).toBe(6);
  });

  it("keeps authoritative acquisition separate from source-contract parity", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.authoritativeAcquisitionClosed).toBeFalse();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.authoritativeAcquisition === "OPEN").length).toBe(6);
  });

  it("keeps rendered closure open until all seven have desktop 393 and 430 evidence", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.renderedClosed).toBeFalse();
    expect(FEDERATION_RECOVERY_PARITY_ROWS.filter(row => row.renderedDesktop393430 === "PASS").map(row => row.app)).toEqual(["Spiderweb"]);
  });

  it("keeps infrastructure migration closed while rendered or acquisition residue remains", () => {
    const result = evaluateFederationRecoveryParity();
    expect(result.infrastructureMigrationEligible).toBeFalse();
  });
});

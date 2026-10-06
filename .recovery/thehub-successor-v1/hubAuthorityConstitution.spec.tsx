import {
  REQUIRED_BINDINGS,
  federationCertificationAllowed,
  implicitAuthorityTransferAllowed,
  validateAuthorityBindings,
} from "./hubAuthorityConstitution";

describe("TheHub authority constitution", () => {
  it("accepts the canonical authority partition", () => {
    expect(validateAuthorityBindings(REQUIRED_BINDINGS).pass).toBeTrue();
  });

  it("rejects unowned functions", () => {
    const trimmed = REQUIRED_BINDINGS.filter(x => x.fn !== "GEOMETRY");
    expect(validateAuthorityBindings(trimmed).reasons).toContain("UNOWNED:GEOMETRY");
  });

  it("rejects duplicate authority owners", () => {
    const duplicate = [...REQUIRED_BINDINGS, { fn: "GEOMETRY" as const, plane: "FEDERATION" as const, owner: "THEHUB" }];
    expect(validateAuthorityBindings(duplicate).reasons).toContain("DUPLICATE_OWNER:GEOMETRY");
  });

  it("rejects domain authority drift into TheHub", () => {
    const drift = REQUIRED_BINDINGS.map(x => x.fn === "GEOMETRY" ? { ...x, owner: "THEHUB" } : x);
    expect(validateAuthorityBindings(drift).reasons).toContain("AUTHORITY_DRIFT:GEOMETRY");
  });

  it("prohibits implicit authority transfer", () => {
    expect(implicitAuthorityTransferAllowed()).toBeFalse();
  });

  it("cannot certify with producer receipt residue", () => {
    expect(federationCertificationAllowed({
      authorityBindingsPass: true,
      producerReceiptsPass: false,
      lockstepPass: true,
      unresolvedResidue: 0,
    })).toBeFalse();
  });

  it("cannot certify with LOCKSTEP failure", () => {
    expect(federationCertificationAllowed({
      authorityBindingsPass: true,
      producerReceiptsPass: true,
      lockstepPass: false,
      unresolvedResidue: 0,
    })).toBeFalse();
  });

  it("cannot certify with unresolved residue", () => {
    expect(federationCertificationAllowed({
      authorityBindingsPass: true,
      producerReceiptsPass: true,
      lockstepPass: true,
      unresolvedResidue: 1,
    })).toBeFalse();
  });

  it("certifies only when authority, receipts, LOCKSTEP and zero residue all close", () => {
    expect(federationCertificationAllowed({
      authorityBindingsPass: true,
      producerReceiptsPass: true,
      lockstepPass: true,
      unresolvedResidue: 0,
    })).toBeTrue();
  });
});

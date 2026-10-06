import { federationReceiptClosure, validateProducerReceipt } from "./hubProducerReceipts";

describe("TheHub producer receipt closure", () => {
  const expected = {
    producer: "SPIDERWEB" as const,
    packageFingerprint: "f".repeat(64),
    sourceHead: "a".repeat(40),
    schemaVersion: "spiderweb.package/v1",
  };
  const receipt = {
    ...expected,
    producedAt: "2026-10-06T00:00:00Z",
    unresolvedResidue: 0,
    state: "PASS" as const,
  };

  it("accepts an exact producer receipt", () => {
    expect(validateProducerReceipt(receipt, expected).pass).toBeTrue();
  });

  it("rejects fingerprint mismatch", () => {
    expect(validateProducerReceipt({ ...receipt, packageFingerprint: "b".repeat(64) }, expected).reasons).toContain("FINGERPRINT_MISMATCH");
  });

  it("rejects source-head mismatch", () => {
    expect(validateProducerReceipt({ ...receipt, sourceHead: "b".repeat(40) }, expected).pass).toBeFalse();
  });

  it("rejects schema-version mismatch", () => {
    expect(validateProducerReceipt({ ...receipt, schemaVersion: "other/v1" }, expected).reasons).toContain("SCHEMA_VERSION_MISMATCH");
  });

  it("cannot synthesize PASS when producer state is OPEN", () => {
    expect(validateProducerReceipt({ ...receipt, state: "OPEN" }, expected).reasons).toContain("PRODUCER_NOT_PASS");
  });

  it("cannot hide unresolved producer residue", () => {
    expect(validateProducerReceipt({ ...receipt, unresolvedResidue: 1 }, expected).reasons).toContain("UNRESOLVED_RESIDUE");
  });

  it("fails federation closure when an expected producer receipt is missing", () => {
    const result = federationReceiptClosure([], [expected]);
    expect(result.pass).toBeFalse();
    expect(result.results[0].reasons).toContain("MISSING_RECEIPT");
  });

  it("passes only when every expected producer receipt closes exactly", () => {
    expect(federationReceiptClosure([receipt], [expected]).pass).toBeTrue();
  });
});

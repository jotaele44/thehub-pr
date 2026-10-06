export type ProducerName = "SPIDERWEB" | "MONEYSWEEP" | "AGUAYLUZ" | "SKYWATCHER" | "OVNIS" | "CENTINELAS";
export type ProducerReceiptState = "PASS" | "OPEN" | "BLOCKED";

export interface ProducerReceipt {
  producer: ProducerName;
  packageFingerprint: string;
  sourceHead: string;
  schemaVersion: string;
  producedAt: string;
  unresolvedResidue: number;
  state: ProducerReceiptState;
}

export interface ExpectedProducerBinding {
  producer: ProducerName;
  packageFingerprint: string;
  sourceHead: string;
  schemaVersion: string;
}

export function validateProducerReceipt(receipt: ProducerReceipt, expected: ExpectedProducerBinding) {
  const reasons: string[] = [];
  if (receipt.producer !== expected.producer) reasons.push("PRODUCER_MISMATCH");
  if (receipt.packageFingerprint !== expected.packageFingerprint) reasons.push("FINGERPRINT_MISMATCH");
  if (receipt.sourceHead !== expected.sourceHead) reasons.push("SOURCE_HEAD_MISMATCH");
  if (receipt.schemaVersion !== expected.schemaVersion) reasons.push("SCHEMA_VERSION_MISMATCH");
  if (!receipt.producedAt) reasons.push("PRODUCED_AT_MISSING");
  if (receipt.unresolvedResidue !== 0) reasons.push("UNRESOLVED_RESIDUE");
  if (receipt.state !== "PASS") reasons.push("PRODUCER_NOT_PASS");
  return { pass: reasons.length === 0, reasons };
}

export function federationReceiptClosure(
  receipts: ProducerReceipt[],
  expected: ExpectedProducerBinding[]
) {
  const byProducer = new Map(receipts.map(r => [r.producer, r]));
  const results = expected.map(e => {
    const r = byProducer.get(e.producer);
    if (!r) return { producer: e.producer, pass: false, reasons: ["MISSING_RECEIPT"] };
    return { producer: e.producer, ...validateProducerReceipt(r, e) };
  });
  return {
    pass: results.every(r => r.pass),
    results,
    expectedCount: expected.length,
    receivedCount: receipts.length,
  };
}

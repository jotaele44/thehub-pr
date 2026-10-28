#!/usr/bin/env node
// Federation design-gate v2: evidence identity and denominator checks.
// This is a DESIGN ONLY validator, not a certification or browser capture producer.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const hex40 = s => typeof s === 'string' && /^[0-9a-f]{40}$/.test(s);
const hex64 = s => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s);
const issue = (code, detail) => ({ code, detail });

export function validateEvidence({ contractBytes, baselineBytes, inventoryBytes, mappingBytes, receiptBytes, reviewBytes }) {
  const errors = [];
  const parse = (bytes, name) => {
    if (!(bytes instanceof Uint8Array)) { errors.push(issue('MISSING_BYTES', name)); return null; }
    try { return JSON.parse(Buffer.from(bytes).toString('utf8')); }
    catch { errors.push(issue('INVALID_JSON', name)); return null; }
  };
  const contract = parse(contractBytes, 'contract');
  const baseline = parse(baselineBytes, 'baseline');
  const inventory = parse(inventoryBytes, 'inventory');
  const mapping = parse(mappingBytes, 'mapping');
  const receipt = parse(receiptBytes, 'receipt');
  const review = parse(reviewBytes, 'review');
  if ([contract, baseline, inventory, mapping, receipt, review].some(x => !x)) return { verdict:'FAIL', errors };

  const contractDigest = sha256(contractBytes);
  const inventoryDigest = sha256(inventoryBytes);
  const mappingDigest = sha256(mappingBytes);
  const receiptDigest = sha256(receiptBytes);
  const expected = baseline?.sourceHeads?.[receipt.app]?.fullSha;

  if (contract.schema !== 'pr-federation/layout-contract/v1') errors.push(issue('CONTRACT_SCHEMA','unexpected schema'));
  if (contract.certification !== 'CERTIFIED' || contract.status !== 'APPROVED') errors.push(issue('CONTRACT_NOT_APPROVED','candidate contract forbidden'));
  if (!hex40(receipt.commitSha) || !hex40(expected) || receipt.commitSha !== expected) errors.push(issue('SOURCE_MISMATCH','receipt does not match approved baseline'));
  if (!hex64(receipt.contractSha256) || receipt.contractSha256 !== contractDigest) errors.push(issue('CONTRACT_HASH_MISMATCH','contract byte hash mismatch'));
  if (!hex64(receipt.inventorySha256) || receipt.inventorySha256 !== inventoryDigest) errors.push(issue('INVENTORY_HASH_MISMATCH','inventory byte hash mismatch'));
  if (!hex64(receipt.mappingSha256) || receipt.mappingSha256 !== mappingDigest) errors.push(issue('MAPPING_HASH_MISMATCH','mapping byte hash mismatch'));
  if (inventory.app !== receipt.app || inventory.commitSha !== expected) errors.push(issue('INVENTORY_SOURCE','wrong inventory identity'));

  const arrays = ['sourceFiles','workspaces','components','instances','states','cases'];
  for (const field of arrays) {
    if (!Array.isArray(inventory[field]) || inventory[field].length === 0) {
      errors.push(issue('DENOMINATOR_MISSING',field));
      continue;
    }
    const ids = inventory[field].map(x => x?.id);
    if (ids.some(x => typeof x !== 'string' || !x.trim()) || new Set(ids).size !== ids.length) errors.push(issue('DENOMINATOR_IDS',field));
    const asserted = inventory.denominators?.[field];
    if (!Number.isSafeInteger(asserted) || asserted !== ids.length) errors.push(issue('DENOMINATOR_COUNT',field));
  }
  if (inventory.completeness?.discovery !== 'PASS' || inventory.completeness?.independentReconciliation !== 'PASS')
    errors.push(issue('INVENTORY_UNVERIFIED','independent completeness required'));
  if (mapping.app !== receipt.app || mapping.commitSha !== expected || mapping.reviewStatus !== 'APPROVED')
    errors.push(issue('MAPPING_UNREVIEWED','reviewed mapping required'));
  if (!Array.isArray(mapping.entries) || mapping.entries.length === 0 || mapping.entries.some(e => !['EQUIVALENT','DISTINCT','DOMAIN_VARIANT'].includes(e.classification) || !e.evidenceId))
    errors.push(issue('MAPPING_UNRESOLVED','unresolved or ungrounded mapping'));

  const expectedCases = new Set((inventory.cases || []).map(x=>x.id));
  const observed = new Set();
  if (!Array.isArray(receipt.measurements)) errors.push(issue('MEASUREMENTS_MISSING','measurements array'));
  else for (const m of receipt.measurements) {
    if (!m || typeof m.caseId !== 'string' || !expectedCases.has(m.caseId)) { errors.push(issue('UNDECLARED_CASE',String(m?.caseId))); continue; }
    if (observed.has(m.caseId)) errors.push(issue('DUPLICATE_CASE',m.caseId));
    observed.add(m.caseId);
    if (!['x','y','width','height'].every(k=>Number.isFinite(m[k])) || m.width < 0 || m.height < 0)
      errors.push(issue('INVALID_GEOMETRY',m.caseId));
    if (m.geometryStatus !== 'PASS' || m.scrollStatus !== 'PASS' || m.accessibilityStatus !== 'PASS')
      errors.push(issue('LAYOUT_CASE_FAILURE',m.caseId));
  }
  for (const id of expectedCases) if (!observed.has(id)) errors.push(issue('CASE_MISSING',id));

  if (review.status !== 'APPROVED' || review.reviewerIndependent !== true || !review.reviewerId ||
      review.contractSha256 !== contractDigest || review.inventorySha256 !== inventoryDigest ||
      review.mappingSha256 !== mappingDigest || review.receiptSha256 !== receiptDigest)
    errors.push(issue('INDEPENDENT_REVIEW_INVALID','review must bind exact bytes and independent reviewer'));
  if (Array.isArray(review.materialFindings) && review.materialFindings.length) errors.push(issue('MATERIAL_FINDINGS_OPEN','must resolve all material findings'));
  return { verdict:errors.length?'FAIL':'PASS', errors, counts:{expectedCases:expectedCases.size, observedCases:observed.size} };
}
if (process.argv[1] && import.meta.url === new URL('file://' + process.argv[1]).href) {
  try {
    const [contract,baseline,inventory,mapping,receipt,review] = process.argv.slice(2);
    if (![contract,baseline,inventory,mapping,receipt,review].every(Boolean)) throw new Error('six evidence file arguments required');
    const out = validateEvidence({contractBytes:readFileSync(contract),baselineBytes:readFileSync(baseline),inventoryBytes:readFileSync(inventory),mappingBytes:readFileSync(mapping),receiptBytes:readFileSync(receipt),reviewBytes:readFileSync(review)});
    process.stdout.write(JSON.stringify(out,null,2)+'\n');
    process.exitCode = out.verdict === 'PASS' ? 0 : 1;
  } catch(e) { process.stderr.write('AUDIT_BLOCKED: '+e.message+'\n'); process.exitCode=2; }
}

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const contract=JSON.parse(fs.readFileSync(new URL("../contracts/federation-execution-gateway-v2.json",import.meta.url)));
const authority=JSON.parse(fs.readFileSync(new URL("../manifests/authority-partition.json",import.meta.url)));
const source=JSON.parse(fs.readFileSync(new URL("../manifests/source-manifest.json",import.meta.url)));

test("capability denominator is exactly 14",()=>{
  assert.equal(contract.capabilityCount,14);
  assert.equal(contract.capabilities.length,14);
  assert.equal(new Set(contract.capabilities.map(x=>x.id)).size,14);
  assert.equal(new Set(contract.capabilities.map(x=>x.name)).size,14);
  assert.equal(new Set(contract.capabilities.map(x=>x.mcpName)).size,14);
});

test("authority remains cross-repository only",()=>{
  assert.equal(contract.authority,"THEHUB_CROSS_REPOSITORY_CONTROL_PLANE");
  assert.equal(contract.producerDomainAuthorityTransfer,"DENY");
  assert.equal(authority.producerDomainAuthority,"RETAINED_BY_EACH_PRODUCER");
});

test("unsafe promotion primitives are denied",()=>{
  assert.equal(contract.invariants.directMainWrite,"DENY");
  assert.equal(contract.invariants.forcePush,"DENY");
  assert.equal(contract.invariants.administrativeBypass,"DENY");
  assert.equal(contract.invariants.staleRevisionPromotion,"DENY");
});

test("source manifest binds TheHub and accepted Vercel manifestation",()=>{
  assert.equal(source.sourceRepository.repositoryId,"github:1258897469");
  assert.equal(source.sourceRepository.baseRevision,"9adf06d31ddffef1010d3d6461373ca3300f48be");
  assert.equal(source.importedFrom.deploymentId,"dpl_HJcSNFBNUKKKoZC4BofHEHibbGLH");
  assert.equal(source.declaredFiles.length,8);
});

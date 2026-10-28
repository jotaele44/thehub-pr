import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { validateEvidence } from './evidence-gate.mjs';
const bytes = v => Buffer.from(JSON.stringify(v));
const digest = v => createHash('sha256').update(bytes(v)).digest('hex');
const sha = 'a'.repeat(40);
const app = 'thehub-pr';
function fixture() {
 const contract={schema:'pr-federation/layout-contract/v1',status:'APPROVED',certification:'CERTIFIED'};
 const baseline={sourceHeads:{[app]:{fullSha:sha}}};
 const inventory={app,commitSha:sha,sourceFiles:[{id:'file'}],workspaces:[{id:'/'}],components:[{id:'header'}],instances:[{id:'header@/'}],states:[{id:'default'}],cases:[{id:'case-1'}],denominators:{sourceFiles:1,workspaces:1,components:1,instances:1,states:1,cases:1},completeness:{discovery:'PASS',independentReconciliation:'PASS'}};
 const mapping={app,commitSha:sha,reviewStatus:'APPROVED',entries:[{classification:'EQUIVALENT',evidenceId:'verified-1'}]};
 const receipt={app,commitSha:sha,contractSha256:digest(contract),inventorySha256:digest(inventory),mappingSha256:digest(mapping),measurements:[{caseId:'case-1',x:0,y:0,width:200,height:60,geometryStatus:'PASS',scrollStatus:'PASS',accessibilityStatus:'PASS'}]};
 const review={status:'APPROVED',reviewerIndependent:true,reviewerId:'independent-reviewer',contractSha256:digest(contract),inventorySha256:digest(inventory),mappingSha256:digest(mapping),receiptSha256:digest(receipt),materialFindings:[]};
 return {contract,baseline,inventory,mapping,receipt,review};
}
const run = o=>validateEvidence(Object.fromEntries(Object.entries(o).map(([k,v])=>[k+'Bytes',bytes(v)])));
test('synthetic all-evidence fixture passes validator only',()=>assert.equal(run(fixture()).verdict,'PASS'));
const cases=[
 ['wrong valid-format contract hash', x=>x.receipt.contractSha256='b'.repeat(64),'CONTRACT_HASH_MISMATCH'],
 ['wrong source SHA',x=>x.receipt.commitSha='b'.repeat(40),'SOURCE_MISMATCH'],
 ['unapproved contract',x=>x.contract.status='CANDIDATE','CONTRACT_NOT_APPROVED'],
 ['missing component denominator',x=>{x.inventory.components=[];x.inventory.denominators.components=0},'DENOMINATOR_MISSING'],
 ['unreconciled inventory',x=>x.inventory.completeness.independentReconciliation='OPEN','INVENTORY_UNVERIFIED'],
 ['ambiguous role mapping',x=>x.mapping.entries[0].classification='UNRESOLVED','MAPPING_UNRESOLVED'],
 ['missing measured case',x=>x.receipt.measurements=[],'CASE_MISSING'],
 ['duplicate measured case',x=>x.receipt.measurements.push({...x.receipt.measurements[0]}),'DUPLICATE_CASE'],
 ['geometry fails',x=>x.receipt.measurements[0].geometryStatus='FAIL','LAYOUT_CASE_FAILURE'],
 ['unreviewed receipt',x=>x.review.reviewerIndependent=false,'INDEPENDENT_REVIEW_INVALID'],
 ['review not bound to measurement bytes',x=>x.review.receiptSha256='b'.repeat(64),'INDEPENDENT_REVIEW_INVALID'],
 ['material findings remain',x=>x.review.materialFindings=['finding'],'MATERIAL_FINDINGS_OPEN']
];
for (const [name,mutate,expected] of cases) test(name,()=>{const x=fixture();mutate(x);const out=run(x);assert.equal(out.verdict,'FAIL');assert.ok(out.errors.some(e=>e.code===expected),JSON.stringify(out));});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { audit } from './audit.mjs';
const contract=JSON.parse(readFileSync(new URL('./contract.json',import.meta.url),'utf8'));
function fixture(){
const measurements=contract.viewports.flatMap(viewport=>{
 const mobile=viewport<=contract.breakpoints.mobileMax;
 const tablet=viewport<=contract.breakpoints.tabletMax;
 return [
 {route:'/',viewport,role:'header',x:0,y:0,width:viewport,height:mobile?56:64},
 {route:'/',viewport,role:'sidebar',x:0,y:0,width:mobile?viewport:256,height:640,mode:mobile?'drawer':'panel'},
 {route:'/',viewport,role:'page',x:0,y:0,width:viewport,height:640,gutter:mobile?16:tablet?24:32},
 {route:'/',viewport,role:'navigation',x:0,y:0,width:44,height:44,hitWidth:44,hitHeight:44}
]});
return {app:'thehub-pr',commitSha:'a'.repeat(40),contractSha256:'b'.repeat(64),measurements,routesComplete:true,roleMappingReviewed:true,exceptions:[]};
}
test('complete matching receipt passes adjudicator (synthetic fixture only)',()=>assert.equal(audit(contract,fixture()).verdict,'PASS'));
const mutations=[
 ['sidebar drift',r=>r.measurements.find(m=>m.role==='sidebar'&&m.viewport===1440).width=263,'GEOMETRY_DRIFT'],
 ['mobile breakpoint',r=>r.measurements.find(m=>m.role==='sidebar'&&m.viewport===393).mode='panel','SIDEBAR_MODE'],
 ['duplicate',r=>r.measurements.push({...r.measurements[0]}),'DUPLICATE_MEASUREMENT'],
 ['missing coverage',r=>r.measurements=r.measurements.filter(m=>!(m.role==='header'&&m.viewport===430)),'COVERAGE_MISSING'],
 ['horizontal overflow',r=>r.measurements[0].overflowX=true,'HORIZONTAL_OVERFLOW'],
 ['unsafe touch target',r=>r.measurements.find(m=>m.role==='navigation').hitWidth=32,'HIT_TARGET'],
 ['stale identity',r=>r.commitSha='short','SOURCE_IDENTITY'],
 ['missing source hash',r=>delete r.contractSha256,'CONTRACT_IDENTITY'],
 ['incomplete route scope',r=>r.routesComplete=false,'ROUTE_COVERAGE_OPEN'],
 ['unreviewed role map',r=>r.roleMappingReviewed=false,'ROLE_MAPPING_OPEN'],
 ['unadjudicated exception',r=>r.exceptions=['unknown'],'EXCEPTIONS_OPEN'],
 ['bad coordinate',r=>r.measurements[0].width=null,'INVALID_GEOMETRY'],
 ['unknown component',r=>r.measurements[0].role='new-role','ROLE_UNMAPPED']
];
for(const [name,mutate,code] of mutations)test(name,()=>{const r=fixture();mutate(r);const out=audit(contract,r);assert.equal(out.verdict,'FAIL');assert.ok(out.findings.some(f=>f.code===code),JSON.stringify(out));});

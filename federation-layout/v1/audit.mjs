#!/usr/bin/env node
// Deterministic measurement-receipt adjudicator; browser capture is a separate producer.
import { readFileSync } from 'node:fs';
const fail=(code,message)=>({code,message});
export function audit(contract, receipt) {
  const findings=[];
  if (!contract || contract.schema!=='pr-federation/layout-contract/v1') findings.push(fail('CONTRACT_SCHEMA','Invalid contract'));
  if (!receipt || typeof receipt!=='object') return {verdict:'FAIL',findings:[fail('RECEIPT_MISSING','No receipt')]};
  if (!/^[0-9a-f]{40}$/.test(receipt.commitSha||'')) findings.push(fail('SOURCE_IDENTITY','Full commit SHA required'));
  if (!/^[0-9a-f]{64}$/.test(receipt.contractSha256||'')) findings.push(fail('CONTRACT_IDENTITY','Contract byte hash required'));
  if (!contract?.expectedConsumers?.includes(receipt.app)) findings.push(fail('CONSUMER_UNKNOWN','Unknown application'));
  if (!Array.isArray(receipt.measurements)) findings.push(fail('MEASUREMENTS_MISSING','Measurement array required'));
  const keys=new Set(), roles=new Set();
  for(const m of Array.isArray(receipt.measurements)?receipt.measurements:[]) {
    if (!m || typeof m!=='object') {findings.push(fail('INVALID_MEASUREMENT','Expected object'));continue;}
    const key=JSON.stringify([m.route,m.viewport,m.role,m.instance||'']);
    if(keys.has(key)) findings.push(fail('DUPLICATE_MEASUREMENT',key));
    keys.add(key);
    if (!contract?.viewports?.includes(m.viewport)) findings.push(fail('VIEWPORT_UNSUPPORTED',key));
    if (!['header','sidebar','page','navigation'].includes(m.role)) findings.push(fail('ROLE_UNMAPPED',key));
    if (m.role==='header') roles.add('header:'+m.viewport);
    for(const p of ['x','y','width','height']){
      if (!Number.isFinite(m[p])) findings.push(fail('INVALID_GEOMETRY',key+':'+p));
    }
    if (Number.isFinite(m.width)&&m.width<0 || Number.isFinite(m.height)&&m.height<0) findings.push(fail('NEGATIVE_SIZE',key));
    const mobile=m.viewport<=contract.breakpoints.mobileMax;
    const tablet=m.viewport<=contract.breakpoints.tabletMax;
    const expected = m.role==='header' ? {height:mobile?contract.geometry.header.height.mobile:contract.geometry.header.height.desktop} :
      m.role==='sidebar'&& !mobile ? {width:contract.geometry.sidebar.width.desktop} :
      m.role==='page' ? {gutter:mobile?contract.geometry.page.gutter.mobile:tablet?contract.geometry.page.gutter.tablet:contract.geometry.page.gutter.desktop} : {};
    for(const [p,v] of Object.entries(expected)){
      if(!Number.isFinite(m[p])) findings.push(fail('EXPECTED_PROPERTY_MISSING',key+':'+p));
      else if(Math.abs(m[p]-v)>contract.tolerancePx) findings.push(fail('GEOMETRY_DRIFT',key+':'+p+' expected '+v+' observed '+m[p]));
    }
    if(m.role==='sidebar' && mobile && m.mode!=='drawer') findings.push(fail('SIDEBAR_MODE',key));
    if(m.role==='navigation' && (!Number.isFinite(m.hitWidth)||!Number.isFinite(m.hitHeight)||Math.min(m.hitWidth,m.hitHeight)<contract.geometry.navigation.minHitTarget)) findings.push(fail('HIT_TARGET',key));
    if (m.overflowX===true) findings.push(fail('HORIZONTAL_OVERFLOW',key));
  }
  for (const vp of contract?.viewports||[]) if(!roles.has('header:'+vp)) findings.push(fail('COVERAGE_MISSING','header:'+vp));
  if (!receipt.routesComplete) findings.push(fail('ROUTE_COVERAGE_OPEN','Route denominator not certified'));
  if (!receipt.roleMappingReviewed) findings.push(fail('ROLE_MAPPING_OPEN','Independent mapping review missing'));
  if (receipt.exceptions?.length) findings.push(fail('EXCEPTIONS_OPEN','Exceptions require separate adjudication'));
  return {verdict: findings.length?'FAIL':'PASS',findings,measurements:receipt.measurements?.length||0};
}
if(process.argv[1] && import.meta.url===new URL('file://'+process.argv[1]).href){
  try {
    const result=audit(JSON.parse(readFileSync(process.argv[2],'utf8')),JSON.parse(readFileSync(process.argv[3],'utf8')));
    process.stdout.write(JSON.stringify(result,null,2)+'\n');
    process.exitCode=result.verdict==='PASS'?0:1;
  } catch(e) {process.stderr.write('AUDIT_BLOCKED: '+e.message+'\n');process.exitCode=2;}
}

export const STATES = Object.freeze({ PASS:'PASS', OPEN:'OPEN', BLOCKED:'BLOCKED', FAIL:'FAIL', UNKNOWN:'UNKNOWN', NOT_STARTED:'NOT_STARTED', PROVISIONAL:'PROVISIONAL', AUDIT_ONLY:'AUDIT_ONLY', SUPERSEDED:'SUPERSEDED' });
const SHA=/^[0-9a-f]{40}$/;
export function classifyComponent(component, snapshotSha) {
  if (!component || !SHA.test(snapshotSha || '') || component.source_sha !== snapshotSha) return { state:STATES.UNKNOWN, reason:'Missing or stale exact-commit evidence' };
  const gates=component.gates;
  if (!Array.isArray(gates) || gates.length===0 || !Array.isArray(component.requirement_ids) || component.requirement_ids.length===0) return {state:STATES.UNKNOWN,reason:'Missing requirement denominator or gate evidence'};
  if (new Set(gates.map(g=>g.id)).size!==gates.length || new Set(component.requirement_ids).size!==component.requirement_ids.length) return {state:STATES.UNKNOWN,reason:'Duplicate requirements or gate identifiers'};
  if (gates.some(g=>g.required && (g.state==='FAIL'||g.state==='BLOCKED'))) return {state:STATES.BLOCKED,reason:'Mandatory gate failed or blocked'};
  if (gates.some(g=>g.required && (!g.evidence_id || g.evidence_sha!==snapshotSha))) return {state:STATES.UNKNOWN,reason:'Mandatory evidence missing or stale'};
  if (gates.some(g=>g.required && !['PASS','OPEN','PROVISIONAL','AUDIT_ONLY','NOT_STARTED'].includes(g.state))) return {state:STATES.UNKNOWN,reason:'Unrecognized mandatory gate result'};
  if (gates.some(g=>g.required && g.state!=='PASS')) return {state:STATES.OPEN,reason:'Mandatory gates not fully passed'};
  if (!gates.some(g=>g.required)) return {state:STATES.UNKNOWN,reason:'No mandatory gates declared'};
  if (component.blocker_ids?.length) return {state:STATES.BLOCKED,reason:'Unresolved dependency blockers'};
  return {state:STATES.PASS,reason:'All declared mandatory gates passed at source commit'};
}
export function deriveSnapshot(data) {
  if (!data || !SHA.test(data.sha || '') || !Array.isArray(data.components) || !Array.isArray(data.edges)) return { valid:false,components:[],edges:[],reason:'Snapshot absent or invalid' };
  const ids=data.components.map(c=>c.id);
  if (new Set(ids).size!==ids.length || ids.some(x=>typeof x!=='string'||!x)) return {valid:false,components:[],edges:[],reason:'Duplicate or invalid component identifiers'};
  const set=new Set(ids);
  if (data.edges.some(e=>!set.has(e.source)||!set.has(e.target)||!e.id)||new Set(data.edges.map(e=>e.id)).size!==data.edges.length) return {valid:false,components:[],edges:[],reason:'Orphan or duplicate dependency edges'};
  const components=data.components.map(c=>({...c, derived:classifyComponent(c,data.sha)}));
  return {valid:true,sha:data.sha,components,edges:data.edges,reason:null};
}

import {describe,it,expect} from 'vitest';
import {classifyComponent,deriveSnapshot} from './status';
const sha='a'.repeat(40);
const gate={id:'test',required:true,state:'PASS',evidence_id:'run-1',evidence_sha:sha};
const node={id:'module-1',name:'Module',source_sha:sha,requirement_ids:['REQ-1'],gates:[gate]};
describe('fail-closed illumination',()=>{
 it('lights only exact commit with mandatory evidence',()=>expect(classifyComponent(node,sha).state).toBe('PASS'));
 it('does not light on stale SHA',()=>expect(classifyComponent(node,'b'.repeat(40)).state).toBe('UNKNOWN'));
 it('does not light on omitted evidence',()=>expect(classifyComponent({...node,gates:[{...gate,evidence_id:null}]},sha).state).toBe('UNKNOWN'));
 it('does not light without required gates',()=>expect(classifyComponent({...node,gates:[]},sha).state).toBe('UNKNOWN'));
 it('does not light a failed dependency',()=>expect(classifyComponent({...node,blocker_ids:['broken']},sha).state).toBe('BLOCKED'));
 it('blocks failed mandatory gate',()=>expect(classifyComponent({...node,gates:[{...gate,state:'FAIL'}]},sha).state).toBe('BLOCKED'));
 it('does not light duplicate requirement IDs',()=>expect(classifyComponent({...node,requirement_ids:['REQ-1','REQ-1']},sha).state).toBe('UNKNOWN'));
 it('rejects duplicated nodes',()=>expect(deriveSnapshot({sha,components:[node,node],edges:[]}).valid).toBe(false));
 it('rejects edges to unknown components',()=>expect(deriveSnapshot({sha,components:[node],edges:[{id:'e1',source:'module-1',target:'missing'}]}).valid).toBe(false));
 it('does not certify a locally asserted evidence graph',()=>expect(deriveSnapshot({sha,components:[node],edges:[]}).components[0].derived.state).toBe('PROVISIONAL'));
});

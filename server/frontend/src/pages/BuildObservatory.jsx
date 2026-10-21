import { useMemo, useState } from 'react';
import { deriveSnapshot } from '@/features/observatory/status';

const palette = { PASS:'#57e7ae', OPEN:'#e7bd69', BLOCKED:'#f18484', FAIL:'#f18484', UNKNOWN:'#8996a9', NOT_STARTED:'#657183', PROVISIONAL:'#e7bd69', AUDIT_ONLY:'#8996a9', SUPERSEDED:'#657183' };
const sample = {sha:null,components:[],edges:[]};
export default function BuildObservatory(){
  const [raw,setRaw]=useState('');
  const [selected,setSelected]=useState(null);
  const [filter,setFilter]=useState('ALL');
  const [error,setError]=useState('');
  const data=useMemo(()=>{try{return deriveSnapshot(raw.trim()?JSON.parse(raw):sample)}catch{return {valid:false,components:[],edges:[],reason:'Malformed JSON snapshot'}}},[raw]);
  const rows=data.components.filter(c=>filter==='ALL'||(filter==='REMAINING'?c.derived.state!=='PASS':c.derived.state==='PASS'));
  const active=data.components.find(c=>c.id===selected);
  function loadFile(event) {const file=event.target.files?.[0];if(!file)return;if(file.size>2_000_000){setError('Snapshot exceeds 2 MB limit');return;}file.text().then(t=>{setRaw(t);setError('');setSelected(null)}).catch(()=>setError('Unable to read snapshot'));}
  return <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8" data-testid="build-observatory">
    <header className="space-y-2"><h1 className="text-3xl font-semibold">Federation Build Observatory</h1><p className="text-sm text-muted-foreground">Evidence-bound architecture illumination. Missing or stale verification remains dark; no inferred completion.</p></header>
    <section className="rounded-xl border p-4 space-y-3" aria-label="Snapshot inputs">
      <label className="block text-sm font-medium" htmlFor="snapshot-file">Load a local, reviewed JSON graph snapshot</label>
      <input id="snapshot-file" type="file" accept=".json,application/json" onChange={loadFile} className="block w-full text-sm" />
      <p className="text-xs text-muted-foreground">Read-only; files remain in this browser. No live GitHub results or certification are inferred.</p>
      {error&&<p role="alert">{error}</p>}
      <p role="status" className="text-sm">{data.valid?`Snapshot SHA: ${data.sha} — ${data.components.length} nodes, ${data.edges.length} edges`:`UNKNOWN — ${data.reason}`}</p>
    </section>
    <section className="space-y-3" aria-label="Component architecture">
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold mr-auto">Architecture illumination</h2>{[['ALL','All'],['REMAINING','Remaining dark'],['PASS','Verified only']].map(([id,label])=><button type="button" key={id} onClick={()=>setFilter(id)} aria-pressed={filter===id} className="rounded-lg border px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2">{label}</button>)}</div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
        <div className="min-h-72 rounded-xl p-4" style={{background:'#0b1320'}}><div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{rows.map(c=><button type="button" key={c.id} onClick={()=>setSelected(c.id)} className="rounded-lg border p-4 text-left focus-visible:outline focus-visible:outline-2" style={{color:'#e7edf5',background:c.derived.state==='PASS'?'#153e35':'#1b2635',borderColor:palette[c.derived.state]||palette.UNKNOWN,boxShadow:c.derived.state==='PASS'?'0 0 14px #57e7ae50':'none'}} aria-label={`${c.name}: ${c.derived.state}`}><span className="block font-medium break-words">{c.name}</span><span className="block text-xs mt-2" style={{color:palette[c.derived.state]}}>{c.derived.state}</span></button>)}</div>{!rows.length&&<p className="text-sm" style={{color:'#aab6c7'}}>No components available in this filter. This is not proof that work is complete.</p>}</div>
        <aside aria-label="Node evidence inspector" className="rounded-xl border p-4 space-y-2 break-words"><h3 className="font-semibold">Evidence inspector</h3>{active?<><p>{active.name}</p><p className="text-sm">{active.derived.state}: {active.derived.reason}</p><p className="text-xs">Component ID: {active.id}</p><p className="text-xs">Source SHA: {active.source_sha||'UNKNOWN'}</p><h4 className="text-sm font-medium">Mandatory gates</h4><ul className="text-xs space-y-1">{(active.gates||[]).map(g=><li key={g.id}>{g.id}: {g.state} {g.evidence_id?`— ${g.evidence_id}`:'— no evidence'}</li>)}</ul></>:<p className="text-sm text-muted-foreground">Select a component to inspect its reasons and gate records.</p>}</aside>
      </div>
    </section>
    <p className="text-xs text-muted-foreground">This initial isolated implementation renders component status cards; connector ingestion, edge routing, interactive topology, historical playback and production certification remain OPEN.</p>
  </main>;
}

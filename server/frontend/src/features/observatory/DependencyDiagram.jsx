import { useMemo } from 'react';
const tones={PASS:'#54d9a3',PROVISIONAL:'#dec075',OPEN:'#dec075',BLOCKED:'#ef8181',FAIL:'#ef8181',UNKNOWN:'#8795a8',NOT_STARTED:'#687586',AUDIT_ONLY:'#8795a8',SUPERSEDED:'#687586'};
/** Bounded read-only topology: edges only represent unverified declarations. */
export default function DependencyDiagram({components=[],edges=[],selected}){
 const layout=useMemo(()=>components.map((node,i)=>({node,x:14+(i%2)*178,y:20+Math.floor(i/2)*106})),[components]);
 const index=new Map(layout.map(x=>[x.node.id,x]));
 const height=Math.max(150,Math.ceil(layout.length/2)*106+24);
 return <div className="overflow-x-auto rounded-xl border p-2" aria-label="Declared dependency topology diagram">
  <svg viewBox={`0 0 370 ${height}`} role="img" aria-label="Unverified component dependency diagram. Select nodes with the accompanying accessible buttons." className="w-full min-w-[320px]" style={{maxHeight:850,background:'#0b1320',borderRadius:12}}>
   {edges.map(e=>{const a=index.get(e.source),b=index.get(e.target);if(!a||!b)return null;return <line key={e.id} x1={a.x+80} y1={a.y+35} x2={b.x+80} y2={b.y+35} stroke="#8a98ad" strokeWidth="1.7" strokeDasharray="5 5" opacity=".8"/>})}
   {layout.map(({node,x,y})=><g key={node.id}><rect x={x} y={y} width="160" height="70" rx="9" fill={node.derived.state==='PASS'?'#164338':'#202b3b'} stroke={tones[node.derived.state]||tones.UNKNOWN} strokeWidth={selected===node.id?3:1.5}/><text x={x+10} y={y+25} fill="#ecf1f9" fontSize="12">{String(node.name||node.id).slice(0,22)}</text><text x={x+10} y={y+48} fill={tones[node.derived.state]||tones.UNKNOWN} fontSize="10">{node.derived.state}</text></g>)}
  </svg>
  <p className="text-xs text-muted-foreground mt-2">Dashed connections represent declared relationships, not verified execution. Node selection uses the keyboard-accessible cards above.</p>
 </div>;
}

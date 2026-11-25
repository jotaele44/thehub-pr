import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftRight, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SYNTHETIC_TONE } from '@/lib/evidenceState';
import { formatCount, kindLabel, linkedNodes, otherLens, stageTitle } from '@/lib/constellation/model';

const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';
const action = 'inline-flex min-h-[44px] items-center gap-2 rounded-md border border-border bg-card px-3 text-left text-sm font-medium text-foreground hover:bg-muted';

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-mono text-lg font-semibold text-foreground">{value}</dd>
      {hint ? <dd className="text-[11px] text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}

function StageOverview({ model, stage, stageIndex }) {
  const { totals } = model;
  return (
    <div className="space-y-3" data-constellation-stage-card={stage.id}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Stage {stageIndex + 1} of {model.stages.length}
      </p>
      <h2 className="text-lg font-semibold text-foreground">{stageTitle(stage)}</h2>
      <p lang="es" className="text-sm text-muted-foreground">{stage.subtitle_es}</p>
      <p className="text-sm text-foreground">{stage.summary}</p>
      <dl className="grid grid-cols-2 gap-2">
        <Stat label="Rows exported" value={formatCount(totals.exported)} hint="graph_summary totals" />
        <Stat label="In this store" value={formatCount(totals.stored)} hint="canonical rows in hub.db" />
        <Stat label="Correlations" value={formatCount(totals.correlations)} hint="all synthetic candidates" />
        <Stat label="Apps" value={model.apps.size} />
      </dl>
      <p className="text-xs text-muted-foreground">Select a node on the stage or in the list below to see what it is.</p>
    </div>
  );
}

function Connections({ model, lens, node, onSelect }) {
  const { edges, nodes, legend } = model.lenses[lens];
  const labels = Object.fromEntries(legend.map((l) => [l.kind, l.label]));
  const rows = edges.filter((e) => e.kind !== 'member' && (e.from === node.id || e.to === node.id));
  if (!rows.length) return null;
  return (
    <section aria-label="Connections" className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Connections</h3>
      <ul className="space-y-2">
        {rows.map((e) => {
          const outgoing = e.from === node.id;
          const other = nodes.get(outgoing ? e.to : e.from);
          return (
            <li key={e.id} className="rounded-md border border-border bg-background p-2 text-sm" data-constellation-edge={e.kind}>
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn(chip, 'border-border font-mono text-muted-foreground')}>{labels[e.kind] || e.kind}</span>
                <span className="text-muted-foreground">{outgoing ? 'to' : 'from'}</span>
                <button type="button" className="min-h-[44px] font-mono text-primary underline" onClick={() => onSelect(other.id)}>
                  {other.label}
                </button>
                {e.weight !== undefined ? <span className="font-mono text-xs text-muted-foreground">{formatCount(e.weight)}</span> : null}
                {e.synthetic ? <span className={cn(chip, SYNTHETIC_TONE)}>Synthetic candidates</span> : null}
              </div>
              {e.artifact || e.contract ? (
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {[e.artifact, e.contract && `contract ${e.contract}`].filter(Boolean).join(' · ')}
                </p>
              ) : null}
              {e.seam ? <p className="mt-1 text-xs text-foreground">{e.seam}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ContentFacts({ node }) {
  return (
    <>
      {node.total !== undefined || node.stored !== undefined ? (
        <dl className="grid grid-cols-2 gap-2">
          <Stat label="Exported" value={formatCount(node.total)} hint={node.total === null ? 'not in graph_summary' : 'graph_summary total'} />
          <Stat label="In this store" value={formatCount(node.stored)} hint="rows in hub.db" />
        </dl>
      ) : null}
      {node.synthetic ? (
        <p className={cn('rounded-md border p-2 text-xs', SYNTHETIC_TONE)}>
          Every link here is a synthetic CANDIDATE derived by the Hub, not an identity claim.
        </p>
      ) : null}
      {node.seam ? <p className="rounded-md border border-border bg-background p-2 text-xs text-foreground">{node.seam}</p> : null}
      {node.lineage?.length ? (
        <section aria-label="Lineage" className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Produced by</h3>
          <ul className="space-y-1">
            {node.lineage.map((l) => (
              <li key={`${l.script}-${l.phase}`} className="font-mono text-xs text-foreground">
                {l.script || 'unrecorded script'} · {l.phase || 'no phase'} · {formatCount(l.count)} rows
                {l.inputs?.length ? <span className="block text-muted-foreground">from {l.inputs.join(', ')}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {node.samples?.length ? (
        <section aria-label="Sample records" className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sample records</h3>
          <ul className="space-y-1.5">
            {node.samples.map((s) => (
              <li key={s.id} className="rounded-md border border-border bg-background p-2 text-sm" data-constellation-sample={s.id}>
                <p className="text-foreground">{s.label}</p>
                <p className="flex flex-wrap items-center gap-x-2 font-mono text-[11px] text-muted-foreground">
                  <span>{s.id}</span>
                  {s.type ? <span>· {s.type}</span> : null}
                  {s.municipality ? <span>· {s.municipality}</span> : null}
                  {s.date ? <span>· {s.date}</span> : null}
                  {s.synthetic ? <span className={cn(chip, SYNTHETIC_TONE)}>Synthetic / test row</span> : null}
                </p>
                <Link className="text-xs text-primary underline" to={s.href}>Provenance</Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

// The side panel: the stage when nothing is selected, otherwise what the
// selected node is, what it connects to and, through lineage, where it shows up
// in the other lens.
export default function NodeDetails({ model, lens, node, stage, stageIndex, onSelect, onShowIn, onClose }) {
  if (!node) return <StageOverview model={model} stage={stage} stageIndex={stageIndex} />;
  const app = model.apps.get(node.app);
  const target = otherLens(lens);
  const linked = node.kind === 'app' ? [node] : linkedNodes(model, lens, node.id);
  return (
    <div className="space-y-3" data-constellation-details={node.id}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{kindLabel(node.kind)}</p>
          <h2 className="break-words font-mono text-lg font-semibold text-foreground">{node.label}</h2>
          <p className="break-all font-mono text-xs text-muted-foreground">{node.sublabel}</p>
        </div>
        <button type="button" className={cn(action, 'shrink-0 px-2.5')} onClick={onClose} aria-label="Close details">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {app ? <span className={cn(chip, 'border-border text-foreground')}>{app.name}</span> : null}
        {app?.registry_status ? <span className={cn(chip, 'border-border font-mono text-muted-foreground')}>{app.registry_status}</span> : null}
        {node.status ? <span className={cn(chip, 'border-border text-muted-foreground')}>{node.status} seam</span> : null}
        {node.generated ? <span className={cn(chip, 'border-border text-muted-foreground')}>built at runtime</span> : null}
      </div>
      {node.summary ? <p className="text-sm text-foreground">{node.summary}</p> : null}
      {lens === 'content' ? <ContentFacts node={node} /> : null}
      <Connections model={model} lens={lens} node={node} onSelect={onSelect} />
      {linked.length ? (
        <section aria-label={`In the ${target} lens`} className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">In the {target} lens</h3>
          <div className="flex flex-wrap gap-2">
            {linked.map((other) => (
              <button key={other.id} type="button" className={action} onClick={() => onShowIn(target, other.id)}>
                <ArrowLeftRight className="h-4 w-4" aria-hidden="true" />
                <span className="font-mono">{other.label}</span>
                <span className="sr-only">{` (${kindLabel(other.kind)}, ${other.sublabel})`}</span>
              </button>
            ))}
          </div>
        </section>
      ) : (
        <p className="text-xs text-muted-foreground">No lineage links this node to the {target} lens.</p>
      )}
    </div>
  );
}

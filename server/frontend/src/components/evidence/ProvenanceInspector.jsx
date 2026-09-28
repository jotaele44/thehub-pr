import React from 'react';
import { cn } from '@/lib/utils';
import IdCode from '@/components/shared/IdCode';
import EvidenceStateStrip from './EvidenceStateStrip';
import { EVIDENCE_AXES, axisValue, contradictionState, edgeState } from '@/lib/evidenceState';

const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';

function Section({ title, children, empty }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4" aria-label={title}>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      <div className="mt-3">{children || <p className="text-sm text-muted-foreground">{empty}</p>}</div>
    </section>
  );
}

function StateBases({ evidence }) {
  return (
    <dl className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2" data-evidence-bases>
      {EVIDENCE_AXES.filter((axis) => axis.basisKey).map((axis) => (
        <div key={axis.key}>
          <dt className="text-muted-foreground">{axis.label}: {axisValue(axis, evidence[axis.key]).label}</dt>
          <dd className="mt-0.5 break-words text-foreground">{evidence[axis.basisKey] || '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

function TimeAndPlace({ evidence }) {
  const coords = evidence.geometry?.coordinates;
  const rows = [
    ['Observed at (at stated precision)', evidence.observed_at],
    ['Valid from', evidence.valid_from],
    ['Valid to', evidence.valid_to],
    ['Retrieved at', evidence.retrieved_at],
    ['Area reference', evidence.area_reference],
    ['Point (lon, lat)', Array.isArray(coords) ? coords.join(', ') : null],
    ['Producer confidence (separate axis)', evidence.confidence],
  ];
  return (
    <dl className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="mt-0.5 break-words font-mono-id text-foreground">{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

function Lineage({ lineage }) {
  const edges = lineage?.edges || [];
  const nodes = new Map((lineage?.nodes || []).map((node) => [node.node_id, node]));
  const missing = (lineage?.nodes || []).filter((node) => node.kind === 'SOURCE_MISSING');
  return (
    <div className="space-y-3">
      {missing.length ? (
        <p className="text-sm text-status-danger-fg" data-lineage-source-missing>
          No source reference: the chain ends here. No source has been substituted.
        </p>
      ) : null}
      {edges.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Lineage edges</caption>
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">From</th>
                <th scope="col" className="py-1 pr-3 font-medium">Relationship</th>
                <th scope="col" className="py-1 pr-3 font-medium">To</th>
                <th scope="col" className="py-1 pr-3 font-medium">Edge state</th>
                <th scope="col" className="py-1 pr-3 font-medium">Method / basis</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => {
                const state = edgeState(edge.edge_state);
                return (
                  <tr key={edge.edge_id} className="border-t border-border align-top" data-lineage-edge={edge.relationship_type}>
                    <td className="py-1.5 pr-3"><span className="text-muted-foreground">{nodes.get(edge.from)?.kind}</span><br /><IdCode>{nodes.get(edge.from)?.label || edge.from}</IdCode></td>
                    <td className="py-1.5 pr-3 font-medium">{edge.relationship_type}</td>
                    <td className="py-1.5 pr-3"><span className="text-muted-foreground">{nodes.get(edge.to)?.kind}</span><br /><IdCode>{nodes.get(edge.to)?.label || edge.to}</IdCode></td>
                    <td className="py-1.5 pr-3"><span className={cn(chip, state.tone)} data-edge-state={state.value} title={state.description}>{state.label}</span></td>
                    <td className="py-1.5 pr-3 break-words">{edge.derivation_method}<br /><span className="text-muted-foreground">{edge.basis}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No lineage edges were recorded for this record.</p>
      )}
    </div>
  );
}

function Contradictions({ items }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const state = contradictionState(item.status);
        return (
          <li key={item.contradiction_id} className="rounded-lg border border-border p-3 text-sm" data-contradiction={item.contradiction_id}>
            <span className={cn(chip, state.tone)}>{state.label}</span>
            <dl className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              <div><dt className="text-xs text-muted-foreground">Claim A ({item.source_a || 'no source'})</dt><dd>{item.claim_a}</dd></div>
              <div><dt className="text-xs text-muted-foreground">Claim B ({item.source_b || 'no source'})</dt><dd>{item.claim_b}</dd></div>
            </dl>
            {item.rationale ? <p className="mt-2 text-xs text-muted-foreground">{item.rationale}</p> : null}
          </li>
        );
      })}
    </ul>
  );
}

export default function ProvenanceInspector({ evidence }) {
  return (
    <div className="space-y-4" data-evidence-id={evidence.id}>
      <Section title="Evidence state">
        <EvidenceStateStrip evidence={evidence} />
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          Each axis is independent. Missing producer declarations fail closed; proximity, timing and name similarity are never promoted to identity or relationship.
        </p>
      </Section>

      <Section title="Why each state holds"><StateBases evidence={evidence} /></Section>
      <Section title="Time and place"><TimeAndPlace evidence={evidence} /></Section>
      <Section title="Lineage"><Lineage lineage={evidence.lineage} /></Section>

      <Section title="Citations" empty="No source is cited by this record.">
        {evidence.citations?.length ? (
          <ul className="space-y-2 text-sm">
            {evidence.citations.map((citation) => (
              <li key={citation.source_id}>
                <IdCode>{citation.source_id}</IdCode> — {citation.title || 'untitled source'}{' '}
                <span className="text-xs text-muted-foreground">({citation.source_state})</span>
                {citation.url ? (
                  <div><a className="break-all text-xs text-primary underline" href={citation.url} target="_blank" rel="noopener noreferrer">{citation.url}</a></div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="Contradictions" empty="No contradiction is recorded. Absence of a recorded contradiction is not evidence of agreement.">
        {evidence.contradictions?.length ? <Contradictions items={evidence.contradictions} /> : null}
      </Section>

      <Section title="Computations and interpretations" empty="No Hub computation or declared interpretation.">
        {evidence.computations?.length || evidence.interpretations?.length ? (
          <ul className="space-y-1 text-sm">
            {(evidence.computations || []).map((c, i) => (
              <li key={`c${i}`}>Computation: {c.method} by {c.producer}{c.algorithm ? ` (${c.algorithm})` : ''}</li>
            ))}
            {(evidence.interpretations || []).map((item, i) => (
              <li key={`i${i}`}>Interpretation (not a measurement): {item.basis}</li>
            ))}
          </ul>
        ) : null}
      </Section>

      {evidence.declaration_errors?.length ? (
        <Section title="Rejected producer declarations">
          <ul className="list-disc space-y-1 pl-5 text-sm text-status-danger-fg">
            {evidence.declaration_errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </Section>
      ) : null}

      <Section title="Audit">
        <dl className="grid grid-cols-1 gap-3 text-xs md:grid-cols-2">
          <div><dt className="text-muted-foreground">Producer record</dt><dd><IdCode>{evidence.producer_record_id}</IdCode> ({evidence.producer_repo})</dd></div>
          <div><dt className="text-muted-foreground">Row SHA-256</dt><dd><IdCode className="break-all">{evidence.audit_metadata?.row_sha256}</IdCode></dd></div>
          <div><dt className="text-muted-foreground">Contract status</dt><dd>{evidence.audit_metadata?.contract_status}</dd></div>
          <div><dt className="text-muted-foreground">Projected at</dt><dd><IdCode>{evidence.audit_metadata?.projected_at}</IdCode></dd></div>
        </dl>
      </Section>
    </div>
  );
}

import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Network } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import IdCode from '@/components/shared/IdCode';
import EvidenceStateStrip from '@/components/evidence/EvidenceStateStrip';
import { cn } from '@/lib/utils';
import { SYNTHETIC_TONE, edgeState, evidenceHref } from '@/lib/evidenceState';

const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';
const DIRECTION = { OUTBOUND: 'to', INBOUND: 'from', SELF: 'self' };

function Section({ title, children }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4" aria-label={title}>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Identity({ identity }) {
  return (
    <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3" data-identity-state={identity.identity_state}>
      <div><dt className="text-xs text-muted-foreground">Identity state</dt><dd className="font-medium">{identity.identity_state}</dd></div>
      <div><dt className="text-xs text-muted-foreground">Scope</dt><dd>{identity.identity_scope}</dd></div>
      <div><dt className="text-xs text-muted-foreground">Basis</dt><dd>{identity.identity_basis}</dd></div>
      <div className="md:col-span-3">
        <dt className="text-xs text-muted-foreground">Identity registry</dt>
        <dd data-registry-status={identity.registry_status}>
          {identity.registry_status === 'NOT_CONFIGURED'
            ? 'Not consulted: no registry is connected to the Hub store, so no producer record is merged with another.'
            : 'Consulted.'}
        </dd>
      </div>
      <div className="md:col-span-3">
        <dt className="text-xs text-muted-foreground">Producer records</dt>
        <dd className="flex flex-wrap gap-2">
          {identity.members.map((m) => <span key={`${m.producer}:${m.record_id}`}>{m.producer} · <IdCode>{m.record_id}</IdCode></span>)}
        </dd>
      </div>
    </dl>
  );
}

function Relationships({ items, truncated, limit }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">The Hub holds no relationship that names this entity.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <caption className="sr-only">Relationships naming this entity</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-1 pr-3 font-medium">Relationship</th>
            <th scope="col" className="py-1 pr-3 font-medium">Other entity</th>
            <th scope="col" className="py-1 pr-3 font-medium">Edge state</th>
            <th scope="col" className="py-1 pr-3 font-medium">Producer</th>
            <th scope="col" className="py-1 pr-3 font-medium">Provenance</th>
          </tr>
        </thead>
        <tbody>
          {items.map((edge) => {
            const state = edgeState(edge.edge_state);
            return (
              <tr key={edge.evidence_id} className="border-t border-border align-top" data-relationship={edge.record_id}>
                <td className="py-1.5 pr-3">{edge.relationship_type} <span className="text-muted-foreground">({DIRECTION[edge.direction]})</span></td>
                <td className="py-1.5 pr-3">
                  {edge.counterpart.resolved
                    ? <Link className="text-primary underline" to={edge.counterpart.entity_href}>{edge.counterpart.title}</Link>
                    : <span className="text-muted-foreground">Not held by the Hub · <IdCode>{edge.counterpart.record_id}</IdCode></span>}
                </td>
                <td className="py-1.5 pr-3">
                  <span className={cn(chip, state.tone)} data-edge-state={state.value} title={edge.edge_basis}>{state.label}</span>
                  {edge.synthetic ? <span className={cn(chip, 'ml-1', SYNTHETIC_TONE)}>Synthetic</span> : null}
                </td>
                <td className="py-1.5 pr-3">{edge.producers.join(', ')}</td>
                <td className="py-1.5 pr-3"><Link className="text-primary underline" to={edge.evidence_href}>Inspect</Link></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {truncated ? <p className="mt-2 text-xs text-muted-foreground">Showing the first {limit}; more relationships exist.</p> : null}
    </div>
  );
}

// Global entity page (FDX-051): one canonical entity with what the Hub store
// already links to it. Producers stay canonical; nothing is merged or inferred.
export default function EntityPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ['entity-composition', id],
    queryFn: () => federation.composition.get(id),
    retry: false,
  });

  return (
    <div>
      <PageHeader
        icon={Network}
        title="Entity"
        description="One producer entity with the relationships, records and sources the Hub holds for it. Identity is shown as recorded, never inferred."
      />
      {isLoading ? (
        <p role="status" className="text-sm text-muted-foreground">Loading entity…</p>
      ) : error ? (
        <div role="alert" className="rounded-xl border border-border bg-card p-4 text-sm">
          {error.status === 404
            ? `The Hub holds no entity ${id}. Nothing is shown in its place.`
            : `The entity could not be loaded: ${error.message}`}
        </div>
      ) : data ? (
        <div className="space-y-4" data-entity-id={id}>
          <div>
            <h2 className="text-lg font-semibold text-foreground">{data.anchor.title}</h2>
            <p className="text-xs text-muted-foreground">
              {data.anchor.canonical_type} · {data.anchor.producer_repo} · <IdCode>{id}</IdCode> ·{' '}
              <Link className="text-primary underline" to={evidenceHref('Entities', id)}>Full provenance</Link>
            </p>
            <EvidenceStateStrip evidence={data.anchor} className="mt-3" />
          </div>
          <Section title="Identity"><Identity identity={data.identity} /></Section>
          <Section title="Relationships">
            <Relationships items={data.relationships} truncated={data.truncated.relationships} limit={data.limits.relationships} />
          </Section>
          <Section title="Linked records">
            {data.linked_records.length ? (
              <ul className="space-y-1 text-sm">
                {data.linked_records.map((record) => (
                  <li key={record.evidence_id} data-linked-record={record.record_id}>
                    <Link className="text-primary underline" to={record.evidence_href}>{record.title}</Link>{' '}
                    <span className="text-xs text-muted-foreground">{record.collection} · {record.producers.join(', ')}</span>
                    {record.synthetic ? <span className={cn(chip, 'ml-1', SYNTHETIC_TONE)}>Synthetic</span> : null}
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">No observation or alert in the Hub names this entity.</p>}
          </Section>
          <Section title="Producers">
            <ul className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
              {data.sections.map((s) => (
                <li key={s.producer} className="flex justify-between gap-2" data-producer-section={s.status}>
                  <span>{s.producer}</span>
                  <span className="text-xs text-muted-foreground">
                    {s.status === 'AVAILABLE' ? `${s.relationship_count} relationships · ${s.linked_record_count} records` : 'No data for this entity'}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      ) : null}
    </div>
  );
}

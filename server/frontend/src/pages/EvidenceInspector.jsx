import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ScanSearch } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import ProvenanceInspector from '@/components/evidence/ProvenanceInspector';

// Deep-linkable provenance inspector: /evidence/:collection/:id renders the
// FEDERATION_EVIDENCE_OBJECT_V1 view of one Hub store record.
export default function EvidenceInspector() {
  const { collection, id } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ['evidence', collection, id],
    queryFn: () => federation.evidence.get(collection, id),
    retry: false,
  });

  return (
    <div>
      <PageHeader
        icon={ScanSearch}
        title="Provenance inspector"
        description="Where this record came from, how it is known, and what the Federation can and cannot claim about it."
      />
      {isLoading ? (
        <p role="status" className="text-sm text-muted-foreground">Loading evidence object…</p>
      ) : error ? (
        <div role="alert" className="rounded-xl border border-border bg-card p-4 text-sm">
          {error.status === 404
            ? `The Hub holds no ${collection} record ${id}. Nothing is shown in its place.`
            : `The evidence object could not be loaded: ${error.message}`}
        </div>
      ) : data ? (
        <>
          <h2 className="mb-1 text-lg font-semibold text-foreground">{data.title}</h2>
          <p className="mb-4 text-xs text-muted-foreground">
            {data.canonical_type} · {data.producer_repo} · <span className="font-mono-id">{data.id}</span>
          </p>
          <ProvenanceInspector evidence={data} />
        </>
      ) : null}
    </div>
  );
}

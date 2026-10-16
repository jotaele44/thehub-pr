import React, { useEffect, useState } from 'react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';

export default function UsgsCatalog() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [program, setProgram] = useState('');
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    federation.usgs.catalog({ signal: controller.signal }).then(setData).catch((e) => {
      if (e.name !== 'AbortError') setError(e.message || 'Catalog could not be loaded');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);
  const rows = (data?.records || []).filter((r) =>
    (!program || r.consumer_candidates.some((c) => c.program_id === program)) &&
    `${r.raw.Title} ${r.sciencebase_id} ${r.raw.DOI || ''}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="space-y-5">
    <PageHeader title="USGS Puerto Rico catalog" subtitle="Release inventory, proposed consumers, and acquisition evidence" />
    <Button onClick={() => setReload((r) => r + 1)} disabled={loading}>Reload catalog</Button>
    {loading && <p role="status">Loading catalog…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <>
      <p>{data.counts.included} included releases · {data.counts.excluded} excluded candidates · {data.acquisition_summary?.activated ?? 0} payloads activated</p>
      {data.continuation_summary && <p>{data.continuation_summary.item_count} enumerated items · {data.continuation_summary.file_count} file descriptors · {data.continuation_summary.payload_states.PASS} byte verified · {data.continuation_summary.payload_states.FAIL} quarantined · {data.continuation_summary.payload_states.BLOCKED} blocked. Byte verification does not establish scientific fitness.</p>}
      {data.producer_export_summary && <p>Spiderweb documentary test export: {data.producer_export_summary.asset_count}/{data.producer_export_summary.inventory_file_count} asset files, {data.producer_export_summary.sources} sources, {data.producer_export_summary.features} native features; validation {data.producer_export_summary.state}. Production export and activation: {data.producer_export_summary.activation_state}.</p>}
      <p>Consumer assignments are review candidates. Payload activation remains blocked until verification passes.</p>
      <details><summary>Scope, provenance, and unresolved issues</summary>
        <p className="break-all">Workbook SHA-256: {data.source.sha256}</p>
        <p>Catalog state: {data.catalog_state}. Payload state: {data.payload_state}.</p>
        {data.issues.map((issue, i) => <p key={i}>{issue.kind}: {issue.detail} ({issue.state})</p>)}
        <pre className="overflow-auto text-xs">{JSON.stringify({ acquisition: data.acquisition_summary, continuation: data.continuation_summary, producerExport: data.producer_export_summary }, null, 2)}</pre>
      </details>
      <div className="flex flex-wrap gap-3">
        <label htmlFor="usgs-release-search">Search releases</label>
        <input id="usgs-release-search" className="rounded border bg-background p-2" value={query} onChange={(e) => setQuery(e.target.value)} />
        <label htmlFor="usgs-consumer-filter">Consumer</label>
        <select id="usgs-consumer-filter" className="rounded border bg-background p-2" value={program} onChange={(e) => setProgram(e.target.value)}>
          <option value="">All consumers</option>
          {data.repositories.map((r) => <option key={r.program_id} value={r.program_id}>{r.program_id}</option>)}
        </select>
      </div>
      <p role="status">{rows.length} releases shown</p>
      <div className="space-y-3">{rows.map((row) => <article key={row.sciencebase_id} className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">{row.raw.Title}</h2>
        <p>{row.raw.Category} · Release year: {row.raw.Year}</p>
        <a className="underline" href={row.raw['ScienceBase URL']} target="_blank" rel="noopener noreferrer">ScienceBase release</a>
        {row.raw.DOI && <a className="ml-4 underline" href={row.raw.DOI} target="_blank" rel="noopener noreferrer">DOI</a>}
        <p>Consumer candidates: {row.consumer_candidates.map((c) => c.program_id).join(', ')}</p>
        <p>Acquisition: {row.acquisition?.state || 'OPEN'} · HTTP: {row.acquisition?.http_status ?? 'unavailable'} · Payload: {row.activation_state}</p>
        <details><summary>Inspect release evidence</summary>
          <pre className="overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(row, null, 2)}</pre>
        </details>
      </article>)}</div>
      {!rows.length && <p>No releases match these filters.</p>}
    </>}
  </div>;
}

import React, { useMemo, useState } from 'react';
import { IMAGERY_PROVIDER_REGISTRY } from './imageryProviderRegistry';

export default function ImageryProviderInspector() {
  const [providerId, setProviderId] = useState(IMAGERY_PROVIDER_REGISTRY[0]?.providerId || '');
  const provider = useMemo(
    () => IMAGERY_PROVIDER_REGISTRY.find((item) => item.providerId === providerId) || IMAGERY_PROVIDER_REGISTRY[0],
    [providerId],
  );
  if (!provider) return null;

  return (
    <section className="space-y-2 rounded-md border border-border bg-muted/20 p-3" aria-label="Imagery provider provenance inspector">
      <div>
        <div className="text-xs font-medium">Imagery provider provenance</div>
        <div className="text-[11px] text-muted-foreground">Render manifestations and retained source manifestations remain separate identities.</div>
      </div>
      <label className="block text-[11px] font-medium" htmlFor="imagery-provider-inspector">Provider / source</label>
      <select
        id="imagery-provider-inspector"
        className="w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
        value={provider.providerId}
        onChange={(event) => setProviderId(event.target.value)}
      >
        {IMAGERY_PROVIDER_REGISTRY.map((item) => <option key={item.providerId} value={item.providerId}>{item.label}</option>)}
      </select>
      <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-2 gap-y-1 text-[11px]">
        <dt className="text-muted-foreground">Manifestation</dt><dd className="break-words">{provider.manifestationType}</dd>
        <dt className="text-muted-foreground">Classes</dt><dd className="break-words">{provider.classes.join(' · ')}</dd>
        <dt className="text-muted-foreground">Authority</dt><dd className="break-words">{provider.authority}</dd>
        <dt className="text-muted-foreground">Availability</dt><dd className="break-words">{provider.availability}</dd>
        <dt className="text-muted-foreground">Temporal</dt><dd className="break-words">{provider.temporalCoverage}</dd>
        <dt className="text-muted-foreground">Resolution</dt><dd className="break-words">{provider.resolution}</dd>
        <dt className="text-muted-foreground">Retention</dt><dd className="break-words">{provider.retention}</dd>
        <dt className="text-muted-foreground">Download</dt><dd className="break-words">{provider.download}</dd>
        <dt className="text-muted-foreground">Attribution</dt><dd className="break-words">{provider.attribution}</dd>
      </dl>
      <div className="break-all border-t border-border pt-2 font-mono text-[10px] text-muted-foreground">{provider.endpoint}</div>
      {provider.manifestationType === 'RENDER_MANIFESTATION' ? (
        <div className="text-[11px] text-muted-foreground">Presentation only. This provider cannot alter canonical geometry, entity identity, or retained source evidence.</div>
      ) : (
        <div className="text-[11px] text-muted-foreground">Retained assets require asset-level URL, native metadata, retrieval UTC, CRS, temporal metadata and SHA256 before evidence certification.</div>
      )}
    </section>
  );
}

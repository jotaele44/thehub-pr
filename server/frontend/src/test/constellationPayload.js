// A small GET /api/constellation payload in the real shape, for unit and
// end-to-end tests. Two apps, three stages, both lenses.

const anchors = [
  {
    id: 'app:centinelas', kind: 'app', app: 'centinelas', stage: 'signal-intake', label: 'Centinelas',
    sublabel: 'centinelas-pr · Pre-signal monitoring', summary: 'Pre-signal monitoring', registry_status: 'ready_for_live',
  },
  {
    id: 'app:thehub', kind: 'app', app: 'thehub', stage: 'hub-aggregate', label: 'TheHub',
    sublabel: 'thehub-pr · Federation control plane', summary: 'Federation control plane', registry_status: null,
  },
];

const code = (id, app, stage, label, path, kind, summary) => ({
  id, kind, app, stage, label, sublabel: `${app === 'thehub' ? 'thehub-pr' : 'centinelas-pr'} · ${path}`,
  summary, path, generated: false,
});

export const constellationPayload = {
  schema_version: 'prii_constellation_v1',
  contract_id: 'federation-constellation-v1',
  store_status: 'AVAILABLE',
  apps: [
    { id: 'centinelas', program_id: 'centinelas-pr', name: 'Centinelas', domain: 'Pre-signal monitoring', home_stage: 'signal-intake', registry_status: 'ready_for_live' },
    { id: 'thehub', program_id: 'thehub-pr', name: 'TheHub', domain: 'Federation control plane', home_stage: 'hub-aggregate', registry_status: null },
  ],
  stages: [
    {
      id: 'signal-intake', index: 0, title: { lead: 'SIGNAL', accent: 'INTAKE' }, subtitle_es: 'Captura de señales · Centinelas',
      apps: ['centinelas'], overview: false,
      summary: 'Centinelas polls news feeds and drops finance items as files.',
      focus: {
        code: ['app:centinelas', 'centinelas.poll', 'centinelas.dispatch'],
        content: ['app:centinelas', 'content:centinelas:observations', 'content:seam:intake-drops'],
      },
    },
    {
      id: 'hub-aggregate', index: 1, title: { lead: 'HUB', accent: 'AGGREGATE' }, subtitle_es: 'Agregación y validación',
      apps: ['thehub'], overview: false,
      summary: 'The Hub validates and unions every package.',
      focus: {
        code: ['app:thehub', 'thehub.fetch', 'thehub.aggregate', 'centinelas.export'],
        content: ['app:thehub', 'content:thehub:stream:observations', 'content:thehub:correlation:alerts'],
      },
    },
    {
      id: 'federation', index: 2, title: { lead: 'THE', accent: 'FEDERATION' }, subtitle_es: 'La federación completa',
      apps: ['centinelas', 'thehub'], overview: true,
      summary: 'Producers hand artifacts to the Hub.',
      focus: {
        code: ['app:centinelas', 'app:thehub', 'centinelas.poll', 'centinelas.dispatch', 'centinelas.export', 'thehub.fetch', 'thehub.aggregate'],
        content: ['app:centinelas', 'app:thehub', 'content:centinelas:observations', 'content:seam:intake-drops',
          'content:thehub:stream:observations', 'content:thehub:correlation:alerts'],
      },
    },
  ],
  lenses: {
    code: {
      legend: [
        { kind: 'call', label: 'CALL', label_es: 'LLAMADA', tone: 1, meaning: 'Invokes or reads something inside the same app.' },
        { kind: 'handoff', label: 'HANDOFF', label_es: 'ENTREGA', tone: 2, meaning: 'An artifact crosses an app boundary.' },
        { kind: 'result', label: 'RESULT', label_es: 'RESULTADO', tone: 3, meaning: 'Writes an artifact.' },
      ],
      nodes: [
        ...anchors,
        code('centinelas.poll', 'centinelas', 'signal-intake', 'poll_all', 'src/centinelas/ingest/rss.py', 'module', 'Polls the feeds.'),
        code('centinelas.dispatch', 'centinelas', 'signal-intake', 'dispatch', 'src/centinelas/route/dispatch.py', 'module', 'Writes intake drops.'),
        code('centinelas.export', 'centinelas', 'hub-aggregate', 'federation_export', 'scripts/federation_export.py', 'script', 'Writes the canonical package.'),
        code('thehub.fetch', 'thehub', 'hub-aggregate', 'fetch_all', 'src/hub/fetch.py', 'module', 'Clones each producer.'),
        code('thehub.aggregate', 'thehub', 'hub-aggregate', 'aggregate', 'src/hub/aggregate.py', 'module', 'Unions validated rows.'),
      ],
      edges: [
        { id: 'member:app:centinelas->centinelas.poll', kind: 'member', from: 'app:centinelas', to: 'centinelas.poll' },
        { id: 'call:centinelas.poll->centinelas.dispatch', kind: 'call', from: 'centinelas.poll', to: 'centinelas.dispatch' },
        { id: 'handoff:centinelas.export->thehub.fetch', kind: 'handoff', from: 'centinelas.export', to: 'thehub.fetch', contract: 'federation_export_manifest', artifact: 'canonical package' },
        { id: 'call:thehub.fetch->thehub.aggregate', kind: 'call', from: 'thehub.fetch', to: 'thehub.aggregate' },
        { id: 'result:centinelas.dispatch->centinelas.export', kind: 'result', from: 'centinelas.dispatch', to: 'centinelas.export', status: 'dormant', seam: 'Dormant: no intake directories are materialized.' },
      ],
    },
    content: {
      legend: [
        { kind: 'flow', label: 'RECORDS', label_es: 'REGISTROS', tone: 1, meaning: 'Canonical rows moving into the Hub.' },
        { kind: 'correlation', label: 'CORRELATION', label_es: 'CORRELACIÓN', tone: 2, meaning: 'Synthetic candidate links.' },
        { kind: 'projection', label: 'PROJECTION', label_es: 'PROYECCIÓN', tone: 3, meaning: 'Rows projected for pages.' },
      ],
      nodes: [
        ...anchors,
        {
          id: 'content:centinelas:observations', kind: 'stream', app: 'centinelas', stage: 'signal-intake', label: 'observations',
          sublabel: 'centinelas-pr · observations.jsonl', summary: 'Centinelas exported 100 observations rows; this store holds 100 of them.',
          stream: 'observations', total: 100, stored: 100,
          lineage: [{ script: 'scripts/federation_export.py', phase: 'OBSERVATION', count: 100, inputs: ['data/signals/example_signals.jsonl'] }],
          samples: [
            { id: 'obs_004a', label: 'Municipio adjudica contrato del acueducto', type: 'unclassified_signal', municipality: null, date: '2026-10-03', synthetic: false, href: '/evidence/Observations/obs_004a' },
            { id: 'obs_0b11', label: 'Junta aprueba presupuesto', type: 'unclassified_signal', municipality: 'Ponce', date: null, synthetic: false, href: '/evidence/Observations/obs_0b11' },
          ],
        },
        {
          id: 'content:seam:intake-drops', kind: 'seam', app: 'centinelas', stage: 'signal-intake', label: 'intake drops',
          sublabel: 'centinelas-pr → moneysweep-pr · intake/*.json', summary: 'Items written as files for MoneySweep.',
          total: null, stored: null, status: 'dormant', seam: 'Dormant: no intake directories are materialized.',
        },
        {
          id: 'content:thehub:stream:observations', kind: 'hub_stream', app: 'thehub', stage: 'hub-aggregate', label: 'observations',
          sublabel: 'thehub-pr · data/aggregate/observations.jsonl', summary: 'The aggregate observations stream.',
          stream: 'observations', total: 572, stored: 400, samples: [],
        },
        {
          id: 'content:thehub:correlation:alerts', kind: 'correlation', app: 'thehub', stage: 'hub-aggregate', label: 'alert footprint',
          sublabel: 'thehub-pr · alert_affects_entity', summary: '9 candidate links from the alert footprint strategy.',
          total: 9, stored: 9, synthetic: true,
          samples: [{ id: 'rel_2b20', label: 'Alert in AGUADILLA co-located with cross-producer entity.', type: 'alert_affects_entity', municipality: null, date: null, synthetic: true, href: '/evidence/Correlations/rel_2b20' }],
        },
      ],
      edges: [
        { id: 'member:app:centinelas->content:centinelas:observations', kind: 'member', from: 'app:centinelas', to: 'content:centinelas:observations' },
        { id: 'flow:content:centinelas:observations->content:thehub:stream:observations', kind: 'flow', from: 'content:centinelas:observations', to: 'content:thehub:stream:observations', weight: 100 },
        { id: 'flow:content:thehub:stream:observations->content:thehub:correlation:alerts', kind: 'flow', from: 'content:thehub:stream:observations', to: 'content:thehub:correlation:alerts', weight: 9 },
        { id: 'flow:app:centinelas->content:seam:intake-drops', kind: 'flow', from: 'app:centinelas', to: 'content:seam:intake-drops', status: 'dormant' },
      ],
    },
  },
  links: [
    { code: 'centinelas.export', content: 'content:centinelas:observations' },
    { code: 'thehub.aggregate', content: 'content:thehub:stream:observations' },
  ],
  totals: { exported: 672, stored: 500, correlations: 9 },
};

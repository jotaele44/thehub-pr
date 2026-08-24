import React from 'react'
import { createRoot } from 'react-dom/client'
import {
  FederationAsyncState,
  FederationSemanticBadge,
  FederationStatusBadge,
  FederationSourceBadge,
  resolveFederationSemantic,
} from '@pr-federation/react'
import '@pr-federation/react/styles.css'
import './styles.css'

const FIXTURES = Object.freeze({
  POS_NONEMPTY: { title: 'Success — non-empty', kind: 'records', rows: [{ id: 'R-001', name: 'Canonical record', value: '$1,250.00' }] },
  POS_EMPTY: { title: 'Success — empty', kind: 'async', state: 'empty', description: 'Authoritative query completed with zero records.' },
  POS_FILTERED_ZERO: { title: 'Filtered to zero', kind: 'async', state: 'filtered_empty', description: 'Records exist, but none match the current filters.' },
  POS_FACT: { title: 'Fact', kind: 'semantic', semanticKind: 'epistemic', value: 'fact' },
  POS_COMPUTED: { title: 'Computed', kind: 'semantic', semanticKind: 'epistemic', value: 'computed' },
  POS_BINDING: { title: 'Binding', kind: 'semantic', semanticKind: 'epistemic', value: 'binding' },
  POS_UNRESOLVED: { title: 'Unresolved', kind: 'semantic', semanticKind: 'certification', value: 'unresolved' },
  POS_SUPERSEDED: { title: 'Superseded', kind: 'semantic', semanticKind: 'certification', value: 'superseded' },

  NEG_NULL: { title: 'Null value', kind: 'value', raw: null, display: '—', certification: 'open' },
  NEG_UNDEFINED: { title: 'Undefined value', kind: 'value', raw: undefined, display: '—', certification: 'open' },
  NEG_EMPTY_STRING: { title: 'Empty string', kind: 'value', raw: '', display: '—', certification: 'open' },
  NEG_DUPLICATE_ID: { title: 'Duplicate identifier', kind: 'duplicate', rows: [{ id: 'E-001', name: 'Entity Alpha' }, { id: 'E-001', name: 'Entity Beta' }] },
  NEG_DUPLICATE_NAME: { title: 'Duplicate display name', kind: 'duplicate', rows: [{ id: 'E-001', name: 'Acme Holdings' }, { id: 'E-002', name: 'Acme Holdings' }] },
  NEG_LONG_NAME: { title: 'Long entity name', kind: 'value', display: 'Corporación para la Investigación, Preservación, Adjudicación y Reconciliación Interagencial de Contratos y Subvenciones de Puerto Rico, Inc.' },
  NEG_UNICODE: { title: 'Unicode / mojibake resistance', kind: 'value', display: 'Peñuelas · Añasco · José Muñoz · 日本語 · العربية · � mojibake sentinel' },
  NEG_LARGE_CURRENCY: { title: 'Large currency', kind: 'value', display: '$9,223,372,036,854,775,807.99' },
  NEG_NEGATIVE_CURRENCY: { title: 'Negative currency', kind: 'value', display: '−$1,250,000.00' },
  NEG_INVALID_DATE: { title: 'Invalid date', kind: 'value', display: 'Invalid date', certification: 'open' },
  NEG_STALE: { title: 'Stale data', kind: 'semantic', semanticKind: 'freshness', value: 'stale' },
  NEG_PARTIAL: { title: 'Partial data', kind: 'async', state: 'partial', description: 'Some authoritative records could not be loaded.' },
  NEG_OFFLINE: { title: 'Offline source', kind: 'async', state: 'offline', description: 'Source unavailable; do not interpret as zero records.' },
  NEG_TIMEOUT: { title: 'Request timeout', kind: 'async', state: 'error', description: 'Timed out before the source returned a complete response.' },
  NEG_429: { title: 'Rate limited (429)', kind: 'async', state: 'degraded', description: 'Source rate limit reached; result set is not complete.' },
  NEG_500: { title: 'Server error (500)', kind: 'async', state: 'error', description: 'Source returned an internal server error.' },
  NEG_MALFORMED_SCHEMA: { title: 'Malformed schema', kind: 'async', state: 'error', description: 'Response failed schema validation; rows were not silently dropped.' },
  NEG_AMBIGUOUS_IDENTITY: { title: 'Ambiguous identity', kind: 'identity', candidates: ['Acme LLC · PR-123', 'Acme LLC · FL-889'], certification: 'candidate_not_identity' },
  NEG_1_TO_N: { title: 'One-to-many relationship', kind: 'relationship', left: ['A'], right: ['B1', 'B2', 'B3'] },
  NEG_N_TO_1: { title: 'Many-to-one relationship', kind: 'relationship', left: ['A1', 'A2', 'A3'], right: ['B'] },
  NEG_N_TO_N: { title: 'Many-to-many relationship', kind: 'relationship', left: ['A1', 'A2'], right: ['B1', 'B2', 'B3'] },
  NEG_CONTRADICTION: { title: 'Contradiction', kind: 'contradiction', claims: ['Source A: status = active', 'Source B: status = inactive'] },
  NEG_SOURCE_MISSING: { title: 'Missing provenance', kind: 'semantic', semanticKind: 'provenance', value: 'missing' },
  NEG_HASH_MISMATCH: { title: 'Hash mismatch', kind: 'semantic', semanticKind: 'provenance', value: 'hash_mismatch' },
})

function Semantic({ kind, value }) {
  const resolved = resolveFederationSemantic(kind, value)
  return <div className="semantic-row"><FederationSemanticBadge kind={kind} value={value}/><code data-resolved-value={resolved.value}>{resolved.value}</code></div>
}

function FixtureBody({ fixture }) {
  switch (fixture.kind) {
    case 'async':
      return <FederationAsyncState state={fixture.state} title={fixture.title} description={fixture.description}/>
    case 'semantic':
      return <Semantic kind={fixture.semanticKind} value={fixture.value}/>
    case 'records':
    case 'duplicate':
      return <table><thead><tr><th>ID</th><th>Name</th><th>Value</th></tr></thead><tbody>{fixture.rows.map((row, i) => <tr key={`${row.id}-${i}`}><td>{row.id}</td><td>{row.name}</td><td>{row.value ?? '—'}</td></tr>)}</tbody></table>
    case 'value':
      return <div className="value-box"><span className="label">Rendered value</span><strong>{fixture.display}</strong>{fixture.certification && <FederationSemanticBadge kind="certification" value={fixture.certification}/>}</div>
    case 'identity':
      return <div className="stack"><FederationSemanticBadge kind="certification" value={fixture.certification}/>{fixture.candidates.map((candidate) => <div className="candidate" key={candidate}>{candidate}</div>)}</div>
    case 'relationship':
      return <div className="relationship"><div>{fixture.left.map((x) => <span className="node" key={x}>{x}</span>)}</div><div className="edge">↔</div><div>{fixture.right.map((x) => <span className="node" key={x}>{x}</span>)}</div></div>
    case 'contradiction':
      return <div className="stack"><FederationStatusBadge kind="workflow" status="needs_review">Contradiction requires adjudication</FederationStatusBadge>{fixture.claims.map((claim) => <div className="claim" key={claim}>{claim}</div>)}</div>
    default:
      return <div>Unsupported fixture</div>
  }
}

function App() {
  const params = new URLSearchParams(location.search)
  const id = params.get('fixture') || 'POS_NONEMPTY'
  const fixture = FIXTURES[id]
  if (!fixture) return <main><h1>Unknown fixture</h1><FederationSemanticBadge kind="certification" value="open"/></main>
  return (
    <main data-fixture-id={id}>
      <header><div><p className="eyebrow">Federation GUI Regression Fixture</p><h1>{fixture.title}</h1></div><FederationSourceBadge source="canonical-fixture-lab" verified/></header>
      <section className="fixture-panel" aria-labelledby="fixture-title"><h2 id="fixture-title">{id}</h2><FixtureBody fixture={fixture}/></section>
      <footer><button type="button" id="keyboard-target">Keyboard target</button><span aria-live="polite">Fixture rendered deterministically.</span></footer>
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App/>)

export { FIXTURES }

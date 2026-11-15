// Shell fixtures. A separate page from main.jsx on purpose: the 32 component
// fixtures assert that the first Tab reaches their footer button, and a shell
// puts a skip link first. Each fixture here is driven by
// tests/runtime-matrix.mjs, which is where the expectations live.
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  FederationAppShell,
  FederationButton,
  FederationInspectorPanel,
  FederationStatusBadge,
  FederationStatusBar,
  defineFederationNav,
  flattenFederationNav,
} from '@pr-federation/react'
import '../../styles/foundation.css'
import '../../styles/primitives.css'
import '../../styles/states.css'
import '../../styles/shell.css'
import './shell-styles.css'

const Glyph = ({ d }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
)
const icon = (d) => function Icon() { return <Glyph d={d} /> }
const Home = icon('M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z')
const Grid = icon('M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z')
const List = icon('M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01')
const Pin = icon('M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z')

const routed = defineFederationNav([
  { label: 'Overview', items: [
    { label: 'Recent activity', path: '/', icon: Home, capabilityId: 'activity', match: ['/activity'] },
    { label: 'Hub', path: '/hub', accent: '#0529a8', capabilityId: 'hub' },
    { label: 'Search', path: '/search', icon: Grid, capabilityId: 'search' },
  ] },
  { label: 'Records', items: [
    { label: 'Programs', path: '/programs', icon: List, capabilityId: 'programs' },
    { label: 'Cases', path: '/cases', icon: List, capabilityId: 'cases' },
    { label: 'Sources', path: '/sources', icon: List, capabilityId: 'sources' },
    { label: 'Gates', path: '/gates', icon: Pin, capabilityId: 'gates', mobile: 'primary' },
  ] },
])

// A state-driven application: no router, views selected by id.
const stateDriven = defineFederationNav([
  { items: [
    { label: 'Cases', id: 'cases', icon: List, capabilityId: 'cases' },
    { label: 'Map', id: 'map', icon: Pin, capabilityId: 'map' },
    { label: 'Statistics', id: 'stats', icon: Grid, capabilityId: 'stats' },
    { label: 'Candidates', id: 'candidates', icon: List, capabilityId: 'candidates' },
    { label: 'Activity', id: 'activity', icon: Home, capabilityId: 'activity' },
    { label: 'Exports', id: 'exports', icon: List, capabilityId: 'exports' },
  ] },
])

// Few enough entries that the bottom bar needs no "More". Its fixture also
// passes no navHeader: host content in that slot has to stay reachable on a
// small screen, so its presence alone forces a "More" entry.
const few = defineFederationNav([
  { items: [
    { label: 'Monitor', path: '/monitor', icon: Home, capabilityId: 'monitor' },
    { label: 'Signals', path: '/signals', icon: Grid, capabilityId: 'signals' },
    { label: 'Matters', path: '/matters', icon: List, capabilityId: 'matters' },
    { label: 'Sources', path: '/sources', icon: Pin, capabilityId: 'sources' },
  ] },
])

// Labels resolved at render time, and long enough to break a careless layout.
const translated = defineFederationNav([
  { label: (ctx) => (ctx.lang === 'es' ? 'Vigilancia de infraestructura crítica y servicios esenciales' : 'Critical infrastructure and essential services monitoring'), items: [
    { label: (ctx) => (ctx.lang === 'es' ? 'Interrupciones de agua y alcantarillado por municipio' : 'Water and sewer disruptions by municipality'), path: '/water', icon: Pin, capabilityId: 'water', description: 'Autoridad de Acueductos y Alcantarillados, reportes diarios consolidados' },
    { label: () => 'Señalesdeprimeramanosinespaciosparaforzarelrecortedeltexto', path: '/signals', icon: Grid, capabilityId: 'signals' },
    { label: (ctx) => (ctx.lang === 'es' ? 'Asuntos legislativos pendientes de evaluación' : 'Legislative matters pending evaluation'), path: '/matters', icon: List, capabilityId: 'matters' },
    { label: 'Entidades', path: '/entities', icon: Home, capabilityId: 'entities' },
    { label: 'Fuentes', path: '/sources', icon: List, capabilityId: 'sources' },
    { label: 'Traspaso entre repositorios', path: '/handoff', icon: List, capabilityId: 'handoff' },
  ] },
])

const FIXTURES = Object.freeze({
  SHELL_SIDEBAR: { title: 'Routed registry, light theme', nav: routed, initial: '/', repo: 'thehub-pr', theme: 'light' },
  SHELL_SIDEBAR_DARK: { title: 'Routed registry, dark theme, lowest-contrast accent', nav: routed, initial: '/programs', repo: 'aguayluz-pr', theme: 'dark' },
  SHELL_STATE_NAV: { title: 'State-driven views, no router', nav: stateDriven, initial: 'cases', repo: 'ovnis-pr', theme: 'dark' },
  SHELL_FEW_DESKTOP_BREAK: { title: 'Four entries, switches to the bar below 1280px', nav: few, initial: '/monitor', repo: 'centinelas-pr', theme: 'light', mobileBelow: 'desktop', bare: true },
  SHELL_INSPECTOR: { title: 'Inspector panel', nav: routed, initial: '/cases', repo: 'moneysweep-pr', theme: 'light', inspector: true },
  SHELL_LONG_LABELS: { title: 'Translated, very long labels', nav: translated, initial: '/water', repo: 'centinelas-pr', theme: 'light', labelContext: { lang: 'es' } },
})

function App() {
  const id = new URLSearchParams(location.search).get('fixture') || 'SHELL_SIDEBAR'
  const fixture = FIXTURES[id]
  const [current, setCurrent] = useState(fixture?.initial)
  const [inspecting, setInspecting] = useState(false)
  if (!fixture) return <main><h1>Unknown shell fixture</h1></main>
  document.documentElement.dataset.theme = fixture.theme
  document.documentElement.dataset.repo = fixture.repo
  const entries = flattenFederationNav(fixture.nav, { labelContext: fixture.labelContext })
  const page = entries.find((entry) => entry.id === current)

  return (
    <FederationAppShell
      data-fixture-id={id}
      nav={fixture.nav}
      current={current}
      onSelect={(item) => setCurrent(item.id)}
      // What a host with a router does: keep the anchor, intercept the click.
      renderLink={({ item, active, onClick, children, ...anchor }) => (
        <a {...anchor} onClick={(event) => { event.preventDefault(); onClick?.(event); setCurrent(item.path) }}>{children}</a>
      )}
      labelContext={fixture.labelContext}
      mobileBelow={fixture.mobileBelow}
      focusMainOnNavigate
      header={<><strong className="lab-brand">Shell fixture</strong><span className="lab-header-title">{fixture.title}</span></>}
      navHeader={fixture.bare ? null : <strong className="lab-brand">{fixture.repo}</strong>}
      statusBar={(
        <FederationStatusBar>
          <span className="fd-status-bar__item"><FederationStatusBadge status="operational">Backend online</FederationStatusBadge></span>
          <span className="fd-status-bar__item">Data as of fixture render</span>
        </FederationStatusBar>
      )}
      inspector={fixture.inspector ? (
        <FederationInspectorPanel open={inspecting} onClose={() => setInspecting(false)} title="Case 2026-0417">
          <p>Record fields, provenance and freshness for the selected record.</p>
          <FederationButton variant="secondary" id="inspector-action">Open full record</FederationButton>
        </FederationInspectorPanel>
      ) : null}
    >
      <h1 id="page-title" data-current={current}>{page?.label}</h1>
      <p>Capability <code>{page?.capabilityId}</code>. This paragraph is long enough to wrap on every certified width without forcing the page wider than the viewport, which is what the matrix checks.</p>
      {fixture.inspector ? (
        <FederationButton id="open-inspector" variant="secondary" onClick={() => setInspecting(true)}>Inspect record</FederationButton>
      ) : null}
    </FederationAppShell>
  )
}

createRoot(document.getElementById('root')).render(<App />)

export { FIXTURES }

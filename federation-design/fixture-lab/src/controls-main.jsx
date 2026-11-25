// Control fixtures: the accent roles, scroll region, responsive label, status
// mark, menu, dialog, rename dialog, and the pinned and recent navigation
// groups. Each is driven from the keyboard by tests/runtime-matrix.mjs, which
// is where the expectations live. `?repo=` and `?theme=` select the accent
// and theme, so the matrix can check every repository in both.
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  FederationAppShell,
  FederationButton,
  FederationDatasetGrid,
  FederationDialog,
  FederationMenu,
  FederationRenameDialog,
  FederationResponsiveLabel,
  FederationScrollRegion,
  FederationStatusMark,
  defineFederationNav,
} from '@pr-federation/react'
import '../../styles/foundation.css'
import '../../styles/primitives.css'
import '../../styles/states.css'
import '../../styles/controls.css'
import '../../styles/shell.css'
import '../../styles/gis.css'
import './shell-styles.css'
import './controls-styles.css'

const nav = defineFederationNav([
  { label: 'Overview', items: [
    { label: 'Controls', path: '/', capabilityId: 'controls' },
    { label: 'Cases', path: '/cases', capabilityId: 'cases' },
  ] },
  { kind: 'pinned', label: 'Pinned' },
  { kind: 'recent', label: 'Recent', maxItems: 3 },
  { kind: 'recent', id: 'recent-searches', label: 'Recent searches', maxItems: 2, overflow: 'scroll' },
])

const RECENT = ['Port authority leases', 'Aqueduct contracts 2024', 'Bridge inspections', 'School repairs', 'Ferry subsidies', 'Landfill permits', 'Shelter grants']
const SEARCHES = ['"emergency procurement"', 'vendor:acme', 'municipio:Ponce', 'amount>1000000', 'status:open']
const ROWS = Array.from({ length: 12 }, (_, index) => ({ id: `R-${index + 1}`, agency: 'Autoridad de Acueductos y Alcantarillados', municipality: 'San Juan', amount: `$${(index + 1) * 12500}`, status: 'Recorded' }))
const COLUMNS = ['id', 'agency', 'municipality', 'amount', 'status'].map((key) => ({ key, label: key }))

function App() {
  const params = new URLSearchParams(location.search)
  const repo = params.get('repo') || 'thehub-pr'
  const theme = params.get('theme') || 'light'
  document.documentElement.dataset.theme = theme
  document.documentElement.dataset.repo = repo

  const [current, setCurrent] = useState('/')
  const [names, setNames] = useState({ 'case-1': 'Budget review', 'case-2': 'Vendor follow-up' })
  const [pinned, setPinned] = useState(['case-1', 'case-2'])
  const [renaming, setRenaming] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [log, setLog] = useState('none')

  const actions = (id) => [
    { id: 'rename', label: 'Rename', onSelect: () => setRenaming(id) },
    { id: 'unpin', label: 'Unpin', onSelect: () => { setPinned((list) => list.filter((value) => value !== id)); setLog(`unpin:${id}`) } },
    { id: 'archive', label: 'Archive', disabled: true },
    { id: 'delete', label: 'Delete', destructive: true, onSelect: () => setConfirming(true) },
  ]
  const collections = {
    pinned: pinned.map((id, index) => ({
      id,
      label: names[id],
      path: `/cases/${id}`,
      status: index === 0 ? { kind: 'spinner', tone: 'info', label: 'Running' } : { kind: 'alert', tone: 'danger', label: 'Needs attention' },
      actions: actions(id),
    })),
    recent: RECENT.map((label, index) => ({ id: `recent-${index}`, label, path: `/recent/${index}` })),
    'recent-searches': SEARCHES.map((label, index) => ({ id: `search-${index}`, label })),
  }

  return (
    <FederationAppShell
      data-fixture-id="CONTROLS"
      nav={nav}
      current={current}
      collections={collections}
      onSelect={(item) => { setCurrent(item.id); setLog(`select:${item.id}`) }}
      renderLink={({ item, active, onClick, children, ...anchor }) => (
        <a {...anchor} onClick={(event) => { event.preventDefault(); onClick?.(event); setCurrent(item.path) }}>{children}</a>
      )}
      header={<strong className="lab-brand">Controls fixture</strong>}
    >
      <h1 id="page-title" data-current={current}>Controls</h1>
      <p id="log" data-log={log}>Last action: {log}</p>

      <section className="lab-section" aria-labelledby="s-accent">
        <h2 id="s-accent">Accent roles</h2>
        <FederationButton id="primary">Primary action</FederationButton>{' '}
        <FederationButton id="responsive" variant="secondary">
          <span aria-hidden="true">▦</span>
          <FederationResponsiveLabel>Board view</FederationResponsiveLabel>
        </FederationButton>
      </section>

      <section className="lab-section" aria-labelledby="s-status">
        <h2 id="s-status">Status marks</h2>
        <p className="lab-row">
          <FederationStatusMark id="mark-dot" tone="success" label="Up to date" />
          <FederationStatusMark id="mark-spinner" kind="spinner" tone="info" label="Running" />
          <FederationStatusMark id="mark-alert" kind="alert" tone="danger" label="Needs attention" />
          <FederationStatusMark id="mark-shown" kind="alert" tone="warning" label="Stale" showLabel />
        </p>
      </section>

      <section className="lab-section" aria-labelledby="s-scroll">
        <h2 id="s-scroll">Scroll regions</h2>
        <FederationScrollRegion id="scroll" label="Long notes" axis="y" className="lab-scroll">
          {Array.from({ length: 12 }, (_, index) => <p key={index}>Note {index + 1}. Text with nothing focusable in it, so the region itself has to take focus for the keyboard to scroll it.</p>)}
        </FederationScrollRegion>
        <FederationScrollRegion id="noscroll" label="Short notes" axis="y" className="lab-scroll">
          <p>One line. Nothing to scroll, so this is not a tab stop.</p>
        </FederationScrollRegion>
        <div className="lab-grid"><FederationDatasetGrid records={ROWS} columns={COLUMNS} getRecordId={(row) => row.id} /></div>
      </section>

      <section className="lab-section" aria-labelledby="s-menu">
        <h2 id="s-menu">Menu and dialogs</h2>
        <FederationMenu id="menu" label="Case actions" items={actions('case-1')} />{' '}
        <FederationButton id="open-dialog" variant="secondary" onClick={() => setConfirming(true)}>Delete case</FederationButton>
        <p>Current name: <strong id="name">{names['case-1']}</strong></p>
      </section>

      <FederationRenameDialog
        open={renaming !== null}
        currentName={renaming ? names[renaming] : ''}
        title="Rename case"
        description="Names are visible to everyone who can open this case."
        maxLength={40}
        onClose={() => setRenaming(null)}
        onRename={async (name) => {
          if (name.toLowerCase() === 'fail') throw new Error('The server refused that name.')
          setNames((all) => ({ ...all, [renaming]: name }))
          setLog(`rename:${renaming}`)
        }}
      />
      <FederationDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete this case?"
        description="This fixture deletes nothing."
        footer={(
          <>
            <FederationButton variant="secondary" data-autofocus="" onClick={() => setConfirming(false)}>Cancel</FederationButton>
            <FederationButton id="confirm-delete" onClick={() => { setLog('delete'); setConfirming(false) }}>Delete</FederationButton>
          </>
        )}
      >
        <FederationMenu id="menu-in-dialog" label="More options" items={[{ id: 'a', label: 'Export first' }, { id: 'b', label: 'Archive instead' }]} />
      </FederationDialog>
    </FederationAppShell>
  )
}

createRoot(document.getElementById('root')).render(<App />)

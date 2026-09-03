import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createDatasetMapBridge } from './bridge.js'

export { createDatasetMapBridge } from './bridge.js'

function GisButton({ children, className = '', ...props }) {
  return <button type="button" className={`fd-button fd-button--secondary fd-focus ${className}`.trim()} {...props}>{children}</button>
}

export function FederationDatasetGrid({ records, columns, getRecordId, selection, onSelectRecord, compact = true }) {
  return (
    <div className={`fd-gis-grid${compact ? ' fd-gis-grid--compact' : ''}`} role="region" aria-label="Dataset records">
      <table>
        <thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label ?? column.key}</th>)}</tr></thead>
        <tbody>{records.map((record) => {
          const recordId = String(getRecordId(record))
          const selected = selection?.recordId === recordId
          return (
            <tr key={recordId} data-record-id={recordId} aria-selected={selected || undefined} onClick={() => onSelectRecord?.(recordId)}>
              {columns.map((column) => <td key={column.key}>{column.render ? column.render(record) : String(record[column.key] ?? '')}</td>)}
            </tr>
          )
        })}</tbody>
      </table>
    </div>
  )
}

export function FederationExportMenu({ exports = [], onExport }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="fd-gis-export">
      <GisButton aria-expanded={open} onClick={() => setOpen((value) => !value)}>Download Results ▾</GisButton>
      {open ? <div className="fd-gis-export__menu" role="menu">{exports.map((item) => (
        <button key={item.id} type="button" role="menuitem" onClick={() => { setOpen(false); onExport?.(item) }}>{item.label}</button>
      ))}</div> : null}
    </div>
  )
}

export function FederationBasemapSelector({ basemaps = [], value, onChange }) {
  return <label className="fd-gis-basemap">Map <select value={value} onChange={(event) => onChange?.(event.target.value)}>{basemaps.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
}

export function FederationMapWorkspace({ records, columns, getRecordId, bridge, provider, basemaps = [], initialBasemapId, onBack, onExportKml }) {
  const mapNode = useRef(null)
  const [basemapId, setBasemapId] = useState(initialBasemapId ?? basemaps[0]?.id ?? '')
  const [selection, setSelection] = useState(() => bridge.getSelection())

  useEffect(() => bridge.subscribe(setSelection), [bridge])
  useEffect(() => {
    if (!provider || !mapNode.current) return undefined
    const instance = provider.mount({ container: mapNode.current, basemapId, onFeatureSelect: (geometryId) => bridge.selectFeature(geometryId, { source: 'map' }) })
    return () => instance?.destroy?.()
  }, [provider, bridge])
  useEffect(() => { provider?.setBasemap?.(basemapId) }, [provider, basemapId])
  useEffect(() => {
    provider?.setSelection?.(selection)
    if (selection.recordId) provider?.flyToRecord?.(selection.recordId, bridge.getFeaturesForRecord(selection.recordId))
  }, [provider, bridge, selection])

  return (
    <div className="fd-gis-map-workspace">
      <aside className="fd-gis-map-workspace__table">
        <div className="fd-gis-map-workspace__toolbar">
          <FederationBasemapSelector basemaps={basemaps} value={basemapId} onChange={setBasemapId} />
          <strong># Facilities {records.length}</strong>
          <GisButton onClick={onBack}>← Back to Advanced Search</GisButton>
          <GisButton onClick={onExportKml}>⇩ Download KML</GisButton>
        </div>
        <FederationDatasetGrid records={records} columns={columns} getRecordId={getRecordId} selection={selection} onSelectRecord={(id) => bridge.selectRecord(id, { source: 'table' })} />
      </aside>
      <main ref={mapNode} className="fd-gis-map-workspace__map" aria-label="Map" />
    </div>
  )
}

export function FederationDatasetWorkspace({ records = [], features = [], columns = [], getRecordId, getFeatureRecordId, getGeometryId, provider, basemaps, exports = [], onExport, onExportKml, onBack }) {
  const [mode, setMode] = useState('table')
  const bridge = useMemo(() => createDatasetMapBridge({ records, features, getRecordId, getFeatureRecordId, getGeometryId }), [records, features, getRecordId, getFeatureRecordId, getGeometryId])
  const [selection, setSelection] = useState(() => bridge.getSelection())
  useEffect(() => bridge.subscribe(setSelection), [bridge])

  if (mode === 'map') return <FederationMapWorkspace records={records} columns={columns} getRecordId={getRecordId} bridge={bridge} provider={provider} basemaps={basemaps} onBack={() => setMode('table')} onExportKml={onExportKml} />
  return (
    <section className="fd-gis-dataset-workspace">
      <header className="fd-gis-dataset-workspace__header">
        <div><h2>Advanced Facility Search</h2><p>Displaying {records.length} of {records.length} Matches</p></div>
        <div className="fd-gis-dataset-workspace__actions">
          <GisButton onClick={onBack}>← Back to Search</GisButton>
          <GisButton onClick={() => setMode('map')}>Display on Map</GisButton>
          <FederationExportMenu exports={exports} onExport={onExport} />
        </div>
      </header>
      <FederationDatasetGrid records={records} columns={columns} getRecordId={getRecordId} selection={selection} onSelectRecord={(id) => bridge.selectRecord(id, { source: 'table' })} />
    </section>
  )
}

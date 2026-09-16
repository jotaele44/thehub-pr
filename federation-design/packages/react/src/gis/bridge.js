function requireStableId(value, label) {
  if (value === null || value === undefined || String(value).trim() === '') {
    throw new Error(`${label} requires a non-empty stable identifier`)
  }
  return String(value)
}

export function createDatasetMapBridge({ records = [], features = [], getRecordId, getFeatureRecordId, getGeometryId }) {
  if (typeof getRecordId !== 'function' || typeof getFeatureRecordId !== 'function' || typeof getGeometryId !== 'function') {
    throw new Error('createDatasetMapBridge requires record and geometry identity accessors')
  }

  const recordById = new Map()
  const featuresByRecordId = new Map()
  const featureByGeometryId = new Map()

  for (const record of records) {
    const recordId = requireStableId(getRecordId(record), 'record')
    if (recordById.has(recordId)) throw new Error(`duplicate recordId: ${recordId}`)
    recordById.set(recordId, record)
  }

  for (const feature of features) {
    const recordId = requireStableId(getFeatureRecordId(feature), 'feature.recordId')
    const geometryId = requireStableId(getGeometryId(feature), 'feature.geometryId')
    if (!recordById.has(recordId)) throw new Error(`orphan feature ${geometryId}: recordId ${recordId} is absent`)
    if (featureByGeometryId.has(geometryId)) throw new Error(`duplicate geometryId: ${geometryId}`)
    featureByGeometryId.set(geometryId, feature)
    const list = featuresByRecordId.get(recordId) || []
    list.push(feature)
    featuresByRecordId.set(recordId, list)
  }

  let selection = { recordId: null, geometryId: null, source: null }
  const listeners = new Set()
  function emit() { for (const listener of listeners) listener(selection) }

  function selectRecord(recordId, { geometryId = null, source = 'table' } = {}) {
    const rid = requireStableId(recordId, 'selection.recordId')
    if (!recordById.has(rid)) throw new Error(`unknown recordId: ${rid}`)
    let gid = geometryId === null ? null : requireStableId(geometryId, 'selection.geometryId')
    const candidates = featuresByRecordId.get(rid) || []
    if (gid !== null && !candidates.some((feature) => String(getGeometryId(feature)) === gid)) {
      throw new Error(`geometryId ${gid} is not bound to recordId ${rid}`)
    }
    if (gid === null && candidates.length === 1) gid = String(getGeometryId(candidates[0]))
    selection = { recordId: rid, geometryId: gid, source }
    emit()
    return selection
  }

  function selectFeature(geometryId, { source = 'map' } = {}) {
    const gid = requireStableId(geometryId, 'selection.geometryId')
    const feature = featureByGeometryId.get(gid)
    if (!feature) throw new Error(`unknown geometryId: ${gid}`)
    const rid = String(getFeatureRecordId(feature))
    selection = { recordId: rid, geometryId: gid, source }
    emit()
    return selection
  }

  return Object.freeze({
    getRecord: (recordId) => recordById.get(String(recordId)) || null,
    getFeaturesForRecord: (recordId) => [...(featuresByRecordId.get(String(recordId)) || [])],
    getFeature: (geometryId) => featureByGeometryId.get(String(geometryId)) || null,
    getSelection: () => ({ ...selection }),
    selectRecord,
    selectFeature,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener) },
    invariants: Object.freeze({
      recordCount: recordById.size,
      featureCount: featureByGeometryId.size,
      orphanFeatureCount: 0,
      duplicateRecordIdCount: 0,
      duplicateGeometryIdCount: 0,
    }),
  })
}

import test from 'node:test'
import assert from 'node:assert/strict'
import { createDatasetMapBridge } from '../src/gis/bridge.js'

const accessors = {
  getRecordId: (record) => record.id,
  getFeatureRecordId: (feature) => feature.properties.recordId,
  getGeometryId: (feature) => feature.properties.geometryId,
}

test('whole-row stable identity drives table-to-map selection', () => {
  const records = [{ id: 'A', name: 'same' }, { id: 'B', name: 'same' }]
  const features = [
    { properties: { recordId: 'A', geometryId: 'GA' } },
    { properties: { recordId: 'B', geometryId: 'GB' } },
  ]
  const bridge = createDatasetMapBridge({ records, features, ...accessors })
  assert.deepEqual(bridge.selectRecord('B'), { recordId: 'B', geometryId: 'GB', source: 'table' })
  assert.equal(bridge.getRecord('B'), records[1])
})

test('map-to-table selection uses geometry identity, not name or proximity', () => {
  const records = [{ id: 'A' }, { id: 'B' }]
  const features = [
    { properties: { recordId: 'A', geometryId: 'GA' } },
    { properties: { recordId: 'B', geometryId: 'GB' } },
  ]
  const bridge = createDatasetMapBridge({ records, features, ...accessors })
  assert.deepEqual(bridge.selectFeature('GA'), { recordId: 'A', geometryId: 'GA', source: 'map' })
})

test('1:N record-to-geometry binding remains explicit and does not choose arbitrarily', () => {
  const records = [{ id: 'A' }]
  const features = [
    { properties: { recordId: 'A', geometryId: 'G1' } },
    { properties: { recordId: 'A', geometryId: 'G2' } },
  ]
  const bridge = createDatasetMapBridge({ records, features, ...accessors })
  assert.equal(bridge.selectRecord('A').geometryId, null)
  assert.deepEqual(bridge.getFeaturesForRecord('A'), features)
})

test('duplicate record ids fail closed', () => {
  assert.throws(() => createDatasetMapBridge({ records: [{ id: 'A' }, { id: 'A' }], features: [], ...accessors }), /duplicate recordId/)
})

test('duplicate geometry ids fail closed', () => {
  const records = [{ id: 'A' }, { id: 'B' }]
  const features = [
    { properties: { recordId: 'A', geometryId: 'G' } },
    { properties: { recordId: 'B', geometryId: 'G' } },
  ]
  assert.throws(() => createDatasetMapBridge({ records, features, ...accessors }), /duplicate geometryId/)
})

test('orphan geometry fails closed', () => {
  const records = [{ id: 'A' }]
  const features = [{ properties: { recordId: 'B', geometryId: 'G' } }]
  assert.throws(() => createDatasetMapBridge({ records, features, ...accessors }), /orphan feature/)
})

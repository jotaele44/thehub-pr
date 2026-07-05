# Skywatcher Sensor Fusion Consumer Pipeline

## Vector

`THEHUB_SENSOR_FUSION_CONSUMER_PIPELINES`

## Purpose

TheHub now has a bounded consumer path for Skywatcher `sensor_fusion_analytics_v1` exports.

## Input

Expected producer artifact:

```text
outputs/federation/thehub_sensor_fusion_analytics.json
```

Expected source repo:

```text
skywatcher-pr
```

## Contract

Schema:

```text
schemas/skywatcher_sensor_fusion_analytics.schema.json
```

Required guardrails:

- `live_tracking: false`
- `operational_cueing: false`
- `operator_action: review_context_only`
- `guardrails.context_only: true`
- `guardrails.public_live_tracking: false`
- `guardrails.operational_cueing: false`

## Consumer Path

```text
scripts/ingest_skywatcher_sensor_fusion.py
src/hub/sensor_fusion_consumer.py
registry/consumers/skywatcher_sensor_fusion.yaml
data/dashboard/skywatcher_sensor_fusion.json
```

## Validation

```bash
pytest tests/test_skywatcher_sensor_fusion_consumer.py
```

or full Hub gate:

```bash
pytest
```

## Boundary

TheHub consumes, validates, and surfaces analytical context. It does not collect airspace/coastal data and does not expose operational tracking or cueing.

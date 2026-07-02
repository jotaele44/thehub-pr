# Data Population and Threshold Tuning

## Vector

`DATA_POPULATION_AND_THRESHOLD_TUNING`

## Purpose

This workflow stages real historical federation inputs, runs Federation Analytics v2, and tunes review thresholds using analyst relevance labels.

## Inputs

Expected local input paths:

```text
data/federation_analytics_v2/records.jsonl
data/federation_analytics_v2/scored_events.jsonl
data/federation_analytics_v2/labels.jsonl
```

### records.jsonl

Historical population records from producer exports.

Minimum fields:

```json
{"producer":"skywatcher-pr","corridor_id":"sj_corridor","domain":"air","observed_at":"2026-01-05T12:00:00+00:00","event_count":4}
```

### scored_events.jsonl

Review candidates with anomaly scores.

Minimum fields:

```json
{"event_id":"e1","corridor_id":"sj_corridor","anomaly_score":0.82}
```

### labels.jsonl

Analyst relevance labels for review candidates.

Minimum fields:

```json
{"event_id":"e1","is_relevant":true}
```

## Run

```bash
python scripts/tune_federation_thresholds.py \
  --records data/federation_analytics_v2/records.jsonl \
  --scored-events data/federation_analytics_v2/scored_events.jsonl \
  --labels data/federation_analytics_v2/labels.jsonl \
  --output data/federation_analytics_v2/threshold_tuning_report.json
```

## Output

```text
data/federation_analytics_v2/threshold_tuning_report.json
```

Report sections:

- population summary
- global threshold recommendation
- corridor-specific thresholds
- precision/recall review metrics
- guardrail fields

## Guardrails

- This is review-threshold tuning only.
- No live tracking.
- No operational cueing.
- Labels indicate analytical relevance, not field action.

## Validation

```bash
pytest tests/test_threshold_tuning.py
pytest
```

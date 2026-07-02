# Federation Analytics v2 Release Report

## Vector

`FEDERATION_ANALYTICS_v2_BUILDOUT`

## Scope

This release adds a TheHub-side analytics layer for populated historical datasets and cross-repo anomaly correlation.

## Implemented

- `src/hub/federation_analytics_v2.py`
  - Seasonality model generation by corridor, domain, month, weekday, and six-hour bucket.
  - Calibrated review-threshold generation.
  - Cross-repo anomaly correlation by corridor and time window.
  - Federation Analytics v2 payload builder.

- `scripts/build_federation_analytics_v2.py`
  - CLI builder for local JSONL historical records and JSON anomaly inputs.

- Fixtures
  - `tests/fixtures/federation_analytics_v2_records.jsonl`
  - `tests/fixtures/federation_analytics_v2_anomalies.json`

- Tests
  - `tests/test_federation_analytics_v2.py`

## Guardrails

- No live tracking.
- No operational cueing.
- Cross-repo correlation is context review only.
- Outputs are analytics payloads, not operational tasking.

## Output

Default output path:

```text
data/federation_analytics_v2/federation_analytics_v2.json
```

## Validation

```bash
pytest tests/test_federation_analytics_v2.py
pytest
```

## Release Name

```text
FEDERATION_ANALYTICS_v2
```

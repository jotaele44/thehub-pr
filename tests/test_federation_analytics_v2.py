import json
from pathlib import Path

from hub.federation_analytics_v2 import (
    build_federation_analytics_v2_payload,
    build_seasonality_models,
    calibrate_anomaly_thresholds,
    correlate_cross_repo_anomalies,
)


RECORDS = Path(__file__).parent / "fixtures" / "federation_analytics_v2_records.jsonl"
ANOMALIES = Path(__file__).parent / "fixtures" / "federation_analytics_v2_anomalies.json"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                records.append(json.loads(text))
    return records


def read_json_records(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload.get("anomalies", []) if isinstance(item, dict)]


def test_build_seasonality_models_groups_by_corridor_domain_and_time_bucket():
    records = read_jsonl(RECORDS)

    models = build_seasonality_models(records)

    assert models
    sj_air = [item for item in models if item["corridor_id"] == "sj_corridor" and item["domain"] == "air"]
    assert len(sj_air) == 1
    assert sj_air[0]["month"] == 1
    assert sj_air[0]["hour_bucket"] == 12
    assert sj_air[0]["mean_count"] == 5
    assert sj_air[0]["sample_count"] == 2


def test_calibrate_anomaly_thresholds_preserves_review_only_guardrails():
    models = [{"corridor_id": "sj_corridor", "domain": "air", "month": 1, "weekday": 0, "hour_bucket": 12, "mean_count": 5, "stddev_count": 1, "sample_count": 6}]

    thresholds = calibrate_anomaly_thresholds(models)

    assert len(thresholds) == 1
    assert 0.40 <= thresholds[0]["threshold"] <= 0.90
    assert thresholds[0]["threshold_type"] == "calibrated_review_v2"
    assert thresholds[0]["operator_action"] == "review_context_only"


def test_correlate_cross_repo_anomalies_requires_multiple_repos():
    events = read_json_records(ANOMALIES)

    correlations = correlate_cross_repo_anomalies(events, window_minutes=120)

    assert len(correlations) == 1
    corr = correlations[0]
    assert corr["corridor_id"] == "sj_corridor"
    assert corr["participating_repos"] == ["aguayluz-pr", "skywatcher-pr"]
    assert corr["event_count"] == 2
    assert corr["correlation_score"] >= 0.7
    assert corr["operator_action"] == "review_context_only"
    assert corr["live_tracking"] is False


def test_build_federation_analytics_v2_payload_shapes_release():
    records = read_jsonl(RECORDS)
    anomalies = read_json_records(ANOMALIES)

    payload = build_federation_analytics_v2_payload(records, anomalies)

    assert payload["release"] == "FEDERATION_ANALYTICS_v2"
    assert payload["seasonality_model_count"] == len(payload["seasonality_models"])
    assert payload["threshold_count"] == len(payload["thresholds"])
    assert payload["cross_repo_correlation_count"] == 1
    assert payload["operator_action"] == "review_context_only"
    assert payload["live_tracking"] is False

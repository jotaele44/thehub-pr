"""Federation Analytics v2: seasonality, calibration, and cross-repo correlation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping


def _parse_timestamp(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _corridor(record: Mapping[str, Any]) -> str:
    return str(record.get("corridor_id") or record.get("zone_id") or "unassigned")


def _domain(record: Mapping[str, Any]) -> str:
    return str(record.get("domain") or record.get("source_domain") or record.get("event_domain") or "context")


def build_seasonality_models(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build corridor/domain/month/weekday/hour-bucket aggregate models."""

    groups: dict[tuple[str, str, int, int, int], list[float]] = defaultdict(list)
    for record in records:
        observed_at = record.get("observed_at") or record.get("generated_at") or record.get("timestamp")
        if not observed_at:
            continue
        ts = _parse_timestamp(observed_at)
        hour_bucket = (ts.hour // 6) * 6
        key = (_corridor(record), _domain(record), ts.month, ts.weekday(), hour_bucket)
        groups[key].append(float(record.get("event_count", record.get("count", 1))))

    models: list[dict[str, Any]] = []
    for (corridor_id, domain, month, weekday, hour_bucket), counts in sorted(groups.items()):
        stddev = pstdev(counts) if len(counts) > 1 else 0.0
        models.append({
            "corridor_id": corridor_id,
            "domain": domain,
            "month": month,
            "weekday": weekday,
            "hour_bucket": hour_bucket,
            "mean_count": round(mean(counts), 3),
            "stddev_count": round(stddev, 3),
            "sample_count": len(counts),
            "model_type": "seasonality_v2",
        })
    return models


def calibrate_anomaly_thresholds(models: Iterable[Mapping[str, Any]], base_threshold: float = 0.60) -> list[dict[str, Any]]:
    """Create calibrated thresholds from seasonality model density and variance."""

    thresholds: list[dict[str, Any]] = []
    for model in models:
        stddev = float(model.get("stddev_count", 0.0))
        mean_count = float(model.get("mean_count", 0.0))
        sample_count = int(model.get("sample_count", 0))
        variance_factor = min(0.20, stddev / (mean_count + 1.0) * 0.10)
        density_factor = -0.05 if sample_count >= 5 else 0.05
        threshold = round(max(0.40, min(0.90, base_threshold + variance_factor + density_factor)), 3)
        thresholds.append({
            "corridor_id": model.get("corridor_id"),
            "domain": model.get("domain"),
            "month": model.get("month"),
            "weekday": model.get("weekday"),
            "hour_bucket": model.get("hour_bucket"),
            "threshold": threshold,
            "threshold_type": "calibrated_review_v2",
            "operator_action": "review_context_only",
        })
    return thresholds


def correlate_cross_repo_anomalies(events: Iterable[Mapping[str, Any]], window_minutes: int = 120) -> list[dict[str, Any]]:
    """Correlate anomalies from multiple repos in the same corridor/time window."""

    buckets: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        observed_at = event.get("observed_at") or event.get("generated_at") or event.get("timestamp")
        if not observed_at:
            continue
        ts = _parse_timestamp(observed_at)
        bucket = int(ts.timestamp() // (window_minutes * 60))
        buckets[(_corridor(event), bucket)].append(event)

    correlations: list[dict[str, Any]] = []
    for (corridor_id, bucket), items in sorted(buckets.items()):
        repos = sorted({str(item.get("producer") or item.get("repo") or item.get("source_repo")) for item in items})
        repos = [repo for repo in repos if repo and repo != "None"]
        if len(repos) < 2:
            continue
        scores = [float(item.get("anomaly_score", item.get("correlation_score", 0.5))) for item in items]
        score = round(min(1.0, 0.35 + 0.15 * len(repos) + 0.50 * mean(scores)), 3)
        correlations.append({
            "correlation_id": f"corr_{corridor_id}_{bucket}",
            "corridor_id": corridor_id,
            "bucket": bucket,
            "time_window_minutes": window_minutes,
            "participating_repos": repos,
            "event_count": len(items),
            "correlation_score": score,
            "operator_action": "review_context_only",
            "live_tracking": False,
        })
    return correlations


def build_federation_analytics_v2_payload(
    records: Iterable[Mapping[str, Any]],
    anomaly_events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the release payload for Federation Analytics v2."""

    record_list = list(records)
    anomaly_list = list(anomaly_events)
    seasonality = build_seasonality_models(record_list)
    thresholds = calibrate_anomaly_thresholds(seasonality)
    correlations = correlate_cross_repo_anomalies(anomaly_list)
    return {
        "release": "FEDERATION_ANALYTICS_v2",
        "seasonality_model_count": len(seasonality),
        "threshold_count": len(thresholds),
        "cross_repo_correlation_count": len(correlations),
        "operator_action": "review_context_only",
        "live_tracking": False,
        "seasonality_models": seasonality,
        "thresholds": thresholds,
        "cross_repo_correlations": correlations,
    }

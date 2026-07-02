"""Data population QA and threshold tuning for Federation Analytics v2."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Iterable, Mapping


def summarize_population(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize staged historical inputs before analytics execution."""

    record_list = list(records)
    by_repo = Counter(str(item.get("producer") or item.get("repo") or "unknown") for item in record_list)
    by_corridor = Counter(str(item.get("corridor_id") or item.get("zone_id") or "unassigned") for item in record_list)
    missing_time = sum(1 for item in record_list if not (item.get("observed_at") or item.get("generated_at") or item.get("timestamp")))
    missing_corridor = sum(1 for item in record_list if not (item.get("corridor_id") or item.get("zone_id")))
    return {
        "record_count": len(record_list),
        "producer_count": len(by_repo),
        "corridor_count": len(by_corridor),
        "records_by_producer": dict(sorted(by_repo.items())),
        "records_by_corridor": dict(sorted(by_corridor.items())),
        "missing_time_count": missing_time,
        "missing_corridor_count": missing_corridor,
        "population_ready": bool(record_list) and missing_time == 0 and missing_corridor == 0,
    }


def review_threshold_performance(
    scored_events: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare scored events against analyst labels.

    Labels use `event_id` and `is_true_positive`. Scored events use `event_id`
    and `anomaly_score`. This function is intentionally aggregate: it tunes
    review thresholds, not operational outcomes.
    """

    label_index = {str(item.get("event_id")): bool(item.get("is_true_positive")) for item in labels}
    events = [item for item in scored_events if str(item.get("event_id")) in label_index]
    if not events:
        return {
            "labeled_event_count": 0,
            "recommended_threshold": 0.60,
            "false_positive_count": 0,
            "false_negative_count": 0,
            "precision": 0.0,
            "recall": 0.0,
        }

    best: dict[str, Any] | None = None
    for step in range(40, 91, 5):
        threshold = step / 100
        tp = fp = fn = 0
        for event in events:
            predicted = float(event.get("anomaly_score", 0.0)) >= threshold
            actual = label_index[str(event.get("event_id"))]
            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and actual:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        candidate = {
            "recommended_threshold": threshold,
            "false_positive_count": fp,
            "false_negative_count": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }
        if best is None or (candidate["f1"], candidate["precision"], candidate["recall"]) > (best["f1"], best["precision"], best["recall"]):
            best = candidate

    assert best is not None
    return {"labeled_event_count": len(events), **best}


def tune_corridor_thresholds(
    scored_events: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Tune thresholds independently by corridor."""

    grouped_events: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in scored_events:
        grouped_events[str(event.get("corridor_id") or "unassigned")].append(event)

    label_list = list(labels)
    results: list[dict[str, Any]] = []
    for corridor_id, events in sorted(grouped_events.items()):
        perf = review_threshold_performance(events, label_list)
        results.append({
            "corridor_id": corridor_id,
            "recommended_threshold": perf["recommended_threshold"],
            "labeled_event_count": perf["labeled_event_count"],
            "false_positive_count": perf["false_positive_count"],
            "false_negative_count": perf["false_negative_count"],
            "precision": perf["precision"],
            "recall": perf["recall"],
            "operator_action": "review_context_only",
        })
    return results


def build_tuning_report(
    records: Iterable[Mapping[str, Any]],
    scored_events: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a complete population/tuning report."""

    record_list = list(records)
    event_list = list(scored_events)
    label_list = list(labels)
    population = summarize_population(record_list)
    global_perf = review_threshold_performance(event_list, label_list)
    corridor_thresholds = tune_corridor_thresholds(event_list, label_list)
    avg_threshold = mean([item["recommended_threshold"] for item in corridor_thresholds]) if corridor_thresholds else global_perf["recommended_threshold"]
    return {
        "report_type": "data_population_threshold_tuning",
        "population": population,
        "global_threshold": global_perf,
        "corridor_thresholds": corridor_thresholds,
        "average_corridor_threshold": round(avg_threshold, 3),
        "operator_action": "review_context_only",
        "live_tracking": False,
        "operational_cueing": False,
    }

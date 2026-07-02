import json
from pathlib import Path

from hub.threshold_tuning import (
    build_tuning_report,
    review_threshold_performance,
    summarize_population,
    tune_corridor_thresholds,
)


FIXTURES = Path(__file__).parent / "fixtures"
RECORDS = FIXTURES / "threshold_tuning_records.jsonl"
SCORED = FIXTURES / "threshold_tuning_scored_events.jsonl"
LABELS = FIXTURES / "threshold_tuning_review_labels.jsonl"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def test_summarize_population_marks_ready_inputs():
    summary = summarize_population(read_jsonl(RECORDS))

    assert summary["record_count"] == 3
    assert summary["producer_count"] == 3
    assert summary["corridor_count"] == 2
    assert summary["missing_time_count"] == 0
    assert summary["missing_corridor_count"] == 0
    assert summary["population_ready"] is True


def test_review_threshold_performance_uses_relevance_labels():
    performance = review_threshold_performance(read_jsonl(SCORED), read_jsonl(LABELS))

    assert performance["labeled_event_count"] == 5
    assert 0.40 <= performance["recommended_threshold"] <= 0.90
    assert performance["precision"] >= 0.5
    assert performance["recall"] >= 0.5


def test_tune_corridor_thresholds_groups_independently():
    thresholds = tune_corridor_thresholds(read_jsonl(SCORED), read_jsonl(LABELS))

    assert {item["corridor_id"] for item in thresholds} == {"ponce_corridor", "sj_corridor"}
    assert all(item["operator_action"] == "review_context_only" for item in thresholds)
    assert all(0.40 <= item["recommended_threshold"] <= 0.90 for item in thresholds)


def test_build_tuning_report_preserves_guardrails():
    report = build_tuning_report(read_jsonl(RECORDS), read_jsonl(SCORED), read_jsonl(LABELS))

    assert report["report_type"] == "data_population_threshold_tuning"
    assert report["population"]["population_ready"] is True
    assert report["global_threshold"]["labeled_event_count"] == 5
    assert len(report["corridor_thresholds"]) == 2
    assert report["operator_action"] == "review_context_only"
    assert report["live_tracking"] is False
    assert report["operational_cueing"] is False

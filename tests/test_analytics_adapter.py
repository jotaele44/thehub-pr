"""Tests for the aggregate -> Federation Analytics v2 record adapter."""
from __future__ import annotations

import json

from hub.analytics_adapter import aggregate_to_analytics_records
from hub.federation_analytics_v2 import build_federation_analytics_v2_payload

_TS = "2026-03-01T08:15:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
SRC = "src_0123456789abcdef0123456789abcdef"


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _observation(obs_id, municipality, *, producers, observed_at=_TS, confidence=0.8):
    return {
        "observation_id": obs_id, "source_id": SRC,
        "observation_type": "aircraft_transit", "observed_at": observed_at,
        "location": {"lat": 18.34, "lon": -66.01, "municipality": municipality},
        "confidence": confidence, "lineage": _LINEAGE, "synthetic": True,
        "created_at": _TS, "extracted_at": _TS, "_producers": producers,
    }


def _alert(alert_id, municipality, *, producers, observed_at=_TS, confidence=0.6):
    return {
        "alert_id": alert_id, "source_id": SRC, "module": "HYDRO_OPS",
        "alert_type": "maintenance", "severity": 2, "status": "draft",
        "observed_at": observed_at,
        "location": {"lat": 18.34, "lon": -66.01, "municipality": municipality},
        "confidence": confidence, "lineage": _LINEAGE, "synthetic": False,
        "created_at": _TS, "extracted_at": _TS, "_producers": producers,
    }


def test_empty_aggregate_yields_no_records(tmp_path):
    assert aggregate_to_analytics_records(tmp_path) == []


def test_maps_observations_and_alerts(tmp_path):
    _write_jsonl(tmp_path / "observations.jsonl", [
        _observation("obs_" + "a" * 32, "San Juan", producers=["skywatcher-pr"]),
    ])
    _write_jsonl(tmp_path / "alerts.jsonl", [
        _alert("alrt_" + "b" * 32, "San Juan", producers=["aguayluz-pr"]),
    ])
    records = aggregate_to_analytics_records(tmp_path)
    assert len(records) == 2
    obs_rec = next(r for r in records if r["domain"] == "observation")
    assert obs_rec["corridor_id"] == "SAN JUAN"
    assert obs_rec["producer"] == "skywatcher-pr"
    assert obs_rec["event_count"] == 1
    assert obs_rec["anomaly_score"] == 0.8
    alert_rec = next(r for r in records if r["domain"] == "alert")
    assert alert_rec["producer"] == "aguayluz-pr"


def test_rows_without_observed_at_dropped(tmp_path):
    row = _observation("obs_" + "a" * 32, "San Juan", producers=["skywatcher-pr"])
    del row["observed_at"]
    _write_jsonl(tmp_path / "observations.jsonl", [row])
    assert aggregate_to_analytics_records(tmp_path) == []


def test_missing_municipality_falls_back_to_unassigned(tmp_path):
    row = _observation("obs_" + "a" * 32, "San Juan", producers=["skywatcher-pr"])
    del row["location"]
    _write_jsonl(tmp_path / "observations.jsonl", [row])
    records = aggregate_to_analytics_records(tmp_path)
    assert records[0]["corridor_id"] == "unassigned"


def test_records_feed_analytics_payload(tmp_path):
    # Two producers, same corridor + time bucket -> a cross-repo correlation.
    _write_jsonl(tmp_path / "observations.jsonl", [
        _observation("obs_" + "a" * 32, "San Juan", producers=["skywatcher-pr"]),
    ])
    _write_jsonl(tmp_path / "alerts.jsonl", [
        _alert("alrt_" + "b" * 32, "San Juan", producers=["aguayluz-pr"]),
    ])
    records = aggregate_to_analytics_records(tmp_path)
    payload = build_federation_analytics_v2_payload(records, records)
    assert payload["release"] == "FEDERATION_ANALYTICS_v2"
    assert payload["seasonality_model_count"] >= 1
    # both producers in the same SAN JUAN corridor/window -> a cross-repo edge
    assert payload["cross_repo_correlation_count"] >= 1


def test_adapter_is_deterministic(tmp_path):
    _write_jsonl(tmp_path / "observations.jsonl", [
        _observation("obs_" + "a" * 32, "San Juan", producers=["skywatcher-pr"]),
        _observation("obs_" + "c" * 32, "Ponce", producers=["spiderweb-pr"]),
    ])
    assert aggregate_to_analytics_records(tmp_path) == aggregate_to_analytics_records(tmp_path)

from pathlib import Path

from hub.sensor_fusion_consumer import (
    build_dashboard_surface,
    consume_sensor_fusion_export,
    load_json,
    validate_sensor_fusion_export,
    write_dashboard_surface,
)


FIXTURE = Path(__file__).parent / "fixtures" / "skywatcher_sensor_fusion_analytics.json"


def test_fixture_validates_against_sensor_fusion_schema():
    payload = load_json(FIXTURE)

    assert validate_sensor_fusion_export(payload) == []


def test_consumer_result_extracts_contract_and_guardrails():
    payload = load_json(FIXTURE)
    result = consume_sensor_fusion_export(payload)

    assert result.valid is True
    assert result.producer == "skywatcher-pr"
    assert result.export_contract == "sensor_fusion_analytics_v1"
    assert result.anomaly_count == 2
    assert result.guardrails == {
        "context_only": True,
        "public_live_tracking": False,
        "operational_cueing": False,
    }
    assert result.errors == []


def test_dashboard_surface_is_review_context_only():
    payload = load_json(FIXTURE)
    surface = build_dashboard_surface(payload)

    assert surface["surface_id"] == "skywatcher_sensor_fusion"
    assert surface["valid"] is True
    assert surface["live_tracking"] is False
    assert surface["operational_cueing"] is False
    assert surface["operator_action"] == "review_context_only"
    assert surface["metrics"]["overlap_count"] == 3
    assert surface["review_bands"] == {"high_review": 1, "moderate_review": 1}


def test_invalid_payload_is_rejected():
    payload = load_json(FIXTURE)
    payload["live_tracking"] = True

    result = consume_sensor_fusion_export(payload)

    assert result.valid is False
    assert any("False was expected" in error for error in result.errors)


def test_non_numeric_anomaly_count_does_not_crash():
    payload = load_json(FIXTURE)
    for bad in ["n/a", None, True]:
        payload["anomaly_count"] = bad
        result = consume_sensor_fusion_export(payload)
        assert result.valid is False
        assert result.anomaly_count == 0
        assert result.errors
        surface = build_dashboard_surface(payload)
        assert surface["valid"] is False


def test_write_dashboard_surface_roundtrip(tmp_path):
    out = tmp_path / "dashboard" / "surface.json"
    surface = write_dashboard_surface(FIXTURE, out)

    assert out.exists()
    assert surface["valid"] is True
    assert load_json(out)["surface_id"] == "skywatcher_sensor_fusion"

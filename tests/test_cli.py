import json
from pathlib import Path


from hub.cli import main

REGISTRY = "registry/producers.yaml"
SF_FIXTURE = Path(__file__).parent / "fixtures" / "skywatcher_sensor_fusion_analytics.json"

_TS = "2026-03-01T08:15:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
_SRC = "src_0123456789abcdef0123456789abcdef"


def test_list_returns_zero(capsys):
    rc = main(["list", "--registry", REGISTRY])
    assert rc == 0
    out = capsys.readouterr().out
    assert "producers" in out


def test_validate_federation_all_missing(tmp_path, capsys):
    rc = main(["validate-federation", "--registry", REGISTRY, "--root", str(tmp_path)])
    assert rc == 1  # none ready -> nonzero, but not a crash
    out = capsys.readouterr().out
    assert "missing_checkout" in out


def test_validate_federation_json_output(tmp_path, capsys):
    main(["validate-federation", "--registry", REGISTRY, "--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "producers" in data
    assert "ready_count" in data


def test_graph_report_empty_dir(tmp_path, capsys):
    rc = main(["graph-report", "--in", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "orphan_entities" in out or "orphan" in out


def test_graph_report_json_flag(tmp_path, capsys):
    rc = main(["graph-report", "--in", str(tmp_path), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "orphan_entities" in data


def test_validate_package_valid(valid_package, capsys):
    rc = main(["validate-package", str(valid_package)])
    assert rc == 0
    assert "VALID" in capsys.readouterr().out


def test_validate_package_invalid(tmp_path, capsys):
    rc = main(["validate-package", str(tmp_path)])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().out


def test_consume_sensor_fusion_cli(tmp_path, capsys):
    out = tmp_path / "surface.json"
    rc = main(["consume-sensor-fusion", str(SF_FIXTURE), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    assert "skywatcher_sensor_fusion" in capsys.readouterr().out
    assert json.loads(out.read_text())["surface_id"] == "skywatcher_sensor_fusion"


def test_analytics_v2_cli_from_aggregate(tmp_path, capsys):
    obs = {
        "observation_id": "obs_" + "a" * 32, "source_id": _SRC,
        "observation_type": "aircraft_transit", "observed_at": _TS,
        "location": {"lat": 18.34, "lon": -66.01, "municipality": "San Juan"},
        "confidence": 0.8, "lineage": _LINEAGE, "synthetic": True,
        "created_at": _TS, "extracted_at": _TS, "_producers": ["skywatcher-pr"],
    }
    (tmp_path / "observations.jsonl").write_text(json.dumps(obs, sort_keys=True) + "\n")
    out = tmp_path / "analytics.json"
    rc = main(["analytics-v2", "--in", str(tmp_path), "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["release"] == "FEDERATION_ANALYTICS_v2"
    assert payload["seasonality_model_count"] >= 1


def test_aggregate_emits_dry_run_warning(tmp_path, capsys):
    # No producer packages under an empty root -> warnings + "no packages" exit 1
    rc = main(["aggregate", "--registry", REGISTRY, "--root", str(tmp_path),
               "--out", str(tmp_path / "agg")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "WARNING" in out and "contributes nothing" in out

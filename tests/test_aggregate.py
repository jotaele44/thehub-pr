import json

from hub.aggregate import aggregate


def test_aggregate_single_producer(valid_package, tmp_path):
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": valid_package}, out)
    assert summary["streams"] == {"sources": 1, "entities": 2, "relationships": 1}
    assert summary["errors"]["moneysweep-pr"] == []
    # merged files exist and are valid JSONL
    rows = (out / "entities.jsonl").read_text().splitlines()
    assert len(rows) == 2
    assert all("_producers" in json.loads(r) for r in rows)
    assert (out / "graph_summary.json").exists()


def test_aggregate_dedups_shared_ids_across_producers(package_factory, tmp_path):
    pkg_a = package_factory(tmp_path / "a", producer="moneysweep-pr")
    pkg_b = package_factory(tmp_path / "b", producer="spiderweb-pr")
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": pkg_a, "spiderweb-pr": pkg_b}, out)
    # identical fixture ids -> deduped, not doubled
    assert summary["streams"]["entities"] == 2
    ent = [json.loads(r) for r in (out / "entities.jsonl").read_text().splitlines()]
    # provenance records both producers
    assert all(set(e["_producers"]) == {"moneysweep-pr", "spiderweb-pr"} for e in ent)


def _alert_package(directory, producer):
    import hashlib

    directory.mkdir(parents=True, exist_ok=True)
    _TS = "2026-01-01T00:00:00Z"
    row = {
        "alert_id": "alrt_0123456789abcdef0123456789abcdef",
        "source_id": "src_0123456789abcdef0123456789abcdef",
        "module": "HYDRO_OPS", "alert_type": "maintenance", "severity": 2,
        "status": "draft", "observed_at": _TS, "confidence": 0.6,
        "lineage": {"producer_script": "x", "producer_phase": "T", "source_inputs": []},
        "synthetic": False, "created_at": _TS, "extracted_at": _TS,
    }
    jsonl = directory / "alerts.jsonl"
    jsonl.write_text(json.dumps(row, sort_keys=True) + "\n")
    manifest = {
        "package_id": "pkg_0123456789abcdef0123456789abcdef",
        "producer": producer, "export_contract_version": "1.0.0", "mode": "test",
        "created_at": _TS, "extracted_at": _TS,
        "federation": {"producer_repo": producer, "hub_parent": "thehub-pr"},
        "files": [{
            "filename": "alerts.jsonl", "stream": "alerts", "record_count": 1,
            "sha256": hashlib.sha256(jsonl.read_bytes()).hexdigest(),
            "schema_id": "federation_alert.schema.json",
        }],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


def test_aggregate_alerts_stream(tmp_path):
    pkg = _alert_package(tmp_path / "ayl", producer="aguayluz-pr")
    out = tmp_path / "agg"
    summary = aggregate({"aguayluz-pr": pkg}, out)
    assert summary["errors"]["aguayluz-pr"] == []
    assert summary["streams"]["alerts"] == 1
    rows = (out / "alerts.jsonl").read_text().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["_producers"] == ["aguayluz-pr"]


def test_strict_mode_skips_invalid_package(package_factory, tmp_path):
    pkg = package_factory(tmp_path / "good", producer="moneysweep-pr")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text("{ not json")
    out = tmp_path / "agg"
    summary = aggregate({"moneysweep-pr": pkg, "ovnis-pr": bad}, out, strict=True)
    assert summary["errors"]["ovnis-pr"]
    assert "ovnis-pr" not in summary["producers"]
    assert summary["streams"]["sources"] == 1

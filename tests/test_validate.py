import json

from hub.validate import validate_package


def test_valid_package_has_no_errors(valid_package):
    assert validate_package(valid_package) == []


def test_missing_manifest(tmp_path):
    errors = validate_package(tmp_path)
    assert errors and "missing manifest.json" in errors[0]


def test_sha256_tamper_is_caught(valid_package):
    # mutate a data file after the manifest's sha256 was computed
    (valid_package / "sources.jsonl").write_text(
        (valid_package / "sources.jsonl").read_text() + "\n"
    )
    errors = validate_package(valid_package)
    assert any("sha256 mismatch" in e for e in errors)


def test_bad_id_pattern_is_caught(valid_package):
    # corrupt the source_id so it no longer matches ^src_[a-f0-9]{32}$
    import hashlib

    rows = (valid_package / "entities.jsonl").read_text().splitlines()
    obj = json.loads(rows[0])
    obj["entity_id"] = "ent_NOT_HEX"
    rows[0] = json.dumps(obj, sort_keys=True)
    (valid_package / "entities.jsonl").write_text("\n".join(rows) + "\n")
    # re-sync the manifest sha so the failure is the schema, not the hash
    manifest = json.loads((valid_package / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["filename"] == "entities.jsonl":
            f["sha256"] = hashlib.sha256((valid_package / "entities.jsonl").read_bytes()).hexdigest()
    (valid_package / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_package(valid_package)
    assert any("entities.jsonl" in e and "entity_id" in e for e in errors)


def test_record_count_mismatch_is_caught(valid_package):
    manifest = json.loads((valid_package / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["stream"] == "sources":
            f["record_count"] = 99
    (valid_package / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_package(valid_package)
    assert any("record_count mismatch" in e for e in errors)


def _rewrite_first_entity(pkg, mutate):
    """Apply `mutate` to entities.jsonl row 0 and re-sync its manifest sha256."""
    import hashlib

    rows = (pkg / "entities.jsonl").read_text().splitlines()
    obj = json.loads(rows[0])
    mutate(obj)
    rows[0] = json.dumps(obj, sort_keys=True)
    (pkg / "entities.jsonl").write_text("\n".join(rows) + "\n")
    manifest = json.loads((pkg / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["filename"] == "entities.jsonl":
            f["sha256"] = hashlib.sha256((pkg / "entities.jsonl").read_bytes()).hexdigest()
    (pkg / "manifest.json").write_text(json.dumps(manifest))


def test_entity_location_accepted(valid_package):
    # an optional WGS84 location (lat/lon + municipality) must validate (Z2)
    _rewrite_first_entity(
        valid_package,
        lambda o: o.__setitem__("location", {"lat": 18.4373, "lon": -66.0018, "municipality": "San Juan"}),
    )
    assert validate_package(valid_package) == []


def test_observation_stream_validates_per_schema(tmp_path):
    import hashlib

    _TS = "2026-01-01T00:00:00Z"
    _LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
    SRC = "src_0123456789abcdef0123456789abcdef"
    OBS = "obs_0123456789abcdef0123456789abcdef"

    obs_row = {
        "observation_id": OBS, "source_id": SRC,
        "observation_type": "aircraft_transit", "observed_at": _TS,
        "confidence": 0.9, "lineage": _LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }
    obs_jsonl = tmp_path / "observations.jsonl"
    obs_jsonl.write_text(json.dumps(obs_row, sort_keys=True) + "\n")

    manifest = {
        "package_id": "pkg_0123456789abcdef0123456789abcdef",
        "producer": "skywatcher-pr",
        "export_contract_version": "1.2.0",
        "mode": "test",
        "created_at": _TS,
        "extracted_at": _TS,
        "federation": {"producer_repo": "skywatcher-pr", "hub_parent": "thehub-pr"},
        "files": [{
            "filename": "observations.jsonl", "stream": "observations",
            "record_count": 1,
            "sha256": hashlib.sha256(obs_jsonl.read_bytes()).hexdigest(),
            "schema_id": "federation_observation.schema.json",
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert validate_package(tmp_path) == []


def test_observation_bad_id_pattern_caught(tmp_path):
    import hashlib

    _TS = "2026-01-01T00:00:00Z"
    _LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
    SRC = "src_0123456789abcdef0123456789abcdef"

    obs_row = {
        "observation_id": "BAD_ID", "source_id": SRC,
        "observation_type": "aircraft_transit", "observed_at": _TS,
        "confidence": 0.9, "lineage": _LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }
    obs_jsonl = tmp_path / "observations.jsonl"
    obs_jsonl.write_text(json.dumps(obs_row, sort_keys=True) + "\n")

    manifest = {
        "package_id": "pkg_0123456789abcdef0123456789abcdef",
        "producer": "skywatcher-pr",
        "export_contract_version": "1.2.0",
        "mode": "test",
        "created_at": _TS,
        "extracted_at": _TS,
        "federation": {"producer_repo": "skywatcher-pr", "hub_parent": "thehub-pr"},
        "files": [{
            "filename": "observations.jsonl", "stream": "observations",
            "record_count": 1,
            "sha256": hashlib.sha256(obs_jsonl.read_bytes()).hexdigest(),
            "schema_id": "federation_observation.schema.json",
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_package(tmp_path)
    assert any("observation_id" in e for e in errors)


def _alert_package(tmp_path, alert_overrides=None):
    import hashlib

    _TS = "2026-01-01T00:00:00Z"
    _LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
    SRC = "src_0123456789abcdef0123456789abcdef"
    ALR = "alrt_0123456789abcdef0123456789abcdef"
    row = {
        "alert_id": ALR, "source_id": SRC, "module": "HYDRO_OPS",
        "alert_type": "maintenance", "severity": 2, "status": "draft",
        "gap_status": "minor", "observed_at": _TS, "confidence": 0.6,
        "lineage": _LINEAGE, "synthetic": False, "created_at": _TS, "extracted_at": _TS,
    }
    row.update(alert_overrides or {})
    jsonl = tmp_path / "alerts.jsonl"
    jsonl.write_text(json.dumps(row, sort_keys=True) + "\n")
    manifest = {
        "package_id": "pkg_0123456789abcdef0123456789abcdef",
        "producer": "aguayluz-pr", "export_contract_version": "1.0.0", "mode": "test",
        "created_at": _TS, "extracted_at": _TS,
        "federation": {"producer_repo": "aguayluz-pr", "hub_parent": "thehub-pr"},
        "files": [{
            "filename": "alerts.jsonl", "stream": "alerts", "record_count": 1,
            "sha256": hashlib.sha256(jsonl.read_bytes()).hexdigest(),
            "schema_id": "federation_alert.schema.json",
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_alert_stream_validates_per_schema(tmp_path):
    assert validate_package(_alert_package(tmp_path)) == []


def test_alert_bad_id_pattern_caught(tmp_path):
    pkg = _alert_package(tmp_path, {"alert_id": "BAD_ID"})
    errors = validate_package(pkg)
    assert any("alert_id" in e for e in errors)


def test_alert_bad_severity_caught(tmp_path):
    pkg = _alert_package(tmp_path, {"severity": 9})
    errors = validate_package(pkg)
    assert any("severity" in e for e in errors)


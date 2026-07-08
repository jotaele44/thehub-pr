import json

from prii_maintenance import detect
from prii_maintenance import state as state_mod


def _federation(root, **outputs):
    fed = {"program_id": "acme-pr", "canonical_outputs": outputs}
    (root / "federation.json").write_text(json.dumps(fed), encoding="utf-8")
    return state_mod.collect_repo_state(root)


def test_missing_federation_json_is_critical(tmp_path):
    state = state_mod.collect_repo_state(tmp_path)
    findings = detect.detect_missing_required_files("acme-pr", tmp_path, state)
    assert any(f.category == "manifest" and f.severity == "critical" for f in findings)


def test_missing_declared_output_is_info_not_error(tmp_path):
    state = _federation(tmp_path, some_output="does/not/exist.json")
    findings = detect.detect_missing_required_files("acme-pr", tmp_path, state)
    assert any(f.category == "artifact_hygiene" and f.severity == "info" for f in findings)


def test_maintenance_report_key_is_skipped_as_self_referential(tmp_path):
    state = _federation(tmp_path, maintenance_report="reports/maintenance/latest.json")
    findings = detect.detect_missing_required_files("acme-pr", tmp_path, state)
    assert findings == []


def test_invalid_json_output_is_error(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "x.json").write_text("{nope", encoding="utf-8")
    state = _federation(tmp_path, x="exports/x.json")
    findings = detect.detect_invalid_json("acme-pr", tmp_path, state)
    assert any(f.category == "schema" and f.severity == "error" for f in findings)


def test_valid_json_output_has_no_finding(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "x.json").write_text("{}", encoding="utf-8")
    state = _federation(tmp_path, x="exports/x.json")
    assert detect.detect_invalid_json("acme-pr", tmp_path, state) == []


def test_duplicate_jsonl_detected(tmp_path):
    d = tmp_path / "exports" / "federation"
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text('{"a":1}\n{"a":1}\n{"a":2}\n', encoding="utf-8")
    state = _federation(tmp_path, canonical_export_dir="exports/federation")
    findings = detect.detect_exact_duplicate_jsonl("acme-pr", tmp_path, state)
    assert len(findings) == 1
    assert findings[0].category == "duplicate"
    assert findings[0].detail == {"duplicate_rows": 1}


def test_no_duplicates_no_finding(tmp_path):
    d = tmp_path / "exports" / "federation"
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    state = _federation(tmp_path, canonical_export_dir="exports/federation")
    assert detect.detect_exact_duplicate_jsonl("acme-pr", tmp_path, state) == []

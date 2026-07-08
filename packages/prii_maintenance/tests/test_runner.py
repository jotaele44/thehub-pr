import json

import pytest

from prii_maintenance import REPORT_RELPATH, run_maintenance
from prii_maintenance.models import MaintenanceFinding


def _federation(root, program_id="acme-pr", **outputs):
    fed = {"program_id": program_id, "canonical_outputs": outputs}
    (root / "federation.json").write_text(json.dumps(fed), encoding="utf-8")


def test_audit_does_not_mutate_but_safe_correct_does(tmp_path):
    d = tmp_path / "exports" / "federation"
    d.mkdir(parents=True)
    jsonl = d / "events.jsonl"
    jsonl.write_text('{"a":1}\n{"a":1}\n{"a":2}\n', encoding="utf-8")
    _federation(tmp_path, canonical_export_dir="exports/federation")

    before = jsonl.read_text(encoding="utf-8")
    audit = run_maintenance(root=tmp_path, mode="audit", write=False)
    assert any(f.category == "duplicate" and f.action == "none" for f in audit.findings)
    assert jsonl.read_text(encoding="utf-8") == before

    fixed = run_maintenance(root=tmp_path, mode="safe-correct", write=False)
    assert any(f.action == "auto_corrected" for f in fixed.findings)
    lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2


def test_run_maintenance_writes_report_and_review_queue(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "bad.json").write_text("{not json", encoding="utf-8")
    _federation(tmp_path, x="exports/bad.json")

    report_obj = run_maintenance(root=tmp_path, mode="audit", write=True)

    assert (tmp_path / REPORT_RELPATH).exists()
    assert (tmp_path / "reports" / "maintenance" / "review_queue.json").exists()
    assert report_obj.promotion_blocked is False  # errors are quarantined, not critical


def test_program_id_param_is_used_when_federation_json_absent(tmp_path):
    report_obj = run_maintenance(root=tmp_path, mode="audit", write=False, program_id="acme-pr")
    assert report_obj.repo == "acme-pr"


def test_federation_json_program_id_takes_precedence_over_param(tmp_path):
    _federation(tmp_path, program_id="from-federation-json")
    report_obj = run_maintenance(
        root=tmp_path, mode="audit", write=False, program_id="from-param"
    )
    assert report_obj.repo == "from-federation-json"


def test_missing_program_id_raises(tmp_path):
    with pytest.raises(ValueError, match="no program id"):
        run_maintenance(root=tmp_path, mode="audit", write=False)


def test_invalid_mode_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown mode"):
        run_maintenance(root=tmp_path, mode="bogus", write=False, program_id="acme-pr")


def test_local_checks_are_invoked_and_merged_into_the_report(tmp_path):
    def fake_local_checks(repo, root, state):
        return [
            MaintenanceFinding(
                finding_id=f"{repo}:dependency_drift:fake",
                repo=repo,
                category="dependency_drift",
                severity="warning",
            )
        ]

    report_obj = run_maintenance(
        root=tmp_path, mode="audit", write=False,
        program_id="acme-pr", local_checks=fake_local_checks,
    )

    assert any(f.category == "dependency_drift" for f in report_obj.findings)


def test_no_local_checks_by_default(tmp_path):
    # Absent an injected local_checks, only the generic detectors run.
    report_obj = run_maintenance(root=tmp_path, mode="audit", write=False, program_id="acme-pr")
    assert not any(f.category == "dependency_drift" for f in report_obj.findings)

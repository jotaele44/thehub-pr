import json

from prii_maintenance import quarantine
from prii_maintenance.models import MaintenanceFinding


def test_write_review_queue_includes_errors_and_quarantined(tmp_path):
    findings = [
        MaintenanceFinding(finding_id="1", repo="acme-pr", category="schema", severity="error"),
        MaintenanceFinding(finding_id="2", repo="acme-pr", category="artifact_hygiene", severity="info"),
        MaintenanceFinding(finding_id="3", repo="acme-pr", category="duplicate",
                            severity="warning", action="quarantined"),
        MaintenanceFinding(finding_id="4", repo="acme-pr", category="manifest", severity="critical"),
    ]

    out = quarantine.write_review_queue("acme-pr", findings, tmp_path)

    assert out == tmp_path / "reports" / "maintenance" / "review_queue.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["repo"] == "acme-pr"
    assert payload["count"] == 3
    assert {item["finding_id"] for item in payload["items"]} == {"1", "3", "4"}


def test_write_review_queue_empty_when_nothing_qualifies(tmp_path):
    findings = [
        MaintenanceFinding(finding_id="1", repo="acme-pr", category="artifact_hygiene", severity="info"),
    ]
    out = quarantine.write_review_queue("acme-pr", findings, tmp_path)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 0
    assert payload["items"] == []

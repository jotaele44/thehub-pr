from prii_maintenance import report
from prii_maintenance.models import MaintenanceFinding, MaintenanceReport


def test_write_latest_report(tmp_path):
    rpt = MaintenanceReport(
        repo="acme-pr",
        findings=[
            MaintenanceFinding(finding_id="1", repo="acme-pr", category="schema", severity="critical"),
        ],
    )

    out = report.write_latest_report(rpt, tmp_path)

    assert out == tmp_path / "reports" / "maintenance" / "latest.json"
    assert out.exists()
    payload = rpt.to_dict()
    assert payload["repo"] == "acme-pr"
    assert payload["critical_count"] == 1
    assert payload["promotion_blocked"] is True

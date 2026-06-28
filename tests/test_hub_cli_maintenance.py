"""CLI integration tests for `hub maintenance`."""
import json

from hub.cli import main

REGISTRY = "registry/producers.yaml"


def _write_report(root, repo, **overrides):
    report = {
        "repo": repo,
        "maintenance_version": "0.1.0",
        "mode": "audit",
        "generated_at": "2026-01-01T00:00:00Z",
        "findings_count": 0,
        "critical_count": 0,
        "promotion_blocked": False,
        "findings": [],
    }
    report.update(overrides)
    path = root / repo / "reports" / "maintenance" / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report))


def test_maintenance_json_emits_rollup(tmp_path, capsys):
    rc = main(["maintenance", "--registry", REGISTRY, "--root", str(tmp_path), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "repo_status" in data
    assert data["reports_missing"] == data["producer_count"]


def test_maintenance_fail_on_blocker_when_missing(tmp_path, capsys):
    rc = main([
        "maintenance", "--registry", REGISTRY, "--root", str(tmp_path), "--fail-on-blocker"
    ])
    assert rc == 1
    assert "PROMOTION BLOCKED" in capsys.readouterr().out


def test_maintenance_passes_when_all_present_and_clean(tmp_path, capsys):
    # Use the real registry but satisfy every producer with a clean report.
    from hub.registry import load_registry
    reg = load_registry(REGISTRY)
    for p in reg.producers:
        _write_report(tmp_path, p.program_id)
    rc = main([
        "maintenance", "--registry", REGISTRY, "--root", str(tmp_path), "--fail-on-blocker"
    ])
    assert rc == 0
    assert "promotion gate: OK" in capsys.readouterr().out


def test_maintenance_write_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = main([
        "maintenance",
        "--registry",
        str(__import__("pathlib").Path(__file__).resolve().parents[1] / REGISTRY),
        "--root",
        str(tmp_path),
        "--write-report",
    ])
    assert rc == 0
    out = tmp_path / "reports" / "federation_maintenance" / "latest.json"
    assert out.exists()
    rollup = json.loads(out.read_text())
    assert "repo_status" in rollup

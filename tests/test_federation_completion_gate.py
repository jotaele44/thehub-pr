from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "federation_completion_gate",
    ROOT / "scripts" / "federation_completion_gate.py",
)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


SHA = "a" * 40


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "completion-gate.json"
    path.write_text(json.dumps({"repositories": ["owner/repo"]}))
    return path


def _one_open_pr() -> list[dict[str, object]]:
    return [{
        "number": 7,
        "title": "Dependency refresh",
        "body": "",
        "draft": False,
        "base": {"ref": "main", "sha": SHA},
        "head": {"sha": "b" * 40},
        "merge_commit_sha": "c" * 40,
    }]


def test_pull_request_mode_can_record_rate_limit_partial(monkeypatch, tmp_path):
    config = _write_config(tmp_path)
    out = tmp_path / "ledger.json"

    def request_json(url, token, *, method="GET", body=None):
        if url.endswith("/commits/main"):
            return {"sha": SHA}
        if "/pulls?state=open" in url:
            return _one_open_pr()
        if "/check-runs" in url:
            raise RuntimeError("GitHub API 403 for check-runs: API rate limit exceeded")
        raise AssertionError(url)

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(gate, "request_json", request_json)
    monkeypatch.setattr(sys, "argv", [
        "federation_completion_gate.py",
        "--config",
        str(config),
        "--out",
        str(out),
        "--allow-rate-limit-partial",
    ])

    assert gate.main() == 0
    ledger = json.loads(out.read_text())
    assert ledger["certification"] == "PROVISIONAL_RATE_LIMIT_PARTIAL"
    assert ledger["rate_limit_error_count"] == 1
    assert ledger["rows"][0]["state"] == "UNRESOLVED"
    assert ledger["rows"][0]["reasons"] == ["AUDIT_EXCEPTION"]


def test_completion_assertion_still_fails_closed_on_rate_limit(monkeypatch, tmp_path):
    config = _write_config(tmp_path)
    out = tmp_path / "ledger.json"

    def request_json(url, token, *, method="GET", body=None):
        if url.endswith("/commits/main"):
            return {"sha": SHA}
        if "/pulls?state=open" in url:
            return _one_open_pr()
        if "/check-runs" in url:
            raise RuntimeError("GitHub API 403 for check-runs: API rate limit exceeded")
        raise AssertionError(url)

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(gate, "request_json", request_json)
    monkeypatch.setattr(sys, "argv", [
        "federation_completion_gate.py",
        "--config",
        str(config),
        "--out",
        str(out),
        "--fail-on-actionable",
    ])

    assert gate.main() == 2
    ledger = json.loads(out.read_text())
    assert ledger["certification"] == "PROVISIONAL_RATE_LIMIT_PARTIAL"
    assert ledger["rate_limit_error_count"] == 1

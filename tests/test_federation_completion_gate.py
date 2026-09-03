from __future__ import annotations

import importlib.util
import hashlib
import http.client
import io
import json
import sys
from pathlib import Path

import pytest


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


def _two_open_prs() -> list[dict[str, object]]:
    first, second = _one_open_pr()[0], dict(_one_open_pr()[0])
    second["number"] = 8
    second["head"] = {"sha": "d" * 40}
    second["merge_commit_sha"] = "e" * 40
    return [first, second]


def test_request_json_retries_incomplete_response(monkeypatch):
    calls = 0

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise http.client.IncompleteRead(b'{"ok":', 4)
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(gate.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(gate.time, "sleep", lambda _: None)

    assert gate.request_json("https://api.github.test/resource", "token") == {"ok": True}
    assert calls == 2


def test_request_json_fails_closed_after_incomplete_response_retries(monkeypatch):
    calls = 0

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise http.client.IncompleteRead(b'{"ok":', 4)

    monkeypatch.setattr(gate.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(gate.time, "sleep", lambda _: None)
    monkeypatch.setattr(gate, "REQUEST_RETRIES", 1)

    with pytest.raises(RuntimeError, match="GitHub API transport error"):
        gate.request_json("https://api.github.test/resource", "token")
    assert calls == 2


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
    assert ledger["open_pr_denominator_complete"] is False
    assert ledger["audit_truncated"] is True
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
    assert ledger["open_pr_denominator_complete"] is True
    assert ledger["audit_truncated"] is False
    assert ledger["rate_limit_error_count"] == 1


def test_rate_limit_partial_stops_crawl_after_first_rate_limit(monkeypatch, tmp_path):
    config = _write_config(tmp_path)
    out = tmp_path / "ledger.json"
    check_run_calls = 0

    def request_json(url, token, *, method="GET", body=None):
        nonlocal check_run_calls
        if url.endswith("/commits/main"):
            return {"sha": SHA}
        if "/pulls?state=open" in url:
            return _two_open_prs()
        if "/check-runs" in url:
            check_run_calls += 1
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
    assert check_run_calls == 1
    assert ledger["audit_truncated"] is True
    assert ledger["open_pr_denominator_complete"] is False
    assert ledger["open_pr_denominator"] == 1
    assert [row["number"] for row in ledger["rows"]] == [7]


def test_max_prs_marks_non_certifying_truncated_partial(monkeypatch, tmp_path):
    config = _write_config(tmp_path)
    out = tmp_path / "ledger.json"

    def request_json(url, token, *, method="GET", body=None):
        if url.endswith("/commits/main"):
            return {"sha": SHA}
        if "/pulls?state=open" in url:
            return _two_open_prs()
        if "/check-runs" in url:
            return {"check_runs": []}
        if "/compare/" in url:
            return {"merge_base_commit": {"sha": SHA}, "files": []}
        if "/pulls/7/files" in url:
            return []
        raise AssertionError(url)

    def unresolved_threads(owner, repo, number, token):
        return 0

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(gate, "request_json", request_json)
    monkeypatch.setattr(gate, "unresolved_threads", unresolved_threads)
    monkeypatch.setattr(sys, "argv", [
        "federation_completion_gate.py",
        "--config",
        str(config),
        "--out",
        str(out),
        "--max-prs",
        "1",
    ])

    assert gate.main() == 0
    ledger = json.loads(out.read_text())
    assert ledger["certification"] == "PROVISIONAL_TRUNCATED_PARTIAL"
    assert ledger["open_pr_denominator_complete"] is False
    assert ledger["audit_truncated"] is True
    assert ledger["truncation_reason"] == "PR_AUDIT_ROW_LIMIT:1"
    assert ledger["open_pr_denominator"] == 1


def test_resume_retries_only_audit_exception_with_frozen_inputs(monkeypatch, tmp_path):
    config = _write_config(tmp_path)
    out = tmp_path / "resumed.json"
    prior_path = tmp_path / "prior.json"
    failed = gate.Disposition(
        "owner/repo", 7, "Dependency refresh", "b" * 40, "main", SHA,
        SHA, "c" * 40, False, "UNRESOLVED", ["AUDIT_EXCEPTION"],
    )
    prior_path.write_text(json.dumps({
        "schema_version": 2,
        "repositories": ["owner/repo"],
        "observed_main_shas": {"owner/repo": SHA},
        "open_pr_denominator": 1,
        "open_pr_denominator_complete": True,
        "audit_truncated": False,
        "errors": ["owner/repo#7: transient"],
        "rows": [gate.asdict(failed)],
    }))

    def request_json(url, token, *, method="GET", body=None):
        if url.endswith("/pulls/7"):
            return _one_open_pr()[0]
        if "/check-runs" in url:
            return {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]}
        if "/compare/" in url:
            return {"merge_base_commit": {"sha": SHA}, "files": []}
        if "/pulls/7/files" in url:
            return []
        raise AssertionError(url)

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(gate, "request_json", request_json)
    monkeypatch.setattr(gate, "unresolved_threads", lambda *args: 0)
    monkeypatch.setattr(sys, "argv", [
        "federation_completion_gate.py", "--config", str(config), "--out", str(out),
        "--resume-from", str(prior_path), "--fail-on-actionable",
    ])

    assert gate.main() == 3
    ledger = json.loads(out.read_text())
    assert ledger["errors"] == []
    assert ledger["resumed_from"] == "prior.json"
    assert ledger["resume_source_sha256"] == hashlib.sha256(prior_path.read_bytes()).hexdigest()
    assert ledger["resumed_rows"] == ["owner/repo#7"]
    assert ledger["rows"][0]["state"] == "MERGE_READY"

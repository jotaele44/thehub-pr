import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import federation_audit.runtime_cert as runtime_cert
from federation_audit.calibration import run_calibration
from federation_audit.classifier import classify_observations
from federation_audit.resolver import build_resolution_index
from federation_audit.runtime_cert import (
    Probe,
    _failure_reason,
    _install_block_wrappers,
    execute_probe,
    git_head,
    validate_topology,
    verify_runtime_dependencies,
    verify_workspace,
)


def test_static_declaration_cannot_self_promote():
    classification, _, _, _ = classify_observations(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
        }
    )
    assert classification.value == "PARTIALLY_WIRED"


def test_contract_promotion_requires_resolver_receipt():
    classification, _, _, _ = classify_observations(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
            "target_resolution_evidence": True,
        }
    )
    assert classification.value == "EXECUTABLE_BY_CONTRACT"


def test_runtime_confirmation_requires_isolation_and_t2():
    classification, _, _, _ = classify_observations(
        {
            "terminal_observed": True,
            "side_effect_intercepted": True,
            "runtime_isolated": True,
            "t2_receipt": True,
        }
    )
    assert classification.value == "EXECUTABLE_CONFIRMED"


def test_adversarial_calibration_has_no_known_fp_or_fn():
    result = run_calibration()
    assert result["passed"] is True, result
    assert result["true_positive"] >= 2
    assert result["true_negative"] >= 3
    assert result["false_positive"] == 0
    assert result["false_negative"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_frontend_resolution_accepts_symlinked_root(tmp_path: Path):
    real_root = tmp_path / "real"
    web = real_root / "web"
    web.mkdir(parents=True)
    (web / "handlers.js").write_text("export const run = () => true;\n", encoding="utf-8")
    (web / "App.jsx").write_text(
        'import { run } from "./handlers";\nexport const App = () => run();\n',
        encoding="utf-8",
    )
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    index = build_resolution_index(linked_root)

    assert index.imports["web/App.jsx"]["run"] == ("web/handlers.js", "run")


def test_block_wrappers_emit_valid_jsonl(tmp_path: Path):
    bin_dir, log_path = _install_block_wrappers(tmp_path)
    env = os.environ | {"FEDERATION_AUDIT_BLOCK_LOG": str(log_path)}

    result = subprocess.run([str(bin_dir / "curl"), "https://example.invalid"], env=env, check=False)

    assert result.returncode == 126
    assert json.loads(log_path.read_text(encoding="utf-8")) == {"command": "curl", "argc": 1}


def test_failure_reason_redacts_exception_message():
    stderr = "Traceback (most recent call last):\nFileNotFoundError: /secret/operator-token\n"

    reason = _failure_reason(None, stderr, timed_out=False, alive_after_startup=False)

    assert reason == "spawn-error:FileNotFoundError"
    assert "secret" not in reason


def test_failure_reason_distinguishes_timeout_and_live_boot():
    assert _failure_reason(1, "", timed_out=True, alive_after_startup=False) == "timeout"
    assert _failure_reason(None, "", timed_out=False, alive_after_startup=True) is None


def test_runtime_dependency_manifest_binds_lock_and_snapshot(tmp_path: Path):
    lock = tmp_path / "requirements.lock"
    snapshot = tmp_path / "runtime-dependencies.txt"
    manifest = tmp_path / "runtime-dependencies.json"
    lock.write_text("fastapi==0.141.1\n", encoding="utf-8")
    snapshot.write_text("fastapi==0.141.1\n", encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "verified": True,
                "lock": {"file": lock.name, "sha256": digest(lock)},
                "snapshot": {"file": snapshot.name, "sha256": digest(snapshot)},
                "package_count": 1,
                "packages": [{"name": "fastapi", "version": "0.141.1"}],
            }
        ),
        encoding="utf-8",
    )

    receipt, failures = verify_runtime_dependencies(lock, manifest)

    assert failures == []
    assert receipt["verified"] is True
    snapshot.write_text("fastapi==0.141.2\n", encoding="utf-8")
    _, failures = verify_runtime_dependencies(lock, manifest)
    assert failures == ["runtime-dependencies-manifest-mismatch"]

    snapshot.write_text("starlette==1.6.0\n", encoding="utf-8")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["snapshot"]["sha256"] = digest(snapshot)
    payload["packages"] = [{"name": "starlette", "version": "1.6.0"}]
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    _, failures = verify_runtime_dependencies(lock, manifest)
    assert failures == ["runtime-dependencies-manifest-mismatch"]


def test_probe_routes_declared_data_path_to_shadow(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / "repo").mkdir(parents=True)
    for name in runtime_cert.ATTESTATIONS:
        monkeypatch.setenv(name, "1")
    probe = Probe(
        probe_id="shadow-path",
        repository="repo",
        surface_kind="api",
        entry_point="app.py",
        cwd=".",
        command=(
            sys.executable,
            "-c",
            "import os, pathlib; pathlib.Path(os.environ['APP_DATA_DIR'], 'written').write_text('ok')",
        ),
        mode="command",
        timeout_seconds=10,
        startup_seconds=1,
        expected_exit=(0,),
        shadow_paths=(("APP_DATA_DIR", "app"),),
        minimum_gate="G4",
    )

    receipt = execute_probe(workspace, tmp_path / "shadow", probe)

    assert receipt["passed"] is True
    assert receipt["shadow_environment_variable_names"] == ["APP_DATA_DIR"]
    assert (tmp_path / "shadow/shadow-path/fs/app/written").read_text() == "ok"


def test_probe_rejects_shadow_path_escape():
    with pytest.raises(ValueError, match="must stay relative"):
        Probe.from_dict(
            {
                "probe_id": "escape",
                "repository": "repo",
                "surface_kind": "api",
                "entry_point": "app.py",
                "command": ["python", "app.py"],
                "mode": "boot",
                "shadow_paths": {"APP_DATA_DIR": "../outside"},
            }
        )


def test_workspace_preflight_names_missing_git(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(runtime_cert.shutil, "which", lambda _: None)

    receipts, failures = verify_workspace(tmp_path, {"repositories": []})

    assert receipts == []
    assert failures == ["runtime-tool-missing:git"]


def test_git_head_scopes_safe_directory_to_repository(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_run(command, **kwargs):
        assert command == ["git", "-c", f"safe.directory={repo.resolve()}", "rev-parse", "HEAD"]
        assert kwargs["cwd"] == repo
        return SimpleNamespace(returncode=0, stdout="a" * 40 + "\n", stderr="")

    monkeypatch.setattr(runtime_cert.subprocess, "run", fake_run)

    assert git_head(repo) == ("a" * 40, None)


def test_topology_must_bind_to_declared_command():
    manifest = {
        "repositories": [
            {
                "workspace_directory": "repo",
                "entry_points": [{"kind": "cli", "path": "cli.py", "command": "tool"}],
            }
        ]
    }
    valid = Probe.from_dict(
        {
            "probe_id": "valid",
            "repository": "repo",
            "surface_kind": "cli",
            "entry_point": "cli.py",
            "command": ["tool", "--help"],
            "mode": "command",
            "minimum_gate": "G4",
        }
    )
    assert validate_topology(manifest, [valid]) == []

    invalid = Probe.from_dict(
        {
            "probe_id": "invalid",
            "repository": "repo",
            "surface_kind": "cli",
            "entry_point": "cli.py",
            "command": ["python", "-c", "print('fake')"],
            "mode": "command",
        }
    )
    failures = validate_topology(manifest, [invalid])
    assert "probe-command-not-declared-prefix:invalid" in failures

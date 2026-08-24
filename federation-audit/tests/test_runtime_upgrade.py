import json
import os
import subprocess
from pathlib import Path

import federation_audit.runtime_cert as runtime_cert
from federation_audit.calibration import run_calibration
from federation_audit.classifier import classify_observations
from federation_audit.resolver import build_resolution_index
from federation_audit.runtime_cert import Probe, _install_block_wrappers, validate_topology, verify_workspace


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


def test_workspace_preflight_names_missing_git(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(runtime_cert.shutil, "which", lambda _: None)

    receipts, failures = verify_workspace(tmp_path, {"repositories": []})

    assert receipts == []
    assert failures == ["runtime-tool-missing:git"]


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

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "federation_completion_contracts_v2",
    ROOT / "scripts" / "federation_completion_contracts.py",
)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contracts
SPEC.loader.exec_module(contracts)


THEHUB_SHA = "f2b81769924689b4d959554928810b1d7b7ef3d6"


def test_uv_tool_sources_are_hard_git_bindings() -> None:
    text = f'''\n[project]\ndependencies = ["prii-maintenance", "prii-export-utils"]\n\n[tool.uv.sources]\nprii-maintenance = {{ git = "https://github.com/jotaele44/thehub-pr.git", rev = "{THEHUB_SHA}", subdirectory = "packages/prii_maintenance" }}\nprii-export-utils = {{ git = "https://github.com/jotaele44/thehub-pr.git", rev = "{THEHUB_SHA}", subdirectory = "packages/prii_export_utils" }}\n'''
    finding = contracts.manifest_transport(text)
    assert finding["git_thehub_count"] == 2
    assert finding["pep508_git_thehub_count"] == 0
    assert finding["uv_git_thehub_count"] == 2
    assert finding["git_thehub_shas"] == [THEHUB_SHA]
    assert finding["immutable_sha_provenance"] is True


def test_pep508_and_uv_bindings_are_counted_independently() -> None:
    text = (
        f'prii-desktop @ git+https://github.com/jotaele44/thehub-pr.git@{THEHUB_SHA}'
        '#subdirectory=packages/prii_desktop\n'
        f'prii-maintenance = {{ git = "https://github.com/jotaele44/thehub-pr.git", '
        f'rev = "{THEHUB_SHA}", subdirectory = "packages/prii_maintenance" }}\n'
    )
    finding = contracts.manifest_transport(text)
    assert finding["git_thehub_count"] == 2
    assert finding["pep508_git_thehub_count"] == 1
    assert finding["uv_git_thehub_count"] == 1


def test_runner_zero_and_no_steps_is_pre_runner() -> None:
    job = {
        "id": 101166806875,
        "run_id": 33917002990,
        "run_attempt": 2,
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "failure",
        "steps": [],
        "labels": ["ubuntu-latest"],
        "runner_id": 0,
        "runner_name": "",
    }
    assert contracts.failure_stage(job) == "PRE_RUNNER"
    evidence = contracts.failure_evidence(job)
    assert evidence["failure_stage"] == "PRE_RUNNER"
    assert evidence["step_count"] == 0
    assert evidence["runner_id"] == 0
    assert evidence["runner_name"] == ""
    assert evidence["run_attempt"] == 2


def test_pre_runner_signature_can_match_across_different_jobs() -> None:
    left = contracts.failure_evidence({
        "id": 1,
        "run_id": 10,
        "run_attempt": 1,
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "failure",
        "steps": [],
        "labels": ["ubuntu-latest"],
        "runner_id": 0,
        "runner_name": "",
    })
    right = contracts.failure_evidence({
        "id": 2,
        "run_id": 11,
        "run_attempt": 2,
        "head_sha": "b" * 40,
        "status": "completed",
        "conclusion": "failure",
        "steps": [],
        "labels": ["ubuntu-latest"],
        "runner_id": 0,
        "runner_name": "",
    })
    assert contracts.same_failure_signature(left, right) is True


def test_failure_stage_does_not_promote_failure_class() -> None:
    assert contracts.classify_failure(
        same_signature_on_baseline=False,
        baseline_green=False,
        causal_binding_to_pr_delta=False,
        same_sha_rerun_passed_without_mutation=False,
        transient_signature_supported=False,
    ) == "UNRESOLVED"


def test_config_binds_skywatcher_and_spiderweb_hard_surfaces() -> None:
    cfg = json.loads((ROOT / "federation" / "completion-contracts.json").read_text())
    sky = cfg["repositories"]["jotaele44/skywatcher-pr"]
    spider = cfg["repositories"]["jotaele44/spiderweb-pr"]
    assert sky["root_requirement_manifests"] == ["pyproject.toml"]
    assert "federation.json" in sky["executable_dependency_surfaces"]
    assert spider["desktop_authority"] == "CUSTOM"
    assert ".github/workflows/ci.yml" in spider["executable_dependency_surfaces"]

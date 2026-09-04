from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "federation_completion_contracts",
    ROOT / "scripts" / "federation_completion_contracts.py",
)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contracts
SPEC.loader.exec_module(contracts)


SHA = "f2b81769924689b4d959554928810b1d7b7ef3d6"


def test_manifest_transport_separates_git_and_archive_bindings():
    text = (
        f"prii-desktop @ git+https://github.com/jotaele44/thehub-pr.git@{SHA}"
        "#subdirectory=packages/prii_desktop\n"
        f"prii-export-utils @ https://github.com/jotaele44/thehub-pr/archive/{SHA}.zip"
        "#subdirectory=packages/prii_export_utils\n"
    )
    result = contracts.manifest_transport(text)
    assert result["git_thehub_count"] == 1
    assert result["archive_thehub_count"] == 1
    assert result["git_thehub_shas"] == [SHA]
    assert result["archive_thehub_shas"] == [SHA]
    assert result["immutable_sha_provenance"] is True


def test_generated_artifact_record_requires_byte_and_hash_equality():
    digest = "a" * 64
    assert contracts.validate_generated_artifact_record({
        "state": "PASS",
        "byte_identical": True,
        "regenerated_sha256": digest,
        "committed_sha256": digest,
    }) == []

    reasons = contracts.validate_generated_artifact_record({
        "state": "STALE",
        "byte_identical": False,
        "regenerated_sha256": "a" * 64,
        "committed_sha256": "b" * 64,
    })
    assert "GENERATED_ARTIFACT_NOT_PASS" in reasons
    assert "GENERATED_ARTIFACT_STALE" in reasons
    assert "GENERATED_ARTIFACT_HASH_MISMATCH" in reasons


def test_gui_candidate_record_requires_arithmetic_closure_and_zero_unclassified():
    assert contracts.validate_gui_candidate_record({
        "candidate_count": 7,
        "bound_count": 3,
        "internal_count": 2,
        "exempt_count": 2,
        "unclassified_count": 0,
    }) == []

    reasons = contracts.validate_gui_candidate_record({
        "candidate_count": 7,
        "bound_count": 3,
        "internal_count": 2,
        "exempt_count": 1,
        "unclassified_count": 1,
    })
    assert "GUI_UNCLASSIFIED_CANDIDATES:1" in reasons

    reasons = contracts.validate_gui_candidate_record({
        "candidate_count": 8,
        "bound_count": 3,
        "internal_count": 2,
        "exempt_count": 1,
        "unclassified_count": 1,
    })
    assert "GUI_CANDIDATE_ARITHMETIC_NOT_CLOSED" in reasons


def test_failure_attribution_defaults_to_unresolved():
    assert contracts.classify_failure(
        same_signature_on_baseline=False,
        baseline_green=False,
        causal_binding_to_pr_delta=False,
        same_sha_rerun_passed_without_mutation=False,
        transient_signature_supported=False,
    ) == "UNRESOLVED"


def test_failure_attribution_requires_hard_evidence_for_specific_states():
    assert contracts.classify_failure(
        same_signature_on_baseline=True,
        baseline_green=False,
        causal_binding_to_pr_delta=False,
        same_sha_rerun_passed_without_mutation=False,
        transient_signature_supported=False,
    ) == "BASE_FAILURE"

    assert contracts.classify_failure(
        same_signature_on_baseline=False,
        baseline_green=True,
        causal_binding_to_pr_delta=True,
        same_sha_rerun_passed_without_mutation=False,
        transient_signature_supported=False,
    ) == "PR_FAILURE"

    assert contracts.classify_failure(
        same_signature_on_baseline=False,
        baseline_green=False,
        causal_binding_to_pr_delta=False,
        same_sha_rerun_passed_without_mutation=True,
        transient_signature_supported=True,
    ) == "TRANSIENT"


def test_desktop_and_root_transport_are_independent(monkeypatch):
    files = {
        ".github/workflows/template-drift.yml": (
            "PRII_TEMPLATE_REF: b1a6f59fc7edacd8172f2849ca17a70f9454390d\n"
        ),
        "requirements-desktop.txt": (
            f"prii-desktop @ https://github.com/jotaele44/thehub-pr/archive/{SHA}.zip"
            "#subdirectory=packages/prii_desktop\n"
        ),
        "requirements.in": (
            f"prii-maintenance @ git+https://github.com/jotaele44/thehub-pr.git@{SHA}"
            "#subdirectory=packages/prii_maintenance\n"
        ),
        ".github/workflows/desktop-build.yml": (
            "PRII_TOOLING_ROOT=/tmp/thehub\n"
            "git clone https://github.com/jotaele44/thehub-pr.git /tmp/thehub\n"
        ),
    }
    monkeypatch.setattr(contracts, "main_sha", lambda *_: "a" * 40)
    monkeypatch.setattr(contracts, "fetch_text", lambda repo, path, ref, token: files[path])

    row = contracts.audit_repository(
        "owner/repo",
        {
            "desktop_authority": "STANDARD",
            "desktop_requirement_manifests": ["requirements-desktop.txt"],
            "root_requirement_manifests": ["requirements.in"],
            "template_ref_path": ".github/workflows/template-drift.yml",
            "desktop_workflow_path": ".github/workflows/desktop-build.yml",
        },
        "b1a6f59fc7edacd8172f2849ca17a70f9454390d",
        "token",
    )
    assert row["desktop_git_thehub_dependency_count"] == 0
    assert row["desktop_archive_thehub_dependency_count"] == 1
    assert row["one_thehub_materialization_contract"] is True
    assert row["root_git_thehub_dependency_count"] == 1
    assert "ROOT_RUNTIME_GIT_THEHUB:1" in row["reasons"]
    assert not any(reason.startswith("STANDARD_DESKTOP_GIT_THEHUB") for reason in row["reasons"])

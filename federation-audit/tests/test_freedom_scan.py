from __future__ import annotations

import json
from pathlib import Path

from federation_audit.freedom_scan import AXES, scan_freedom


def _policy() -> dict:
    return {
        "policy_id": "FEDERATION_FREEDOM_CONTRACT_v1",
        "scan": {
            "ignored_directories": [".git", "node_modules", "dist", "build"],
            "authored_suffixes": [".py", ".js", ".jsx", ".yml", ".yaml", ".toml"],
            "exact_names": ["package.json", "requirements.txt", "requirements.in", ".env.example"],
            "raw_evidence_globs": ["data/raw/**", "**/data/raw/**"],
        },
        "offline_bundle_manifest_candidates": [".federation/offline-dependencies.json"],
        "rules": [
            {
                "id": "PAID",
                "axes": ["COST_FREE", "SERVICE_INDEPENDENT"],
                "severity": "BLOCKER",
                "classification": "REMOVE_OR_LOCALIZE",
                "pattern": r"api\.anthropic\.com|ANTHROPIC_API_KEY",
                "include_globs": ["**/*.py", "**/.env.example"],
                "exclude_globs": ["**/tests/**"],
                "rationale": "paid service",
            },
            {
                "id": "CDN",
                "axes": ["SELF_CONTAINED_RELEASE"],
                "severity": "BLOCKER",
                "classification": "BUNDLE_LOCALLY",
                "pattern": r"unpkg\.com",
                "include_globs": ["**/*.py"],
                "exclude_globs": [],
                "rationale": "remote executable asset",
            },
        ],
        "dynamic_gates": ["NETWORK_DENY_STARTUP"],
    }


def _snapshot() -> dict:
    return {
        "snapshot_id": "fixture",
        "repositories": [
            {
                "id": "demo",
                "repository": "example/demo",
                "commit": "a" * 40,
                "tree": "b" * 40,
                "workspace_directory": "demo",
            }
        ],
    }


def test_freedom_scan_fails_closed_and_preserves_raw_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    (repo / "src").mkdir(parents=True)
    (repo / "data" / "raw").mkdir(parents=True)
    (repo / "src" / "service.py").write_text(
        'URL = "https://api.anthropic.com/v1/messages"\n',
        encoding="utf-8",
    )
    (repo / "src" / "report.py").write_text(
        'HTML = "<script src=\\"https://unpkg.com/lib.js\\"></script>"\n',
        encoding="utf-8",
    )
    (repo / "data" / "raw" / "snapshot.py").write_text(
        'URL = "https://api.anthropic.com/v1/messages"\n',
        encoding="utf-8",
    )
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"react": "latest", "shared": "https://example.test/shared.tgz"}}),
        encoding="utf-8",
    )

    result = scan_freedom(tmp_path, _snapshot(), _policy())

    assert result["certified"] is False
    assert result["certification_state"] == "FAIL"
    assert result["summary"]["arithmetic_closed"] is True
    assert result["summary"]["dynamic_gates_executed"] == 0
    assert result["summary"]["raw_evidence_files_preserved"] == 1
    rules = {finding["rule_id"] for finding in result["repositories"][0]["findings"]}
    expected = {
        "PAID",
        "CDN",
        "FF-BUILD-FLOATING-SPEC",
        "FF-BUILD-REMOTE-PACKAGE-SOURCE",
        "FF-BUILD-NO-OFFLINE-BUNDLE-MANIFEST",
    }
    assert expected <= rules


def test_offline_manifest_closes_only_the_structural_bundle_finding(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    (repo / ".federation").mkdir(parents=True)
    (repo / ".federation" / "offline-dependencies.json").write_text("{}\n", encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"react": "19.2.8"}}),
        encoding="utf-8",
    )

    result = scan_freedom(tmp_path, _snapshot(), _policy())

    rules = {finding["rule_id"] for finding in result["repositories"][0]["findings"]}
    assert "FF-BUILD-NO-OFFLINE-BUNDLE-MANIFEST" not in rules
    assert result["repositories"][0]["axis_states"] == {axis: "PROVISIONAL" for axis in AXES}
    assert result["certified"] is False
    assert result["certification_state"] == "PROVISIONAL"


def test_root_pyproject_detects_core_test_tool_and_remote_source(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        """[project]
dependencies = [
    "pytest>=8.0",
    "shared",
]

[tool.uv.sources]
shared = { git = "https://github.com/example/shared.git", rev = "aaaaaaaa" }
""",
        encoding="utf-8",
    )

    result = scan_freedom(tmp_path, _snapshot(), _policy())

    rules = {finding["rule_id"] for finding in result["repositories"][0]["findings"]}
    assert "FF-DEPENDENCY-PLANE-MIX" in rules
    assert "FF-BUILD-REMOTE-PYTHON-SOURCE" in rules

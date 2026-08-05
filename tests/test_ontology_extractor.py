from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROGRAMS = ["thehub-pr", "spiderweb-pr", "centinelas-pr", "aguayluz-pr", "ovnis-pr", "skywatcher-pr", "moneysweep-pr"]


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def build_repo(root: Path, program: str) -> str:
    root.mkdir(parents=True)
    (root / "models.py").write_text("""from dataclasses import dataclass\nfrom enum import Enum\n\nclass ReviewStatus(str, Enum):\n    DRAFT = 'draft'\n    ACTIVE = 'active'\n\n@dataclass\nclass SourceRecord:\n    source_id: str\n    confidence: float\n\nclass DomainError(Exception):\n    pass\n""", encoding="utf-8")
    (root / "schema.json").write_text(json.dumps({"$schema": "http://json-schema.org/draft-07/schema#", "title": "Observation", "type": "object", "required": ["observation_id", "confidence"], "properties": {"observation_id": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "status": {"type": "string", "enum": ["draft", "active"]}, "items": {"type": "array"}}}, indent=2), encoding="utf-8")
    (root / "config.yaml").write_text("source_registry:\n  status: active\n  retry_count: 2\n", encoding="utf-8")
    (root / "README.md").write_text("# Public Matter\n\n- **Evidence** — source support.\n\n`AlertEvent`\n", encoding="utf-8")
    (root / "bad.yaml").write_text("broken: [\n", encoding="utf-8")
    (root / "federation.json").write_text(json.dumps({"schema_version": "repo_federation_manifest_v1", "program_id": program, "repository_full_name": f"jotaele44/{program}", "federation_role": "test_producer", "hub_parent": "thehub-pr", "hub_callable_commands": {"setup": "true", "test_suite": "true"}, "canonical_outputs": {"canonical_export_dir": "exports/federation"}, "federation_readiness_gate": {"ready_for_hub_discovery": True, "ready_for_hub_live_execution": False, "blocking_conditions": ["fixture"]}}, indent=2), encoding="utf-8")
    tests = root / "tests"; tests.mkdir(); (tests / "test_contract.py").write_text("def test_status():\n    status = 'active'\n    assert status == 'active'\n", encoding="utf-8")
    run("git", "init", "-q", cwd=root); run("git", "config", "user.email", "ontology@example.invalid", cwd=root); run("git", "config", "user.name", "Ontology Test", cwd=root); run("git", "add", ".", cwd=root); run("git", "commit", "-qm", "fixture", cwd=root)
    return run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()


def test_seven_repository_extraction_and_analysis(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]; workspace = tmp_path / "workspace"; pins = []
    for program in PROGRAMS:
        commit = build_repo(workspace / program, program)
        pins.append({"program_id": program, "repository": f"jotaele44/{program}", "directory": program, "commit": commit, "owner": program})
    pins_path = tmp_path / "pins.json"; pins_path.write_text(json.dumps({"repositories": pins}), encoding="utf-8"); out = tmp_path / "generated"
    extract = run(sys.executable, str(project_root / "tools/ontology/extract_terms.py"), "--workspace", str(workspace), "--pins", str(pins_path), "--out", str(out), cwd=project_root, check=False)
    assert extract.returncode == 0, extract.stderr + extract.stdout
    coverage = json.loads((out / "coverage.json").read_text(encoding="utf-8")); assert coverage["repositories_scanned"] == 7; assert coverage["all_repositories_100_percent"] is True; assert all(repo["coverage_percent"] == 100.0 for repo in coverage["repositories"]); assert any(repo["warnings"] for repo in coverage["repositories"])
    records = [json.loads(line) for line in (out / "raw-term-ledger.jsonl").read_text(encoding="utf-8").splitlines()]; kinds = {record["term_kind"] for record in records}
    assert {"python_enum", "enum_member", "python_dataclass", "schema_property", "config_key", "documented_term", "test_assertion_term"} <= kinds; assert all(len(record["commit"]) == 40 for record in records); assert len({record["observation_id"] for record in records}) == len(records)
    analyze = run(sys.executable, str(project_root / "tools/ontology/analyze_terms.py"), "--ledger", str(out / "raw-term-ledger.jsonl"), "--coverage", str(out / "coverage.json"), "--resolutions", str(project_root / "federation/ontology/resolutions/priority-term-families.yaml"), "--out", str(out), cwd=project_root, check=False)
    assert analyze.returncode == 0, analyze.stderr + analyze.stdout
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8")); assert summary["coordinated_pr_gate"] is True; assert summary["deduplicated_records"] > 0


def test_extractor_rejects_commit_mismatch(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]; workspace = tmp_path / "workspace"; pins = []
    for program in PROGRAMS:
        build_repo(workspace / program, program); pins.append({"program_id": program, "repository": f"jotaele44/{program}", "directory": program, "commit": "0" * 40, "owner": program})
    pins_path = tmp_path / "pins.json"; pins_path.write_text(json.dumps({"repositories": pins}), encoding="utf-8")
    result = run(sys.executable, str(project_root / "tools/ontology/extract_terms.py"), "--workspace", str(workspace), "--pins", str(pins_path), "--out", str(tmp_path / "out"), cwd=project_root, check=False)
    assert result.returncode == 2
    coverage = json.loads((tmp_path / "out/coverage.json").read_text(encoding="utf-8")); assert coverage["all_repositories_100_percent"] is False; assert len(coverage["fatal_errors"]) == 7

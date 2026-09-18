from __future__ import annotations

import json
import subprocess
from pathlib import Path

from federation_audit.parity_ancestry import contract_commit_relation


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", message], check=True)
    return _git(root, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, dict, str]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "audit@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Audit Fixture"], check=True)
    (root / "server/backend").mkdir(parents=True)
    (root / "frontend/src").mkdir(parents=True)
    (root / "server/backend/main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "frontend/src/App.jsx").write_text("export default () => null;\n", encoding="utf-8")
    source = _commit(root, "source")
    contract = {
        "source_commit": source,
        "discovery": {
            "backend_roots": ["server/backend"],
            "frontend_roots": ["frontend/src"],
            "route_files": ["frontend/src/App.jsx"],
            "navigation_files": ["frontend/src/App.jsx"],
            "existing_gui_capability_manifests": [],
        },
    }
    return root, contract, source


def test_contract_commit_exact(tmp_path: Path) -> None:
    root, contract, source = _repo(tmp_path)
    receipt = contract_commit_relation(root, contract, source)
    assert receipt["relation"] == "EXACT"
    assert receipt["changed_watched_paths"] == []


def test_contract_commit_clean_ancestor_allows_contract_only_commit(tmp_path: Path) -> None:
    root, contract, _source = _repo(tmp_path)
    (root / ".federation").mkdir()
    (root / ".federation/gui_backend_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    head = _commit(root, "contract only")
    receipt = contract_commit_relation(root, contract, head)
    assert receipt["relation"] == "ANCESTOR_CLEAN"
    assert receipt["changed_watched_paths"] == []


def test_contract_commit_stale_when_audited_source_changes(tmp_path: Path) -> None:
    root, contract, _source = _repo(tmp_path)
    (root / "frontend/src/App.jsx").write_text("export default () => 'changed';\n", encoding="utf-8")
    head = _commit(root, "frontend change")
    receipt = contract_commit_relation(root, contract, head)
    assert receipt["relation"] == "ANCESTOR_STALE"
    assert receipt["changed_watched_paths"] == ["frontend/src/App.jsx"]


def test_contract_commit_rejects_non_ancestor(tmp_path: Path) -> None:
    root, contract, source = _repo(tmp_path)
    subprocess.run(["git", "-C", str(root), "checkout", "--orphan", "other"], check=True)
    subprocess.run(["git", "-C", str(root), "rm", "-rf", "."], check=True)
    (root / "README.md").write_text("other\n", encoding="utf-8")
    head = _commit(root, "other history")
    assert head != source
    receipt = contract_commit_relation(root, contract, head)
    assert receipt["relation"] == "NOT_ANCESTOR"

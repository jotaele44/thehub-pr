import json
from pathlib import Path

import pytest

from hub.registry import Producer, Registry
from hub.workspace import (
    CANONICAL_PYTHON,
    HUB_NAME,
    WorkspaceError,
    _command_for_mode,
    _production_gate,
    clone_workspace,
    execute_mode,
    repository_specs,
    validate_workspace,
)


class Result:
    stdout = ""


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append((list(cmd), cwd))
        return Result()


def registry():
    return Registry(
        hub=HUB_NAME,
        schema_version="hub_registry_v1",
        producers=[
            Producer(program_id="alpha-pr", repo="jotaele44/alpha-pr", role="producer"),
            Producer(program_id="beta-pr", repo="jotaele44/beta-pr", role="producer"),
        ],
    )


def materialize_checkout(path: Path, *, hub=False, ready=True, command=None):
    (path / ".git").mkdir(parents=True)
    (path / ".python-version").write_text(CANONICAL_PYTHON + "\n")
    if hub:
        for shared in ("packages/prii_maintenance", "packages/prii_export_utils"):
            (path / shared).mkdir(parents=True)
        return
    payload = {
        "program_id": path.name,
        "production_status": "PRODUCTION" if ready else "NON_PRODUCTION_DIAGNOSTIC",
        "federation_readiness_gate": {
            "ready_for_hub_live_execution": ready,
            "blocking_conditions": [],
        },
        "hub_callable_commands": command or {"export_canonical": "python3 scripts/export.py --mode test"},
    }
    (path / "federation.json").write_text(json.dumps(payload))


def test_repository_specs_puts_hub_first():
    specs = repository_specs(registry())
    assert specs[0].name == HUB_NAME
    assert [item.name for item in specs[1:]] == ["alpha-pr", "beta-pr"]


def test_clone_workspace_is_hub_first(tmp_path):
    runner = FakeRunner()
    receipts = clone_workspace(registry(), tmp_path / "workspace", runner=runner)
    assert receipts[0].program_id == HUB_NAME
    assert "thehub-pr.git" in runner.calls[0][0][-2]
    assert runner.calls[0][0][-1].endswith("/thehub-pr")


def test_clone_workspace_rejects_non_git_destination(tmp_path):
    root = tmp_path / "workspace"
    (root / HUB_NAME).mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="not a Git checkout"):
        clone_workspace(registry(), root, runner=FakeRunner())


def test_clone_workspace_rejects_nested_workspace(tmp_path):
    parent = tmp_path / "outer"
    (parent / ".git").mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="nested inside Git checkout"):
        clone_workspace(registry(), parent / "workspace", runner=FakeRunner())


def test_validate_workspace_requires_siblings_shared_packages_and_python_policy(tmp_path):
    root = tmp_path / "workspace"
    materialize_checkout(root / HUB_NAME, hub=True)
    materialize_checkout(root / "alpha-pr")
    materialize_checkout(root / "beta-pr")
    report = validate_workspace(registry(), root)
    assert report["valid"] is True
    assert not report["errors"]

    (root / "alpha-pr" / ".python-version").write_text("3.13\n")
    report = validate_workspace(registry(), root)
    assert report["valid"] is False
    assert any("expected 3.11" in item for item in report["errors"])


def test_production_gate_is_fail_closed():
    assert _production_gate({})[0] is False
    assert _production_gate({"production_status": "PRODUCTION"})[0] is False
    blocked = {
        "production_status": "PRODUCTION",
        "federation_readiness_gate": {
            "ready_for_hub_live_execution": True,
            "blocking_conditions": ["operator receipt missing"],
        },
    }
    assert _production_gate(blocked)[0] is False
    ready = {
        "production_status": "PRODUCTION",
        "federation_readiness_gate": {
            "ready_for_hub_live_execution": True,
            "blocking_conditions": [],
        },
    }
    assert _production_gate(ready) == (True, "ready")


def test_production_command_must_be_explicit():
    test_only = {"hub_callable_commands": {"export_canonical": "python3 export.py --mode test"}}
    assert _command_for_mode(test_only, "test")
    assert _command_for_mode(test_only, "production") is None

    production = {"hub_callable_commands": {"export_production": "python3 export.py --mode production"}}
    assert _command_for_mode(production, "production") == [
        "python3", "export.py", "--mode", "production"
    ]


def test_execute_production_blocks_unready_and_missing_command(tmp_path):
    root = tmp_path / "workspace"
    materialize_checkout(root / HUB_NAME, hub=True)
    materialize_checkout(
        root / "alpha-pr",
        ready=False,
        command={"export_production": "python3 scripts/export.py --mode production"},
    )
    materialize_checkout(root / "beta-pr", ready=True)
    runner = FakeRunner()
    receipts = execute_mode(registry(), root, "production", runner=runner)
    assert [item.status for item in receipts] == ["blocked", "blocked"]
    assert runner.calls == []


def test_execute_test_does_not_require_live_readiness(tmp_path):
    root = tmp_path / "workspace"
    materialize_checkout(root / HUB_NAME, hub=True)
    materialize_checkout(root / "alpha-pr", ready=False)
    materialize_checkout(root / "beta-pr", ready=False)
    runner = FakeRunner()
    receipts = execute_mode(registry(), root, "test", runner=runner)
    assert all(item.status == "ok" for item in receipts)
    assert len(runner.calls) == 2

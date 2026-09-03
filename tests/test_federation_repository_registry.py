from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from server.backend.federation_manager_repository_registry import (
    RepositoryBindingError,
    WorkspaceRepositoryRegistry,
)


def _write_registry(path: Path, *, local_path: Optional[str] = None) -> None:
    local = f"\n    local_path: {local_path}" if local_path is not None else ""
    path.write_text(
        "\n".join(
            [
                "schema_version: hub_registry_v1",
                "hub: thehub-pr",
                "producers:",
                "  - program_id: spiderweb-pr",
                "    repo: jotaele44/spiderweb-pr",
                "    role: spatial_operational_producer",
                "    federation_manifest: federation.json",
                f"    status: ready_for_live{local}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_manifest(root: Path, **overrides) -> None:
    root.mkdir(parents=True, exist_ok=True)
    doc = {
        "program_id": "spiderweb-pr",
        "repository_full_name": "jotaele44/spiderweb-pr",
    }
    doc.update(overrides)
    (root / "federation.json").write_text(json.dumps(doc), encoding="utf-8")


def _registry(tmp_path: Path, *, local_path: Optional[str] = None) -> WorkspaceRepositoryRegistry:
    workspace = tmp_path / "workspace"
    hub = workspace / "thehub-pr"
    hub.mkdir(parents=True)
    registry = hub / "producers.yaml"
    _write_registry(registry, local_path=local_path)
    return WorkspaceRepositoryRegistry(
        workspace_root=workspace,
        hub_root=hub,
        producer_registry_path=registry,
    )


def test_resolve_requires_registry_and_manifest_identity(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    producer = registry.workspace_root / "spiderweb-pr"
    _write_manifest(producer)

    binding = registry.resolve("spiderweb-pr")

    assert binding.repository_full_name == "jotaele44/spiderweb-pr"
    assert binding.app_id == "spiderweb"
    assert binding.root == producer.resolve()


def test_name_only_directory_cannot_override_manifest_identity(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    producer = registry.workspace_root / "spiderweb-pr"
    _write_manifest(producer, repository_full_name="attacker/spiderweb-pr")

    with pytest.raises(RepositoryBindingError, match="identity contradiction"):
        registry.resolve("spiderweb-pr")


def test_program_id_contradiction_fails_closed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    producer = registry.workspace_root / "spiderweb-pr"
    _write_manifest(producer, program_id="other-pr")

    with pytest.raises(RepositoryBindingError, match="program_id"):
        registry.resolve("spiderweb-pr")


def test_unknown_repo_never_falls_back_by_name(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    (registry.workspace_root / "unknown-pr").mkdir()

    with pytest.raises(RepositoryBindingError, match="not registered"):
        registry.resolve("unknown-pr")


def test_local_path_escape_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path, local_path="../outside")
    outside = registry.workspace_root.parent / "outside"
    _write_manifest(outside)

    with pytest.raises(RepositoryBindingError, match="escapes configured workspace"):
        registry.resolve("spiderweb-pr")

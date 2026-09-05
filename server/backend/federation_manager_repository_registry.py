"""Fail-closed repository bindings for the federation operations plane.

The signed operations policy names a repository (for example ``spiderweb-pr``),
but a repository name is not sufficient evidence that an arbitrary directory is
that producer. This module resolves the name through the Hub's authoritative
producer registry and then verifies the producer's own manifest before returning
a filesystem root.

The binding deliberately separates discovery from identity:

* workspace path/name is discovery only;
* ``registry/producers.yaml`` supplies the expected owner/repository and program id;
* ``federation.json`` must independently agree with both values;
* every resolved root must stay within the configured workspace;
* duplicate registry identities fail closed.

No command is executed here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from hub.registry import Producer, load_registry


class RepositoryBindingError(RuntimeError):
    """A repository could not be bound to an independently verified local root."""


@dataclass(frozen=True)
class RepositoryBinding:
    repo_key: str
    app_id: str
    repository_full_name: str
    root: Path
    manifest_path: Optional[Path]
    source: str

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "repoKey": self.repo_key,
            "appId": self.app_id,
            "repositoryFullName": self.repository_full_name,
            "root": str(self.root),
            "manifestPath": str(self.manifest_path) if self.manifest_path else None,
            "source": self.source,
        }


class WorkspaceRepositoryRegistry:
    """Resolve signed-policy repo keys to verified roots inside one workspace."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        hub_root: Path,
        producer_registry_path: Path,
        hub_repository_full_name: str = "jotaele44/thehub-pr",
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.hub_root = Path(hub_root).expanduser().resolve()
        self.producer_registry_path = Path(producer_registry_path).expanduser().resolve()
        self.hub_repository_full_name = hub_repository_full_name
        self.registry = load_registry(self.producer_registry_path)
        self._producers = self._index(self.registry.producers)
        self._assert_within_workspace(self.hub_root)

    @staticmethod
    def _index(producers: Iterable[Producer]) -> Dict[str, Producer]:
        by_repo_key: Dict[str, Producer] = {}
        seen_program_ids = set()
        seen_full_names = set()
        for producer in producers:
            repo_key = producer.repo_name
            if repo_key in by_repo_key:
                raise RepositoryBindingError(f"duplicate repository key in registry: {repo_key}")
            if producer.program_id in seen_program_ids:
                raise RepositoryBindingError(
                    f"duplicate producer program_id in registry: {producer.program_id}"
                )
            if producer.repo in seen_full_names:
                raise RepositoryBindingError(
                    f"duplicate repository_full_name in registry: {producer.repo}"
                )
            by_repo_key[repo_key] = producer
            seen_program_ids.add(producer.program_id)
            seen_full_names.add(producer.repo)
        return by_repo_key

    def _assert_within_workspace(self, candidate: Path) -> None:
        try:
            candidate.resolve().relative_to(self.workspace_root)
        except ValueError as exc:
            raise RepositoryBindingError(
                f"repository root escapes configured workspace: {candidate}"
            ) from exc

    def _producer_root(self, producer: Producer) -> Path:
        relative = producer.local_path or producer.repo_name
        candidate = (self.workspace_root / relative).resolve()
        self._assert_within_workspace(candidate)
        return candidate

    def resolve(self, repo_key: str) -> RepositoryBinding:
        """Return a verified binding or raise; never fall back by nearest name."""
        if repo_key == "thehub-pr":
            if not self.hub_root.is_dir():
                raise RepositoryBindingError(f"Hub root is missing: {self.hub_root}")
            return RepositoryBinding(
                repo_key="thehub-pr",
                app_id="thehub",
                repository_full_name=self.hub_repository_full_name,
                root=self.hub_root,
                manifest_path=None,
                source=str(self.producer_registry_path),
            )

        producer = self._producers.get(repo_key)
        if producer is None:
            raise RepositoryBindingError(f"repo key is not registered: {repo_key!r}")

        root = self._producer_root(producer)
        if not root.is_dir():
            raise RepositoryBindingError(
                f"registered checkout is missing for {producer.repo}: {root}"
            )

        manifest_path = (root / producer.federation_manifest).resolve()
        self._assert_within_workspace(manifest_path)
        if not manifest_path.is_file():
            raise RepositoryBindingError(
                f"registered manifest is missing for {producer.repo}: {manifest_path}"
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryBindingError(
                f"registered manifest is unreadable for {producer.repo}: {exc}"
            ) from exc

        observed_full_name = manifest.get("repository_full_name")
        observed_program_id = manifest.get("program_id")
        conflicts = []
        if observed_full_name != producer.repo:
            conflicts.append(
                f"repository_full_name expected {producer.repo!r}, observed {observed_full_name!r}"
            )
        if observed_program_id != producer.program_id:
            conflicts.append(
                f"program_id expected {producer.program_id!r}, observed {observed_program_id!r}"
            )
        if conflicts:
            raise RepositoryBindingError(
                f"identity contradiction for {repo_key}: " + "; ".join(conflicts)
            )

        return RepositoryBinding(
            repo_key=repo_key,
            app_id=(
                producer.program_id[:-3]
                if producer.program_id.endswith("-pr")
                else producer.program_id
            ),
            repository_full_name=producer.repo,
            root=root,
            manifest_path=manifest_path,
            source=str(self.producer_registry_path),
        )

    def resolve_all(self) -> list[RepositoryBinding]:
        """Resolve the complete declared denominator; one bad producer fails the call."""
        keys = ["thehub-pr", *sorted(self._producers)]
        return [self.resolve(key) for key in keys]

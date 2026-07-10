"""GitHub bridge adapter — read-only view over the producer registry.

Backed by ``registry/producers.yaml`` (already in the repo); no network, no
secrets. Serves the ``github-bridge`` capability every project inherits.

Live git operations (clone/pull) go through hub.fetch.clone_or_pull and are
deliberately out of scope for this hermetic adapter — they remain future
work so the read-only default is preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest
from hub.registry import Registry, load_registry

_DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[4] / "registry" / "producers.yaml"
)


class GithubBridgeAdapter(MCPAdapter):
    """Resolve producer program ids to their GitHub repos.

    Actions:
      - ``list_producers``: every producer (program_id/repo/role/status).
      - ``resolve_repo``:   params ``program_id`` -> repo, repo_name,
                            clone_url.

    The registry path defaults to ``registry/producers.yaml`` and can be
    overridden with params ``registry`` (used by tests).
    """

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self._registry_path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY

    def name(self) -> str:
        return "github-bridge"

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return ["github-bridge"]

    @staticmethod
    def _clone_url(repo: str) -> str:
        return f"https://github.com/{repo}.git"

    def _effective_registry(self, request: MCPRequest) -> Path:
        raw = request.params.get("registry")
        return Path(raw) if raw else self._registry_path

    def _load(self, request: MCPRequest) -> Registry:
        return load_registry(self._effective_registry(request))

    def execute(self, request: MCPRequest) -> Any:
        registry = self._load(request)

        if request.action == "list_producers":
            return {
                "producers": [
                    {
                        "program_id": p.program_id,
                        "repo": p.repo,
                        "repo_name": p.repo_name,
                        "role": p.role,
                        "status": p.status,
                    }
                    for p in registry.producers
                ],
                "count": len(registry.producers),
            }

        if request.action == "resolve_repo":
            program_id = request.params.get("program_id")
            if not program_id:
                raise ValueError("resolve_repo requires a 'program_id' param")
            producer = registry.by_id(program_id)
            if producer is None:
                raise LookupError(f"no producer with program_id {program_id!r}")
            return {
                "program_id": producer.program_id,
                "repo": producer.repo,
                "repo_name": producer.repo_name,
                "clone_url": self._clone_url(producer.repo),
            }

        raise ValueError(f"unknown action {request.action!r}")

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        # Record the registry actually loaded, honoring a params override.
        block["registry"] = str(self._effective_registry(request))
        return block

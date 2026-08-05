"""Load the MCP capability registry and project manifests for the runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Capability:
    name: str
    capability_class: str
    status: str
    version_pin: str
    description: str
    required_by: List[str] = field(default_factory=list)


@dataclass
class ProjectManifest:
    project: str
    inherits: List[str]
    capabilities: List[str]
    write_default: str
    allowed_writes: List[str] = field(default_factory=list)

    @property
    def declared(self) -> List[str]:
        return list(self.inherits) + list(self.capabilities)


class RuntimeRegistry:
    """In-memory view of mcp/registry + mcp/manifests.

    The static validators (tools/validate_mcp_*.py) remain the CI gate; this
    loader re-checks only what the runtime needs to route safely and raises
    ValueError on a registry/manifest state the validators would reject.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        root = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
        self.registry_path = root / "mcp" / "registry" / "capability_registry.yaml"
        self.manifests_dir = root / "mcp" / "manifests"
        self.capabilities: Dict[str, Capability] = {}
        self.project_local: Dict[str, List[str]] = {}
        self.manifests: Dict[str, ProjectManifest] = {}
        self._load()

    def _load(self) -> None:
        if not self.registry_path.is_file():
            raise ValueError(f"capability registry not found: {self.registry_path}")
        raw = yaml.safe_load(self.registry_path.read_text(encoding="utf-8"))
        statuses = set(raw.get("adapter_status_values", []))

        for name, spec in raw.get("capabilities", {}).items():
            status = spec.get("status")
            if status not in statuses:
                raise ValueError(f"capability {name!r} has invalid status {status!r}")
            version_pin = spec.get("version_pin")
            if not version_pin:
                raise ValueError(f"capability {name!r} is missing version_pin")
            self.capabilities[name] = Capability(
                name=name,
                capability_class=spec.get("class", ""),
                status=status,
                version_pin=str(version_pin),
                description=spec.get("description", "").strip(),
                required_by=list(spec.get("required_by", [])),
            )

        self.project_local = {
            project: list(caps or [])
            for project, caps in raw.get("project_local_capabilities", {}).items()
        }

        for path in sorted(self.manifests_dir.glob("*.mcp.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            manifest = ProjectManifest(
                project=data["project"],
                inherits=list(data.get("inherits", [])),
                capabilities=list(data.get("capabilities", [])),
                write_default=data["write_policy"]["default"],
                allowed_writes=list(data["write_policy"].get("allowed_writes", [])),
            )
            local = set(self.project_local.get(manifest.project, []))
            for cap in manifest.declared:
                if cap not in self.capabilities and cap not in local:
                    raise ValueError(
                        f"{path.name}: capability {cap!r} is not a registry "
                        f"capability or a project-local capability of "
                        f"{manifest.project!r}"
                    )
            self.manifests[manifest.project] = manifest

    def manifest_for(self, project: str) -> ProjectManifest:
        try:
            return self.manifests[project]
        except KeyError:
            raise ValueError(f"no manifest for project {project!r}") from None

    def project_declares(self, project: str, capability: str) -> bool:
        return capability in self.manifest_for(project).declared

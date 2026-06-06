"""Load the producer registry (registry/producers.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class Producer:
    program_id: str
    repo: str
    role: str
    status: str = "pending"
    federation_manifest: str = "federation.json"
    local_path: Optional[str] = None

    @property
    def repo_name(self) -> str:
        return self.repo.split("/")[-1]


@dataclass
class Registry:
    hub: str
    schema_version: str
    producers: List[Producer] = field(default_factory=list)

    def by_id(self, program_id: str) -> Optional[Producer]:
        for p in self.producers:
            if p.program_id == program_id:
                return p
        return None


def load_registry(path) -> Registry:
    data = yaml.safe_load(Path(path).read_text()) or {}
    producers = [Producer(**p) for p in data.get("producers", [])]
    return Registry(
        hub=data["hub"],
        schema_version=data["schema_version"],
        producers=producers,
    )

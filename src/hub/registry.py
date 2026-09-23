"""Load the producer registry (registry/producers.yaml)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_REPO_PATTERN = re.compile(r"^[\w.-]+/[\w.-]+$")


@dataclass
class Producer:
    program_id: str
    repo: str
    role: str
    status: str = "pending"
    federation_manifest: str = "federation.json"
    export_path: str = "exports/federation"
    local_path: Optional[str] = None
    # Icon path + accent colour, mirroring the producer's own federation.json
    # "branding" block. Optional so a registry entry written before a producer
    # had artwork still loads — Producer(**entry) is a strict splat.
    branding: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        # Defense-in-depth: `repo` feeds a GitHub clone URL (src/hub/fetch.py).
        # That call is already shell=False with a fixed URL prefix, so this
        # isn't exploitable today, but a malformed registry entry should fail
        # loudly here rather than produce a broken clone URL downstream.
        if not _REPO_PATTERN.match(self.repo):
            raise ValueError(
                f"Producer {self.program_id!r}: repo {self.repo!r} must look like "
                "'owner/name'"
            )

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

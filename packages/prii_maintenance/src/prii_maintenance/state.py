"""Read-only inventory of repo files declared in federation.json."""

from __future__ import annotations

import json
from pathlib import Path


def load_federation(root: Path) -> dict:
    path = root / "federation.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def collect_repo_state(root: Path) -> dict:
    path = root / "federation.json"
    raw_present = path.exists()
    malformed = False
    if raw_present:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            malformed = True

    fed = load_federation(root)
    outputs = fed.get("canonical_outputs", {})
    present = {
        key: (root / rel).exists()
        for key, rel in outputs.items()
        if isinstance(rel, str)
    }
    return {
        # True only when the file exists AND parses; a malformed manifest is
        # distinct from a missing one (see federation_json_malformed) so a
        # corrupt federation.json can't silently produce a clean report.
        "federation_json_present": raw_present and not malformed,
        "federation_json_malformed": malformed,
        "federation": fed,
        "canonical_outputs": outputs,
        "canonical_outputs_present": present,
    }

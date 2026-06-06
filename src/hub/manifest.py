"""Validate a producer's federation.json against repo_federation_manifest_v1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import jsonschema

from ._schemas import load_schema


def _fmt(error: jsonschema.ValidationError) -> str:
    loc = "/".join(str(p) for p in error.path) or "<root>"
    return f"{loc}: {error.message}"


def validate_repo_manifest(manifest: dict) -> List[str]:
    """Return a list of human-readable validation errors ([] == valid)."""
    schema = load_schema("repo_federation_manifest.schema.json")
    validator = jsonschema.Draft7Validator(schema)
    return [_fmt(e) for e in sorted(validator.iter_errors(manifest), key=str)]


def load_and_validate_manifest(path) -> Tuple[dict, List[str]]:
    data = json.loads(Path(path).read_text())
    return data, validate_repo_manifest(data)

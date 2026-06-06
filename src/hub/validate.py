"""Validate a producer export package: manifest shape, file integrity, and
every JSONL row against its stream schema."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List

import jsonschema

from ._schemas import STREAM_SCHEMA, load_schema


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_rows(path: Path):
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        raw = raw.strip()
        if raw:
            yield lineno, raw


def validate_package(pkg_dir) -> List[str]:
    """Return a list of validation errors for an export package ([] == valid)."""
    pkg = Path(pkg_dir)
    errors: List[str] = []

    manifest_path = pkg / "manifest.json"
    if not manifest_path.exists():
        return [f"missing manifest.json in {pkg}"]

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"manifest.json: invalid JSON ({exc})"]

    manifest_schema = load_schema("federation_export_manifest.schema.json")
    for e in sorted(jsonschema.Draft7Validator(manifest_schema).iter_errors(manifest), key=str):
        loc = "/".join(str(p) for p in e.path) or "<root>"
        errors.append(f"manifest: {loc}: {e.message}")

    for fentry in manifest.get("files", []):
        fname = fentry.get("filename")
        stream = fentry.get("stream")
        if not fname:
            errors.append("manifest file entry missing filename")
            continue
        fpath = pkg / fname
        if not fpath.exists():
            errors.append(f"declared file missing: {fname}")
            continue

        declared_sha = fentry.get("sha256")
        if declared_sha:
            actual = _sha256(fpath)
            if actual != declared_sha:
                errors.append(
                    f"{fname}: sha256 mismatch "
                    f"(declared {declared_sha[:12]}…, actual {actual[:12]}…)"
                )

        schema_name = STREAM_SCHEMA.get(stream)
        count = 0
        if schema_name is None:
            # Stream with no Hub-canonical schema (e.g. producer-specific
            # 'observations'): count rows, skip per-row schema validation.
            for _lineno, _raw in _iter_rows(fpath):
                count += 1
        else:
            validator = jsonschema.Draft7Validator(load_schema(schema_name))
            for lineno, raw in _iter_rows(fpath):
                count += 1
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    errors.append(f"{fname}:{lineno}: invalid JSON ({exc})")
                    continue
                for e in validator.iter_errors(row):
                    loc = "/".join(str(p) for p in e.path) or "<root>"
                    errors.append(f"{fname}:{lineno}: {loc}: {e.message}")

        declared_count = fentry.get("record_count")
        if declared_count is not None and count != declared_count:
            errors.append(
                f"{fname}: record_count mismatch "
                f"(declared {declared_count}, actual {count})"
            )

    return errors

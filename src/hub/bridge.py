"""Adapt a producer's raw JSONL stream directory into a Hub-conformant export
package by generating a ``federation_export_manifest.json``.

Some producers (e.g. Contract-Sweeper's canonical_v1 bridge) emit the canonical
``sources/entities/relationships.jsonl`` streams but with a producer-specific
manifest. This adapter wraps such a directory into the Hub's package contract
(deterministic ``package_id``, per-file ``sha256`` + ``record_count``,
``hub_parent`` handshake) so ``hub validate-package`` / ``hub aggregate`` can
consume it without the producer changing its bridge output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ._schemas import STREAM_SCHEMA

# Canonical filename -> stream name (only files that exist are included).
_CANDIDATES = [
    ("sources.jsonl", "sources"),
    ("entities.jsonl", "entities"),
    ("relationships.jsonl", "relationships"),
    ("funding_awards.jsonl", "funding_awards"),
    ("transactions.jsonl", "transactions"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_count(path: Path) -> int:
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def write_manifest(
    pkg_dir,
    producer: str,
    *,
    mode: str = "test",
    created_at: str = "1970-01-01T00:00:00Z",
    export_contract_version: str = "1.0.0",
) -> dict:
    """Generate manifest.json for a directory of canonical JSONL streams.

    ``created_at`` is passed in (not wall-clock) so the package_id stays
    deterministic and reproducible.
    """
    pkg = Path(pkg_dir)
    files = []
    for filename, stream in _CANDIDATES:
        fpath = pkg / filename
        if not fpath.exists():
            continue
        files.append({
            "filename": filename,
            "stream": stream,
            "record_count": _record_count(fpath),
            "sha256": _sha256(fpath),
            "schema_id": STREAM_SCHEMA[stream],
        })
    if not files:
        raise ValueError(f"no canonical JSONL streams found in {pkg}")

    # Deterministic package id from sorted (filename, sha256) + mode.
    digest = hashlib.sha256(
        ("|".join(f"{f['filename']}:{f['sha256']}" for f in sorted(files, key=lambda x: x["filename"])) + f"|{mode}").encode()
    ).hexdigest()[:32]

    manifest = {
        "package_id": f"pkg_{digest}",
        "producer": producer,
        "export_contract_version": export_contract_version,
        "mode": mode,
        "created_at": created_at,
        "federation": {"producer_repo": producer, "hub_parent": "thehub-pr"},
        "files": files,
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest

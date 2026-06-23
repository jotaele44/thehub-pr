"""Merge validated producer export packages into a single federation graph.

Rows are deduplicated by their deterministic id (same id across producers ->
last writer wins, but a ``_producers`` provenance list records every contributor).
Writes ``<out>/<stream>.jsonl`` plus ``<out>/graph_summary.json``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping

from ._schemas import STREAM_ID_FIELD
from .bridge import write_manifest
from .validate import validate_package


def aggregate(packages: Mapping[str, Path], out_dir, strict: bool = True) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    streams: Dict[str, Dict[str, dict]] = {}
    summary = {"producers": {}, "streams": {}, "errors": {}}

    for producer, pkg in packages.items():
        pkg = Path(pkg)
        errs = validate_package(pkg)
        summary["errors"][producer] = errs
        if errs and strict:
            continue

        manifest = json.loads((pkg / "manifest.json").read_text())
        per_stream_counts: Dict[str, int] = {}
        for fentry in manifest.get("files", []):
            stream = fentry["stream"]
            fpath = pkg / fentry["filename"]
            if not fpath.exists():
                continue
            id_field = STREAM_ID_FIELD.get(stream)
            bucket = streams.setdefault(stream, {})
            n = 0
            with fpath.open() as _fh:
                for raw in _fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    row = json.loads(raw)
                    key = row.get(id_field) if id_field else f"{producer}:{stream}:{n}"
                    existing = bucket.get(key)
                    provenance = (existing or {}).get("_producers", []) if existing else []
                    row = dict(row)
                    row["_producers"] = sorted(set(provenance) | {producer})
                    bucket[key] = row
                    n += 1
            per_stream_counts[stream] = n
        summary["producers"][producer] = per_stream_counts

    for stream, rows in streams.items():
        with (out / f"{stream}.jsonl").open("w") as fh:
            for row in rows.values():
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        summary["streams"][stream] = len(rows)

    (out / "graph_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _is_ready_for_discovery(base: Path) -> bool:
    """Read a producer's federation.json readiness gate. Default True if absent."""
    fed = base / "federation.json"
    if not fed.exists():
        return True
    try:
        gate = json.loads(fed.read_text()).get("federation_readiness_gate", {})
    except (json.JSONDecodeError, OSError):
        return True
    return bool(gate.get("ready_for_hub_discovery", True))


def discover_packages(registry, root, enforce_readiness: bool = True) -> Dict[str, Path]:
    """Discover each producer's export package under a workspace root.

    For each producer, resolves ``<base>/<export_path>`` where ``base`` is the
    producer's ``local_path`` or ``<root>/<repo_name>`` and ``export_path`` comes
    from the registry (default ``exports/federation``). If the directory has a
    ``manifest.json`` it is used as-is; otherwise, if it holds raw canonical
    streams (sources/entities/relationships.jsonl) a Hub-conformant manifest is
    generated on the fly via :func:`hub.bridge.write_manifest`. Producers whose
    ``federation.json`` gate sets ``ready_for_hub_discovery: false`` are skipped
    when ``enforce_readiness`` is set.
    """
    root = Path(root)
    found: Dict[str, Path] = {}
    for producer in registry.producers:
        base = Path(producer.local_path) if producer.local_path else root / producer.repo_name
        if enforce_readiness and not _is_ready_for_discovery(base):
            continue
        candidate = base / producer.export_path
        if (candidate / "manifest.json").exists():
            found[producer.program_id] = candidate
        elif any((candidate / f"{s}.jsonl").exists() for s in ("sources", "entities", "relationships")):
            try:
                write_manifest(candidate, producer.program_id)
                found[producer.program_id] = candidate
            except ValueError:
                pass
    return found

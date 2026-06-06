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
            for raw in fpath.read_text().splitlines():
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


def discover_packages(registry, root) -> Dict[str, Path]:
    """Best-effort discovery of export packages under a workspace root.

    Looks for ``<root>/<repo_name>/exports/federation/manifest.json`` for each
    registered producer.
    """
    root = Path(root)
    found: Dict[str, Path] = {}
    for producer in registry.producers:
        candidate = root / producer.repo_name / "exports" / "federation"
        if (candidate / "manifest.json").exists():
            found[producer.program_id] = candidate
    return found

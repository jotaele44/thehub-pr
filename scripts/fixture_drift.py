#!/usr/bin/env python3
"""Decide whether a regenerated fixture differs from the committed one *in substance*.

Why this exists
---------------
`federation-ingest.yml` regenerates the bounded fixture and proposes it as a pull
request. Without this check it would propose one on every single dispatch,
forever, because the producers stamp wall-clock timestamps into every record —
`scripts/federation_export.py` derives a `now` per run and writes it through — so
two back-to-back exports of byte-identical upstream data still differ on every
line.

Measured on aguayluz (34,633 entities), exporting twice with nothing changed
upstream: `created_at` and `extracted_at` differ on **100%** of records in
entities, relationships, sources and alerts. Nothing else differs — `lineage`,
ids, names, confidences and locations are all stable. So those two fields are the
volatile set, and they were determined by running the experiment rather than by
reading the exporters and guessing.

What it deliberately does not catch
-----------------------------------
Dropping `created_at` means a change that touches *only* that field goes
unreported. That is a real blind spot, accepted knowingly: some producers stamp
the export run into `created_at` (aguayluz) while others carry a genuine source
date there (moneysweep's canonical bridge), and there is no honest way to tell
the two apart from the value alone. A producer correcting real data essentially
always moves another field too, and record additions and removals are caught
regardless because ids are part of the digest.

Usage:
    python3 scripts/fixture_drift.py <baseline-dir> <candidate-dir>

Prints `drift=true` or `drift=false` — the GITHUB_OUTPUT format the workflow
appends — plus a per-stream summary on stderr. Exits 0 either way; a non-zero
exit means the comparison itself failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

#: Fields the producers rewrite on every export run. Determined empirically (see
#: the module docstring); extend it only with a field shown to differ between two
#: back-to-back exports of unchanged data.
VOLATILE_FIELDS = frozenset({"created_at", "extracted_at"})

#: Files in an aggregate directory worth comparing. `manifest.json` is excluded
#: on purpose: it carries per-file sha256s and a `package_id` derived from
#: content that includes the volatile timestamps, so it always differs and never
#: says anything the streams have not already said.
STREAMS = ("sources.jsonl", "entities.jsonl", "relationships.jsonl",
           "alerts.jsonl", "observations.jsonl", "correlations.jsonl")
SUMMARIES = ("graph_summary.json",)


def strip_volatile(value: Any) -> Any:
    """Recursively drop volatile keys so two runs of the same data compare equal."""
    if isinstance(value, dict):
        return {k: strip_volatile(v) for k, v in value.items()
                if k not in VOLATILE_FIELDS}
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def _normalised_records(path: Path) -> Iterable[str]:
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                # Keep unparseable bytes in the comparison rather than dropping
                # them — a corrupted stream is drift worth surfacing, not hiding.
                yield line.decode("utf-8", "replace").strip()
                continue
            yield json.dumps(strip_volatile(record), sort_keys=True)


def stream_digest(path: Path) -> str:
    """Order-independent digest of a JSONL stream, volatile fields removed.

    Sorted because the aggregate concatenates producers and a reordering that
    preserves every record is not a data change worth a pull request.
    """
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    for record in sorted(_normalised_records(path)):
        digest.update(record.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def json_digest(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return "unreadable"
    return hashlib.sha256(
        json.dumps(strip_volatile(payload), sort_keys=True).encode("utf-8")
    ).hexdigest()


def compare(baseline: Path, candidate: Path) -> dict[str, bool]:
    """Per-file: True when the substantive content changed."""
    changed: dict[str, bool] = {}
    for name in STREAMS:
        changed[name] = stream_digest(baseline / name) != stream_digest(candidate / name)
    for name in SUMMARIES:
        changed[name] = json_digest(baseline / name) != json_digest(candidate / name)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path, help="the committed aggregate")
    parser.add_argument("candidate", type=Path, help="the freshly built aggregate")
    args = parser.parse_args(argv)

    if not args.candidate.is_dir():
        sys.stderr.write(f"candidate directory not found: {args.candidate}\n")
        return 2

    changed = compare(args.baseline, args.candidate)
    for name, differs in sorted(changed.items()):
        sys.stderr.write(f"  {name:24} {'CHANGED' if differs else 'unchanged'}\n")

    drift = any(changed.values())
    sys.stderr.write(
        "substantive drift detected\n" if drift else
        "no substantive drift — only per-run timestamps moved\n"
    )
    print(f"drift={'true' if drift else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

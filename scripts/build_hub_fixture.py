#!/usr/bin/env python3
"""Build a committable, bounded fixture of the federation aggregate.

Why this exists
---------------
The hub is the federation's product surface (ADR 0001) and it ships with an
empty `data/` directory, so most of its pages render nothing. The pipeline that
would fill it already works — `hub aggregate` -> `correlate` -> `ingest`
populates twenty collections from the six producers. Two things stopped that
reaching a user:

* `federation-ingest.yml` ends at `actions/upload-artifact`, so a successful run
  leaves the deployed hub's `data/` untouched.
* A full run is far too large to commit. Measured against the current corpus:
  the aggregate is **77 MB** and the resulting `hub.db` is **281 MB**. GitHub
  warns past 50 MB per file; `entities.jsonl` alone is 27 MB.

So the committed artefact has to be a sample. This builds one with the *real*
pipeline rather than a hand-written stub, so the fixture exercises the same
projection code the production path does and cannot drift into fiction.

What it is not
--------------
Not a substitute for a real ingest. The sample is capped per stream, so counts
in the UI are not federation totals, and `fixture.json` records both the sampled
and the true count for every stream so nobody mistakes one for the other. A page
reading a sampled collection is showing real records, truncated — never invented
ones.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Streams the aggregate emits, in the order the pipeline writes them.
STREAMS = ("sources", "entities", "relationships", "alerts", "observations")

DEFAULT_CAP = 400


def _run(args: list[str]) -> None:
    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"pipeline step failed: {' '.join(args)}")


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _producer_of(raw: bytes) -> str:
    """Which producer contributed a record, for stratification."""
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return "?"
    producers = record.get("_producers")
    if isinstance(producers, list) and producers:
        return str(producers[0])
    if isinstance(producers, str):
        return producers
    return str(record.get("producer") or record.get("program_id") or "?")


def cap_stream(path: Path, cap: int) -> tuple[int, int]:
    """Sample a JSONL stream down to `cap` records. Returns (kept, original).

    Round-robin across producers rather than taking the first `cap` lines. The
    aggregate concatenates producers and one of them dominates the corpus —
    aguayluz contributes 96% of entities — so a head-truncated sample contains
    that producer and nothing else. Measured: head-400 produced 16 collections
    and silently dropped UnifiedCases, PatternObservations, PublicMatters and
    ContinuityRisks, because the producers that project them sort last.

    Round-robin keeps every producer represented, which is the point of a
    fixture that stands in for the federation.
    """
    original = _line_count(path)
    if original <= cap:
        return original, original

    buckets: dict[str, list[bytes]] = {}
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            normalised = line if line.endswith(b"\n") else line + b"\n"
            buckets.setdefault(_producer_of(normalised), []).append(normalised)

    kept: list[bytes] = []
    index = 0
    # Smallest producers first, so a cap that cannot fit everyone still favours
    # breadth of representation over the dominant producer's bulk.
    order = sorted(buckets, key=lambda name: len(buckets[name]))
    while len(kept) < cap and any(index < len(buckets[name]) for name in order):
        for name in order:
            if len(kept) >= cap:
                break
            if index < len(buckets[name]):
                kept.append(buckets[name][index])
        index += 1

    path.write_bytes(b"".join(kept))
    return len(kept), original


def build(root: Path, out: Path, cap: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "aggregate"

        # Step 1 — the real aggregate, unbounded. Sampling before this point
        # would bias which producers are represented; sampling after keeps every
        # producer in the mix.
        _run([sys.executable, "-m", "hub.cli", "aggregate",
              "--root", str(root), "--out", str(work)])

        provenance: dict[str, dict[str, int]] = {}
        for stream in STREAMS:
            path = work / f"{stream}.jsonl"
            if not path.exists():
                continue
            kept, original = cap_stream(path, cap)
            provenance[stream] = {"sampled": kept, "actual": original}

        # Step 2 and 3 — correlate and ingest run over the *sampled* streams, so
        # the database is internally consistent: no correlation points at a
        # record the fixture does not contain.
        _run([sys.executable, "-m", "hub.cli", "correlate",
              "--in", str(work), "--out", str(work)])

        # `ingest` upserts, so a database left over from a previous run would
        # keep rows this fixture no longer contains and the counts reported
        # below would overstate what the committed JSONL actually produces.
        # Measured: rebuilding over an existing db reported 20 collections where
        # a clean build of the same streams produces 18.
        database = out / "hub.db"
        database.unlink(missing_ok=True)
        _run([sys.executable, "-m", "hub.cli", "ingest",
              "--in", str(work), "--db", str(database)])

        aggregate_out = out / "aggregate"
        aggregate_out.mkdir(parents=True, exist_ok=True)
        # Replace the stream files, but leave anything else (notably .gitkeep,
        # which is tracked) alone.
        for stale in aggregate_out.glob("*.jsonl"):
            stale.unlink()
        for item in work.iterdir():
            if item.is_file():
                shutil.copy2(item, aggregate_out / item.name)

    return provenance


def collection_counts(db: Path) -> dict[str, int]:
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    finally:
        conn.close()
    return {name: count for name, count in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT.parent,
                        help="workspace holding the producer checkouts")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data",
                        help="destination for hub.db, aggregate/ and fixture.json")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP,
                        help=f"max records kept per stream (default {DEFAULT_CAP})")
    args = parser.parse_args(argv)

    provenance = build(args.root.resolve(), args.out.resolve(), args.cap)
    counts = collection_counts(args.out / "hub.db")

    manifest = {
        "kind": "bounded-sample",
        "cap_per_stream": args.cap,
        "streams": provenance,
        "collections": counts,
        "note": (
            "Built by scripts/build_hub_fixture.py from the real "
            "aggregate/correlate/ingest pipeline. Records are genuine but "
            "truncated: 'sampled' is what this fixture holds, 'actual' is what a "
            "full run produced. Counts shown in the UI against this fixture are "
            "not federation totals."
        ),
    }
    (args.out / "fixture.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    total = sum(counts.values())
    print(f"fixture written to {args.out}")
    print(f"  {len(counts)} collections, {total} rows, cap={args.cap}/stream")
    for stream, numbers in sorted(provenance.items()):
        marker = "" if numbers["sampled"] == numbers["actual"] else "  (capped)"
        print(f"  {stream:16} {numbers['sampled']:>6} of {numbers['actual']:>7}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

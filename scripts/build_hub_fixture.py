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


def _producer_of(record: dict) -> str:
    """Which producer contributed a record, for stratification."""
    producers = record.get("_producers")
    if isinstance(producers, list) and producers:
        return str(producers[0])
    if isinstance(producers, str):
        return producers
    return str(record.get("producer") or record.get("program_id") or "?")


#: Second stratification axis per stream. Producer alone is not enough: within a
#: producer's bucket the sample is taken in export order, so a record type that
#: sorts late never surfaces however wide the producer spread is. Measured
#: against a cap-400 sample stratified by producer only:
#:
#:   * moneysweep contributed 96 entities — 60 person, 15 funding_agency,
#:     11 recipient, 10 municipality — and *zero* of its 3 `contract` entities,
#:     which sit at indices 177-179 of its 200-row export. Contracts was empty.
#:   * aguayluz contributed 146 relationships, none of them `energized_by`. Those
#:     edges are appended last by the producer's water/power crosswalk, behind
#:     41,000 rows, so ContinuityRisks was empty too.
#:
#: Splitting on the record's own type fixes both without raising the cap: a
#: three-row bucket is drained whole long before a bulk one is.
_SUBKEY = {
    "entities": "entity_type",
    "relationships": "relationship_type",
    "alerts": "module",
}


def _bucket_key(stream: str, record: dict) -> tuple[str, str]:
    field = _SUBKEY.get(stream)
    subkey = str(record.get(field) or "?") if field else ""
    return _producer_of(record), subkey


def cap_stream(path: Path, cap: int, stream: str = "") -> tuple[int, int]:
    """Sample a JSONL stream down to `cap` records. Returns (kept, original).

    Round-robin across (producer, record type) rather than taking the first
    `cap` lines. The aggregate concatenates producers and one of them dominates
    the corpus — aguayluz contributes 96% of entities — so a head-truncated
    sample contains that producer and nothing else. Measured: head-400 produced
    16 collections and silently dropped UnifiedCases, PatternObservations,
    PublicMatters and ContinuityRisks, because the producers that project them
    sort last.

    Stratifying by producer alone fixed that but left a second head-truncation
    inside each producer's bucket; see `_SUBKEY` for what that cost. Bucketing on
    the record type as well keeps every (producer, type) combination
    represented, which is the point of a fixture that stands in for the
    federation.
    """
    original = _line_count(path)
    if original <= cap:
        return original, original

    buckets: dict[tuple[str, str], list[bytes]] = {}
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            normalised = line if line.endswith(b"\n") else line + b"\n"
            try:
                record = json.loads(normalised)
            except (ValueError, UnicodeDecodeError):
                record = {}
            buckets.setdefault(_bucket_key(stream, record), []).append(normalised)

    kept: list[bytes] = []
    index = 0
    # Smallest buckets first, so a cap that cannot fit everyone still favours
    # breadth of representation over the dominant producer/type's bulk.
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


#: Fields that point at an entity from another stream. `project_continuity_risks`
#: joins relationships -> entities and alerts -> entities, and drops any row whose
#: endpoint is absent (`src/hub/ingest.py`, the `water_id not in ents` guard).
_ENTITY_REFERENCES = {
    "relationships": ("source_entity_id", "target_entity_id"),
    "alerts": ("entity_id",),
}


def _entity_lines(path: Path) -> dict[str, bytes]:
    """entity_id -> raw line, taken before the stream is capped."""
    index: dict[str, bytes] = {}
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            entity_id = record.get("entity_id")
            if entity_id:
                index[str(entity_id)] = line if line.endswith(b"\n") else line + b"\n"
    return index


def _referenced_ids(work: Path) -> set[str]:
    wanted: set[str] = set()
    for stream, fields in _ENTITY_REFERENCES.items():
        path = work / f"{stream}.jsonl"
        if not path.exists():
            continue
        with path.open("rb") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                for field in fields:
                    value = record.get(field)
                    if value:
                        wanted.add(str(value))
    return wanted


def close_entity_references(work: Path, entity_lines: dict[str, bytes]) -> int:
    """Re-admit entities referenced by surviving relationships and alerts.

    Each stream is capped independently, so a relationship can survive while the
    entity it points at does not. The Hub-side projections join across streams
    and silently drop those rows, which is the second half of why
    ContinuityRisks came out empty: even with `energized_by` edges in the sample,
    `project_continuity_risks` needs the water asset they name.

    Returns the number of entities added. This deliberately exceeds the entity
    cap — a sample whose cross-stream joins do not resolve is not a smaller
    federation, it is a broken one — and the overage is recorded in fixture.json.
    """
    path = work / "entities.jsonl"
    if not path.exists():
        return 0

    present = set(_entity_lines(path))
    missing = [
        entity_id for entity_id in sorted(_referenced_ids(work) - present)
        if entity_id in entity_lines
    ]
    if missing:
        with path.open("ab") as handle:
            handle.write(b"".join(entity_lines[entity_id] for entity_id in missing))
    return len(missing)


def build(root: Path, out: Path, cap: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "aggregate"

        # Step 1 — the real aggregate, unbounded. Sampling before this point
        # would bias which producers are represented; sampling after keeps every
        # producer in the mix.
        _run([sys.executable, "-m", "hub.cli", "aggregate",
              "--root", str(root), "--out", str(work)])

        # Index the entities before capping truncates the file — the closure pass
        # below needs the rows the sample is about to drop.
        entities_path = work / "entities.jsonl"
        entity_lines = _entity_lines(entities_path) if entities_path.exists() else {}

        provenance: dict[str, dict[str, int]] = {}
        for stream in STREAMS:
            path = work / f"{stream}.jsonl"
            if not path.exists():
                continue
            kept, original = cap_stream(path, cap, stream)
            provenance[stream] = {"sampled": kept, "actual": original}

        # Step 1b — restore cross-stream referential integrity. Runs after every
        # stream is capped, so it sees the relationships and alerts that actually
        # survived.
        added = close_entity_references(work, entity_lines)
        if added and "entities" in provenance:
            provenance["entities"]["closure_added"] = added
            provenance["entities"]["sampled"] += added

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
            "not federation totals. Streams are sampled round-robin across "
            "(producer, record type); 'closure_added' counts entities re-admitted "
            "beyond the cap because a surviving relationship or alert refers to "
            "them, without which cross-stream projections would drop those rows."
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
        closure = numbers.get("closure_added")
        if closure:
            marker += f"  (+{closure} for reference closure)"
        print(f"  {stream:16} {numbers['sampled']:>6} of {numbers['actual']:>7}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

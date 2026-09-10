"""Merge validated producer export packages into a single federation graph.

Rows are deduplicated by deterministic id only when their canonical payloads are
identical. If two producers emit the same deterministic id with different
payloads, the aggregate fails closed for that id: no arbitrary winner is emitted
into the canonical stream and every conflicting variant is preserved in
``aggregation_collisions.json``.

This makes aggregation order-independent and prevents a producer encountered
later in the input mapping from silently replacing another producer's record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from ._schemas import STREAM_ID_FIELD
from .bridge import write_manifest
from .validate import validate_package


def _canonical_payload(row: Mapping[str, Any]) -> dict:
    """Return the producer payload used for equality comparison.

    ``_producers`` is Hub aggregation provenance, not producer-owned canonical
    content, so it must not make otherwise identical records compare unequal.
    """
    return {key: value for key, value in row.items() if key != "_producers"}


def _variant(producer: str, row: Mapping[str, Any]) -> dict:
    """Stable collision-ledger representation for one producer variant."""
    return {"producer": producer, "row": _canonical_payload(row)}


def aggregate(packages: Mapping[str, Path], out_dir, strict: bool = True) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    streams: Dict[str, Dict[str, dict]] = {}
    owners: Dict[str, Dict[str, set[str]]] = {}
    blocked: Dict[str, set[str]] = {}
    collisions: Dict[tuple[str, str], dict] = {}
    summary: Dict[str, Any] = {
        "producers": {},
        "streams": {},
        "errors": {},
        "collisions": {"count": 0, "by_stream": {}},
    }

    # Producer iteration is sorted deliberately. Canonical outputs and collision
    # ledgers therefore do not depend on caller mapping insertion order.
    for producer in sorted(packages):
        pkg = Path(packages[producer])
        # Full row-schema validation belongs to validate-package/federation.
        # Aggregation still checks manifest, hashes, counts, and JSON integrity.
        errs = validate_package(pkg, validate_rows=False)
        summary["errors"][producer] = errs
        if errs and strict:
            continue

        manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
        per_stream_counts: Dict[str, int] = {}
        for fentry in sorted(
            manifest.get("files", []),
            key=lambda entry: (str(entry.get("stream", "")), str(entry.get("filename", ""))),
        ):
            stream = fentry["stream"]
            fpath = pkg / fentry["filename"]
            if not fpath.exists():
                continue
            id_field = STREAM_ID_FIELD.get(stream)
            bucket = streams.setdefault(stream, {})
            stream_owners = owners.setdefault(stream, {})
            stream_blocked = blocked.setdefault(stream, set())
            n = 0
            with fpath.open("r", encoding="utf-8") as _fh:
                for raw in _fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    row = json.loads(raw)
                    key_value = row.get(id_field) if id_field else None
                    key = str(key_value) if key_value is not None else f"{producer}:{stream}:{n}"
                    canonical = _canonical_payload(row)

                    if key in stream_blocked:
                        collision = collisions[(stream, key)]
                        variant = _variant(producer, canonical)
                        if variant not in collision["variants"]:
                            collision["variants"].append(variant)
                            collision["variants"].sort(key=lambda item: item["producer"])
                        n += 1
                        continue

                    existing = bucket.get(key)
                    if existing is None:
                        stamped = dict(canonical)
                        stamped["_producers"] = [producer]
                        bucket[key] = stamped
                        stream_owners[key] = {producer}
                        n += 1
                        continue

                    if _canonical_payload(existing) == canonical:
                        contributors = stream_owners.setdefault(
                            key, set(existing.get("_producers") or [])
                        )
                        contributors.add(producer)
                        existing["_producers"] = sorted(contributors)
                        n += 1
                        continue

                    # Same deterministic id, different payload: remove the row
                    # from the canonical stream and preserve every variant. No
                    # producer wins by input order.
                    prior_producers = sorted(
                        stream_owners.get(key, set(existing.get("_producers") or []))
                    )
                    collision = {
                        "stream": stream,
                        "id_field": id_field,
                        "record_id": key,
                        "status": "UNRESOLVED",
                        "reason": "same_deterministic_id_different_payload",
                        "variants": [
                            _variant(prior, existing) for prior in prior_producers
                        ]
                        + [_variant(producer, canonical)],
                    }
                    collision["variants"].sort(key=lambda item: item["producer"])
                    collisions[(stream, key)] = collision
                    stream_blocked.add(key)
                    bucket.pop(key, None)
                    stream_owners.pop(key, None)
                    n += 1
            per_stream_counts[stream] = n
        summary["producers"][producer] = per_stream_counts

    for stream in sorted(streams):
        rows = streams[stream]
        with (out / f"{stream}.jsonl").open("w") as fh:
            for key in sorted(rows):
                fh.write(json.dumps(rows[key], sort_keys=True) + "\n")
        summary["streams"][stream] = len(rows)

    collision_rows = [collisions[key] for key in sorted(collisions)]
    collision_path = out / "aggregation_collisions.json"
    collision_path.write_text(json.dumps(collision_rows, indent=2, sort_keys=True) + "\n")
    summary["collisions"]["count"] = len(collision_rows)
    by_stream: Dict[str, int] = {}
    for collision in collision_rows:
        stream = collision["stream"]
        by_stream[stream] = by_stream.get(stream, 0) + 1
    summary["collisions"]["by_stream"] = dict(sorted(by_stream.items()))

    (out / "graph_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
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
        elif any((candidate / f"{s}.jsonl").exists()
                 for s in ("sources", "entities", "relationships", "observations")):
            try:
                write_manifest(candidate, producer.program_id)
                found[producer.program_id] = candidate
            except ValueError:
                pass
    return found


#: The canonical export directory every producer's federation.json declares.
CANONICAL_EXPORT_DIR = "exports/federation"


def discovery_status(registry, root, enforce_readiness: bool = True) -> Dict[str, dict]:
    """Classify each producer's discoverability without side effects.

    Companion to :func:`discover_packages` used for operator-facing warnings: it
    resolves the same paths but writes nothing (no on-the-fly manifest) and
    reports *why* a producer will or will not contribute to the aggregate.

    Each value is a dict with:

    * ``status`` — one of ``found`` (a real ``manifest.json`` is present),
      ``found_bridged`` (raw canonical streams the Hub will auto-wrap),
      ``skipped_unready`` (``ready_for_hub_discovery: false``), or ``missing``
      (no package at the registered ``export_path``).
    * ``on_canonical_path`` — whether the registered ``export_path`` is the
      canonical ``exports/federation`` the producer contract declares.
    * ``canonical_dir_present`` — whether ``<base>/exports/federation`` exists on
      disk at all (``False`` means only a precursor/staging package, if any).
    """
    root = Path(root)
    status: Dict[str, dict] = {}
    for producer in registry.producers:
        base = Path(producer.local_path) if producer.local_path else root / producer.repo_name
        canonical_dir = base / CANONICAL_EXPORT_DIR
        entry = {
            "on_canonical_path": producer.export_path == CANONICAL_EXPORT_DIR,
            "canonical_dir_present": canonical_dir.exists(),
        }
        if enforce_readiness and not _is_ready_for_discovery(base):
            entry["status"] = "skipped_unready"
            status[producer.program_id] = entry
            continue
        candidate = base / producer.export_path
        if (candidate / "manifest.json").exists():
            entry["status"] = "found"
        elif any((candidate / f"{s}.jsonl").exists()
                 for s in ("sources", "entities", "relationships", "observations")):
            entry["status"] = "found_bridged"
        else:
            entry["status"] = "missing"
        status[producer.program_id] = entry
    return status


def dry_run_warnings(status: Mapping[str, dict]) -> list[str]:
    """Human-readable warnings from a :func:`discovery_status` result.

    Surfaces the two silent failure modes: a producer contributing nothing
    (``missing`` / ``skipped_unready``) and a producer whose canonical
    ``exports/federation`` package is absent so the Hub is reading a precursor
    path (or would read nothing)."""
    warnings: list[str] = []
    for program_id, entry in sorted(status.items()):
        st = entry.get("status")
        if st == "missing":
            warnings.append(
                f"{program_id}: no export package found — contributes nothing to the aggregate"
            )
        elif st == "skipped_unready":
            warnings.append(
                f"{program_id}: skipped (ready_for_hub_discovery=false) — contributes nothing"
            )
        elif st in ("found", "found_bridged") and not entry.get("canonical_dir_present"):
            warnings.append(
                f"{program_id}: canonical '{CANONICAL_EXPORT_DIR}' absent — "
                f"aggregating a precursor package instead"
            )
    return warnings

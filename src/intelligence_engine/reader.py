"""Read-only Intelligence Engine query boundary over the certified ACTIVE snapshot.

Serves ``EXACT_ID`` and ``STRUCTURED`` queries only. No embedding, spatial, or
graph index exists anywhere in this repo yet (every manifest built by
``hub.snapshot_runtime.build_snapshot_manifest`` carries ``index_version ==
"none"``), so ``LEXICAL`` ranking, ``VECTOR``, ``SPATIAL``, ``TEMPORAL``,
``GRAPH``, and ``HYBRID`` modes are not implemented — see ``query.QuerySpec``.
``resolve_citation`` is intentionally absent: nothing in this repo populates
``claim_ledger.v1`` yet, so there is nothing to cite against.

The ``correlations`` aggregate stream (unresolved cross-producer identity-match
candidates, see ADR 0009) is deliberately not indexed here: it is evidence
*about* possible entity equivalence, not a canonical record in its own right,
and ADR 0009's federation identity registry is still Proposed, not runtime
certified.

KNOWN GAP: see ``intelligence_engine.objects`` docstring — this reader cannot
enforce real per-row access classification because no producer populates it
yet. Every object returned carries a placeholder ``INTERNAL`` classification
with an explicit reason; do not treat that as an access-policy decision.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from control_plane.active_snapshot import get_active_snapshot
from hub._schemas import STREAM_ID_FIELD

from .abstention import decide_abstention
from .objects import canonical_record_object
from .query import QuerySpec

_DEFAULT_AGGREGATE_DIR = Path("data/aggregate")


class ActiveSnapshotReader:
    """``get_active_snapshot()`` / ``get_object(object_id)`` / ``query(spec)`` only."""

    def __init__(self, storage_root: Any, aggregate_dir: Any = None) -> None:
        self._storage_root = storage_root
        self._aggregate_dir = Path(aggregate_dir) if aggregate_dir is not None else _DEFAULT_AGGREGATE_DIR
        self._manifest: dict[str, Any] | None = None
        self._streams: dict[str, dict[str, dict[str, Any]]] = {}
        self._integrity_error: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            self._manifest = get_active_snapshot(self._storage_root)
        except Exception as exc:  # ActiveSnapshotError, or a malformed pointer/manifest
            self._integrity_error = str(exc)
            return
        if self._manifest is None:
            return

        for entry in self._manifest["sha256_manifest"]:
            path_str = entry["path"]
            if not path_str.startswith("aggregate/"):
                continue
            stream = Path(path_str).stem
            if stream not in STREAM_ID_FIELD:
                continue  # e.g. correlations.jsonl, graph_summary.json — not indexed here
            file_path = self._aggregate_dir / Path(path_str).name
            if not file_path.is_file():
                self._integrity_error = f"missing aggregate artifact: {path_str}"
                self._streams = {}
                return
            actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual != entry["sha256"]:
                self._integrity_error = f"aggregate artifact hash mismatch: {path_str}"
                self._streams = {}
                return
            id_field = STREAM_ID_FIELD[stream]
            rows: dict[str, Any] = {}
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                rows[str(row[id_field])] = row
            self._streams[stream] = rows

    def get_active_snapshot(self) -> dict[str, Any] | None:
        return self._manifest

    def get_object(self, object_id: str) -> dict[str, Any]:
        return self.query(QuerySpec(mode="EXACT_ID", object_id=object_id))

    def query(self, spec: QuerySpec) -> dict[str, Any]:
        if self._integrity_error is not None:
            return {
                "abstention": decide_abstention("RETRIEVAL_FAILURE", self._integrity_error),
                "objects": [],
            }
        if self._manifest is None:
            return {
                "abstention": decide_abstention(
                    "SNAPSHOT_INCOMPLETE", "no ACTIVE snapshot has ever been promoted"
                ),
                "objects": [],
            }

        if spec.mode == "EXACT_ID":
            assert spec.object_id is not None
            for stream, rows in self._streams.items():
                if spec.object_id in rows:
                    obj = canonical_record_object(rows[spec.object_id], stream=stream, manifest=self._manifest)
                    return {
                        "abstention": decide_abstention("ANSWERED", "exact identifier match"),
                        "objects": [obj],
                        "profile_id": "exact_identifier",
                    }
            return {
                "abstention": decide_abstention(
                    "INSUFFICIENT_EVIDENCE", f"no object found for id {spec.object_id!r}"
                ),
                "objects": [],
                "profile_id": "exact_identifier",
            }

        if spec.mode == "STRUCTURED":
            assert spec.stream is not None
            rows = self._streams.get(spec.stream, {})
            filters = spec.filters or {}
            matches = [row for row in rows.values() if all(row.get(k) == v for k, v in filters.items())]
            if not matches:
                return {
                    "abstention": decide_abstention(
                        "INSUFFICIENT_EVIDENCE", "no rows matched structured filters"
                    ),
                    "objects": [],
                    "profile_id": "structured",
                }
            objects = [canonical_record_object(row, stream=spec.stream, manifest=self._manifest) for row in matches]
            return {
                "abstention": decide_abstention(
                    "ANSWERED", f"{len(objects)} row(s) matched structured filters"
                ),
                "objects": objects,
                "profile_id": "structured",
            }

        raise ValueError(f"unsupported query mode: {spec.mode!r}")


__all__ = ["ActiveSnapshotReader"]

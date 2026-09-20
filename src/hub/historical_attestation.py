"""Historical temporal-attestation ingestion and lineage adjudication.

Input observations are preserved. Missing source bindings stay UNRESOLVED.
Supersession edges are validated independently of report-name similarity.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from .temporal_attestation import validate_temporal_attestation


class LineageError(ValueError):
    pass


def ingest_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("source_sha", None)
    out.setdefault("deployment_sha", None)
    out.setdefault("observed_at", None)
    out.setdefault("certification_scope", None)
    out.setdefault("deployment_state", "UNKNOWN")
    out.setdefault("supersedes", [])
    out.setdefault("superseded_by", [])
    out.setdefault("evidence_binding_state", "UNRESOLVED")
    validate_temporal_attestation(out)
    return out


def adjudicate_lineage(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = [ingest_observation(r) for r in rows]
    ids = [str(r["manifestation_id"]) for r in records]
    if len(ids) != len(set(ids)):
        raise LineageError("duplicate_manifestation_id")
    by_id = {str(r["manifestation_id"]): r for r in records}
    edges: set[tuple[str, str]] = set()
    orphans: set[tuple[str, str]] = set()
    reciprocal_mismatches: set[tuple[str, str]] = set()
    for child, row in by_id.items():
        for parent in row.get("supersedes", []):
            edge = (str(parent), child)
            if parent not in by_id:
                orphans.add(edge)
            else:
                edges.add(edge)
                if child not in by_id[str(parent)].get("superseded_by", []):
                    reciprocal_mismatches.add(edge)
        for newer in row.get("superseded_by", []):
            edge = (child, str(newer))
            if newer not in by_id:
                orphans.add(edge)
            elif child not in by_id[str(newer)].get("supersedes", []):
                reciprocal_mismatches.add(edge)

    children: dict[str, list[str]] = {k: [] for k in by_id}
    indegree = {k: 0 for k in by_id}
    for parent, child in edges:
        children[parent].append(child)
        indegree[child] += 1
    ready = sorted(k for k, v in indegree.items() if v == 0)
    while ready:
        node = ready.pop(0)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    cycles = sorted(k for k, v in indegree.items() if v)

    collisions = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            record.get("program_id"),
            record.get("source_sha"),
            record.get("environment"),
            record.get("valid_at"),
            record.get("certification_scope"),
        )
        grouped.setdefault(key, []).append(record)
    for key, group in grouped.items():
        states = {
            (r.get("execution_state"), r.get("test_state"), r.get("deployment_state"))
            for r in group
        }
        if len(group) > 1 and len(states) > 1:
            collisions.append(
                {
                    "key": key,
                    "manifestations": sorted(str(r["manifestation_id"]) for r in group),
                }
            )

    return {
        "record_count": len(records),
        "edge_count": len(edges),
        "orphan_edges": sorted(orphans),
        "reciprocal_mismatches": sorted(reciprocal_mismatches),
        "cycle_nodes": cycles,
        "state_collisions": collisions,
        "status": (
            "PASS"
            if not (orphans or reciprocal_mismatches or cycles or collisions)
            else "OPEN"
        ),
    }

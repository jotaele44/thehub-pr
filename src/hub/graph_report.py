"""Graph quality report for a Hub aggregate directory.

Reads the JSONL streams produced by `hub aggregate` + `hub correlate` and
returns quality metrics: orphan entities, duplicate external IDs,
low-confidence edge counts, producer-pair correlation counts, and
match-basis distribution.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def graph_report(aggregate_dir: str | Path) -> Dict[str, Any]:
    """Return a quality report dict for an existing aggregate directory."""
    agg = Path(aggregate_dir)

    entities = _read_jsonl(agg / "entities.jsonl")
    relationships = _read_jsonl(agg / "relationships.jsonl")
    correlations = _read_jsonl(agg / "correlations.jsonl")
    observations = _read_jsonl(agg / "observations.jsonl")

    # Orphan entities: entity IDs that appear in no relationship, correlation edge,
    # or observation anchor. Correlation rows written by `hub correlate` use the
    # canonical `source_entity_id`/`target_entity_id` fields; the legacy
    # `entity_a_id`/`entity_b_id` aliases are also honoured for back-compat.
    entity_ids = {e["entity_id"] for e in entities if "entity_id" in e}
    referenced: set = set()
    for r in relationships:
        referenced.add(r.get("source_entity_id"))
        referenced.add(r.get("target_entity_id"))
    for c in correlations:
        referenced.add(c.get("source_entity_id"))
        referenced.add(c.get("target_entity_id"))
        referenced.add(c.get("entity_a_id"))
        referenced.add(c.get("entity_b_id"))
    for o in observations:
        referenced.add(o.get("entity_id"))
    referenced.discard(None)
    orphan_count = len(entity_ids - referenced)

    # Duplicate external IDs: external_id value shared by >1 entity_id
    ext_id_to_entities: Dict[str, set] = defaultdict(set)
    for e in entities:
        eid = e.get("entity_id")
        for _key, val in (e.get("external_ids") or {}).items():
            if val:
                ext_id_to_entities[str(val)].add(eid)
    duplicate_external_ids = {
        ext_id: sorted(eids)
        for ext_id, eids in ext_id_to_entities.items()
        if len(eids) > 1
    }

    # Low-confidence edges: relationships with confidence < 0.5
    low_confidence_edges = sum(
        1 for r in relationships if (r.get("confidence") or 1.0) < 0.5
    )

    # Producer-pair correlation counts (from correlations.jsonl _producers field)
    pair_counts: Dict[str, int] = defaultdict(int)
    for c in correlations:
        producers = sorted(c.get("_producers") or [])
        if len(producers) >= 2:
            key = "+".join(producers)
            pair_counts[key] += 1

    # Match-basis distribution (from correlations.jsonl match_basis field)
    basis_dist: Dict[str, int] = defaultdict(int)
    for c in correlations:
        basis = c.get("match_basis") or "unknown"
        basis_dist[basis] += 1

    # Observation participation: how many observations carry an entity anchor that
    # exists in the aggregate (i.e. actually join the graph vs. float unanchored).
    anchored_observations = sum(
        1 for o in observations if o.get("entity_id") in entity_ids
    )

    return {
        "aggregate_dir": str(agg),
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "correlation_count": len(correlations),
        "observation_count": len(observations),
        "anchored_observations": anchored_observations,
        "orphan_entities": orphan_count,
        "duplicate_external_ids": duplicate_external_ids,
        "low_confidence_edges": low_confidence_edges,
        "producer_pair_counts": dict(sorted(pair_counts.items())),
        "match_basis_distribution": dict(sorted(basis_dist.items())),
    }

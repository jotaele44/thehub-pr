"""Hydro-Toponym Recurrence (HTR).

HTR is a discovery/context layer. Name matching, normalization, proximity and
clustering never establish canonical identity. Pair relations require explicit
binding evidence; third-party infrastructure context cannot promote a name match.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

SCHEMA_VERSION = "htr-1.0"
DISCOVERY_METHODS: Set[str] = {
    "EXACT_NORMALIZED_NAME", "ORTHOGRAPHIC_NEAR_MATCH", "FUZZY_MATCH",
    "PROXIMITY", "CLUSTER",
}
FORBIDDEN_RELATIONS: Set[str] = {"SAME_AS", "IDENTICAL_TO", "CANONICAL_IDENTITY"}
PAIR_RELATIONS: Set[str] = {
    "NAMED_AFTER", "HISTORICAL_ALIAS", "PERSON_EPONYM", "PROJECT_EPONYM",
    "HYDROLOGIC_RELATION", "ELECTRICAL_RELATION", "ADMINISTRATIVE_RELATION",
    "ADDRESS_OF", "HYDRAULICALLY_CONNECTED_TO", "ELECTRICALLY_CONNECTED_TO",
}
CONTEXT_STATES: Set[str] = {"CONTEXT_SUPPORTED", "ADJUDICATED"}
GENERIC_TOKENS: Set[str] = {
    "calle", "camino", "carretera", "avenida", "street", "road", "sector", "barrio",
    "lago", "lake", "embalse", "presa", "dam", "rio", "river", "quebrada", "canal",
    "planta", "plant", "central", "hidroelectrica", "hydro", "hydroelectric",
}


class HTRInvariantError(ValueError):
    pass


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:24]}"


def normalize_name(raw: str) -> Dict[str, str]:
    if not isinstance(raw, str) or not raw.strip():
        raise HTRInvariantError("name must be a non-empty string")
    folded = unicodedata.normalize("NFKD", raw.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())
    core = " ".join(t for t in normalized.split() if t not in GENERIC_TOKENS) or normalized
    return {"raw": raw, "normalized": normalized, "core": core}


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    seq = SequenceMatcher(None, a, b, autojunk=False).ratio()
    edit = 1.0 - levenshtein(a, b) / max(len(a), len(b), 1)
    return round(max(0.0, seq, edit), 6)


def _require_unique(rows: Sequence[Mapping[str, Any]], id_field: str, kind: str) -> None:
    seen: Set[str] = set()
    for row in rows:
        rid = row.get(id_field)
        if not isinstance(rid, str) or not rid:
            raise HTRInvariantError(f"{kind} missing {id_field}")
        if rid in seen:
            raise HTRInvariantError(f"duplicate {id_field}: {rid}")
        seen.add(rid)


def _is_authoritative_context(evidence: Mapping[str, Any]) -> bool:
    source_id = evidence.get("source_id")
    return (
        evidence.get("contextual") is True
        and evidence.get("authoritative") is True
        and isinstance(source_id, str)
        and bool(source_id)
        and evidence.get("relation_type") in PAIR_RELATIONS
    )


def discover_candidates(
    hydro_registry: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    *,
    fuzzy_threshold: float = 0.86,
) -> List[Dict[str, Any]]:
    if not 0 <= fuzzy_threshold <= 1:
        raise HTRInvariantError("fuzzy_threshold must be between 0 and 1")
    _require_unique(hydro_registry, "hydro_entity_id", "registry row")
    _require_unique(observations, "observation_id", "observation")

    registry = []
    for row in hydro_registry:
        if not isinstance(row.get("raw_name"), str):
            raise HTRInvariantError("registry row missing raw_name")
        registry.append((row, normalize_name(str(row["raw_name"]))))

    out: List[Dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs.get("raw_name"), str) or not isinstance(obs.get("feature_type"), str):
            raise HTRInvariantError("observation missing raw_name or feature_type")
        oname = normalize_name(str(obs["raw_name"]))
        for hydro, hname in registry:
            sim = _similarity(oname["core"], hname["core"])
            if oname["core"] == hname["core"]:
                method, relation = "EXACT_NORMALIZED_NAME", "EXACT_NAME"
            elif sim >= fuzzy_threshold:
                near = levenshtein(oname["core"], hname["core"]) <= 2
                method = "ORTHOGRAPHIC_NEAR_MATCH" if near else "FUZZY_MATCH"
                relation = "ORTHOGRAPHIC_VARIANT" if near else "UNRESOLVED"
            else:
                continue
            oid, hid = str(obs["observation_id"]), str(hydro["hydro_entity_id"])
            out.append({
                "schema_version": SCHEMA_VERSION,
                "candidate_id": _stable_id("htr", oid, hid, method, oname["raw"], hname["raw"]),
                "source_observation_id": oid,
                "source_feature_type": str(obs["feature_type"]),
                "source_name": oname,
                "hydro_entity_id": hid,
                "hydro_name": hname,
                "discovery_method": method,
                "relation_type": relation,
                "similarity": sim,
                "state": "CANDIDATE_NOT_IDENTITY",
                "identity_state": "UNRESOLVED",
                "pair_binding_state": "UNBOUND",
                "evidence": [], "contradictions": [], "rejected_reasons": [],
                "context": {
                    "observation": {k: obs[k] for k in sorted(obs) if k != "raw_name"},
                    "hydro": {k: hydro[k] for k in sorted(hydro) if k != "raw_name"},
                },
            })
    return sorted(out, key=lambda r: (r["source_observation_id"], r["hydro_entity_id"], r["candidate_id"]))


def adjudicate_candidate(
    candidate: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    *,
    contradictions: Sequence[Mapping[str, Any]] = (),
    rejection_reasons: Sequence[str] = (),
) -> Dict[str, Any]:
    row = json.loads(json.dumps(candidate))
    if row.get("identity_state") not in {"UNRESOLVED", "DISTINCT_ENTITIES"}:
        raise HTRInvariantError("HTR cannot carry an identity promotion")
    row["evidence"] = [dict(e) for e in evidence]
    row["contradictions"] = [dict(c) for c in contradictions]
    row["rejected_reasons"] = list(rejection_reasons)

    for ev in evidence:
        if ev.get("relation_type") in FORBIDDEN_RELATIONS:
            raise HTRInvariantError(f"forbidden identity relation: {ev.get('relation_type')}")

    if rejection_reasons:
        row.update(state="REJECTED", identity_state="DISTINCT_ENTITIES", pair_binding_state="UNBOUND")
        return row
    if contradictions:
        row.update(state="UNRESOLVED", identity_state="DISTINCT_ENTITIES", pair_binding_state="UNBOUND")
        return row

    pair_relations: List[str] = []
    contextual = False
    for ev in evidence:
        relation = ev.get("relation_type")
        source_id = ev.get("source_id")
        stable_source = isinstance(source_id, str) and bool(source_id)
        if _is_authoritative_context(ev):
            contextual = True
        if not ev.get("binds_candidate_pair"):
            continue
        if relation not in PAIR_RELATIONS:
            continue
        if relation in {"NAMED_AFTER", "HISTORICAL_ALIAS", "ADDRESS_OF", "HYDRAULICALLY_CONNECTED_TO", "ELECTRICALLY_CONNECTED_TO"}:
            if not (ev.get("authoritative") and stable_source):
                continue
        elif not stable_source:
            continue
        pair_relations.append(str(relation))

    if pair_relations:
        priority = [
            "NAMED_AFTER", "HISTORICAL_ALIAS", "ADDRESS_OF", "PROJECT_EPONYM", "PERSON_EPONYM",
            "HYDRAULICALLY_CONNECTED_TO", "ELECTRICALLY_CONNECTED_TO", "HYDROLOGIC_RELATION",
            "ELECTRICAL_RELATION", "ADMINISTRATIVE_RELATION",
        ]
        relation = min(pair_relations, key=lambda x: priority.index(x))
        row.update(
            state="ADJUDICATED", identity_state="DISTINCT_ENTITIES",
            pair_binding_state="BOUND_RELATION_NOT_IDENTITY", relation_type=relation,
        )
    elif contextual:
        row.update(state="CONTEXT_SUPPORTED", identity_state="DISTINCT_ENTITIES", pair_binding_state="UNBOUND")
    else:
        row.update(state="CANDIDATE_NOT_IDENTITY", identity_state="UNRESOLVED", pair_binding_state="UNBOUND")
    return row


def downstream_context(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in candidates:
        if row.get("state") not in CONTEXT_STATES:
            continue
        if row.get("identity_state") != "DISTINCT_ENTITIES":
            raise HTRInvariantError("context rows must keep entities distinct")
        copy = json.loads(json.dumps(row))
        copy["downstream_semantics"] = "CONTEXT_ONLY_NOT_IDENTITY"
        out.append(copy)
    return sorted(out, key=lambda r: r["candidate_id"])


def make_graph(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    for row in candidates:
        sid, hid = str(row["source_observation_id"]), str(row["hydro_entity_id"])
        nodes[sid] = {"node_id": sid, "node_type": str(row["source_feature_type"]).upper(), **row["source_name"]}
        nodes[hid] = {"node_id": hid, "node_type": "HYDRO_FEATURE", **row["hydro_name"]}
        if row.get("state") != "REJECTED":
            pair_bound = row.get("pair_binding_state") == "BOUND_RELATION_NOT_IDENTITY"
            relation = str(row["relation_type"]) if pair_bound else "POSSIBLE_EPONYM_OF"
            edges.append({
                "edge_id": _stable_id("htre", sid, hid, relation, str(row["candidate_id"])),
                "source_node_id": sid, "target_node_id": hid, "relationship_type": relation,
                "candidate_id": row["candidate_id"], "evidence_state": row["state"],
                "pair_binding_state": row.get("pair_binding_state", "UNBOUND"), "identity_claim": False,
            })
        for ev in row.get("evidence") or []:
            rid, relation = ev.get("related_entity_id"), ev.get("relation_type")
            if not (_is_authoritative_context(ev) and isinstance(rid, str) and rid):
                continue
            raw = str(ev.get("related_entity_raw_name") or rid)
            nodes.setdefault(rid, {"node_id": rid, "node_type": str(ev.get("related_entity_type") or "INFRASTRUCTURE").upper(), **normalize_name(raw)})
            edges.append({
                "edge_id": _stable_id("htre", sid, rid, str(relation), str(ev.get("source_id") or "")),
                "source_node_id": sid, "target_node_id": rid, "relationship_type": relation,
                "candidate_id": row["candidate_id"], "evidence_state": "CONTEXT_EVIDENCE",
                "pair_binding_state": "THIRD_PARTY_CONTEXT", "identity_claim": False,
                "source_id": ev.get("source_id"),
            })
    node_list = sorted(nodes.values(), key=lambda n: n["node_id"])
    edge_list = sorted(edges, key=lambda e: (e["source_node_id"], e["target_node_id"], e["relationship_type"], e["edge_id"]))
    return {"schema_version": SCHEMA_VERSION, "nodes": node_list, "edges": edge_list,
            "invariants": {"identity_edges": 0, "node_count": len(node_list), "edge_count": len(edge_list)}}


def cluster_candidates(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for row in candidates:
        obs = (row.get("context") or {}).get("observation") or {}
        cid = obs.get("cluster_id")
        if isinstance(cid, str) and cid:
            groups.setdefault(cid, []).append(row)
    return [{
        "cluster_id": cid, "candidate_count": len(rows),
        "unique_hydro_name_families": len({r["hydro_entity_id"] for r in rows}),
        "source_observation_count": len({r["source_observation_id"] for r in rows}),
        "candidate_ids": sorted(r["candidate_id"] for r in rows),
        "state": "DISCOVERY_CLUSTER_NOT_IDENTITY",
    } for cid, rows in sorted(groups.items())]


def write_bundle(
    out_dir: str, candidates: Sequence[Mapping[str, Any]], *,
    source_manifest: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = sorted((json.loads(json.dumps(r)) for r in candidates), key=lambda r: r["candidate_id"])
    graph, downstream, clusters = make_graph(rows), downstream_context(rows), cluster_candidates(rows)

    def j(path: str, value: Any) -> None:
        (root / path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def jl(path: str, values: Iterable[Mapping[str, Any]]) -> None:
        (root / path).write_text("".join(json.dumps(v, sort_keys=True) + "\n" for v in values), encoding="utf-8")

    jl("candidates.jsonl", rows)
    j("graph.json", graph)
    jl("downstream_context.jsonl", downstream)
    j("clusters.json", clusters)
    manifest = {
        "schema_version": SCHEMA_VERSION, "candidate_count": len(rows),
        "context_supported_count": len(downstream), "rejected_count": sum(r.get("state") == "REJECTED" for r in rows),
        "unresolved_count": sum(r.get("state") in {"UNRESOLVED", "CANDIDATE_NOT_IDENTITY"} for r in rows),
        "identity_edge_count": 0, "source_manifest": dict(source_manifest or {}),
    }
    j("manifest.json", manifest)
    return manifest

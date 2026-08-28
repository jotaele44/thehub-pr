"""Hydro-Toponym Recurrence (HTR) discovery and adjudication.

HTR detects recurrence of known hydro/infrastructure names in roads, sectors,
barrios, facilities and other toponyms.  Name similarity, fuzzy matching,
proximity and clustering are *discovery* signals only.  They never establish
canonical identity.

The module is deliberately dependency-free so producer repositories can consume
its JSON contract without importing GIS or ML stacks.  Geometry and historical
adjudication remain source-specific and are represented as explicit evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

SCHEMA_VERSION = "htr-1.0"

DISCOVERY_METHODS: Set[str] = {
    "EXACT_NORMALIZED_NAME",
    "ORTHOGRAPHIC_NEAR_MATCH",
    "TOKEN_MATCH",
    "FUZZY_MATCH",
    "PHONETIC_MATCH",
    "PROXIMITY",
    "CLUSTER",
}

RELATION_TYPES: Set[str] = {
    "EXACT_NAME",
    "ORTHOGRAPHIC_VARIANT",
    "HISTORICAL_ALIAS",
    "PERSON_EPONYM",
    "PROJECT_EPONYM",
    "HYDROLOGIC_RELATION",
    "ELECTRICAL_RELATION",
    "ADMINISTRATIVE_RELATION",
    "COINCIDENTAL_NAME",
    "UNRESOLVED",
    "NAMED_AFTER",
    "POSSIBLE_EPONYM_OF",
    "ORTHOGRAPHIC_VARIANT_OF",
    "ADDRESS_OF",
    "WITHIN",
    "NEAR",
    "HYDRAULICALLY_CONNECTED_TO",
    "ELECTRICALLY_CONNECTED_TO",
    "OBSERVED_AS_LABEL_IN_SOURCE",
}

# Explicitly forbidden because HTR is not an identity engine.
FORBIDDEN_RELATION_TYPES: Set[str] = {"SAME_AS", "IDENTICAL_TO", "CANONICAL_IDENTITY"}

CONTEXTUAL_STATES: Set[str] = {"CONTEXT_SUPPORTED", "ADJUDICATED"}
FINAL_STATES: Set[str] = {
    "CANDIDATE_NOT_IDENTITY",
    "CONTEXT_SUPPORTED",
    "ADJUDICATED",
    "REJECTED",
    "UNRESOLVED",
}

GENERIC_FEATURE_TOKENS: Set[str] = {
    "calle", "camino", "carretera", "avenida", "ave", "street", "road", "rd",
    "sector", "barrio", "urbanizacion", "urb", "lago", "lake", "embalse", "presa",
    "dam", "rio", "river", "quebrada", "canal", "puente", "bridge", "parque", "park",
    "planta", "plant", "central", "hidroelectrica", "hydro", "hydroelectric",
}


class HTRInvariantError(ValueError):
    """Raised when a caller attempts a semantically unsafe HTR state."""


@dataclass(frozen=True)
class NameForm:
    raw: str
    normalized: str
    core: str


@dataclass
class Candidate:
    candidate_id: str
    source_observation_id: str
    source_feature_type: str
    source_name: NameForm
    hydro_entity_id: str
    hydro_name: NameForm
    discovery_method: str
    relation_type: str
    similarity: float
    state: str = "CANDIDATE_NOT_IDENTITY"
    identity_state: str = "UNRESOLVED"
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    rejected_reasons: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "source_observation_id": self.source_observation_id,
            "source_feature_type": self.source_feature_type,
            "source_name": {
                "raw": self.source_name.raw,
                "normalized": self.source_name.normalized,
                "core": self.source_name.core,
            },
            "hydro_entity_id": self.hydro_entity_id,
            "hydro_name": {
                "raw": self.hydro_name.raw,
                "normalized": self.hydro_name.normalized,
                "core": self.hydro_name.core,
            },
            "discovery_method": self.discovery_method,
            "relation_type": self.relation_type,
            "similarity": self.similarity,
            "state": self.state,
            "identity_state": self.identity_state,
            "evidence": list(self.evidence),
            "contradictions": list(self.contradictions),
            "rejected_reasons": list(self.rejected_reasons),
            "context": dict(self.context),
        }


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_name(raw: str) -> NameForm:
    """Return RAW/NORMALIZED/CORE without erasing the raw spelling.

    ``normalized`` is only a discovery representation.  ``core`` removes generic
    feature-class tokens to compare the distinctive name component.  Neither is
    suitable as identity proof.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise HTRInvariantError("name must be a non-empty string")
    text = _strip_accents(raw).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    normalized = " ".join(text.split())
    core_tokens = [tok for tok in normalized.split() if tok not in GENERIC_FEATURE_TOKENS]
    core = " ".join(core_tokens) or normalized
    return NameForm(raw=raw, normalized=normalized, core=core)


def levenshtein(a: str, b: str) -> int:
    """Deterministic edit distance, optimized to O(min(len(a), len(b))) memory."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]


def name_similarity(a: NameForm, b: NameForm) -> float:
    """Return a bounded discovery score based on the distinctive name core."""
    if a.core == b.core:
        return 1.0
    seq = SequenceMatcher(None, a.core, b.core, autojunk=False).ratio()
    max_len = max(len(a.core), len(b.core), 1)
    edit = 1.0 - (levenshtein(a.core, b.core) / max_len)
    return round(max(0.0, min(1.0, max(seq, edit))), 6)


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _validate_registry_row(row: Mapping[str, Any]) -> None:
    required = ("hydro_entity_id", "raw_name")
    missing = [key for key in required if not isinstance(row.get(key), str) or not row.get(key)]
    if missing:
        raise HTRInvariantError(f"hydro registry row missing required field(s): {', '.join(missing)}")


def _validate_observation(row: Mapping[str, Any]) -> None:
    required = ("observation_id", "raw_name", "feature_type")
    missing = [key for key in required if not isinstance(row.get(key), str) or not row.get(key)]
    if missing:
        raise HTRInvariantError(f"toponym observation missing required field(s): {', '.join(missing)}")


def discover_candidates(
    hydro_registry: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    *,
    fuzzy_threshold: float = 0.86,
) -> List[Dict[str, Any]]:
    """Generate the complete bounded candidate set for supplied inputs.

    Exact and fuzzy matching are discovery operations only.  Every emitted row is
    ``CANDIDATE_NOT_IDENTITY`` with ``identity_state=UNRESOLVED``.
    """
    if not 0.0 <= fuzzy_threshold <= 1.0:
        raise HTRInvariantError("fuzzy_threshold must be between 0 and 1")

    registry: List[Tuple[Mapping[str, Any], NameForm]] = []
    seen_hydro: Set[str] = set()
    for row in hydro_registry:
        _validate_registry_row(row)
        hid = str(row["hydro_entity_id"])
        if hid in seen_hydro:
            raise HTRInvariantError(f"duplicate hydro_entity_id: {hid}")
        seen_hydro.add(hid)
        registry.append((row, normalize_name(str(row["raw_name"]))))

    obs_seen: Set[str] = set()
    candidates: List[Candidate] = []
    for obs in observations:
        _validate_observation(obs)
        oid = str(obs["observation_id"])
        if oid in obs_seen:
            raise HTRInvariantError(f"duplicate observation_id: {oid}")
        obs_seen.add(oid)
        obs_name = normalize_name(str(obs["raw_name"]))

        for hydro, hydro_name in registry:
            similarity = name_similarity(obs_name, hydro_name)
            if obs_name.core == hydro_name.core:
                method = "EXACT_NORMALIZED_NAME"
                relation = "EXACT_NAME"
            elif similarity >= fuzzy_threshold:
                method = "ORTHOGRAPHIC_NEAR_MATCH" if levenshtein(obs_name.core, hydro_name.core) <= 2 else "FUZZY_MATCH"
                relation = "ORTHOGRAPHIC_VARIANT" if method == "ORTHOGRAPHIC_NEAR_MATCH" else "UNRESOLVED"
            else:
                continue

            hid = str(hydro["hydro_entity_id"])
            cid = _stable_id("htr", oid, hid, method, obs_name.raw, hydro_name.raw)
            context = {
                "observation": {k: obs[k] for k in sorted(obs) if k not in {"raw_name"}},
                "hydro": {k: hydro[k] for k in sorted(hydro) if k not in {"raw_name"}},
            }
            candidates.append(Candidate(
                candidate_id=cid,
                source_observation_id=oid,
                source_feature_type=str(obs["feature_type"]),
                source_name=obs_name,
                hydro_entity_id=hid,
                hydro_name=hydro_name,
                discovery_method=method,
                relation_type=relation,
                similarity=similarity,
                context=context,
            ))

    # Stable whole-row ordering: deterministic and preserves multiplicity.
    return [c.as_dict() for c in sorted(
        candidates,
        key=lambda c: (c.source_observation_id, c.hydro_entity_id, c.discovery_method, c.candidate_id),
    )]


def _is_authoritative(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence.get("authoritative")) and isinstance(evidence.get("source_id"), str) and bool(evidence.get("source_id"))


def adjudicate_candidate(
    candidate: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    *,
    contradictions: Sequence[Mapping[str, Any]] = (),
    rejection_reasons: Sequence[str] = (),
) -> Dict[str, Any]:
    """Adjudicate one candidate without ever promoting source/hydro identity.

    Supported evidence types are explicit relations.  ``NAMED_AFTER`` and
    connectivity relations require authoritative evidence.  Fuzzy/name/proximity
    observations remain discovery evidence and cannot promote a row by themselves.
    """
    out = json.loads(json.dumps(candidate))  # deterministic deep copy of JSON-like row
    if out.get("state") not in FINAL_STATES:
        raise HTRInvariantError(f"invalid candidate state: {out.get('state')}")
    if out.get("identity_state") not in {"UNRESOLVED", "DISTINCT_ENTITIES"}:
        raise HTRInvariantError("HTR cannot carry an identity promotion")

    evidence_rows = [dict(e) for e in evidence]
    contradiction_rows = [dict(c) for c in contradictions]
    out["evidence"] = evidence_rows
    out["contradictions"] = contradiction_rows
    out["rejected_reasons"] = list(rejection_reasons)

    if rejection_reasons:
        out["state"] = "REJECTED"
        out["identity_state"] = "DISTINCT_ENTITIES"
        if not out.get("relation_type") or out.get("relation_type") == "UNRESOLVED":
            out["relation_type"] = "COINCIDENTAL_NAME"
        return out

    promotable_relations: List[str] = []
    for ev in evidence_rows:
        etype = ev.get("evidence_type")
        relation = ev.get("relation_type")
        if isinstance(relation, str) and relation in FORBIDDEN_RELATION_TYPES:
            raise HTRInvariantError(f"forbidden identity relation: {relation}")
        if relation is not None and relation not in RELATION_TYPES:
            raise HTRInvariantError(f"unknown relation_type: {relation}")

        # Discovery signals alone cannot support context promotion.
        if etype in DISCOVERY_METHODS or relation in {"EXACT_NAME", "ORTHOGRAPHIC_VARIANT", "NEAR", "POSSIBLE_EPONYM_OF"}:
            continue

        if relation in {"NAMED_AFTER", "ADDRESS_OF", "HYDRAULICALLY_CONNECTED_TO", "ELECTRICALLY_CONNECTED_TO", "HISTORICAL_ALIAS"}:
            if not _is_authoritative(ev):
                continue
            promotable_relations.append(str(relation))
        elif relation in {"PROJECT_EPONYM", "PERSON_EPONYM", "ADMINISTRATIVE_RELATION", "HYDROLOGIC_RELATION", "ELECTRICAL_RELATION", "OBSERVED_AS_LABEL_IN_SOURCE", "WITHIN"}:
            # These contextual relations may be supported by independently sourced
            # evidence; require a stable source id even if source isn't authoritative.
            if isinstance(ev.get("source_id"), str) and ev.get("source_id"):
                promotable_relations.append(str(relation))

    if contradiction_rows:
        out["state"] = "UNRESOLVED"
        out["identity_state"] = "DISTINCT_ENTITIES"
        return out

    if promotable_relations:
        out["state"] = "CONTEXT_SUPPORTED"
        out["identity_state"] = "DISTINCT_ENTITIES"
        # Pick highest-evidence relation deterministically, not first input row.
        priority = [
            "NAMED_AFTER", "ADDRESS_OF", "HISTORICAL_ALIAS",
            "HYDRAULICALLY_CONNECTED_TO", "ELECTRICALLY_CONNECTED_TO",
            "PROJECT_EPONYM", "PERSON_EPONYM", "ADMINISTRATIVE_RELATION",
            "HYDROLOGIC_RELATION", "ELECTRICAL_RELATION",
            "OBSERVED_AS_LABEL_IN_SOURCE", "WITHIN",
        ]
        out["relation_type"] = min(promotable_relations, key=lambda r: priority.index(r))
    else:
        out["state"] = "CANDIDATE_NOT_IDENTITY"
        out["identity_state"] = "UNRESOLVED"
    return out


def make_graph(
    candidates: Sequence[Mapping[str, Any]],
    *,
    include_discovery_edges: bool = True,
) -> Dict[str, Any]:
    """Build a deterministic infrastructure-toponym graph from HTR candidates.

    Nodes remain distinct.  No SAME_AS/identity edge exists in the HTR graph.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    for row in candidates:
        state = row.get("state")
        if state not in FINAL_STATES:
            raise HTRInvariantError(f"invalid candidate state: {state}")
        source_id = str(row["source_observation_id"])
        hydro_id = str(row["hydro_entity_id"])
        src = row["source_name"]
        hyd = row["hydro_name"]
        nodes[source_id] = {
            "node_id": source_id,
            "node_type": str(row.get("source_feature_type", "TOPONYM")).upper(),
            "raw_name": src["raw"],
            "normalized_name": src["normalized"],
        }
        nodes[hydro_id] = {
            "node_id": hydro_id,
            "node_type": "HYDRO_FEATURE",
            "raw_name": hyd["raw"],
            "normalized_name": hyd["normalized"],
        }

        relation = str(row.get("relation_type", "UNRESOLVED"))
        if relation in FORBIDDEN_RELATION_TYPES:
            raise HTRInvariantError(f"forbidden identity relation: {relation}")
        if relation not in RELATION_TYPES:
            raise HTRInvariantError(f"unknown relation_type: {relation}")
        if state == "REJECTED":
            continue
        if state not in CONTEXTUAL_STATES and not include_discovery_edges:
            continue
        edge_type = relation if state in CONTEXTUAL_STATES else "POSSIBLE_EPONYM_OF"
        edges.append({
            "edge_id": _stable_id("htre", source_id, hydro_id, edge_type, str(row["candidate_id"])),
            "source_node_id": source_id,
            "target_node_id": hydro_id,
            "relationship_type": edge_type,
            "candidate_id": row["candidate_id"],
            "evidence_state": state,
            "identity_claim": False,
        })

    node_list = sorted(nodes.values(), key=lambda n: n["node_id"])
    edge_list = sorted(edges, key=lambda e: (e["source_node_id"], e["target_node_id"], e["relationship_type"], e["edge_id"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": node_list,
        "edges": edge_list,
        "invariants": {
            "identity_edges": 0,
            "node_count": len(node_list),
            "edge_count": len(edge_list),
        },
    }


def downstream_context(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return only adjudicated/context-supported rows safe for downstream context.

    The export strips no provenance but explicitly states that it is contextual,
    not canonical identity.
    """
    out: List[Dict[str, Any]] = []
    for row in candidates:
        if row.get("state") not in CONTEXTUAL_STATES:
            continue
        if row.get("identity_state") != "DISTINCT_ENTITIES":
            raise HTRInvariantError("context-supported HTR row must preserve distinct entities")
        copied = json.loads(json.dumps(row))
        copied["downstream_semantics"] = "CONTEXT_ONLY_NOT_IDENTITY"
        out.append(copied)
    return sorted(out, key=lambda r: str(r["candidate_id"]))


def cluster_candidates(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Group recurrence by supplied context cluster key without spatial invention.

    Callers may supply ``context.observation.cluster_id`` based on authoritative or
    separately certified spatial analysis.  HTR does not invent buffers or nearest
    neighbours.  Candidate multiplicity is preserved in the returned member ids.
    """
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for row in candidates:
        context = row.get("context")
        obs = context.get("observation") if isinstance(context, dict) else None
        cluster_id = obs.get("cluster_id") if isinstance(obs, dict) else None
        if isinstance(cluster_id, str) and cluster_id:
            groups.setdefault(cluster_id, []).append(row)

    result: List[Dict[str, Any]] = []
    for cluster_id, rows in sorted(groups.items()):
        hydro_ids = sorted({str(r["hydro_entity_id"]) for r in rows})
        source_ids = sorted({str(r["source_observation_id"]) for r in rows})
        result.append({
            "cluster_id": cluster_id,
            "candidate_count": len(rows),
            "unique_hydro_name_families": len(hydro_ids),
            "source_observation_count": len(source_ids),
            "candidate_ids": sorted(str(r["candidate_id"]) for r in rows),
            "state": "DISCOVERY_CLUSTER_NOT_IDENTITY",
        })
    return result


def write_bundle(
    out_dir: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    source_manifest: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Write restartable, deterministic HTR JSON/JSONL artifacts."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = sorted((json.loads(json.dumps(r)) for r in candidates), key=lambda r: str(r["candidate_id"]))
    graph = make_graph(rows)
    downstream = downstream_context(rows)
    clusters = cluster_candidates(rows)

    def dump_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def dump_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
        path.write_text("".join(json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n" for v in values), encoding="utf-8")

    dump_jsonl(root / "candidates.jsonl", rows)
    dump_json(root / "graph.json", graph)
    dump_jsonl(root / "downstream_context.jsonl", downstream)
    dump_json(root / "clusters.json", clusters)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "candidate_count": len(rows),
        "context_supported_count": len(downstream),
        "rejected_count": sum(1 for r in rows if r.get("state") == "REJECTED"),
        "unresolved_count": sum(1 for r in rows if r.get("state") in {"UNRESOLVED", "CANDIDATE_NOT_IDENTITY"}),
        "identity_edge_count": graph["invariants"]["identity_edges"],
        "source_manifest": dict(source_manifest or {}),
    }
    dump_json(root / "manifest.json", manifest)
    return manifest

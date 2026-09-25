"""FEDERATION_EVIDENCE_LINEAGE_V1 — provenance-bearing lineage for one record.

Lineage is built only from what the producer row actually carries: its source
references and its ``lineage`` block (producer script, extraction method,
input artifacts). Nothing is inferred from proximity or timing, and a missing
source terminates the chain at an explicit SOURCE_MISSING node instead of an
invented edge.

Node kinds follow directive §4 (SOURCE → … → REPORT). ``PRODUCER_INPUT`` marks
an input artifact whose pipeline stage the producer did not declare; it is
deliberately not guessed into RAW/NORMALIZED.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .epistemic import EDGE_STATES, FORBIDDEN_SOLE_EDGE_BASES, as_mapping, edge_state_for

NODE_KINDS = (
    "SOURCE", "SOURCE_MANIFESTATION", "RAW_RECORD", "NORMALIZED_RECORD", "CANONICAL_ENTITY",
    "CANONICAL_EVENT", "FINDING", "COMPUTATION", "INTERPRETATION", "REPORT", "PRODUCER_INPUT",
    "SOURCE_MISSING",
)

# Stream → the node kind a row of that stream represents.
STREAM_NODE_KIND: Mapping[str, str] = {
    "sources": "SOURCE",
    "entities": "CANONICAL_ENTITY",
    "observations": "CANONICAL_EVENT",
    "alerts": "CANONICAL_EVENT",
    "relationships": "CANONICAL_ENTITY",
    "funding_awards": "CANONICAL_ENTITY",
    "transactions": "CANONICAL_EVENT",
    "correlations": "COMPUTATION",
}

EDGE_REQUIRED = ("edge_id", "relationship_type", "from", "to", "producer", "edge_state", "derivation_method")


def _edge(edge_id: str, rtype: str, src: str, dst: str, *, producer: str, state: str, method: str,
          evidence_ids: List[str], created_at: Optional[str], basis: str) -> Dict[str, Any]:
    return {
        "edge_id": edge_id,
        "relationship_type": rtype,
        "from": src,
        "to": dst,
        "producer": producer,
        "source": evidence_ids[0] if evidence_ids else None,
        "evidence_ids": evidence_ids,
        "created_at": created_at,
        "valid_from": None,
        "valid_to": None,
        "edge_state": state,
        "derivation_method": method,
        "basis": basis,
        "contradiction_state": None,
    }


def build_lineage(stream: str, row: Mapping[str, Any], record_node: str, *, producer: str,
                  source_state: str) -> Dict[str, Any]:
    """Nodes and edges explaining where ``row`` came from."""
    lineage = as_mapping(row.get("lineage"))
    kind = STREAM_NODE_KIND.get(stream, "CANONICAL_ENTITY")
    nodes: List[Dict[str, Any]] = [{"node_id": record_node, "kind": kind, "label": stream}]
    edges: List[Dict[str, Any]] = []
    created = row.get("extracted_at") or row.get("created_at")

    if stream != "sources":
        source_ref = row.get("source_id") or row.get("evidence_source_id")
        if source_ref:
            node_id = f"source:{source_ref}"
            nodes.append({"node_id": node_id, "kind": "SOURCE", "label": str(source_ref)})
            state = "DOCUMENTED" if source_state == "SOURCE_BOUND" else "UNKNOWN"
            edges.append(_edge(f"{node_id}->{record_node}", "DOCUMENTS", node_id, record_node,
                               producer=producer, state=state, method="producer_asserted_source_reference",
                               evidence_ids=[str(source_ref)], created_at=created,
                               basis=f"source_state {source_state}"))
        else:
            nodes.append({"node_id": f"missing-source:{record_node}", "kind": "SOURCE_MISSING",
                          "label": "no source reference"})

    method = str(lineage.get("extraction_method") or "undeclared")
    script = lineage.get("producer_script")
    for artifact in lineage.get("source_inputs") or []:
        node_id = f"input:{producer}:{artifact}"
        nodes.append({"node_id": node_id, "kind": "PRODUCER_INPUT", "label": str(artifact)})
        edges.append(_edge(f"{node_id}->{record_node}", "DERIVED_FROM", node_id, record_node,
                           producer=producer, state="COMPUTED", method=method,
                           evidence_ids=[], created_at=created,
                           basis=f"producer script {script}" if script else "producer lineage block"))

    if stream in ("relationships", "correlations"):
        a, b = row.get("source_entity_id"), row.get("target_entity_id")
        if a and b:
            state, basis = edge_state_for(row, hub_computed=(stream == "correlations"), source_state=source_state)
            ids = [str(x) for x in (row.get("evidence_source_id") or row.get("source_id"),) if x]
            edges.append(_edge(str(row.get("relationship_id") or f"{a}->{b}"),
                               str(row.get("relationship_type") or "related_to"),
                               f"entity:{a}", f"entity:{b}", producer=producer, state=state,
                               method=str(row.get("match_basis") or method), evidence_ids=ids,
                               created_at=created, basis=basis))
            nodes.append({"node_id": f"entity:{a}", "kind": "CANONICAL_ENTITY", "label": str(a)})
            nodes.append({"node_id": f"entity:{b}", "kind": "CANONICAL_ENTITY", "label": str(b)})
    unique = {node["node_id"]: node for node in nodes}
    return {"nodes": list(unique.values()), "edges": edges}


def validate_edge(edge: Mapping[str, Any]) -> List[str]:
    """Rule violations for one lineage/relationship edge (empty = valid)."""
    errors = [f"edge missing {key}" for key in EDGE_REQUIRED if edge.get(key) in (None, "")]
    state = edge.get("edge_state")
    if state not in EDGE_STATES:
        errors.append(f"edge_state {state!r} is not valid")
    method = str(edge.get("derivation_method") or "")
    if state in ("DOCUMENTED", "COMPUTED") and method in FORBIDDEN_SOLE_EDGE_BASES:
        errors.append(f"{state} edge cannot rest solely on {method!r} (proximity/timing/name is not a relationship)")
    if state == "DOCUMENTED" and not edge.get("evidence_ids"):
        errors.append("DOCUMENTED edge requires evidence_ids")
    return errors


def validate_lineage(lineage: Mapping[str, Any]) -> List[str]:
    """Every edge valid and every edge endpoint present as a node."""
    node_ids = {n.get("node_id") for n in lineage.get("nodes") or []}
    errors: List[str] = []
    for node in lineage.get("nodes") or []:
        if node.get("kind") not in NODE_KINDS:
            errors.append(f"node {node.get('node_id')}: kind {node.get('kind')!r} is not valid")
    for edge in lineage.get("edges") or []:
        errors.extend(f"{edge.get('edge_id')}: {e}" for e in validate_edge(edge))
        for end in ("from", "to"):
            if edge.get(end) not in node_ids:
                errors.append(f"{edge.get('edge_id')}: {end} endpoint {edge.get(end)!r} is not a node")
    return errors

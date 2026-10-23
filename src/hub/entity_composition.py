"""FEDERATION_ENTITY_COMPOSITION_V1 — compose one canonical entity from the Hub store.

Pure and read-only. The caller supplies the anchor entity row plus the rows the
store already links to it (relationship/correlation edges that name it, and
observations/alerts that carry its ``entity_id``); this module only arranges
them. Producers stay canonical: every item is a reference back to a producer row
with its own Evidence Object deep link.

Identity is reported as recorded and never inferred. The Hub's identity registry
is not wired to the store, so ``registry_status`` is ``NOT_CONFIGURED`` unless a
caller passes a registry membership view; no matching runs here, and proximity,
timing or name similarity never join two entities (audit F13).
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import jsonschema
from referencing import Registry, Resource

from . import epistemic as ep
from ._schemas import schema_dir
from .evidence_object import SCHEMA_FILES, evidence_id, project_evidence_object, record_title
from .federated_search import IN_SCOPE_PRODUCERS

CONTRACT_ID = "federation-entity-composition-v1"
ANCHOR_COLLECTION = "Entities"
EDGE_COLLECTIONS: Mapping[str, str] = {"Relationships": "relationships", "Correlations": "correlations"}
LINKED_COLLECTIONS: Mapping[str, str] = {"Observations": "observations", "Alerts": "alerts"}
DEFAULT_RELATIONSHIP_LIMIT = 200
DEFAULT_LINKED_LIMIT = 200
_ID_FIELD = {"relationships": "relationship_id", "correlations": "relationship_id",
             "observations": "observation_id", "alerts": "alert_id"}


@lru_cache(maxsize=None)
def _validator() -> jsonschema.Draft202012Validator:
    names = (*SCHEMA_FILES, "entity_composition.v1.schema.json")
    schemas = [json.loads((schema_dir() / "federation" / name).read_text(encoding="utf-8")) for name in names]
    registry: Registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return jsonschema.Draft202012Validator(schemas[-1], registry=registry)


def validate_entity_composition(obj: Mapping[str, Any]) -> List[str]:
    return [
        f"schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(_validator().iter_errors(obj), key=lambda e: list(e.absolute_path))
    ]


def _producers(row: Mapping[str, Any], fallback: str) -> List[str]:
    return [str(p) for p in row.get("_producers") or []] or [fallback]


def _edge(
    collection: str,
    row: Mapping[str, Any],
    anchor_id: str,
    counterparts: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    stream = EDGE_COLLECTIONS[collection]
    record_id = str(row.get("relationship_id") or row.get("id"))
    source_id, target_id = str(row.get("source_entity_id") or ""), str(row.get("target_entity_id") or "")
    if source_id == anchor_id and target_id == anchor_id:
        direction, other = "SELF", anchor_id
    elif source_id == anchor_id:
        direction, other = "OUTBOUND", target_id
    else:
        direction, other = "INBOUND", source_id
    hub_computed = stream == "correlations"
    source_state, _ = ep.source_state_for(row, sources)
    edge_state, edge_basis = ep.edge_state_for(row, hub_computed=hub_computed, source_state=source_state)
    counterpart = counterparts.get(other)
    return {
        "evidence_id": evidence_id(stream, record_id),
        "collection": collection,
        "record_id": record_id,
        "relationship_type": str(row.get("relationship_type") or "related"),
        "direction": direction,
        "counterpart": {
            "record_id": other or "unknown",
            "title": record_title(counterpart, other) if counterpart else None,
            "resolved": counterpart is not None,
            "entity_href": f"/entity/{other}" if counterpart else None,
        },
        "edge_state": edge_state,
        "edge_basis": edge_basis,
        "producers": _producers(row, "thehub-pr" if hub_computed else "unknown"),
        "synthetic": bool(row.get("synthetic", False)),
        "match_basis": str(row["match_basis"]) if row.get("match_basis") else None,
        "evidence_href": f"/evidence/{collection}/{record_id}",
    }


def _linked(collection: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    stream = LINKED_COLLECTIONS[collection]
    record_id = str(row.get(_ID_FIELD[stream]) or row.get("id"))
    return {
        "evidence_id": evidence_id(stream, record_id),
        "collection": collection,
        "record_id": record_id,
        "title": record_title(row, record_id),
        "producers": _producers(row, "unknown"),
        "synthetic": bool(row.get("synthetic", False)),
        "evidence_href": f"/evidence/{collection}/{record_id}",
    }


def compose_entity(
    anchor: Mapping[str, Any],
    *,
    now: datetime,
    edges: Iterable[Tuple[str, Mapping[str, Any]]] = (),
    linked: Iterable[Tuple[str, Mapping[str, Any]]] = (),
    counterparts: Optional[Mapping[str, Mapping[str, Any]]] = None,
    sources: Optional[Mapping[str, Mapping[str, Any]]] = None,
    registry_membership: Optional[Mapping[str, Any]] = None,
    relationship_limit: int = DEFAULT_RELATIONSHIP_LIMIT,
    linked_limit: int = DEFAULT_LINKED_LIMIT,
) -> Dict[str, Any]:
    """Compose the anchor entity. ``edges``/``linked`` are ``(collection, row)`` pairs.

    Passing one more row than a limit marks that list truncated; nothing beyond
    the limit is returned.
    """
    anchor_id = str(anchor.get("entity_id") or "")
    if not anchor_id:
        raise ValueError("anchor entity has no entity_id")
    sources = sources or {}
    counterparts = counterparts or {}
    evidence = project_evidence_object(
        "entities", anchor, now=now, sources_index=sources, identity_membership=registry_membership,
    )

    edge_rows: Sequence[Tuple[str, Mapping[str, Any]]] = sorted(
        ((c, r) for c, r in edges if c in EDGE_COLLECTIONS),
        key=lambda item: (item[0], str(item[1].get("relationship_id") or "")),
    )
    linked_rows: Sequence[Tuple[str, Mapping[str, Any]]] = sorted(
        ((c, r) for c, r in linked if c in LINKED_COLLECTIONS),
        key=lambda item: (item[0], str(item[1].get(_ID_FIELD[LINKED_COLLECTIONS[item[0]]]) or "")),
    )
    relationships = [_edge(c, r, anchor_id, counterparts, sources) for c, r in edge_rows[:relationship_limit]]
    linked_records = [_linked(c, r) for c, r in linked_rows[:linked_limit]]

    members = [{"producer": p, "collection": ANCHOR_COLLECTION, "record_id": anchor_id}
               for p in evidence["producers"]]
    rel_counts: Dict[str, int] = {}
    for item in relationships:
        for producer in item["producers"]:
            rel_counts[producer] = rel_counts.get(producer, 0) + 1
    linked_counts: Dict[str, int] = {}
    for item in linked_records:
        for producer in item["producers"]:
            linked_counts[producer] = linked_counts.get(producer, 0) + 1
    present = set(evidence["producers"]) | set(rel_counts) | set(linked_counts)
    sections = [
        {"producer": name, "status": "AVAILABLE" if name in present else "NO_DATA",
         "relationship_count": rel_counts.get(name, 0), "linked_record_count": linked_counts.get(name, 0)}
        for name in sorted(present | set(IN_SCOPE_PRODUCERS))
    ]
    return {
        "contract": CONTRACT_ID,
        "contract_status": ep.CONTRACT_STATUS,
        "anchor": evidence,
        "identity": {
            "identity_state": evidence["identity_state"],
            "identity_scope": evidence["identity_scope"],
            "identity_basis": evidence["identity_basis"],
            "registry_status": "CONSULTED" if registry_membership else "NOT_CONFIGURED",
            "members": members,
        },
        "sections": sections,
        "relationships": relationships,
        "linked_records": linked_records,
        "truncated": {
            "relationships": len(edge_rows) > relationship_limit,
            "linked_records": len(linked_rows) > linked_limit,
        },
        "limits": {"relationships": relationship_limit, "linked_records": linked_limit},
    }

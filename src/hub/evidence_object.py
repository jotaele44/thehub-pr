"""FEDERATION_EVIDENCE_OBJECT_V1 — project a Federation stream row into an Evidence Object.

The projection is pure and read-only: it never mutates the producer row and
never asserts anything the row (or the producer's additive ``evidence_state``
declaration) does not support. Every axis carries its basis. The canonical
producer record stays authoritative; the Evidence Object is an inspectable
view of it, keyed ``evo:<stream>:<producer record id>``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

import jsonschema
from referencing import Registry, Resource

from . import epistemic as ep
from ._schemas import STREAM_ID_FIELD, schema_dir
from .evidence_lineage import build_lineage, validate_lineage

CONTRACT_ID = "federation-evidence-object-v1"
HUB_PRODUCER = "thehub-pr"

ID_FIELDS: Mapping[str, str] = {**STREAM_ID_FIELD, "correlations": "relationship_id"}
HUB_COMPUTED_STREAMS = frozenset({"correlations"})

_TYPE_FIELDS = ("entity_type", "observation_type", "relationship_type", "alert_type", "source_type")
_TITLE_FIELDS = ("name", "source_name", "location_name", "title", "alert_type", "relationship_type", "observation_type")
_SINGULAR = {
    "sources": "source", "entities": "entity", "relationships": "relationship", "funding_awards": "funding_award",
    "transactions": "transaction", "observations": "observation", "alerts": "alert", "correlations": "correlation",
}
_DATED_PRECISIONS = {"DATE_ONLY": 10, "MONTH_YEAR": 7, "YEAR_ONLY": 4}
_POINT_PRECISIONS = frozenset({"OBSERVED_POINT", "INTERPRETED_POINT", "REPRESENTATIVE_POINT"})

SCHEMA_FILES = ("epistemic_state.v1.schema.json", "evidence_lineage.v1.schema.json", "evidence_object.v1.schema.json")


@lru_cache(maxsize=None)
def _validator() -> jsonschema.Draft202012Validator:
    schemas = [json.loads((schema_dir() / "federation" / name).read_text(encoding="utf-8")) for name in SCHEMA_FILES]
    registry: Registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return jsonschema.Draft202012Validator(schemas[-1], registry=registry)


def row_sha256(row: Mapping[str, Any]) -> str:
    """SHA-256 of the row's canonical JSON (sorted keys, compact separators)."""
    blob = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def evidence_id(stream: str, record_id: str) -> str:
    return f"evo:{stream}:{record_id}"


def _record_id(stream: str, row: Mapping[str, Any]) -> str:
    field = ID_FIELDS.get(stream)
    value = row.get(field) if field else None
    return str(value or row.get("id") or "")


def _first(row: Mapping[str, Any], fields: tuple) -> Optional[str]:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return None


def record_title(row: Mapping[str, Any], fallback: str) -> str:
    """Human label for a stream row: its first populated name/title field."""
    return _first(row, _TITLE_FIELDS) or fallback


def _contradictions(row: Mapping[str, Any], errors: List[str]) -> List[Dict[str, Any]]:
    """Pass through well-formed producer contradictions; report (never repair) malformed ones."""
    out: List[Dict[str, Any]] = []
    for index, item in enumerate(row.get("contradictions") or []):
        if not isinstance(item, Mapping) or not item.get("claim_a") or not item.get("claim_b"):
            errors.append(f"contradictions[{index}]: requires claim_a and claim_b; original claims were not recorded")
            continue
        status = ep.pick(item.get("status"), ep.CONTRADICTION_STATES, "OPEN", errors, f"contradictions[{index}].status")
        out.append({
            "contradiction_id": str(item.get("contradiction_id") or f"c{index}"),
            "claim_a": str(item["claim_a"]),
            "source_a": item.get("source_a"),
            "claim_b": str(item["claim_b"]),
            "source_b": item.get("source_b"),
            "status": status,
            "adjudication": item.get("adjudication"),
            "rationale": item.get("rationale"),
        })
    return out


def project_evidence_object(
    stream: str,
    row: Mapping[str, Any],
    *,
    now: datetime,
    sources_index: Optional[Mapping[str, Mapping[str, Any]]] = None,
    identity_membership: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the Evidence Object for one stream row. ``now`` must be timezone-aware."""
    if stream not in ID_FIELDS:
        raise ValueError(f"unknown federation stream {stream!r}")
    record_id = _record_id(stream, row)
    if not record_id:
        raise ValueError(f"{stream} row has no {ID_FIELDS[stream]}")

    sources = sources_index or {}
    errors: List[str] = []
    hub_computed = stream in HUB_COMPUTED_STREAMS
    producers = [str(p) for p in row.get("_producers") or []]
    producer = producers[0] if producers else (HUB_PRODUCER if hub_computed else "unknown")

    source_state, source_basis = (
        ep.source_binding_basis(row, "this source record") if stream == "sources"
        else ep.source_state_for(row, sources)
    )
    klass, klass_basis = ep.epistemic_class_for(row, hub_computed=hub_computed, errors=errors)
    stage = ep.data_stage_for(row, hub_computed=hub_computed, errors=errors)
    identity = ep.identity_for(row, identity_membership, errors=errors)
    temporal = ep.temporal_for(row, errors=errors)
    temporal_state, temporal_state_basis = ep.temporal_state_at(row, now)
    observation, observation_basis = ep.observation_state_for(row, errors=errors)
    geometry = ep.geometry_for(row, errors=errors)
    decl = ep.declared(row)

    record_node = f"record:{stream}:{record_id}"
    lineage = build_lineage(stream, row, record_node, producer=producer, source_state=source_state)

    raw_source_ids = sorted({str(v) for v in (row.get("source_id"), row.get("evidence_source_id")) if v})
    citations: List[Dict[str, Any]] = []
    for source_id in raw_source_ids:
        source = sources.get(source_id) or {}
        state, _ = ep.source_state_for({"source_id": source_id}, sources)
        text = str(source.get("source_url") or "").strip()
        url = ep.retrievable_locator(source)
        citations.append({"source_id": source_id, "title": source.get("source_name"), "url": url,
                          "citation_text": text if text and text != url else None, "source_state": state})

    computations: List[Dict[str, Any]] = []
    if hub_computed:
        lin = ep.as_mapping(row.get("lineage"))
        computations.append({"method": str(row.get("match_basis") or "unspecified"), "producer": HUB_PRODUCER,
                             "algorithm": lin.get("producer_script"),
                             "inputs": [str(x) for x in lin.get("source_inputs") or []]})
    interpretations: List[Dict[str, Any]] = []
    if klass == "INTERPRETIVE":
        interpretations.append({"basis": str(decl.get("interpretation_basis")), "author": producer})

    type_value = _first(row, _TYPE_FIELDS) or "record"
    confidence = row.get("confidence")
    return {
        "contract": CONTRACT_ID,
        "id": evidence_id(stream, record_id),
        "canonical_type": f"{_SINGULAR[stream]}:{type_value}",
        "stream": stream,
        "producer_repo": producer,
        "producers": producers or [producer],
        "producer_record_id": record_id,
        "title": record_title(row, record_id),
        "raw_source_ids": raw_source_ids,
        "manifestations": [{"producer_repo": p, "stream": stream, "record_id": record_id} for p in (producers or [producer])],
        "data_stage": stage,
        "source_state": source_state,
        "source_state_basis": source_basis,
        "epistemic_class": klass,
        "epistemic_class_basis": klass_basis,
        **identity,
        "temporal_state": temporal_state,
        "temporal_state_basis": temporal_state_basis,
        "temporal_precision": temporal["temporal_precision"],
        "temporal_basis": temporal["temporal_basis"],
        "observation_state": observation,
        "observation_state_basis": observation_basis,
        "geometry": geometry["geometry"],
        "geometry_precision": geometry["geometry_precision"],
        "geometry_basis": geometry["geometry_basis"],
        "area_reference": geometry["area_reference"],
        "valid_from": decl.get("valid_from") or row.get("start_at"),
        "valid_to": decl.get("valid_to") or row.get("end_at"),
        "observed_at": temporal["observed_at"],
        "retrieved_at": row.get("extracted_at"),
        "synthetic": bool(row.get("synthetic", False)),
        "confidence": float(confidence) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else None,
        "lineage": lineage,
        "contradictions": _contradictions(row, errors),
        "computations": computations,
        "interpretations": interpretations,
        "citations": citations,
        "declaration_errors": errors,
        "audit_metadata": {
            "projector": "hub.evidence_object.project_evidence_object",
            "contract_status": ep.CONTRACT_STATUS,
            "projected_at": now.isoformat(),
            "row_sha256": row_sha256(row),
        },
    }


def validate_evidence_object(obj: Mapping[str, Any]) -> List[str]:
    """Schema violations plus the semantic invariants the schema cannot express."""
    errors = [
        f"schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(_validator().iter_errors(obj), key=lambda e: list(e.absolute_path))
    ]
    precision = obj.get("temporal_precision")
    observed_at = obj.get("observed_at")
    if precision in _DATED_PRECISIONS and isinstance(observed_at, str):
        if "T" in observed_at or len(observed_at) != _DATED_PRECISIONS[precision]:
            errors.append(f"observed_at {observed_at!r} carries more precision than {precision}")
    geo = obj.get("geometry_precision")
    if geo in _POINT_PRECISIONS and obj.get("geometry") is None:
        errors.append(f"{geo} requires a point geometry")
    if geo == "AREA_REFERENCE" and obj.get("geometry") is not None:
        errors.append("AREA_REFERENCE must not carry a point geometry")
    if obj.get("observation_state") == "OBSERVED_ABSENT" and "absence" not in str(obj.get("observation_state_basis")):
        errors.append("OBSERVED_ABSENT requires a declared absence basis")
    if obj.get("epistemic_class") == "INTERPRETIVE" and not obj.get("interpretations"):
        errors.append("INTERPRETIVE object requires an interpretation basis")
    if (obj.get("epistemic_class") == "UNCLASSIFIED") != (obj.get("epistemic_class_basis") == "NONE"):
        errors.append("epistemic_class_basis must be NONE exactly when the class is UNCLASSIFIED")
    lineage = obj.get("lineage")
    if isinstance(lineage, Mapping):
        errors.extend(f"lineage: {e}" for e in validate_lineage(lineage))
    return errors

"""Runtime bridge to the frozen Phase-1 federation contracts.

The files under ``schemas/contracts`` are immutable contract authority. This
module loads and validates those exact schemas at runtime; it does not duplicate
or reinterpret them. It also provides deterministic projections from Hub
correlation/adjudication rows into ``entity_resolution.v1`` ledger records.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "schemas" / "contracts"

CONTRACT_FILES = {
    "access_classification.v1": "access_classification.v1.schema.json",
    "provenance.v1": "provenance.v1.schema.json",
    "snapshot_manifest.v1": "snapshot_manifest.v1.schema.json",
    "entity_resolution.v1": "entity_resolution.v1.schema.json",
}


def _load_contract(name: str) -> dict[str, Any]:
    try:
        filename = CONTRACT_FILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown frozen contract: {name}") from exc
    return json.loads((CONTRACT_DIR / filename).read_text(encoding="utf-8"))


def validate_contract(name: str, payload: Mapping[str, Any]) -> None:
    """Validate a payload against an exact frozen Phase-1 contract.

    Raises ``jsonschema.ValidationError`` on contract violation. Provenance's
    access-classification reference is resolved only from the sibling frozen
    schema, never from the network.
    """
    schema = _load_contract(name)
    if name == "provenance.v1":
        access = _load_contract("access_classification.v1")
        resolver = jsonschema.RefResolver.from_schema(
            schema, store={access["$id"]: access}
        )
        jsonschema.Draft202012Validator(schema, resolver=resolver).validate(dict(payload))
        return
    jsonschema.Draft202012Validator(schema).validate(dict(payload))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def correlation_candidate_record(
    relationship: Mapping[str, Any], *, evidence_ids: Sequence[str] | None = None
) -> dict[str, Any]:
    """Project one Hub correlation into a frozen entity-resolution candidate.

    This never asserts identity. Similarity/proximity information is retained
    only in ``similarity_signals``; the reason code names the reviewable act of
    creating a cross-producer candidate rather than a disallowed bare signal.
    """
    if relationship.get("identity_assertion") is not False:
        raise ValueError("correlation candidate must explicitly state identity_assertion=false")
    if relationship.get("identity_adjudication_state") != "CANDIDATE":
        raise ValueError("correlation candidate must be in CANDIDATE state")
    if relationship.get("identity_cardinality") != "UNRESOLVED":
        raise ValueError("correlation candidate cardinality must be UNRESOLVED")

    src = str(relationship["source_entity_id"])
    tgt = str(relationship["target_entity_id"])
    relationship_id = str(relationship["relationship_id"])
    supplied = list(evidence_ids or ())
    if relationship.get("evidence_source_id"):
        supplied.append(str(relationship["evidence_source_id"]))
    supplied.append(relationship_id)
    evidence = sorted({value for value in supplied if value})

    row = {
        "decision_type": "entity_match_candidate",
        "decision_id": _stable_id("erd", "candidate", relationship_id),
        "reason_code": "cross_producer_correlation_candidate",
        "evidence_ids": evidence,
        "created_at": str(relationship["created_at"]),
        "candidate_entity_ids": sorted({src, tgt}),
        "similarity_signals": {
            "relationship_id": relationship_id,
            "relationship_type": relationship.get("relationship_type"),
            "match_basis": relationship.get("match_basis"),
            "confidence": relationship.get("confidence"),
            "identity_evidence_class": relationship.get("identity_evidence_class"),
        },
    }
    validate_contract("entity_resolution.v1", row)
    return row


def adjudication_record(
    relationship: Mapping[str, Any], *, decided_by: str
) -> dict[str, Any]:
    """Project an explicit runtime adjudication into the frozen decision ledger.

    RESOLVED becomes MERGE; REJECTED becomes ``rejected_match``. CANDIDATE rows
    cannot enter this path. Evidence references are mandatory because the runtime
    adjudicator already fails closed when they are absent.
    """
    state = relationship.get("identity_adjudication_state")
    relationship_id = str(relationship["relationship_id"])
    evidence = sorted({str(v) for v in relationship.get("identity_evidence_refs", []) if str(v)})
    if not evidence:
        raise ValueError("adjudication record requires identity_evidence_refs")
    basis = str(relationship.get("identity_decision_basis") or "").strip()
    if not basis:
        raise ValueError("adjudication record requires identity_decision_basis")

    candidate_ref = _stable_id("erd", "candidate", relationship_id)
    if state == "RESOLVED":
        if relationship.get("identity_assertion") is not True:
            raise ValueError("RESOLVED adjudication must assert identity")
        row = {
            "decision_type": "entity_identity_decision",
            "decision_id": _stable_id("erd", "identity", relationship_id, basis),
            "reason_code": "explicit_evidence_bearing_identity_adjudication",
            "evidence_ids": evidence,
            "created_at": str(relationship.get("extracted_at") or relationship["created_at"]),
            "candidate_ref": candidate_ref,
            "outcome": "MERGE",
            "decided_by": decided_by,
        }
    elif state == "REJECTED":
        row = {
            "decision_type": "rejected_match",
            "decision_id": _stable_id("erd", "rejected", relationship_id, basis),
            "reason_code": "explicit_evidence_bearing_distinct_adjudication",
            "evidence_ids": evidence,
            "created_at": str(relationship.get("extracted_at") or relationship["created_at"]),
            "candidate_ref": candidate_ref,
            "rejected_by": decided_by,
        }
    else:
        raise ValueError(f"unsupported adjudication state for frozen ledger: {state!r}")

    validate_contract("entity_resolution.v1", row)
    return row


def provenance_record(
    *,
    producer_id: str,
    canonical_stream: str,
    artifact_sha256: str,
    snapshot_id: str,
    schema_version: str,
    evidence_tier: str,
    tier_source: str,
    tier_review_status: str,
    synthetic_status: str,
    access_level: str,
    canonical_record_id: str | None = None,
    source_url: str | None = None,
    contradiction_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build and validate the minimum frozen provenance block."""
    row: dict[str, Any] = {
        "producer_id": producer_id,
        "canonical_stream": canonical_stream,
        "artifact_sha256": artifact_sha256,
        "snapshot_id": snapshot_id,
        "schema_version": schema_version,
        "evidence_tier": evidence_tier,
        "tier_authority": {
            "tier_value": evidence_tier,
            "tier_source": tier_source,
            "tier_review_status": tier_review_status,
        },
        "synthetic_status": synthetic_status,
        "access_classification": {"level": access_level},
    }
    if canonical_record_id is not None:
        row["canonical_record_id"] = canonical_record_id
    if source_url is not None:
        row["source_url"] = source_url
    if contradiction_refs:
        row["contradiction_refs"] = sorted({str(v) for v in contradiction_refs})
    validate_contract("provenance.v1", row)
    return row

"""Stateless client validator for the independent spatial-identity authority.

TheHub may validate/cache these rows but this module neither persists nor assigns
federation identity. Raw producer identifiers are never normalized. Canonical
serialization changes only mapping-key and set-like list order for hashing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "registry" / "federation" / "spatial_identity_decision_contract.v1.json"


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _member_key(member: Mapping[str, Any], allowed_producers: set[str]) -> tuple[str, str]:
    if set(member) != {"source_producer", "local_record_id"}:
        raise ValueError("identity member must contain only source_producer and local_record_id")
    producer = member.get("source_producer")
    record_id = member.get("local_record_id")
    if not isinstance(producer, str) or producer not in allowed_producers:
        raise ValueError("identity member source_producer is not a canonical producer")
    if not isinstance(record_id, str) or not record_id:
        raise ValueError("identity member local_record_id must be a non-empty string")
    return producer, record_id


def _computed_identity_cardinality(left_count: int, right_count: int) -> str:
    if left_count == 1 and right_count == 1:
        return "1:1"
    if left_count == 1 and right_count > 1:
        return "1:N"
    if left_count > 1 and right_count == 1:
        return "N:1"
    if left_count > 1 and right_count > 1:
        return "N:N"
    raise ValueError(
        f"identity cardinality requires members on both sides; left={left_count} right={right_count}"
    )


def _computed_crosswalk_cardinality(left_count: int, right_count: int) -> str:
    if left_count == 0 and right_count == 1:
        return "0:1"
    raise ValueError(
        f"unsupported non-identity crosswalk shape left={left_count} right={right_count}"
    )


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("created_at must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("created_at must be valid RFC3339 UTC") from exc
    if parsed.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")


def _validate_evidence(
    evidence: Any, contract: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("identity decision requires at least one evidence row")
    priority = {name: index for index, name in enumerate(contract["evidence_priority"])}
    dispositions = set(contract["evidence_dispositions"])
    seen: set[tuple[str, str, str]] = set()
    validated: list[dict[str, Any]] = []
    for row in evidence:
        if not isinstance(row, Mapping):
            raise ValueError("identity evidence rows must be objects")
        if set(row) - {"evidence_class", "evidence_ref", "disposition", "detail"}:
            raise ValueError("identity evidence row contains unknown fields")
        evidence_class = row.get("evidence_class")
        evidence_ref = row.get("evidence_ref")
        disposition = row.get("disposition")
        if evidence_class not in priority:
            raise ValueError(f"unsupported identity evidence_class: {evidence_class!r}")
        if disposition not in dispositions:
            raise ValueError("unsupported identity evidence disposition")
        if not isinstance(evidence_ref, str) or not evidence_ref:
            raise ValueError("identity evidence_ref must be a non-empty string")
        if "detail" in row and not isinstance(row["detail"], str):
            raise ValueError("identity evidence detail must be a string")
        key = (str(evidence_class), evidence_ref, str(disposition))
        if key in seen:
            raise ValueError("duplicate identity evidence row")
        seen.add(key)
        validated.append(dict(row))
    return validated, priority


def _strongest_rank(
    evidence: list[dict[str, Any]],
    priority: Mapping[str, int],
    disposition: str,
    binding: set[str],
) -> int | None:
    ranks = [
        priority[str(row["evidence_class"])]
        for row in evidence
        if row["disposition"] == disposition and row["evidence_class"] in binding
    ]
    return min(ranks) if ranks else None


def validate_identity_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a canonicalized whole identity-decision row."""
    if not isinstance(payload, Mapping):
        raise ValueError("identity decision must be an object")
    contract = load_contract()
    required = set(contract["required_decision_fields"])
    optional = set(contract["allowed_optional_fields"])
    actual = set(payload)
    missing = required - actual
    unknown = actual - required - optional
    if missing:
        raise ValueError("identity decision missing required fields: " + ", ".join(sorted(missing)))
    if unknown:
        raise ValueError("identity decision contains unknown fields: " + ", ".join(sorted(unknown)))

    if payload["schema_version"] != contract["schema_version"]:
        raise ValueError("identity decision schema_version mismatch")
    if payload["authority_plane"] != contract["authority_plane"]:
        raise ValueError("identity decision authority_plane mismatch")
    if payload["decision_type"] not in contract["decision_types"]:
        raise ValueError("unsupported identity decision_type")
    if payload["outcome"] not in contract["outcomes"]:
        raise ValueError("unsupported identity outcome")
    if payload["resolution_state"] not in contract["resolution_states"]:
        raise ValueError("unsupported identity resolution_state")
    for field in ("decision_id", "frozen_scope_id", "decision_basis", "decided_by"):
        if not isinstance(payload[field], str) or not payload[field]:
            raise ValueError(f"identity decision {field} must be a non-empty string")
    _validate_timestamp(payload["created_at"])
    if not isinstance(payload["candidate_set_complete"], bool):
        raise ValueError("candidate_set_complete must be boolean")
    tie_count = payload["top_evidence_tie_count"]
    if not isinstance(tie_count, int) or isinstance(tie_count, bool) or tie_count < 1:
        raise ValueError("top_evidence_tie_count must be an integer >= 1")

    left = payload["left_members"]
    right = payload["right_members"]
    if not isinstance(left, list) or not isinstance(right, list):
        raise ValueError("left_members and right_members must be arrays")
    allowed_producers = set(contract["member_producers"])
    left_keys = [_member_key(row, allowed_producers) for row in left]
    right_keys = [_member_key(row, allowed_producers) for row in right]
    if len(left_keys) != len(set(left_keys)) or len(right_keys) != len(set(right_keys)):
        raise ValueError("duplicate identity member")
    if set(left_keys) & set(right_keys):
        raise ValueError("identity member cannot appear on both sides")

    evidence, priority = _validate_evidence(payload["evidence"], contract)
    binding = set(contract["binding_evidence_classes"])
    strongest_support = _strongest_rank(evidence, priority, "SUPPORTS", binding)
    strongest_contradiction = _strongest_rank(evidence, priority, "CONTRADICTS", binding)

    outcome = str(payload["outcome"])
    decision_type = str(payload["decision_type"])
    resolution_state = str(payload["resolution_state"])
    complete = bool(payload["candidate_set_complete"])
    identity_cardinality = payload.get("identity_cardinality")
    crosswalk_cardinality = payload.get("crosswalk_cardinality")
    federation_entity_id = payload.get("federation_entity_id")

    if tie_count > 1 and (
        decision_type != "IDENTITY_EQUIVALENCE"
        or outcome != "DEFER"
        or resolution_state != "UNRESOLVED"
    ):
        raise ValueError("tied top evidence requires identity DEFER with UNRESOLVED state")

    if decision_type == "CROSSWALK_ONLY":
        if not complete:
            raise ValueError("CROSSWALK_ONLY requires a complete bounded candidate set")
        if outcome != "DEFER" or resolution_state != "NON_IDENTITY":
            raise ValueError("CROSSWALK_ONLY must DEFER with NON_IDENTITY state")
        if identity_cardinality is not None:
            raise ValueError("CROSSWALK_ONLY cannot carry identity_cardinality")
        if crosswalk_cardinality not in contract["crosswalk_cardinalities"]:
            raise ValueError("CROSSWALK_ONLY requires a supported crosswalk_cardinality")
        computed = _computed_crosswalk_cardinality(len(left_keys), len(right_keys))
        if crosswalk_cardinality != computed:
            raise ValueError(
                f"declared crosswalk cardinality {crosswalk_cardinality} does not match computed {computed}"
            )
        if federation_entity_id is not None:
            raise ValueError("CROSSWALK_ONLY cannot assign federation_entity_id")
    else:
        if crosswalk_cardinality is not None:
            raise ValueError("IDENTITY_EQUIVALENCE cannot carry crosswalk_cardinality")

        if not complete:
            if outcome != "DEFER" or resolution_state != "UNRESOLVED":
                raise ValueError("incomplete candidate set requires DEFER with UNRESOLVED state")

        if outcome == "DEFER":
            if resolution_state != "UNRESOLVED":
                raise ValueError("DEFER identity decision requires UNRESOLVED state")
            if identity_cardinality is not None:
                raise ValueError("UNRESOLVED identity decision cannot claim identity_cardinality")
            if federation_entity_id is not None:
                raise ValueError("DEFER cannot assign federation_entity_id")
        else:
            if resolution_state != "RESOLVED":
                raise ValueError("binding identity decision requires RESOLVED state")
            if identity_cardinality not in contract["identity_cardinalities"]:
                raise ValueError("binding identity decision requires a valid identity_cardinality")
            computed = _computed_identity_cardinality(len(left_keys), len(right_keys))
            if identity_cardinality != computed:
                raise ValueError(
                    f"declared identity cardinality {identity_cardinality} does not match computed {computed}"
                )

            if outcome == "MERGE":
                if strongest_support is None:
                    raise ValueError("MERGE requires binding SUPPORTS evidence")
                if strongest_contradiction is not None and strongest_contradiction <= strongest_support:
                    raise ValueError("equal or stronger contradictory evidence requires DEFER")
                if federation_entity_id is None:
                    raise ValueError("MERGE requires authority-supplied federation_entity_id")
                pattern = re.compile(contract["canonical_federation_entity_id_pattern"])
                if not isinstance(federation_entity_id, str) or not pattern.fullmatch(
                    federation_entity_id
                ):
                    raise ValueError("invalid authority-supplied federation_entity_id")
            elif outcome == "DISTINCT":
                if strongest_contradiction is None:
                    raise ValueError("DISTINCT requires binding CONTRADICTS evidence")
                if strongest_support is not None and strongest_support <= strongest_contradiction:
                    raise ValueError("equal or stronger supporting evidence requires DEFER")
                if federation_entity_id is not None:
                    raise ValueError("DISTINCT cannot assign federation_entity_id")

    if "supersedes_decision_id" in payload and (
        not isinstance(payload["supersedes_decision_id"], str)
        or not payload["supersedes_decision_id"]
    ):
        raise ValueError("supersedes_decision_id must be a non-empty string")
    if "notes" in payload and not isinstance(payload["notes"], str):
        raise ValueError("notes must be a string")
    return canonical_identity_decision(payload)


def canonical_identity_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical whole-row ordering without altering raw identifier strings."""
    row = copy.deepcopy(dict(payload))
    row["left_members"] = sorted(
        row["left_members"], key=lambda m: (m["source_producer"], m["local_record_id"])
    )
    row["right_members"] = sorted(
        row["right_members"], key=lambda m: (m["source_producer"], m["local_record_id"])
    )
    row["evidence"] = sorted(
        row["evidence"],
        key=lambda e: (
            e["evidence_class"],
            e["evidence_ref"],
            e["disposition"],
            e.get("detail", ""),
        ),
    )
    return row


def identity_decision_bytes(payload: Mapping[str, Any]) -> bytes:
    row = validate_identity_decision(payload)
    return (
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def identity_decision_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(identity_decision_bytes(payload)).hexdigest()

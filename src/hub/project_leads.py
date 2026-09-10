"""Fail-closed cross-producer adjudication for project leads.

This module is intentionally separate from generic entity correlation. Name,
municipality, temporal overlap, shared lead_id, and proximity are discovery
signals only. A project becomes banner-eligible only when MoneySweep and
SpiderWeb independently expose the same permitted authoritative binding.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

STATES = {
    "LEAD_ONLY",
    "FISCAL_ONLY",
    "PHYSICAL_ONLY",
    "CROSS_DOMAIN_CANDIDATE",
    "REVIEW",
    "BANNER_ELIGIBLE",
}

_STABLE_ID_TYPES = {
    "stable_project_id",
    "contract_id",
    "award_id",
    "parcel_id",
    "facility_id",
}


def _binding_keys(assertion: dict[str, Any]) -> set[tuple[str, str]]:
    """Return only independently authoritative, explicitly binding evidence."""
    out: set[tuple[str, str]] = set()
    for ev in assertion.get("independent_binding_evidence") or []:
        if not isinstance(ev, dict):
            continue
        etype = str(ev.get("evidence_type") or "")
        value = str(ev.get("value") or "").strip()
        if (
            etype in _STABLE_ID_TYPES
            and value
            and ev.get("authoritative") is True
            and ev.get("identity_effect") == "BINDING"
        ):
            out.add((etype, value))
            continue
        if (
            etype == "certified_geometry_binding"
            and value
            and ev.get("certified") is True
            and ev.get("independent_support") is True
            and ev.get("identity_effect") == "BINDING"
        ):
            out.add((etype, value))
    return out


def _contradictions(*assertions: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for assertion in assertions:
        for item in assertion.get("contradictions") or []:
            if isinstance(item, dict):
                out.append(item)
            else:
                out.append({"type": "UNCLASSIFIED", "detail": str(item)})
    return out


def _first_by_lead(rows: Iterable[dict[str, Any]], lead_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("lead_id") or "") == lead_id]


def _require_unique_assertion_ids(rows: list[dict[str, Any]], producer: str) -> None:
    seen: set[str] = set()
    for row in rows:
        assertion_id = str(row.get("assertion_id") or "").strip()
        if not assertion_id:
            raise ValueError(f"{producer} assertion_id required")
        if assertion_id in seen:
            raise ValueError(f"duplicate {producer} assertion_id: {assertion_id}")
        seen.add(assertion_id)


def _join_cardinality(fiscal_count: int, physical_count: int) -> str:
    def label(count: int) -> str:
        if count == 0:
            return "0"
        return "1" if count == 1 else "N"

    return f"{label(fiscal_count)}:{label(physical_count)}"


def adjudicate_project(
    lead: dict[str, Any] | None,
    fiscal_assertions: Iterable[dict[str, Any]],
    physical_assertions: Iterable[dict[str, Any]],
    *,
    lead_id: str | None = None,
) -> dict[str, Any]:
    """Classify one project lead without heuristic identity promotion."""
    resolved_lead_id = str(
        lead_id or ((lead or {}).get("lead_id") if isinstance(lead, dict) else "") or ""
    ).strip()
    if not resolved_lead_id:
        raise ValueError("lead_id required")

    fiscals = _first_by_lead(fiscal_assertions, resolved_lead_id)
    physicals = _first_by_lead(physical_assertions, resolved_lead_id)
    _require_unique_assertion_ids(fiscals, "fiscal")
    _require_unique_assertion_ids(physicals, "physical")
    result: dict[str, Any] = {
        "lead_id": resolved_lead_id,
        "identity_effect": "NONE",
        "state": "LEAD_ONLY",
        "fiscal_assertion_count": len(fiscals),
        "physical_assertion_count": len(physicals),
        "join_cardinality": _join_cardinality(len(fiscals), len(physicals)),
        "binding_candidates": [],
        "contradictions": [],
        "banner": None,
    }

    if not fiscals and not physicals:
        return result
    if fiscals and not physicals:
        result["state"] = "FISCAL_ONLY"
        return result
    if physicals and not fiscals:
        result["state"] = "PHYSICAL_ONLY"
        return result

    # Preserve the complete assertion cross-product. Never whole-row aggregate
    # into a synthetic record that did not exist in either producer.
    binding_pairs: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    contradictions = _contradictions(*fiscals, *physicals)
    for fiscal in fiscals:
        fk = _binding_keys(fiscal)
        for physical in physicals:
            pk = _binding_keys(physical)
            shared = sorted(fk & pk)
            if shared:
                for evidence_type, value in shared:
                    binding_pairs.append(
                        {
                            "evidence_type": evidence_type,
                            "value": value,
                            "fiscal_assertion_id": fiscal.get("assertion_id"),
                            "physical_assertion_id": physical.get("assertion_id"),
                        }
                    )
            elif fk and pk:
                conflicts.append(
                    {
                        "type": "IDENTITY",
                        "fiscal_keys": sorted(fk),
                        "physical_keys": sorted(pk),
                    }
                )

    # De-duplicate exact evidence tuples without collapsing distinct assertion pairs.
    result["binding_candidates"] = binding_pairs
    result["contradictions"] = contradictions + conflicts

    if result["contradictions"]:
        result["state"] = "REVIEW"
        return result
    if not binding_pairs:
        result["state"] = "CROSS_DOMAIN_CANDIDATE"
        return result

    unique_bindings = sorted({(p["evidence_type"], p["value"]) for p in binding_pairs})
    if len(unique_bindings) != 1:
        # Multiple equally permitted bindings are a tie, not determinism-as-evidence.
        result["state"] = "REVIEW"
        return result

    evidence_type, value = unique_bindings[0]
    result["state"] = "BANNER_ELIGIBLE"
    result["identity_effect"] = "BINDING"
    result["banner"] = build_project_banner(
        lead or {"lead_id": resolved_lead_id}, evidence_type=evidence_type, binding_value=value
    )
    return result


def build_project_banner(
    lead: dict[str, Any], *, evidence_type: str, binding_value: str
) -> dict[str, Any]:
    """Create ``project_banner/v1`` only after the binding gate has passed."""
    lead_id = str(lead.get("lead_id") or "").strip()
    if not lead_id:
        raise ValueError("lead_id required")
    digest = hashlib.sha256(
        f"project-banner-v1|{lead_id}|{evidence_type}|{binding_value}".encode("utf-8")
    ).hexdigest()[:32]
    return {
        "schema": "project_banner/v1",
        "banner_id": f"prjban_{digest}",
        "lead_id": lead_id,
        "title_raw": lead.get("source_title_raw"),
        "binding": {"evidence_type": evidence_type, "value": binding_value},
        "certification_state": "PASS",
    }


__all__ = ["STATES", "adjudicate_project", "build_project_banner"]

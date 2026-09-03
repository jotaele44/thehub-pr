"""Explicit identity-adjudication semantics for cross-producer federation links.

Correlation is not identity. This module provides the runtime vocabulary used to
keep discovery signals (name similarity, proximity, temporal proximity, shared
identifiers) separate from an adjudicated identity decision.

Nothing in this module auto-merges entities. A caller must supply an explicit
cardinality and an evidence-bearing decision before identity can be asserted.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

CARDINALITIES = frozenset({"1:1", "1:N", "N:1", "N:N", "0:1", "UNRESOLVED"})
ADJUDICATION_STATES = frozenset({"CANDIDATE", "RESOLVED", "REJECTED", "SUPERSEDED"})

# These bases may be useful for discovery/correlation, but must never be treated
# as sufficient identity evidence on their own.
WEAK_CORRELATION_BASES = frozenset({
    "normalized_name",
    "location",
    "award_transaction_date",
})


def evidence_class(match_basis: str | None) -> str:
    """Classify a Hub correlation basis without asserting entity identity."""
    if not match_basis:
        return "UNSPECIFIED_CORRELATION"
    if match_basis in WEAK_CORRELATION_BASES:
        return "WEAK_CORRELATION"
    if match_basis.startswith("external_id:"):
        return "HARD_IDENTIFIER_CANDIDATE"
    return "OTHER_CORRELATION"


def annotate_candidate_relationship(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a relationship row explicitly marked as non-identity candidate.

    The existing ``federation_relationship`` schema permits additive properties,
    so this can be introduced without mutating the frozen schema boundary.
    """
    out = dict(row)
    out["identity_assertion"] = False
    out["identity_adjudication_state"] = "CANDIDATE"
    out["identity_cardinality"] = "UNRESOLVED"
    out["identity_evidence_class"] = evidence_class(
        str(out.get("match_basis")) if out.get("match_basis") is not None else None
    )
    return out


def adjudicate_identity(
    row: Mapping[str, Any],
    *,
    cardinality: str,
    evidence_refs: Sequence[str],
    decision_basis: str,
) -> Dict[str, Any]:
    """Create an explicit resolved identity decision from a candidate link.

    Resolution fails closed unless the caller supplies:
    - a supported non-UNRESOLVED cardinality;
    - at least one evidence reference;
    - a non-empty human/machine-readable decision basis.

    Weak correlation bases remain insufficient by themselves; callers must cite
    independent evidence in ``evidence_refs``. This function deliberately does
    not inspect or infer that evidence.
    """
    if cardinality not in CARDINALITIES or cardinality == "UNRESOLVED":
        raise ValueError(f"unsupported resolved cardinality: {cardinality}")
    refs = sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()})
    if not refs:
        raise ValueError("identity resolution requires at least one evidence reference")
    basis = decision_basis.strip()
    if not basis:
        raise ValueError("identity resolution requires a decision basis")

    out = annotate_candidate_relationship(row)
    out["identity_assertion"] = True
    out["identity_adjudication_state"] = "RESOLVED"
    out["identity_cardinality"] = cardinality
    out["identity_evidence_refs"] = refs
    out["identity_decision_basis"] = basis
    return out


def reject_identity(
    row: Mapping[str, Any], *, evidence_refs: Sequence[str], decision_basis: str
) -> Dict[str, Any]:
    """Record an explicit negative identity adjudication without deleting the link."""
    refs = sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()})
    if not refs:
        raise ValueError("identity rejection requires at least one evidence reference")
    basis = decision_basis.strip()
    if not basis:
        raise ValueError("identity rejection requires a decision basis")

    out = annotate_candidate_relationship(row)
    out["identity_adjudication_state"] = "REJECTED"
    out["identity_evidence_refs"] = refs
    out["identity_decision_basis"] = basis
    return out

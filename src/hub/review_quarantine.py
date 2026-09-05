"""Independent TheHub validation of producer review/quarantine semantics."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

POLICY_VERSION = "federation-review-quarantine/1.0"
RECEIPT_SCHEMA = "aguayluz_federation_review_quarantine_v1"
SCOPE_SCHEMA = "prii_federation_spatial_certification_scope_v1"
CLAIM = "FEDERATION_SPATIAL_ARCHITECTURE"
REQUIRED_NONBLOCKING_CLASS = "DOMAIN_RECORD_ADJUDICATION"


class ReviewQuarantineError(ValueError):
    """Raised when a frozen package can silently promote unresolved evidence."""


@dataclass(frozen=True)
class ReviewQuarantineValidation:
    state: str
    promotable: bool
    quarantined_total: int
    canonical_primary_counts: Mapping[str, int]


def _json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewQuarantineError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ReviewQuarantineError(f"{label} root must be an object")
    return value


def _jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ReviewQuarantineError(f"missing {label}: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReviewQuarantineError(f"{label}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ReviewQuarantineError(f"{label}:{line_no}: row must be an object")
        rows.append(row)
    return rows


def _nonnegative_int(value: Any, label: str, errors: list[str]) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{label} must be a non-negative integer")
        return 0
    return value


def _validate_scope(package_root: Path, errors: list[str]) -> None:
    path = package_root / "governance" / "federation_spatial_certification_scope_v1.json"
    if not path.is_file():
        errors.append("missing bound federation spatial certification scope")
        return
    scope = _json(path, "certification scope")
    if scope.get("schema_version") != SCOPE_SCHEMA:
        errors.append("certification scope schema_version mismatch")
    if scope.get("claim") != CLAIM:
        errors.append("certification scope claim mismatch")
    if scope.get("producer") != "jotaele44/aguayluz-pr":
        errors.append("certification scope producer mismatch")
    if scope.get("consumer_authority") != "jotaele44/thehub-pr":
        errors.append("certification scope consumer mismatch")
    if scope.get("zero_residue_rule") != "ZERO_MATERIAL_UNRESOLVED_WITHIN_CLAIM":
        errors.append("certification scope zero-residue rule drift")
    nonblocking = scope.get("nonblocking_disclosed_residue_classes")
    if not isinstance(nonblocking, list) or REQUIRED_NONBLOCKING_CLASS not in nonblocking:
        errors.append("certification scope must classify domain record adjudication explicitly")
    if not isinstance(scope.get("blocking_residue_classes"), list) or "UNCLASSIFIED" not in scope["blocking_residue_classes"]:
        errors.append("certification scope must fail closed on unclassified residue")
    promotion_rule = scope.get("promotion_rule")
    if not isinstance(promotion_rule, str) or "must never be rewritten as resolved" not in promotion_rule:
        errors.append("certification scope promotion rule drift")


def _validate_receipt(receipt: Mapping[str, Any], errors: list[str]) -> tuple[int, dict[str, int]]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        errors.append("review quarantine receipt schema mismatch")
    if receipt.get("policy_version") != POLICY_VERSION:
        errors.append("review quarantine policy mismatch")
    if receipt.get("producer") != "aguayluz-pr":
        errors.append("review quarantine producer mismatch")
    if receipt.get("state") != "PASS":
        errors.append(f"review quarantine state={receipt.get('state')!r}, expected PASS")
    if receipt.get("canonical_admission_rule") != "ACCEPTED_ONLY":
        errors.append("canonical admission rule must be ACCEPTED_ONLY")
    if receipt.get("legacy_aliases") != {"approved": "accepted"}:
        errors.append("legacy review alias contract drift")
    if receipt.get("problems") not in ([], tuple()):
        errors.append("review quarantine receipt contains problems")

    raw = receipt.get("raw_counts")
    accepted = receipt.get("accepted_input_counts")
    quarantined = receipt.get("quarantined_input_counts")
    if not isinstance(raw, Mapping):
        errors.append("raw_counts object is required")
        raw = {}
    if not isinstance(accepted, Mapping):
        errors.append("accepted_input_counts object is required")
        accepted = {}
    if not isinstance(quarantined, Mapping):
        errors.append("quarantined_input_counts object is required")
        quarantined = {}

    accepted_counts: dict[str, int] = {}
    q_sum = 0
    for key in ("assets", "events", "alerts"):
        r = _nonnegative_int(raw.get(key), f"raw_counts.{key}", errors)
        a = _nonnegative_int(accepted.get(key), f"accepted_input_counts.{key}", errors)
        q = _nonnegative_int(quarantined.get(key), f"quarantined_input_counts.{key}", errors)
        accepted_counts[key] = a
        q_sum += q
        if r != a + q:
            errors.append(f"{key} review arithmetic does not close: raw={r}, accepted={a}, quarantined={q}")
    q_total = _nonnegative_int(quarantined.get("total"), "quarantined_input_counts.total", errors)
    if q_total != q_sum:
        errors.append(f"quarantined total={q_total} != per-kind sum={q_sum}")

    items = receipt.get("quarantined")
    if not isinstance(items, list):
        errors.append("quarantined list is required")
        items = []
    if len(items) != q_total:
        errors.append(f"quarantined item count={len(items)} != declared total={q_total}")
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            errors.append(f"quarantined[{index}] must be an object")
            continue
        if item.get("review_status") not in {"needs_review", "rejected", "blocked"}:
            errors.append(f"quarantined[{index}] has invalid review state")
        if not isinstance(item.get("record_id"), str) or not item["record_id"]:
            errors.append(f"quarantined[{index}] missing stable record_id")

    invariants = receipt.get("invariants")
    if not isinstance(invariants, Mapping) or not invariants:
        errors.append("quarantine invariants object is required")
    else:
        for key, value in invariants.items():
            if value is not True:
                errors.append(f"producer quarantine invariant {key} is not true")
    return q_total, accepted_counts


def validate_review_quarantine_package(
    package_root: str | Path,
    *,
    certification: bool,
) -> ReviewQuarantineValidation:
    root = Path(package_root)
    receipt_path = root / "outputs" / "review_quarantine_receipt.json"
    if not receipt_path.is_file():
        if certification:
            raise ReviewQuarantineError("missing outputs/review_quarantine_receipt.json")
        return ReviewQuarantineValidation(
            state="UNVERIFIED_LEGACY_AUDIT",
            promotable=False,
            quarantined_total=0,
            canonical_primary_counts={},
        )

    errors: list[str] = []
    receipt = _json(receipt_path, "review quarantine receipt")
    q_total, accepted_counts = _validate_receipt(receipt, errors)
    _validate_scope(root, errors)

    manifest = _json(root / "outputs" / "federation" / "manifest.json", "canonical manifest")
    if manifest.get("review_quarantine_policy") != POLICY_VERSION:
        errors.append("canonical manifest review_quarantine_policy mismatch")

    entities = _jsonl(root / "outputs" / "federation" / "entities.jsonl", "entities")
    relationships = _jsonl(root / "outputs" / "federation" / "relationships.jsonl", "relationships")
    alerts = _jsonl(root / "outputs" / "federation" / "alerts.jsonl", "alerts")

    entity_ids: set[str] = set()
    primary_counts = {"assets": 0, "events": 0, "alerts": len(alerts)}
    for index, entity in enumerate(entities):
        eid = entity.get("entity_id")
        if not isinstance(eid, str) or not eid:
            errors.append(f"entities[{index}] missing entity_id")
            continue
        if eid in entity_ids:
            errors.append(f"duplicate canonical entity_id: {eid}")
        entity_ids.add(eid)
        etype = entity.get("entity_type")
        if etype not in {"utility_asset", "service_event"}:
            continue
        key = "assets" if etype == "utility_asset" else "events"
        primary_counts[key] += 1
        attrs = entity.get("attributes")
        if not isinstance(attrs, Mapping):
            errors.append(f"{etype} {eid} missing review attributes")
            continue
        if attrs.get("review_status") != "accepted":
            errors.append(f"{etype} {eid} is not accepted")
        if attrs.get("promotion_eligible") is not True:
            errors.append(f"{etype} {eid} is not promotion_eligible=true")
        if not isinstance(attrs.get("review_status_raw"), str) or not attrs["review_status_raw"]:
            errors.append(f"{etype} {eid} missing review_status_raw")

    for key in ("assets", "events"):
        if primary_counts[key] != accepted_counts.get(key, 0):
            errors.append(
                f"canonical {key} count={primary_counts[key]} != accepted input count={accepted_counts.get(key, 0)}"
            )

    for index, alert in enumerate(alerts):
        attrs = alert.get("attributes")
        if not isinstance(attrs, Mapping):
            errors.append(f"alerts[{index}] missing review attributes")
            continue
        if attrs.get("review_status") != "accepted":
            errors.append(f"alerts[{index}] is not accepted")
        if attrs.get("promotion_eligible") is not True:
            errors.append(f"alerts[{index}] is not promotion_eligible=true")
        if alert.get("is_critical") is True and attrs.get("review_status") != "accepted":
            errors.append(f"alerts[{index}] critical promotion without accepted review")
    if len(alerts) != accepted_counts.get("alerts", 0):
        errors.append(
            f"canonical alerts count={len(alerts)} != accepted input count={accepted_counts.get('alerts', 0)}"
        )

    for index, relationship in enumerate(relationships):
        left = relationship.get("source_entity_id")
        right = relationship.get("target_entity_id")
        if left not in entity_ids or right not in entity_ids:
            errors.append(f"relationships[{index}] endpoint is outside retained canonical entity set")

    if errors:
        raise ReviewQuarantineError("; ".join(errors))
    return ReviewQuarantineValidation(
        state="PASS",
        promotable=certification,
        quarantined_total=q_total,
        canonical_primary_counts=primary_counts,
    )

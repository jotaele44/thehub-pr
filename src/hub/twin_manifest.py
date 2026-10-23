"""Validation and reconciliation for the two Twin capability manifests.

``federation/twin/TWIN_OBSERVED_CAPABILITY_MANIFEST_V1.json`` holds every
element observed in the Twin reference application (the operator's frame
census). ``federation/twin/FEDERATION_TWIN_DERIVED_EXTENSION_MANIFEST_V1.json``
holds Federation-native extensions inspired by it. The two denominators must
never mix: a derived entry is never a Twin capability, and the observed
census closes only when every one of its rows carries an explicit, evidenced
disposition.

The ``reconciliation`` block in each manifest is derived from the rows by
:func:`reconcile_observed` / :func:`reconcile_derived`; it is written by
``scripts/validate_twin_manifests.py --write`` and never typed by hand.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import jsonschema

OBSERVED_TOTAL_EXPECTED = 223

IN_SCOPE_REPOS = frozenset(
    {"thehub-pr", "ovnis-pr", "spiderweb-pr", "skywatcher-pr", "aguayluz-pr", "moneysweep-pr"}
)

# delivery_state values that claim work inside run 1 (Phases 1-3).
RUN1_DELIVERY_STATES = frozenset({"SCHEDULED_THIS_RUN", "PARTIAL_THIS_RUN", "IMPLEMENTED_THIS_RUN"})
RUN1_PHASES = frozenset({1, 2, 3})
# Run 2 (Phase 4, OVNIS; Phase 5, Spiderweb). Each run's states may only be
# claimed by rows of that run's phases, so a later run never rewrites what an
# earlier run delivered.
RUN2_DELIVERY_STATES = frozenset({"SCHEDULED_RUN_2", "PARTIAL_RUN_2", "IMPLEMENTED_RUN_2"})
RUN2_PHASES = frozenset({4, 5})
RUN_PHASES: Mapping[str, frozenset] = {
    **{state: RUN1_PHASES for state in RUN1_DELIVERY_STATES},
    **{state: RUN2_PHASES for state in RUN2_DELIVERY_STATES},
}
IMPLEMENTED_STATES = frozenset({"IMPLEMENTED_THIS_RUN", "IMPLEMENTED_RUN_2"})

# implementation_status -> the delivery_state values it may carry.
_ALLOWED_DELIVERY: Mapping[str, frozenset] = {
    "EXISTING": frozenset({"ALREADY_PRESENT"}),
    "NOT_APPLICABLE": frozenset({"NOT_APPLICABLE"}),
    "BLOCKED": frozenset({"BLOCKED"}),
    "EXTEND": RUN1_DELIVERY_STATES | RUN2_DELIVERY_STATES | {"DEFERRED"},
    "NEW": RUN1_DELIVERY_STATES | RUN2_DELIVERY_STATES | {"DEFERRED"},
}

OBSERVED_RELPATH = Path("federation/twin/TWIN_OBSERVED_CAPABILITY_MANIFEST_V1.json")
DERIVED_RELPATH = Path("federation/twin/FEDERATION_TWIN_DERIVED_EXTENSION_MANIFEST_V1.json")
OBSERVED_SCHEMA_RELPATH = Path("schemas/federation/twin_observed_capability_manifest.v1.schema.json")
DERIVED_SCHEMA_RELPATH = Path("schemas/federation/federation_twin_derived_extension_manifest.v1.schema.json")


def _load(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be an object")
    return data


def _schema_errors(doc: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> List[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{label}: schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]


def _disposition_errors(row: Mapping[str, Any], label: str) -> List[str]:
    """Rules shared by observed and derived rows."""
    errors: List[str] = []
    status = row.get("implementation_status")
    delivery = row.get("delivery_state")
    repo = row.get("canonical_repo")
    if repo not in IN_SCOPE_REPOS:
        errors.append(f"{label}: canonical_repo {repo!r} is not an in-scope Federation repo")
    allowed = _ALLOWED_DELIVERY.get(str(status))
    if allowed is not None and delivery not in allowed:
        errors.append(f"{label}: delivery_state {delivery!r} is inconsistent with implementation_status {status!r}")
    if status == "NOT_APPLICABLE" and not str(row.get("rationale") or "").strip():
        errors.append(f"{label}: NOT_APPLICABLE requires a rationale")
    if status == "BLOCKED" and not str(row.get("blocker") or "").strip():
        errors.append(f"{label}: BLOCKED requires a blocker")
    if status in ("EXISTING", "EXTEND") and not str(row.get("existing_equivalent") or "").strip():
        errors.append(f"{label}: {status} requires an existing_equivalent path")
    run_phases = RUN_PHASES.get(str(delivery))
    if run_phases is not None and row.get("phase") not in run_phases:
        run = "run-1" if delivery in RUN1_DELIVERY_STATES else "run-2"
        errors.append(f"{label}: delivery_state {delivery!r} claims {run} work but phase is {row.get('phase')!r}")
    return errors


def validate_observed(doc: Mapping[str, Any], schema: Optional[Mapping[str, Any]] = None) -> List[str]:
    """Return every rule violation in the observed manifest (empty list = valid)."""
    errors: List[str] = []
    if schema is not None:
        errors.extend(_schema_errors(doc, schema, "observed"))
    rows = doc.get("capabilities")
    if not isinstance(rows, list):
        return errors + ["observed: capabilities must be a list"]
    if len(rows) != OBSERVED_TOTAL_EXPECTED:
        errors.append(f"observed: expected {OBSERVED_TOTAL_EXPECTED} rows, found {len(rows)}")
    seen_ids = Counter(r.get("capability_id") for r in rows if isinstance(r, dict))
    for cid, count in seen_ids.items():
        if count > 1:
            errors.append(f"observed: duplicate capability_id {cid!r}")
    numbers = [r.get("census_number") for r in rows if isinstance(r, dict)]
    if numbers != list(range(1, len(numbers) + 1)):
        errors.append("observed: census_number must run 1..N contiguously in order")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("observed: every capability must be an object")
            continue
        label = f"observed {row.get('capability_id')}"
        number = row.get("census_number")
        if isinstance(number, int) and row.get("capability_id") != "TWIN-%03d" % number:
            errors.append(f"{label}: capability_id does not match census_number {number}")
        if row.get("reference") != "TWIN":
            errors.append(f"{label}: reference must be TWIN")
        if row.get("evidence_status") not in ("RECORDED", "LIVE_VERIFIED", "INFERRED_FROM_LABEL"):
            errors.append(f"{label}: evidence_status {row.get('evidence_status')!r} cannot be counted as observed")
        if row.get("producer") != row.get("canonical_repo"):
            errors.append(f"{label}: producer must equal canonical_repo (exactly one canonical owner)")
        if row.get("implementation_status") == "NEW" and "search_terms_without_equivalent" not in row:
            errors.append(f"{label}: NEW requires search_terms_without_equivalent")
        if row.get("delivery_state") in IMPLEMENTED_STATES and not row.get("tests"):
            errors.append(f"{label}: {row.get('delivery_state')} requires tests")
        errors.extend(_disposition_errors(row, label))
    for module in doc.get("unrecorded_bundle_modules") or []:
        if module.get("counted_in_denominator") is not False or module.get("evidence_status") != "NOT_OBSERVED":
            errors.append(f"observed: unrecorded bundle module {module.get('file')!r} must stay NOT_OBSERVED and uncounted")
    return errors


def validate_derived(
    doc: Mapping[str, Any],
    observed_elements: Sequence[str] = (),
    schema: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Return every rule violation in the derived manifest (empty list = valid).

    ``observed_elements`` are the observed manifest's element names; a derived
    entry (or alias) repeating one would silently promote a derived capability
    into the observed denominator, so it is rejected.
    """
    errors: List[str] = []
    if schema is not None:
        errors.extend(_schema_errors(doc, schema, "derived"))
    rows = doc.get("capabilities")
    if not isinstance(rows, list):
        return errors + ["derived: capabilities must be a list"]
    observed_names = {str(e).strip().casefold() for e in observed_elements}
    names: Counter = Counter()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append("derived: every capability must be an object")
            continue
        label = f"derived {row.get('capability_id')}"
        if row.get("capability_id") != "FDX-%03d" % index:
            errors.append(f"{label}: capability_id must be FDX-{index:03d} (contiguous)")
        if row.get("origin") != "FEDERATION_DERIVED":
            errors.append(f"{label}: origin must be FEDERATION_DERIVED")
        for name in [row.get("name")] + list(row.get("aliases") or []):
            key = str(name or "").strip().casefold()
            names[key] += 1
            if key in observed_names:
                errors.append(f"{label}: {name!r} duplicates an observed Twin element")
        errors.extend(_disposition_errors(row, label))
    for key, count in names.items():
        if count > 1:
            errors.append(f"derived: name or alias {key!r} appears {count} times")
    return errors


def _counts(rows: Sequence[Mapping[str, Any]], key: str) -> Dict[str, int]:
    return dict(sorted(Counter(str(r.get(key)) for r in rows).items()))


def reconcile_observed(doc: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive the observed denominator block from the rows."""
    rows = [r for r in doc.get("capabilities") or [] if isinstance(r, dict)]
    status = Counter(r.get("implementation_status") for r in rows)
    accounted = sum(status[s] for s in _ALLOWED_DELIVERY)
    return {
        "OBSERVED_TOTAL": len(rows),
        "ACCOUNTED_FOR": accounted,
        "UNACCOUNTED": len(rows) - accounted,
        "EXISTING": status["EXISTING"],
        "EXTEND": status["EXTEND"],
        "NEW": status["NEW"],
        "NOT_APPLICABLE": status["NOT_APPLICABLE"],
        "BLOCKED": status["BLOCKED"],
        "by_evidence_status": _counts(rows, "evidence_status"),
        "by_canonical_repo": _counts(rows, "canonical_repo"),
        "by_phase": _counts(rows, "phase"),
        "by_delivery_state": _counts(rows, "delivery_state"),
        "census_closed": len(rows) == OBSERVED_TOTAL_EXPECTED and accounted == OBSERVED_TOTAL_EXPECTED,
    }


def reconcile_derived(doc: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive the Federation-derived denominator block from the rows."""
    rows = [r for r in doc.get("capabilities") or [] if isinstance(r, dict)]
    delivery = Counter(r.get("delivery_state") for r in rows)
    return {
        "FEDERATION_DERIVED_TOTAL": len(rows),
        "DERIVED_IMPLEMENTED": delivery["IMPLEMENTED_THIS_RUN"],
        "DERIVED_PARTIAL": delivery["PARTIAL_THIS_RUN"],
        "DERIVED_SCHEDULED": delivery["SCHEDULED_THIS_RUN"],
        "DERIVED_ALREADY_PRESENT": delivery["ALREADY_PRESENT"],
        "DERIVED_BLOCKED": delivery["BLOCKED"],
        "DERIVED_DEFERRED": delivery["DEFERRED"],
        "DERIVED_IMPLEMENTED_RUN_2": delivery["IMPLEMENTED_RUN_2"],
        "DERIVED_PARTIAL_RUN_2": delivery["PARTIAL_RUN_2"],
        "DERIVED_SCHEDULED_RUN_2": delivery["SCHEDULED_RUN_2"],
        "by_implementation_status": _counts(rows, "implementation_status"),
        "by_canonical_repo": _counts(rows, "canonical_repo"),
        "by_phase": _counts(rows, "phase"),
        "by_enumeration_source": _counts(rows, "enumeration_source"),
    }


def check_repo(root: Path, write: bool = False) -> List[str]:
    """Validate both manifests under ``root``; optionally rewrite reconciliation blocks.

    Returns the list of errors. With ``write=True`` the reconciliation blocks
    are refreshed from the rows first, so only row-level errors remain.
    """
    observed_path = root / OBSERVED_RELPATH
    derived_path = root / DERIVED_RELPATH
    observed = _load(observed_path)
    derived = _load(derived_path)
    errors = validate_observed(observed, _load(root / OBSERVED_SCHEMA_RELPATH))
    elements = [str(r.get("element")) for r in observed.get("capabilities") or [] if isinstance(r, dict)]
    errors += validate_derived(derived, elements, _load(root / DERIVED_SCHEMA_RELPATH))

    for doc, path, reconcile in (
        (observed, observed_path, reconcile_observed),
        (derived, derived_path, reconcile_derived),
    ):
        expected = reconcile(doc)
        if write:
            if doc.get("reconciliation") != expected:
                doc["reconciliation"] = expected
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif doc.get("reconciliation") != expected:
            errors.append(f"{path.name}: reconciliation block is stale; run scripts/validate_twin_manifests.py --write")
    if not reconcile_observed(observed)["census_closed"]:
        errors.append("observed: census is not closed (OBSERVED_TOTAL/ACCOUNTED_FOR must both equal 223)")
    return errors

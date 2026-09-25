"""FEDERATION_EPISTEMIC_STATE_CONTRACT_V1 — the Hub's runtime vocabulary.

Every Federation object answers, independently:

* what stage it is at (``data_stage``) and how it came to be known
  (``epistemic_class``: MEASURED / COMPUTED / CURATED / INTERPRETIVE);
* how certain its identity is (``identity_state``), at which scope;
* whether its source is bound (``source_state``);
* how current it is (``temporal_state``) and how precisely it is dated
  (``temporal_precision``);
* whether something was observed present, observed absent, or simply not
  observed (``observation_state``);
* how precise its geometry is (``geometry_precision``).

The axes never collapse into one another, and every derivation here fails
closed: a value the Hub cannot establish from producer-declared evidence
becomes the axis sentinel (``UNCLASSIFIED`` / ``UNKNOWN`` / ``UNRESOLVED``),
never a guess. Each derivation returns ``(value, basis)`` so the reason for a
value is always inspectable.

The JSON Schema mirror is ``schemas/federation/epistemic_state.v1.schema.json``;
``tests/test_epistemic_state.py`` keeps the two enumerations identical.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .identity_adjudication import WEAK_CORRELATION_BASES, evidence_class

CONTRACT_ID = "federation-evidence-state-v1"
CONTRACT_STATUS = "CANDIDATE"

DATA_STAGES = (
    "RAW", "NORMALIZED", "CANONICAL", "EVIDENCE_CLASSIFICATION", "FINDING",
    "COMPUTATION", "INTERPRETATION", "REPORT", "UNKNOWN",
)
EPISTEMIC_CLASSES = ("MEASURED", "COMPUTED", "CURATED", "INTERPRETIVE", "UNCLASSIFIED")
EPISTEMIC_CLASS_BASES = ("PRODUCER_DECLARED", "HUB_CROSSWALK", "NONE")
IDENTITY_STATES = ("BOUND", "CANDIDATE", "UNRESOLVED", "CONFLICTING")
IDENTITY_SCOPES = ("PRODUCER_LOCAL", "FEDERATION")
SOURCE_STATES = ("SOURCE_BOUND", "SOURCE_REPORTED", "SOURCE_MISSING", "SOURCE_BLOCKED")
TEMPORAL_STATES = ("LIVE", "CURRENT", "STALE", "HISTORICAL", "UNKNOWN")
TEMPORAL_PRECISIONS = (
    "EXACT_TIMESTAMP", "BOUNDED_INTERVAL", "DATE_ONLY", "MONTH_YEAR", "YEAR_ONLY", "APPROXIMATE", "UNKNOWN",
)
OBSERVATION_STATES = ("OBSERVED_PRESENT", "OBSERVED_ABSENT", "NOT_OBSERVED", "UNKNOWN")
GEOMETRY_PRECISIONS = (
    "OBSERVED_POINT", "INTERPRETED_POINT", "AREA_REFERENCE", "REPRESENTATIVE_POINT", "UNKNOWN",
)
EDGE_STATES = ("DOCUMENTED", "COMPUTED", "CANDIDATE", "CONFLICTING", "REJECTED", "UNKNOWN")
CONTRADICTION_STATES = ("OPEN", "NARROWED", "RESOLVED", "SUPERSEDED", "UNRESOLVABLE")

# Spiderweb `coordinate_method` (schemas/federation_spatial_feature_v1) → precision.
# Only unambiguous methods are mapped; anything else is UNKNOWN.
COORDINATE_METHOD_PRECISION: Mapping[str, str] = {
    "EXACT": "OBSERVED_POINT",
    "SURVEYED": "OBSERVED_POINT",
    "AUTHORITATIVE": "OBSERVED_POINT",
    "GEOCODED_ROOFTOP": "INTERPRETED_POINT",
    "GEOCODED_PARCEL": "INTERPRETED_POINT",
    "GEOCODED_STREET": "INTERPRETED_POINT",
    "INFERRED": "INTERPRETED_POINT",
    "INTERPOLATED": "INTERPRETED_POINT",
    "LINKED_ASSET": "INTERPRETED_POINT",
    "GEOCODED_LOCALITY": "REPRESENTATIVE_POINT",
    "DERIVED_CENTROID": "REPRESENTATIVE_POINT",
    "DERIVED_AVERAGE": "REPRESENTATIVE_POINT",
    "FIRST_VERTEX": "REPRESENTATIVE_POINT",
}

# Producer/provenance.v1 `date_precision` → temporal precision.
DATE_PRECISION_MAP: Mapping[str, str] = {
    "day": "DATE_ONLY",
    "month": "MONTH_YEAR",
    "year": "YEAR_ONLY",
    "uncertain_range": "BOUNDED_INTERVAL",
}

# Source rows whose type/ref says there is no document behind them.
_NO_SOURCE_TOKENS = frozenset({"", "none", "null", "unknown", "n/a", "na"})
_BLOCKED_SOURCE_STATUSES = frozenset({"blocked", "unavailable"})

# Relationship bases that can never, alone, make an edge DOCUMENTED or COMPUTED
# (entity_resolution.v1 forbidden reason codes + hub weak correlation bases).
FORBIDDEN_SOLE_EDGE_BASES = frozenset(
    set(WEAK_CORRELATION_BASES)
    | {
        "similar_name", "shared_address", "shared_coordinates", "co_occurrence", "embedding_similarity",
        "spatial_proximity", "proximity", "co_location", "temporal_proximity", "temporal_adjacency",
        "name_similarity",
    }
)

_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_YEAR_RE = re.compile(r"^\d{4}$")

Basis = Tuple[str, str]


def as_mapping(value: Any) -> Mapping[str, Any]:
    """``value`` when it is a mapping, else an empty mapping (tolerates malformed rows)."""
    return value if isinstance(value, Mapping) else {}


def declared(row: Mapping[str, Any]) -> Dict[str, Any]:
    """The producer's additive ``evidence_state`` declaration (empty if absent/malformed)."""
    value = row.get("evidence_state")
    return dict(value) if isinstance(value, Mapping) else {}


def pick(value: Any, allowed: Tuple[str, ...], fallback: str, errors: Optional[List[str]] = None,
         field: str = "") -> str:
    """Return ``value`` when it is one of ``allowed``; otherwise the fail-closed ``fallback``.

    An invalid, non-empty value is reported into ``errors`` (never silently trusted).
    """
    if isinstance(value, str) and value in allowed:
        return value
    if value not in (None, "") and errors is not None:
        errors.append(f"{field}: {value!r} is not a valid value")
    return fallback


# ── epistemic class / stage ───────────────────────────────────────────────────


def epistemic_class_for(row: Mapping[str, Any], *, hub_computed: bool = False,
                        errors: Optional[List[str]] = None) -> Basis:
    """(class, basis). Producer declaration wins; hub-derived rows are COMPUTED; else UNCLASSIFIED."""
    decl = declared(row)
    value = pick(decl.get("epistemic_class"), EPISTEMIC_CLASSES, "UNCLASSIFIED", errors, "epistemic_class")
    if value != "UNCLASSIFIED":
        if value == "INTERPRETIVE" and not str(decl.get("interpretation_basis") or "").strip():
            if errors is not None:
                errors.append("epistemic_class: INTERPRETIVE requires interpretation_basis")
            return "UNCLASSIFIED", "NONE"
        return value, "PRODUCER_DECLARED"
    if hub_computed:
        return "COMPUTED", "PRODUCER_DECLARED"
    return "UNCLASSIFIED", "NONE"


def data_stage_for(row: Mapping[str, Any], *, hub_computed: bool = False,
                   errors: Optional[List[str]] = None) -> str:
    value = pick(declared(row).get("data_stage"), DATA_STAGES, "", errors, "data_stage")
    if value:
        return value
    return "COMPUTATION" if hub_computed else "CANONICAL"


# ── geometry ──────────────────────────────────────────────────────────────────


def _coords(row: Mapping[str, Any]) -> Optional[Tuple[float, float]]:
    location = as_mapping(row.get("location"))
    lat = location.get("lat", row.get("latitude"))
    lon = location.get("lon", row.get("longitude"))
    try:
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _area(row: Mapping[str, Any]) -> Optional[str]:
    location = as_mapping(row.get("location"))
    value = location.get("municipality") or row.get("municipality")
    return str(value) if value not in (None, "") else None


def geometry_for(row: Mapping[str, Any], errors: Optional[List[str]] = None) -> Dict[str, Any]:
    """Geometry, its precision and the basis. Never promotes precision.

    Precedence: a producer-declared precision (validated against its declared
    coordinate method) → a crosswalked ``coordinate_method`` → an area-only
    reference → UNKNOWN for a bare coordinate pair of undeclared derivation.
    """
    decl = declared(row)
    attributes = as_mapping(row.get("attributes"))
    method = decl.get("coordinate_method") or attributes.get("coordinate_method")
    method = str(method).upper() if method else None
    method_precision = COORDINATE_METHOD_PRECISION.get(method) if method else None
    coords = _coords(row)
    area = _area(row)
    geometry = {"type": "Point", "coordinates": [coords[1], coords[0]]} if coords else None

    declared_value = pick(decl.get("geometry_precision"), GEOMETRY_PRECISIONS, "", errors, "geometry_precision")
    if declared_value:
        promotes = (
            declared_value == "OBSERVED_POINT"
            and method_precision is not None
            and method_precision != "OBSERVED_POINT"
        )
        needs_point = declared_value in ("OBSERVED_POINT", "INTERPRETED_POINT", "REPRESENTATIVE_POINT")
        if promotes:
            if errors is not None:
                errors.append(f"geometry_precision: OBSERVED_POINT contradicts coordinate_method {method}")
        elif needs_point and geometry is None:
            if errors is not None:
                errors.append(f"geometry_precision: {declared_value} declared without coordinates")
        else:
            basis = f"producer declared {declared_value}" + (f" (coordinate_method {method})" if method else "")
            return {"geometry": geometry, "geometry_precision": declared_value, "geometry_basis": basis, "area_reference": area}

    if geometry is not None and method_precision:
        return {"geometry": geometry, "geometry_precision": method_precision,
                "geometry_basis": f"coordinate_method {method}", "area_reference": area}
    if geometry is None and area:
        return {"geometry": None, "geometry_precision": "AREA_REFERENCE",
                "geometry_basis": f"area reference only ({area})", "area_reference": area}
    if geometry is not None:
        return {"geometry": geometry, "geometry_precision": "UNKNOWN",
                "geometry_basis": "coordinates without a declared derivation method", "area_reference": area}
    return {"geometry": None, "geometry_precision": "UNKNOWN", "geometry_basis": "no geometry", "area_reference": None}


# ── time ──────────────────────────────────────────────────────────────────────


def parse_instant(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 instant; naive values are taken as UTC. Dates-only return None."""
    if not isinstance(value, str) or "T" not in value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def truncate_to_precision(value: str, precision: str) -> str:
    """Render a date/time at exactly its precision (a date never acquires a time)."""
    length = {"DATE_ONLY": 10, "MONTH_YEAR": 7, "YEAR_ONLY": 4}.get(precision)
    return value[:length] if length else value


def temporal_for(row: Mapping[str, Any], errors: Optional[List[str]] = None) -> Dict[str, Any]:
    """observed_at at its true precision, plus the precision and its basis.

    A producer-padded timestamp (e.g. ``1929-01-01T00:00:00-04:00`` for a
    year-only case) is rendered at the declared precision; the raw value is kept
    in the basis so nothing is hidden.
    """
    decl = declared(row)
    raw_observed = row.get("observed_at") or row.get("start_at")
    date_local = row.get("date_local")
    declared_value = pick(decl.get("temporal_precision"), TEMPORAL_PRECISIONS, "", errors, "temporal_precision")
    mapped = DATE_PRECISION_MAP.get(str(row.get("date_precision") or ""))

    if declared_value:
        precision, basis = declared_value, "producer declared"
    elif mapped:
        precision, basis = mapped, f"date_precision={row.get('date_precision')}"
    elif isinstance(date_local, str) and _YEAR_RE.match(date_local):
        precision, basis = "YEAR_ONLY", "date_local pattern YYYY"
    elif isinstance(date_local, str) and _MONTH_RE.match(date_local):
        precision, basis = "MONTH_YEAR", "date_local pattern YYYY-MM"
    elif isinstance(date_local, str) and _DATE_ONLY_RE.match(date_local):
        precision, basis = "DATE_ONLY", "date_local pattern YYYY-MM-DD"
    elif raw_observed:
        precision, basis = "UNKNOWN", "timestamp without a declared precision (may be padded)"
    else:
        precision, basis = "UNKNOWN", "no observation time"

    source_value = date_local if isinstance(date_local, str) and date_local else raw_observed
    observed_at = truncate_to_precision(str(source_value), precision) if source_value else None
    if raw_observed and observed_at != raw_observed:
        basis += f"; producer timestamp {raw_observed} not asserted at that precision"
    return {"observed_at": observed_at, "temporal_precision": precision, "temporal_basis": basis}


def temporal_state_at(row: Mapping[str, Any], now: datetime) -> Basis:
    """(state, basis) at ``now``. LIVE/STALE need a declared cadence; otherwise never guessed."""
    decl = declared(row)
    valid_to = parse_instant(decl.get("valid_to") or row.get("end_at"))
    valid_from = parse_instant(decl.get("valid_from") or row.get("start_at"))
    retrieved = parse_instant(row.get("extracted_at"))
    observed = parse_instant(row.get("observed_at"))
    cadence = decl.get("expected_cadence_seconds")

    if valid_to is not None and valid_to < now:
        return "HISTORICAL", "valid_to is in the past"
    if isinstance(cadence, (int, float)) and cadence > 0 and not isinstance(cadence, bool):
        latest = observed or retrieved
        if latest is None:
            return "UNKNOWN", "cadence declared but no observation or retrieval time"
        age = (now - latest).total_seconds()
        if age <= cadence:
            return ("LIVE" if decl.get("live_feed") is True else "CURRENT"), f"age {int(age)}s ≤ cadence {int(cadence)}s"
        return "STALE", f"age {int(age)}s > cadence {int(cadence)}s"
    if valid_from is not None and valid_from <= now and valid_to is not None:
        return "CURRENT", "inside declared validity window"
    if row.get("observed_at") or row.get("date_local"):
        return "HISTORICAL", "dated observation of a past moment (no cadence declared)"
    return "UNKNOWN", "no validity window or cadence declared"


# ── source ────────────────────────────────────────────────────────────────────


def has_locator(source: Mapping[str, Any]) -> bool:
    for key in ("source_url", "source_ref", "archive_locator", "url"):
        value = str(source.get(key) or "").strip().lower()
        if value and value not in _NO_SOURCE_TOKENS:
            return True
    return False


def source_state_for(row: Mapping[str, Any], sources_index: Mapping[str, Mapping[str, Any]]) -> Basis:
    """(state, basis). A cited source missing from the Hub index is REPORTED, not MISSING.

    The Hub's index may be partial (capped aggregates), so an unresolved
    reference proves only that the Hub cannot bind it — not that no source exists.
    """
    ref = row.get("source_id") or row.get("evidence_source_id")
    if not ref:
        if has_locator(row):
            return "SOURCE_REPORTED", "row carries a citation but no source record id"
        return "SOURCE_MISSING", "no source reference"
    source = sources_index.get(str(ref))
    if source is None:
        return "SOURCE_REPORTED", f"source {ref} cited but not resolvable in the Hub index"
    if str(source.get("status") or "").lower() in _BLOCKED_SOURCE_STATUSES:
        return "SOURCE_BLOCKED", f"source {ref} status={source.get('status')}"
    if has_locator(source):
        return "SOURCE_BOUND", f"source {ref} resolves with a locator"
    return "SOURCE_REPORTED", f"source {ref} resolves but has no retrievable locator"


# ── observation ───────────────────────────────────────────────────────────────


def observation_state_for(row: Mapping[str, Any], errors: Optional[List[str]] = None) -> Basis:
    """(state, basis). Only a producer declaration sets it; OBSERVED_ABSENT needs an absence basis."""
    decl = declared(row)
    value = pick(decl.get("observation_state"), OBSERVATION_STATES, "UNKNOWN", errors, "observation_state")
    if value == "OBSERVED_ABSENT":
        basis = str(decl.get("observation_absence_basis") or "").strip()
        if not basis:
            if errors is not None:
                errors.append("observation_state: OBSERVED_ABSENT requires observation_absence_basis")
            return "NOT_OBSERVED", "absence declared without a coverage basis; treated as not observed"
        return value, f"producer declared absence ({basis})"
    if value == "UNKNOWN":
        return value, "no producer observation declaration"
    return value, "producer declared"


# ── identity ──────────────────────────────────────────────────────────────────

_BINDING_MATCH_CLASSES = frozenset({"EXACT_IDENTIFIER", "EXPLICIT_CROSSWALK", "REVIEWED_MATCH"})


def identity_for(row: Mapping[str, Any], membership: Optional[Mapping[str, Any]] = None,
                 errors: Optional[List[str]] = None) -> Dict[str, str]:
    """Identity state/scope/basis. Fails closed to UNRESOLVED.

    ``membership`` is an optional identity-registry view
    ``{"state": ADJUDICATION_STATE, "match_class": ..., "conflicting": bool}``.
    """
    if membership:
        if membership.get("conflicting"):
            state, basis = "CONFLICTING", "registry holds a contradicting assertion"
        elif membership.get("state") == "RESOLVED" and membership.get("match_class") in _BINDING_MATCH_CLASSES:
            state, basis = "BOUND", f"registry RESOLVED via {membership.get('match_class')}"
        elif membership.get("state") == "CANDIDATE":
            state, basis = "CANDIDATE", "registry candidate (not an identity decision)"
        else:
            state, basis = "UNRESOLVED", f"registry state {membership.get('state')!r} does not bind identity"
        return {"identity_state": state, "identity_scope": "FEDERATION", "identity_basis": basis}
    value = pick(declared(row).get("identity_state"), IDENTITY_STATES, "UNRESOLVED", errors, "identity_state")
    basis = "producer declared" if value != "UNRESOLVED" or declared(row).get("identity_state") else "no identity adjudication"
    return {"identity_state": value, "identity_scope": "PRODUCER_LOCAL", "identity_basis": basis}


# ── relationships ─────────────────────────────────────────────────────────────


def edge_state_for(row: Mapping[str, Any], *, hub_computed: bool, source_state: str) -> Basis:
    """(edge_state, basis) for a relationship row.

    Hub correlations are discovery signals: a weak basis (name, location,
    temporal proximity) stays CANDIDATE; a shared external identifier is
    COMPUTED (still not identity). A producer-asserted relationship is
    DOCUMENTED only when its source is bound.
    """
    basis = str(row.get("match_basis") or "")
    if hub_computed:
        klass = evidence_class(basis or None)
        if basis in FORBIDDEN_SOLE_EDGE_BASES or klass == "WEAK_CORRELATION":
            return "CANDIDATE", f"hub correlation on weak basis {basis!r} (not a relationship claim)"
        if klass == "HARD_IDENTIFIER_CANDIDATE":
            return "COMPUTED", f"hub correlation on shared identifier {basis!r} (not identity)"
        return "UNKNOWN", f"hub correlation basis {basis or 'unspecified'!r}"
    if basis in FORBIDDEN_SOLE_EDGE_BASES:
        return "CANDIDATE", f"producer relationship on weak basis {basis!r}"
    if source_state == "SOURCE_BOUND":
        return "DOCUMENTED", "producer-asserted relationship with a bound source"
    return "UNKNOWN", f"producer-asserted relationship; source state {source_state}"

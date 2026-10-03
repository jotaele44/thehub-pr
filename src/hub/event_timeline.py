"""Event timeline over the OVNIS case corpus (TWIN-180…200, directive §13).

Pure and read-only. OVNIS owns the event corpus; the Hub orders the case
observations its store already holds and renders them. Nothing is inferred:

* A date is shown exactly as the producer recorded it. A year-only case stays a
  year, and no day, month or time is invented to sort or display it.
* Geography is source-bounded: the municipality when the source gives one,
  otherwise the source's own location text. Coordinates are never required.
* A case with no parseable date is kept and counted as undated, never dropped.
* Findings attach only through records OVNIS publishes. Until it publishes
  any, ``findings_status`` says so instead of showing an empty mode as a result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from . import epistemic as ep

CONTRACT_ID = "federation-event-timeline-v1"
PRODUCER = "ovnis-pr"
OBSERVATION_TYPE = "uap_case"
SORTS = ("oldest", "newest")
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_PRECISION_FROM_DATE = {1: "YEAR_ONLY", 2: "MONTH_YEAR", 3: "DATE_ONLY"}
_LEGACY_PRECISION = {"year": "YEAR_ONLY", "month": "MONTH_YEAR", "day": "DATE_ONLY"}
# Coarser first: on the same start, "1967" sorts before "1967-03" before "1967-03-02".
_PRECISION_RANK = {"YEAR_ONLY": 0, "MONTH_YEAR": 1, "DATE_ONLY": 2, "EXACT_TIMESTAMP": 3}


@dataclass(frozen=True)
class TimelineEvent:
    row: Mapping[str, Any]
    sort_key: Optional[Tuple[str, int]]
    category: str
    synthetic: bool


def is_timeline_row(row: Mapping[str, Any]) -> bool:
    producers = row.get("_producers") or []
    return row.get("observation_type") == OBSERVATION_TYPE and (not producers or PRODUCER in producers)


def recorded_date(row: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[Tuple[str, int]]]:
    """``(date as recorded, temporal precision, sort key)``; all None when undated.

    The declared ``evidence_state.temporal_precision`` wins; otherwise the
    precision is read from the shape of the recorded date itself.
    """
    date = str(row.get("date_local") or "").strip()
    match = _DATE.match(date)
    if not match:
        return None, None, None
    parts = sum(1 for group in match.groups() if group)
    declared = ep.declared(row).get("temporal_precision")
    precision = declared if declared in _PRECISION_RANK else (
        _LEGACY_PRECISION.get(str(row.get("date_precision") or "")) or _PRECISION_FROM_DATE[parts]
    )
    year, month, day = match.group(1), match.group(2) or "01", match.group(3) or "01"
    return date, precision, (f"{year}-{month}-{day}", _PRECISION_RANK.get(precision, 0))


def _category(row: Mapping[str, Any]) -> str:
    return str(row.get("object_type") or "Uncategorized")


def _event(row: Mapping[str, Any]) -> TimelineEvent:
    _, _, key = recorded_date(row)
    return TimelineEvent(row=row, sort_key=key, category=_category(row), synthetic=bool(row.get("synthetic", False)))


def build_timeline(
    rows: Iterable[Mapping[str, Any]],
    *,
    sort: str = "oldest",
    categories: Sequence[str] = (),
    findings_only: bool = False,
    include_synthetic: bool = False,
    finding_links: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Dict[str, Any]:
    """Order and filter case events. ``finding_links`` maps a case entity id to the
    OVNIS findings that name it; it is empty until OVNIS publishes findings."""
    if sort not in SORTS:
        raise ValueError(f"unknown sort {sort!r}; expected one of {', '.join(SORTS)}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))
    links = finding_links or {}
    events = [_event(r) for r in rows if is_timeline_row(r)]
    loaded = len(events)
    visible = [e for e in events if include_synthetic or not e.synthetic]
    excluded_synthetic = loaded - len(visible)

    category_counts: Dict[str, int] = {}
    for event in visible:
        category_counts[event.category] = category_counts.get(event.category, 0) + 1
    wanted = set(categories)
    matched = [e for e in visible if not wanted or e.category in wanted]
    findings_total = sum(len(v) for v in links.values())
    if findings_only:
        matched = [e for e in matched if links.get(str(e.row.get("entity_id") or ""))]

    dated = [e for e in matched if e.sort_key is not None]
    undated = [e for e in matched if e.sort_key is None]
    dated.sort(key=lambda e: (e.sort_key, str(e.row.get("observation_id") or "")), reverse=(sort == "newest"))
    ordered = dated + sorted(undated, key=lambda e: str(e.row.get("observation_id") or ""))
    page = ordered[offset:offset + limit]

    return {
        "contract": CONTRACT_ID,
        "producer": PRODUCER,
        "producer_status": "AVAILABLE" if loaded else "NO_DATA",
        "sort": sort,
        "categories": [{"category": name, "count": count} for name, count in sorted(category_counts.items())],
        "selected_categories": sorted(wanted),
        "findings_only": findings_only,
        "include_synthetic": include_synthetic,
        "loaded_events": loaded,
        "excluded_synthetic": excluded_synthetic,
        "matched": len(ordered),
        "undated": len(undated),
        "findings_total": findings_total,
        "findings_status": "OK" if findings_total else "NO_FINDINGS_RECORDED",
        "events": [_render(e.row, links) for e in page],
        "next_cursor": str(offset + limit) if offset + limit < len(ordered) else None,
    }


def era(date: Optional[str]) -> Optional[str]:
    if not date:
        return None
    return f"{int(date[:4]) // 10 * 10}s"


def _render(row: Mapping[str, Any], links: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    date, precision, _ = recorded_date(row)
    attrs = ep.as_mapping(row.get("attributes"))
    location = ep.as_mapping(row.get("location"))
    observation_id = str(row.get("observation_id") or "")
    entity_id = str(row.get("entity_id") or "") or None
    time = row.get("time_local") if precision == "EXACT_TIMESTAMP" else None
    return {
        "evidence_id": f"evo:observations:{observation_id}",
        "observation_id": observation_id,
        "entity_id": entity_id,
        "case_id": attrs.get("case_id"),
        "title": row.get("location_name") or attrs.get("case_id") or observation_id,
        "category": _category(row),
        "environment": row.get("environment"),
        "date": date,
        "time": time,
        "temporal_precision": precision or "UNKNOWN",
        "era": era(date),
        "narrative": attrs.get("description"),
        "place": {
            "municipality": row.get("municipality") or location.get("municipality"),
            "location_name": row.get("location_name"),
        },
        "evidence_tier": row.get("evidence_tier"),
        "source_id": row.get("source_id"),
        "source_citation": attrs.get("source_citation"),
        "producers": list(row.get("_producers") or []),
        "synthetic": bool(row.get("synthetic", False)),
        "findings": list(links.get(entity_id or "", [])),
        "evidence_href": f"/evidence/Observations/{observation_id}",
        "entity_href": f"/entity/{entity_id}" if entity_id else None,
    }


def parse_cursor(cursor: Optional[str]) -> int:
    if cursor in (None, ""):
        return 0
    if not str(cursor).isdigit():
        raise ValueError("invalid cursor")
    return int(str(cursor))

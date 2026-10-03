"""Research composition over the OVNIS research records the Hub store holds.

Pure and read-only. OVNIS owns the research record (``ovnis-pr``,
docs/RESEARCH_LEDGERS.md there) and exports it as typed ``entities`` rows:
research topics, findings, hypotheses with their falsification checks,
contradictions, manifestation adjudications, research-queue items, media
episodes and per-case reports. This module only arranges those rows:

* Nothing is promoted. A finding keeps its own status (CANDIDATE, ACCEPTED,
  REJECTED, SUPERSEDED); ACCEPTED means a reviewer accepted it as supported by
  its cited sources, not that it is established fact.
* A computed duplicate pair stays a CANDIDATE. Only a curated adjudication
  records SAME_EVENT, DISTINCT or UNRESOLVABLE, and no case is merged.
* An empty ledger is reported as ``NONE_RECORDED``, never shown as a result.
* Source counts are distinct sources, not copies: a case's cited source is
  counted once however many findings cite it (directive §44).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from . import epistemic as ep
from .event_timeline import recorded_date

CONTRACT_ID = "federation-research-v1"
PRODUCER = "ovnis-pr"
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

# Public kind -> (exported entity_type, external_ids key holding the record id).
KINDS: Mapping[str, Tuple[str, str]] = {
    "topics": ("research_topic", "ovnis_topic_id"),
    "findings": ("finding", "ovnis_finding_id"),
    "hypotheses": ("hypothesis", "ovnis_hypothesis_id"),
    "contradictions": ("contradiction", "ovnis_contradiction_id"),
    "adjudications": ("manifestation_adjudication", "ovnis_adjudication_id"),
    "queue": ("research_queue_item", "ovnis_item_id"),
    "episodes": ("media_episode", "ovnis_episode_id"),
    "reports": ("case_report", "ovnis_report_id"),
}
ENTITY_TYPES: Tuple[str, ...] = tuple(entity_type for entity_type, _ in KINDS.values())
_KIND_OF_TYPE = dict(zip(ENTITY_TYPES, KINDS))
FALSIFICATION_CHECKS: Tuple[str, ...] = (
    "identity_errors", "duplicate_manifestations", "ordinary_explanations", "background_prevalence",
    "missing_data", "source_dependence", "temporal_mismatch", "geometry_uncertainty", "contradictions",
)
CASE_TYPE = "uap_case"


def kind_of(row: Mapping[str, Any]) -> Optional[str]:
    return _KIND_OF_TYPE.get(str(row.get("entity_type") or ""))


def is_research_row(row: Mapping[str, Any]) -> bool:
    producers = row.get("_producers") or []
    return kind_of(row) is not None and (not producers or PRODUCER in producers)


def _attributes(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return ep.as_mapping(row.get("attributes"))


def record_id(row: Mapping[str, Any]) -> str:
    kind = kind_of(row)
    key = KINDS[kind][1] if kind else ""
    return str(ep.as_mapping(row.get("external_ids")).get(key) or row.get("entity_id") or "")


def cases_named(row: Mapping[str, Any]) -> Set[str]:
    """Every OVNIS case id a research record names: its case lists, an adjudicated
    pair, a report's case, and the cases its cited source refs point at."""
    attrs = _attributes(row)
    named: Set[str] = {str(c) for c in attrs.get("case_ids") or [] if c}
    named |= {str(attrs[k]) for k in ("case_a", "case_b") if attrs.get(k)}
    report = ep.as_mapping(attrs.get("report"))
    if report.get("case_id"):
        named.add(str(report["case_id"]))
    refs = list(attrs.get("source_refs") or [])
    refs += [ep.as_mapping(attrs.get(side)).get("source_ref") for side in ("claim_a", "claim_b")]
    named |= {str(ref["case_id"]) for ref in refs if isinstance(ref, Mapping) and ref.get("case_id")}
    return named


def record(row: Mapping[str, Any]) -> Dict[str, Any]:
    """One research row as the API serves it: the producer's record, its ids and its state."""
    attrs = dict(_attributes(row))
    entity_id = str(row.get("entity_id") or "")
    state = ep.declared(row)
    return {
        "kind": kind_of(row),
        "record_id": record_id(row),
        "entity_id": entity_id,
        "evidence_id": f"evo:entities:{entity_id}",
        "title": row.get("name"),
        "status": attrs.get("status"),
        "origin": attrs.get("origin"),
        "epistemic_class": state.get("epistemic_class"),
        "data_stage": state.get("data_stage"),
        "case_ids": sorted(cases_named(row)),
        "attributes": attrs,
        "producers": list(row.get("_producers") or []),
        "synthetic": bool(row.get("synthetic", False)),
        "evidence_href": f"/evidence/Entities/{entity_id}",
        "entity_href": f"/entity/{entity_id}",
    }


def _by_kind(rows: Iterable[Mapping[str, Any]], *, include_synthetic: bool) -> Dict[str, List[Mapping[str, Any]]]:
    out: Dict[str, List[Mapping[str, Any]]] = {kind: [] for kind in KINDS}
    for row in rows:
        kind = kind_of(row)
        if kind and is_research_row(row) and (include_synthetic or not row.get("synthetic")):
            out[kind].append(row)
    for kind in out:
        out[kind].sort(key=record_id)
    return out


def topic_cards(
    topics: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
    case_sources: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Topic cards with their finding count and distinct-source count.

    ``case_sources`` maps a case id to the Hub source id its export cites. A
    finding citing a case counts that case's source; one citing a source-registry
    entry counts the entry. Each distinct source counts once (§44).
    """
    cards: List[Dict[str, Any]] = []
    for topic in topics:
        topic_id = record_id(topic)
        members = [f for f in findings if topic_id in (_attributes(f).get("topic_ids") or [])]
        sources: Set[str] = set()
        for finding in members:
            for ref in _attributes(finding).get("source_refs") or []:
                if not isinstance(ref, Mapping):
                    continue
                if ref.get("source_id"):
                    sources.add(f"registry:{ref['source_id']}")
                elif ref.get("case_id"):
                    sources.add(case_sources.get(str(ref["case_id"])) or f"case:{ref['case_id']}")
        status_counts: Dict[str, int] = {}
        for finding in members:
            status = str(_attributes(finding).get("status") or "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
        cards.append({
            **record(topic),
            "finding_count": len(members),
            "finding_status_counts": dict(sorted(status_counts.items())),
            "finding_ids": sorted(record_id(f) for f in members),
            "source_count": len(sources),
            "source_count_basis": "distinct cited sources; repeated citations of one source count once",
        })
    return cards


def overview(
    rows: Iterable[Mapping[str, Any]],
    *,
    case_sources: Optional[Mapping[str, str]] = None,
    include_synthetic: bool = False,
) -> Dict[str, Any]:
    """Counts per kind and status, plus the topic cards."""
    by_kind = _by_kind(rows, include_synthetic=include_synthetic)
    kinds: Dict[str, Any] = {}
    for kind, members in by_kind.items():
        statuses: Dict[str, int] = {}
        for row in members:
            status = str(_attributes(row).get("status") or "NONE")
            statuses[status] = statuses.get(status, 0) + 1
        kinds[kind] = {
            "total": len(members),
            "kind_status": "RECORDED" if members else "NONE_RECORDED",
            "status_counts": dict(sorted(statuses.items())),
        }
    adjudications = by_kind["adjudications"]
    kinds["adjudications"]["computed_candidates"] = sum(
        1 for row in adjudications if _attributes(row).get("origin") == "COMPUTED")
    kinds["adjudications"]["curated_decisions"] = sum(
        1 for row in adjudications if _attributes(row).get("origin") == "CURATED")
    return {
        "contract": CONTRACT_ID,
        "producer": PRODUCER,
        "producer_status": "AVAILABLE" if any(by_kind.values()) else "NO_DATA",
        "include_synthetic": include_synthetic,
        "kinds": kinds,
        "topics": topic_cards(by_kind["topics"], by_kind["findings"], case_sources or {}),
    }


def records(
    kind: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    status: Optional[str] = None,
    origin: Optional[str] = None,
    include_synthetic: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Dict[str, Any]:
    """One page of a kind's records, optionally narrowed to a status or origin."""
    if kind not in KINDS:
        raise ValueError(f"unknown research kind {kind!r}; expected one of {', '.join(KINDS)}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))
    members = _by_kind(rows, include_synthetic=include_synthetic)[kind]
    matched = [row for row in members
               if (status is None or _attributes(row).get("status") == status)
               and (origin is None or _attributes(row).get("origin") == origin)]
    page = matched[offset:offset + limit]
    return {
        "contract": CONTRACT_ID,
        "kind": kind,
        "kind_status": "RECORDED" if members else "NONE_RECORDED",
        "total": len(members),
        "matched": len(matched),
        "records": [record(row) for row in page],
        "next_cursor": str(offset + limit) if offset + limit < len(matched) else None,
    }


def finding_links(rows: Iterable[Mapping[str, Any]], case_entities: Mapping[str, str]) -> Dict[str, List[Dict[str, Any]]]:
    """Case entity id -> the OVNIS findings that name the case, for the event timeline."""
    links: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if kind_of(row) != "findings" or not is_research_row(row):
            continue
        summary = {"finding_id": record_id(row), "status": _attributes(row).get("status"),
                   "statement": _attributes(row).get("statement"), "entity_href": f"/entity/{row.get('entity_id')}"}
        for case_id in sorted(cases_named(row)):
            entity_id = case_entities.get(case_id)
            if entity_id:
                links.setdefault(entity_id, []).append(summary)
    return links


def case_summary(case_entity: Mapping[str, Any], observation: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """A case as recorded: dates keep their precision and places stay as the source gives them."""
    attrs = _attributes(case_entity)
    obs = observation or {}
    # Without the observation, the entity's own recorded event date is read the same way.
    date, precision, _ = recorded_date(obs if obs else {"date_local": attrs.get("event_date")})
    entity_id = str(case_entity.get("entity_id") or "")
    location = ep.as_mapping(obs.get("location"))
    return {
        "case_id": attrs.get("case_id") or ep.as_mapping(case_entity.get("external_ids")).get("ovnis_case_id"),
        "entity_id": entity_id,
        "title": case_entity.get("name"),
        "category": attrs.get("object_type") or obs.get("object_type"),
        "date": date,
        "time": obs.get("time_local") if precision == "EXACT_TIMESTAMP" else None,
        "temporal_precision": precision or "UNKNOWN",
        "place": {"municipality": obs.get("municipality") or location.get("municipality"),
                  "location_name": obs.get("location_name")},
        "evidence_tier": attrs.get("evidence_tier") or obs.get("evidence_tier"),
        "narrative": attrs.get("description"),
        "source_citation": attrs.get("source_citation"),
        "observation_id": obs.get("observation_id"),
        "entity_href": f"/entity/{entity_id}",
        "evidence_href": f"/evidence/Entities/{entity_id}",
        "timeline_href": "/timeline",
    }


def case_reconstruction(
    case_entity: Mapping[str, Any],
    *,
    observation: Optional[Mapping[str, Any]] = None,
    source: Optional[Mapping[str, Any]] = None,
    research_rows: Iterable[Mapping[str, Any]] = (),
    other_cases: Optional[Mapping[str, Mapping[str, Any]]] = None,
    include_synthetic: bool = False,
) -> Dict[str, Any]:
    """Everything the Hub holds about one OVNIS case (FDX-016), arranged, not inferred.

    ``other_cases`` maps a case id to that case's summary, so a candidate pair
    shows what the other case records. A pair whose other case the store does
    not hold is kept and marked ``held: False``.
    """
    summary = case_summary(case_entity, observation)
    case_id = str(summary["case_id"] or "")
    by_kind = _by_kind((r for r in research_rows if case_id in cases_named(r)), include_synthetic=include_synthetic)
    other_cases = other_cases or {}

    adjudications: List[Dict[str, Any]] = []
    for row in by_kind["adjudications"]:
        item = record(row)
        attrs = item["attributes"]
        other_id = str(attrs.get("case_b") if attrs.get("case_a") == case_id else attrs.get("case_a"))
        other = other_cases.get(other_id)
        item["other_case"] = {**dict(other), "held": True} if other else {"case_id": other_id, "held": False}
        item["reviewed"] = attrs.get("origin") == "CURATED"
        adjudications.append(item)

    reports = [record(row) for row in by_kind["reports"]]
    report = ep.as_mapping(reports[0]["attributes"].get("report")) if reports else {}
    src = source or {}
    return {
        "contract": CONTRACT_ID,
        "case": summary,
        "source": ({"source_id": src.get("source_id"), "name": src.get("source_name"),
                    "url": src.get("source_url"), "ref": src.get("source_ref"),
                    "evidence_href": f"/evidence/Sources/{src.get('source_id')}"} if src else None),
        # OVNIS exports a report for every case; a sampled store may not hold this one.
        "report_status": "HELD" if report else "NOT_HELD",
        "report": dict(report) if report else None,
        "unresolved": list(report.get("unresolved") or []) if report else [],
        "findings": [record(row) for row in by_kind["findings"]],
        "hypotheses": [record(row) for row in by_kind["hypotheses"]],
        "contradictions": [record(row) for row in by_kind["contradictions"]],
        "adjudications": adjudications,
        "queue": [record(row) for row in by_kind["queue"]],
        "episodes": [record(row) for row in by_kind["episodes"]],
    }

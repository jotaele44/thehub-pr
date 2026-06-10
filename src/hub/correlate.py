"""Derive cross-producer correlation relationships from a Hub aggregate.

The Hub's ``aggregate`` step unions + id-dedups every producer's canonical rows
into one graph, stamping each row with a ``_producers`` provenance list. This
module reads that aggregate and links entities that different producers describe
independently — the cross-producer correlation that used to live in spiderweb's
query-hub (now retired), re-homed here where the Hub sees *all* producers.

Four strategies, each emitting canonical ``federation_relationship`` rows:

* **normalized-entity** — entities sharing a ``normalized_name``.
* **external-id** — entities sharing an ``external_ids`` value (uei/duns/…).
* **spatial-haversine** — entities whose ``location`` points fall within a km threshold.
* **temporal** — entities anchoring funding awards / transactions whose dates fall
  within a day window. Entities themselves carry no event timestamp (only extraction
  provenance), so temporal homes on the dated finance streams and links their primary
  entity (award ``recipient_entity_id`` / transaction ``payee_entity_id``). Returns
  ``[]`` when neither stream is present.

Two rows are linkable iff their ``_producers`` sets are **disjoint** (a genuine
cross-producer pair). Same-id matches are already merged by ``aggregate`` and are
invisible here by design. Output is deterministic (sorted, fixed timestamps,
sha256-derived ids) so re-runs are byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Deterministic, out-of-band so re-runs are byte-identical (mirrors bridge.py).
_FIXED_TS = "1970-01-01T00:00:00Z"
_LINEAGE = {
    "producer_script": "src/hub/correlate.py",
    "producer_phase": "HUB_CORRELATE",
    "source_inputs": ["entities.jsonl", "funding_awards.jsonl", "transactions.jsonl"],
    "extraction_method": "deterministic",
}


# --------------------------------------------------------------------------
# Row accessors (adapted to the Hub canonical schemas)
# --------------------------------------------------------------------------

def _disjoint(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True iff the two rows come from non-overlapping producer sets."""
    return set(a.get("_producers") or []).isdisjoint(b.get("_producers") or [])


def _score(row: Dict[str, Any]) -> Optional[float]:
    conf = row.get("confidence")
    return float(conf) if isinstance(conf, (int, float)) else None


def _normalized_name(entity: Dict[str, Any]) -> Optional[str]:
    norm = entity.get("normalized_name")
    return norm if isinstance(norm, str) and norm else None


def _external_ids(entity: Dict[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    xids = entity.get("external_ids")
    if isinstance(xids, dict):
        for key, val in xids.items():
            if isinstance(val, str) and val.strip():
                out.append((str(key), val.strip()))
    return out


def _coerce_latlon(lat: Any, lon: Any) -> Optional[Tuple[float, float]]:
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        if -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180:
            return (float(lat), float(lon))
    return None


def _point(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """(lat, lon) from a row's ``location``. Entities use ``lat``/``lon``;
    awards/transactions use ``latitude``/``longitude`` — accept either."""
    loc = row.get("location")
    if isinstance(loc, dict):
        return _coerce_latlon(loc.get("lat", loc.get("latitude")),
                              loc.get("lon", loc.get("longitude")))
    return None


def _parse_date(value: Any) -> Optional[date]:
    """Parse an ISO ``YYYY-MM-DD`` (the award/transaction date format)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _link(a_id: str, b_id: str, rtype: str, match_basis: str, confidence: float,
          explanation: str) -> Dict[str, Any]:
    return {
        "source_entity_id": a_id,
        "target_entity_id": b_id,
        "relationship_type": rtype,
        "match_basis": match_basis,
        "confidence": confidence,
        "explanation": explanation,
    }


# --------------------------------------------------------------------------
# Correlation strategies (consume Hub rows, emit partial link dicts)
# --------------------------------------------------------------------------

def correlate_entities(entities: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Link cross-producer entities sharing a normalized name."""
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for ent in entities:
        norm = _normalized_name(ent)
        if norm:
            by_name.setdefault(norm, []).append(ent)

    links: List[Dict[str, Any]] = []
    for norm, recs in by_name.items():
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i], recs[j]
                if a["entity_id"] == b["entity_id"] or not _disjoint(a, b):
                    continue
                scores = [s for s in (_score(a), _score(b)) if s is not None]
                conf = round(min(scores), 3) if scores else 0.0
                links.append(_link(a["entity_id"], b["entity_id"], "entity_correlation",
                                   "normalized_name", conf,
                                   f"Shared normalized entity name '{norm}'."))
    return links


def correlate_by_external_id(entities: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Link cross-producer entities sharing an external id (uei/duns/…)."""
    by_xid: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for ent in entities:
        for key, val in _external_ids(ent):
            by_xid.setdefault((key, val), []).append(ent)

    links: List[Dict[str, Any]] = []
    for (key, val), recs in by_xid.items():
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i], recs[j]
                if a["entity_id"] == b["entity_id"] or not _disjoint(a, b):
                    continue
                scores = [s for s in (_score(a), _score(b)) if s is not None]
                conf = round(min(scores), 3) if scores else 0.9
                links.append(_link(a["entity_id"], b["entity_id"], "entity_correlation",
                                   f"external_id:{key}", conf,
                                   f"Shared external id {key}={val}."))
    return links


def correlate_spatial(entities: Sequence[Dict[str, Any]],
                      threshold_km: float = 1.0) -> List[Dict[str, Any]]:
    """Link cross-producer entities whose locations fall within ``threshold_km``."""
    pts = [(ent, _point(ent)) for ent in entities]
    pts = [(ent, pt) for ent, pt in pts if pt is not None]

    links: List[Dict[str, Any]] = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            a, pa = pts[i]
            b, pb = pts[j]
            if a["entity_id"] == b["entity_id"] or not _disjoint(a, b):
                continue
            dist = _haversine_km(pa[0], pa[1], pb[0], pb[1])
            if dist > threshold_km:
                continue
            conf = round(max(0.0, 1.0 - dist / threshold_km), 3)
            links.append(_link(a["entity_id"], b["entity_id"], "spatial_proximity",
                               "location", conf, f"Entities within {round(dist, 2)} km."))
    return links


def correlate_temporal(awards: Sequence[Dict[str, Any]],
                       transactions: Sequence[Dict[str, Any]],
                       window_days: int = 7) -> List[Dict[str, Any]]:
    """Link the primary entities of cross-producer funding awards / transactions
    whose dates fall within ``window_days``. Entities carry no event timestamp,
    so this homes on the dated finance streams. Returns ``[]`` if both absent."""
    anchored: List[Tuple[str, date, Dict[str, Any]]] = []
    for awd in awards:
        ent = awd.get("recipient_entity_id")
        when = _parse_date(awd.get("award_date"))
        if isinstance(ent, str) and when is not None:
            anchored.append((ent, when, awd))
    for txn in transactions:
        ent = txn.get("payee_entity_id")
        when = _parse_date(txn.get("transaction_date"))
        if isinstance(ent, str) and when is not None:
            anchored.append((ent, when, txn))

    links: List[Dict[str, Any]] = []
    for i in range(len(anchored)):
        for j in range(i + 1, len(anchored)):
            ent_a, date_a, row_a = anchored[i]
            ent_b, date_b, row_b = anchored[j]
            if ent_a == ent_b or not _disjoint(row_a, row_b):
                continue
            delta = abs((date_a - date_b).days)
            if delta > window_days:
                continue
            conf = round(max(0.0, 1.0 - 0.5 * (delta / window_days)), 3)
            links.append(_link(ent_a, ent_b, "temporal_proximity", "award_transaction_date",
                               conf, f"Cross-producer funding activity within {delta} day(s)."))
    return links


# --------------------------------------------------------------------------
# Relationship emission
# --------------------------------------------------------------------------

def correlator_source_id() -> str:
    return "src_" + hashlib.sha256(b"hub:correlate").hexdigest()[:32]


def correlator_source() -> Dict[str, Any]:
    """The synthetic provenance source row the correlator attributes links to."""
    return {
        "source_id": correlator_source_id(),
        "source_type": "hub_correlation",
        "source_name": "Hub cross-producer correlation",
        "source_ref": "hub:correlate",
        "confidence": 1.0,
        "lineage": _LINEAGE,
        "synthetic": True,
        "created_at": _FIXED_TS,
        "extracted_at": _FIXED_TS,
    }


def _to_relationship(link: Dict[str, Any]) -> Dict[str, Any]:
    src, tgt = sorted((link["source_entity_id"], link["target_entity_id"]))
    rtype = link["relationship_type"]
    rid = "rel_" + hashlib.sha256(f"{src}|{tgt}|{rtype}".encode()).hexdigest()[:32]
    sid = correlator_source_id()
    return {
        "relationship_id": rid,
        "source_id": sid,
        "source_entity_id": src,
        "target_entity_id": tgt,
        "relationship_type": rtype,
        "evidence_source_id": sid,
        "confidence": link["confidence"],
        "match_basis": link["match_basis"],
        "explanation": link["explanation"],
        "lineage": _LINEAGE,
        "synthetic": True,
        "created_at": _FIXED_TS,
        "extracted_at": _FIXED_TS,
    }


def _dedupe_links(links: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicate edges (same unordered pair + relationship_type), keeping
    the highest-confidence one. Name- and external-id matches both produce
    ``entity_correlation`` and intentionally collapse to one edge."""
    best: Dict[Any, Dict[str, Any]] = {}
    for link in links:
        key = (frozenset((link["source_entity_id"], link["target_entity_id"])),
               link["relationship_type"])
        if key not in best or link["confidence"] > best[key]["confidence"]:
            best[key] = link
    return list(best.values())


# --------------------------------------------------------------------------
# I/O + orchestration
# --------------------------------------------------------------------------

def _read_stream(in_dir: Path, stream: str) -> List[Dict[str, Any]]:
    fpath = in_dir / f"{stream}.jsonl"
    if not fpath.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for raw in fpath.read_text().splitlines():
        raw = raw.strip()
        if raw:
            rows.append(json.loads(raw))
    return rows


def derive_relationships(entities: Sequence[Dict[str, Any]],
                         awards: Sequence[Dict[str, Any]] = (),
                         transactions: Sequence[Dict[str, Any]] = (),
                         *, window_days: int = 7,
                         threshold_km: float = 1.0) -> List[Dict[str, Any]]:
    """Run all 4 strategies, dedupe, and emit sorted canonical relationship rows."""
    links = (
        correlate_entities(entities)
        + correlate_by_external_id(entities)
        + correlate_spatial(entities, threshold_km=threshold_km)
        + correlate_temporal(awards, transactions, window_days=window_days)
    )
    relationships = [_to_relationship(link) for link in _dedupe_links(links)]
    relationships.sort(key=lambda r: (r["relationship_type"],
                                      r["source_entity_id"], r["target_entity_id"]))
    return relationships


def correlate(in_dir, out_dir, *, window_days: int = 7,
              threshold_km: float = 1.0) -> Dict[str, Any]:
    """Read a Hub aggregate, derive cross-producer relationships, write
    ``<out_dir>/correlations.jsonl``. Returns a summary."""
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    entities = _read_stream(in_dir, "entities")
    awards = _read_stream(in_dir, "funding_awards")
    transactions = _read_stream(in_dir, "transactions")

    relationships = derive_relationships(
        entities, awards, transactions,
        window_days=window_days, threshold_km=threshold_km,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "correlations.jsonl").open("w") as fh:
        for rel in relationships:
            fh.write(json.dumps(rel, sort_keys=True) + "\n")

    by_type: Dict[str, int] = {}
    for rel in relationships:
        by_type[rel["relationship_type"]] = by_type.get(rel["relationship_type"], 0) + 1
    return {
        "correlations": len(relationships),
        "by_type": by_type,
        "source": correlator_source(),
    }

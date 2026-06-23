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
    """Link cross-producer entities whose locations fall within ``threshold_km``.

    Indexed with a lat/lon grid: points are binned into ~``threshold_km``-sized
    cells and each point is only compared against points in its own and the 8
    adjacent cells, so no within-threshold pair is missed while the all-pairs
    O(n²) scan collapses to roughly O(n) for sparsely populated grids.

    The emitted links are byte-identical to the naive all-pairs version: each
    unordered pair is examined under the same ``entity_id``/``_disjoint``/
    ``haversine <= threshold`` filter, the haversine distance is symmetric under
    argument swap, and there is no within-pair tie that emission order could
    break differently. Over-inclusion of candidates is harmless (the filter is
    identical); only *missing* a true pair would change output, which the
    cell-coverage guarantee below prevents.

    Scope: the grid treats longitude as planar — it does **not** wrap across the
    ±180° antimeridian, nor does adjacency hold across the poles. A within-
    threshold pair straddling those discontinuities (e.g. lon 179.999 vs
    -179.999) would be binned into non-adjacent cells and missed. This is a
    deliberate non-goal: the Hub's data is PR-domain (lon ≈ -66), nowhere near
    those edges, so wraparound adjacency would be unused complexity. Revisit if
    a producer ever emits points near the antimeridian or a pole.
    """
    _raw = [(ent, _point(ent)) for ent in entities]
    pts: List[Tuple[Dict[str, Any], Tuple[float, float]]] = [
        (ent, pt) for ent, pt in _raw if pt is not None
    ]

    # Degrees-per-km vary with latitude: one degree of latitude is ~110.574 km
    # everywhere, but one degree of longitude shrinks to ~111.320*cos(lat) km.
    # Bin lat with a fixed cell height and lon with a *wider* cell so that any
    # two points within ``threshold_km`` always land in the same or an adjacent
    # cell. We size cells from the most extreme latitude in the set (largest
    # |lat| → smallest cos → widest lon cell needed) and round generously: the
    # grid only groups candidates, it never produces an output value, so erring
    # large just adds harmless comparisons.
    KM_PER_DEG_LAT = 110.574
    KM_PER_DEG_LON_EQUATOR = 111.320
    lat_cell = threshold_km / KM_PER_DEG_LAT
    if pts:
        max_abs_lat = max(abs(pt[0]) for _, pt in pts)
    else:
        max_abs_lat = 0.0
    cos_lat = math.cos(math.radians(min(max_abs_lat, 89.9)))
    cos_lat = max(cos_lat, 1e-9)  # guard against division blow-up near the poles
    lon_cell = threshold_km / (KM_PER_DEG_LON_EQUATOR * cos_lat)

    # Bucket points by integer (lat_cell, lon_cell) index, preserving input order
    # within each bucket so candidate enumeration is deterministic.
    grid: Dict[Tuple[int, int], List[int]] = {}
    cells: List[Tuple[int, int]] = []
    for idx, (_, pt) in enumerate(pts):
        cell = (int(math.floor(pt[0] / lat_cell)), int(math.floor(pt[1] / lon_cell)))
        cells.append(cell)
        grid.setdefault(cell, []).append(idx)

    links: List[Dict[str, Any]] = []
    for i in range(len(pts)):
        ci, cj = cells[i]
        for dci in (-1, 0, 1):
            for dcj in (-1, 0, 1):
                for j in grid.get((ci + dci, cj + dcj), ()):  # type: ignore[arg-type]
                    if j <= i:
                        continue  # only consider each unordered pair once, i<j
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

    # Sorted-by-date sweep instead of an all-pairs O(n²) scan: order rows by date
    # and, for each row, only walk forward while the next row is within
    # ``window_days``. Because the rows are date-sorted the forward window stops
    # early, so a row is compared against only its near-in-time neighbours.
    #
    # Byte-identity vs. the naive all-pairs loop: the surviving link for a pair is
    # its min-delta (= max-confidence) one, and ``conf``/``explanation`` are pure
    # functions of ``delta``, so *which* row wins is order-independent — except
    # that two distinct deltas could (for a very large window) round to the same
    # confidence, where ``_dedupe_links`` first-wins would pick by emission order.
    # To depend on nothing, we tag every emitted link with the unordered pair of
    # the rows' *original* indices and re-sort by it before returning, reproducing
    # the naive ``(i, j)`` emission order exactly regardless of window size.
    order = sorted(range(len(anchored)), key=lambda k: anchored[k][1])
    tagged: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
    for si in range(len(order)):
        oi = order[si]
        ent_a, date_a, row_a = anchored[oi]
        for sj in range(si + 1, len(order)):
            oj = order[sj]
            ent_b, date_b, row_b = anchored[oj]
            delta = (date_b - date_a).days  # >= 0, rows are date-sorted ascending
            if delta > window_days:
                break  # all further rows are even later → out of window
            if ent_a == ent_b or not _disjoint(row_a, row_b):
                continue
            conf = round(max(0.0, 1.0 - 0.5 * (delta / window_days)), 3)
            link = _link(ent_a, ent_b, "temporal_proximity", "award_transaction_date",
                         conf, f"Cross-producer funding activity within {delta} day(s).")
            tagged.append(((min(oi, oj), max(oi, oj)), link))

    tagged.sort(key=lambda t: t[0])
    return [link for _, link in tagged]


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

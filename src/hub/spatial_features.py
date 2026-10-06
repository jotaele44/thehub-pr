"""Spatial features over the rows the Hub store holds (Phase 5, Property Map).

Pure and read-only. A row is drawn as a point only when its producer declared a
point ``geometry_precision`` (OBSERVED_POINT, INTERPRETED_POINT or
REPRESENTATIVE_POINT) and the row carries valid coordinates. Everything else is
kept honest rather than drawn:

* a row with coordinates but no declared point precision (none declared, or
  UNKNOWN, or AREA_REFERENCE) is counted as ``coordinates_without_point_precision``
  per producer and not mapped, because a point would imply a precision nobody
  declared;
* a row that records a municipality is counted under that municipality as an
  area reference, so the map can outline the municipality instead of placing a
  point inside it. The value is passed through as recorded; whether it names a
  real municipality is decided by the boundary layer it is joined to, never here;
* a REPRESENTATIVE_POINT stays representative (for example a municipio centroid)
  and is labelled as such; it is never promoted.

Each point also carries its time as recorded: ``observed_at`` at its declared
precision, any validity window (``valid_from``/``valid_to``), the span that
precision covers (``time_start``/``time_end``: a year-only date spans its whole
year) and its ``temporal_state`` at read time. Undated records carry no span and
are counted, never placed in time.

Categories are the record types the producers exported (``entity_type``,
``observation_type`` or the alert's ``module``/``alert_type``), so the map's
symbology comes from Federation data, not from any reference application. A
producer's own ``object_type`` (for example OVNIS's UAP, Lights or Mutilation)
is passed through as recorded and counted alongside.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import epistemic as ep
from .evidence_object import ID_FIELDS, evidence_id, record_title

CONTRACT_ID = "federation-spatial-features-v1"
POINT_PRECISIONS: Tuple[str, ...] = ("OBSERVED_POINT", "INTERPRETED_POINT", "REPRESENTATIVE_POINT")
STREAMS: Tuple[str, ...] = ("entities", "observations", "alerts")
MAX_LIMIT = 5000
DEFAULT_LIMIT = 2000
EARTH_RADIUS_M = 6_371_008.8

Row = Tuple[str, str, Mapping[str, Any]]  # (stream, collection, row)


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def coordinates(row: Mapping[str, Any]) -> Optional[Tuple[float, float]]:
    """``(lon, lat)`` when the row carries valid WGS84 coordinates, else None."""
    location = ep.as_mapping(row.get("location"))
    for lat, lon in ((location.get("lat"), location.get("lon")),
                     (row.get("latitude"), row.get("longitude")),
                     (row.get("lat"), row.get("lon"))):
        lat_f, lon_f = _number(lat), _number(lon)
        if lat_f is not None and lon_f is not None and -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
            return lon_f, lat_f
    return None


def category(stream: str, row: Mapping[str, Any]) -> str:
    if stream == "alerts":
        return str(row.get("module") or row.get("alert_type") or "alert")
    return str(row.get("entity_type") or row.get("observation_type") or stream)


def municipality(row: Mapping[str, Any]) -> Optional[str]:
    """The municipality value as the producer recorded it, if any."""
    for value in (ep.as_mapping(row.get("location")).get("municipality"), row.get("municipality"),
                  ep.as_mapping(row.get("attributes")).get("municipality")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def object_type(row: Mapping[str, Any]) -> Optional[str]:
    """The producer's own ``object_type`` value, if it recorded one."""
    value = row.get("object_type")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _tally(counts: Dict[str, int], key: Optional[str]) -> None:
    if key is not None:
        counts[key] = counts.get(key, 0) + 1


def producer(row: Mapping[str, Any]) -> str:
    producers = row.get("_producers") or []
    return str(producers[0]) if producers else "unattributed"


def _record_id(stream: str, row: Mapping[str, Any]) -> str:
    return str(row.get(ID_FIELDS.get(stream, "")) or "")


def _iso(moment: datetime) -> str:
    """Fixed-width UTC ISO-8601 (millisecond precision), so instants also sort as text."""
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def time_span(observed_at: Optional[str], precision: str, valid_from: Any = None,
              valid_to: Any = None) -> Optional[Tuple[datetime, datetime]]:
    """The UTC interval a record's time covers, at its declared precision, or None.

    A validity window wins; otherwise a date covers its whole day, month or year,
    and only a full timestamp is an instant. Nothing is narrowed or invented.
    """
    window = [moment for moment in (ep.parse_instant(valid_from), ep.parse_instant(valid_to)) if moment is not None]
    if window:
        return min(window), max(window)
    if not observed_at:
        return None
    instant = ep.parse_instant(observed_at)
    if instant is not None:
        return instant, instant
    try:
        year = int(observed_at[:4])
        if precision == "YEAR_ONLY" or len(observed_at) == 4:
            begin = datetime(year, 1, 1, tzinfo=timezone.utc)
            return begin, datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
        month = int(observed_at[5:7])
        if precision == "MONTH_YEAR" or len(observed_at) == 7:
            begin = datetime(year, month, 1, tzinfo=timezone.utc)
            return begin, begin + timedelta(days=monthrange(year, month)[1]) - timedelta(microseconds=1)
        begin = datetime(year, month, int(observed_at[8:10]), tzinfo=timezone.utc)
        return begin, begin + timedelta(days=1) - timedelta(microseconds=1)
    except (ValueError, IndexError):
        return None


def _time_properties(row: Mapping[str, Any], now: datetime) -> Dict[str, Any]:
    temporal = ep.temporal_for(row)
    valid_from, valid_to = row.get("start_at"), row.get("end_at")
    span = time_span(temporal["observed_at"], temporal["temporal_precision"], valid_from, valid_to)
    state, state_basis = ep.temporal_state_at(row, now)
    if span is None:
        span_basis = "undated"
    elif ep.parse_instant(valid_from) or ep.parse_instant(valid_to):
        span_basis = "validity window as recorded"
    elif span[0] == span[1]:
        span_basis = "instant as recorded"
    else:
        unit = {4: "year", 7: "month"}.get(len(temporal["observed_at"] or ""), "day")
        span_basis = f"whole {unit} (UTC; the producer declares no time zone)"
    return {
        "observed_at": temporal["observed_at"],
        "temporal_precision": temporal["temporal_precision"],
        "valid_from": valid_from if isinstance(valid_from, str) else None,
        "valid_to": valid_to if isinstance(valid_to, str) else None,
        "time_start": _iso(span[0]) if span else None,
        "time_end": _iso(span[1]) if span else None,
        "time_basis": span_basis,
        "temporal_state": state,
        "temporal_state_basis": state_basis,
    }


def feature(stream: str, collection: str, row: Mapping[str, Any],
            now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """A GeoJSON point feature for a row with declared point precision, else None."""
    declared = ep.declared(row)
    precision = declared.get("geometry_precision")
    point = coordinates(row)
    record_id = _record_id(stream, row)
    if precision not in POINT_PRECISIONS or point is None or not record_id:
        return None
    return {
        "type": "Feature",
        "id": evidence_id(stream, record_id),
        "geometry": {"type": "Point", "coordinates": [point[0], point[1]]},
        "properties": {
            "evidence_id": evidence_id(stream, record_id),
            "stream": stream,
            "collection": collection,
            "record_id": record_id,
            "title": record_title(row, record_id),
            "category": category(stream, row),
            "object_type": object_type(row),
            "producer": producer(row),
            "producers": list(row.get("_producers") or []),
            "geometry_precision": precision,
            "geometry_basis": declared.get("coordinate_method") or declared.get("geometry_precision_basis"),
            "municipality": municipality(row),
            "synthetic": bool(row.get("synthetic", False)),
            "evidence_href": f"/evidence/{collection}/{record_id}",
            "entity_href": f"/entity/{record_id}" if stream == "entities" else None,
            **_time_properties(row, now or datetime.now(timezone.utc)),
        },
    }


def _in_bbox(point: Sequence[float], bbox: Optional[Sequence[float]]) -> bool:
    if bbox is None:
        return True
    lon, lat = point
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def parse_bbox(text: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    """``minLon,minLat,maxLon,maxLat`` -> tuple; ValueError on anything else."""
    if text in (None, ""):
        return None
    parts = str(text).split(",")
    try:
        values = tuple(float(part) for part in parts)
    except ValueError as error:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat") from error
    if len(values) != 4 or not (-180 <= values[0] < values[2] <= 180 and -90 <= values[1] < values[3] <= 90):
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat within WGS84 bounds")
    return values  # type: ignore[return-value]


def build_features(
    rows: Iterable[Row],
    *,
    bbox: Optional[Sequence[float]] = None,
    categories: Sequence[str] = (),
    producers: Sequence[str] = (),
    include_synthetic: bool = False,
    limit: int = DEFAULT_LIMIT,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """The mappable features, plus an account of every row that is not drawn and why.

    Every row that passes the producer and category filters is accounted for
    exactly once: ``loaded == matched + outside_bbox + excluded_synthetic +
    sum(not_drawn[*].count)``.
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    now = now or datetime.now(timezone.utc)
    wanted_categories, wanted_producers = set(categories), set(producers)
    features: List[Dict[str, Any]] = []
    category_counts: Dict[Tuple[str, str, str], int] = {}
    precision_counts: Dict[str, int] = {}
    unplaced: Dict[str, int] = {}
    not_drawn: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    area_refs: Dict[Tuple[str, str, str, str], Dict[str, int]] = {}
    loaded = excluded_synthetic = outside_bbox = 0
    for stream, collection, row in rows:
        if stream not in STREAMS:
            continue
        if wanted_producers and producer(row) not in wanted_producers:
            continue
        kind = category(stream, row)
        if wanted_categories and kind not in wanted_categories:
            continue
        loaded += 1
        if row.get("synthetic") and not include_synthetic:
            excluded_synthetic += 1
            continue
        item = feature(stream, collection, row, now)
        if item is not None:
            if not _in_bbox(item["geometry"]["coordinates"], bbox):
                outside_bbox += 1
                continue
            features.append(item)
            key = (item["properties"]["producer"], stream, kind)
            category_counts[key] = category_counts.get(key, 0) + 1
            precision = item["properties"]["geometry_precision"]
            precision_counts[precision] = precision_counts.get(precision, 0) + 1
            continue
        account = not_drawn.setdefault((producer(row), stream, kind),
                                       {"count": 0, "coordinates_without_point_precision": 0,
                                        "municipality_recorded": 0, "object_type_counts": {}})
        account["count"] += 1
        _tally(account["object_type_counts"], object_type(row))
        if coordinates(row) is not None:
            unplaced[producer(row)] = unplaced.get(producer(row), 0) + 1
            account["coordinates_without_point_precision"] += 1
        place = municipality(row)
        if place:
            account["municipality_recorded"] += 1
            _tally(area_refs.setdefault((producer(row), stream, kind, place), {}), object_type(row) or "")
    features.sort(key=lambda f: f["id"])
    starts = [f["properties"]["time_start"] for f in features if f["properties"]["time_start"]]
    ends = [f["properties"]["time_end"] for f in features if f["properties"]["time_end"]]
    return {
        "contract": CONTRACT_ID,
        "type": "FeatureCollection",
        "bbox_filter": list(bbox) if bbox else None,
        "include_synthetic": include_synthetic,
        "loaded": loaded,
        "matched": len(features),
        "truncated": len(features) > limit,
        "features": features[:limit],
        "categories": [{"producer": p, "stream": st, "category": c, "count": n}
                       for (p, st, c), n in sorted(category_counts.items())],
        "precision_counts": dict(sorted(precision_counts.items())),
        "excluded_synthetic": excluded_synthetic,
        "outside_bbox": outside_bbox,
        "time_extent": {"start": min(starts), "end": max(ends)} if starts else None,
        "undated": len(features) - len(starts),
        "read_at": _iso(now),
        "coordinates_without_point_precision": dict(sorted(unplaced.items())),
        "not_drawn": [{"producer": p, "stream": st, "category": c, **counts,
                       "object_type_counts": dict(sorted(counts["object_type_counts"].items()))}
                      for (p, st, c), counts in sorted(not_drawn.items())],
        "area_references": [
            {"producer": p, "stream": st, "category": c, "municipality_as_recorded": m, "count": sum(types.values()),
             "object_type_counts": {t: n for t, n in sorted(types.items()) if t}}
            for (p, st, c, m), types in sorted(area_refs.items())
        ],
    }


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres (spherical Earth, mean radius)."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))


def nearby(features: Iterable[Mapping[str, Any]], lat: float, lon: float, radius_m: float) -> List[Dict[str, Any]]:
    """Features within ``radius_m`` of a point, nearest first, each with its distance.

    Distance is to the feature's mapped point; for a REPRESENTATIVE_POINT that is
    a stand-in, which the result says rather than hides.
    """
    out: List[Dict[str, Any]] = []
    for item in features:
        f_lon, f_lat = item["geometry"]["coordinates"]
        meters = distance_m(lon, lat, f_lon, f_lat)
        if meters <= radius_m:
            props = dict(item["properties"])
            props["distance_m"] = round(meters, 1)
            props["distance_basis"] = ("distance to a representative point, not to the feature itself"
                                       if props["geometry_precision"] == "REPRESENTATIVE_POINT"
                                       else "distance to the mapped point")
            out.append(props)
    out.sort(key=lambda p: (p["distance_m"], p["evidence_id"]))
    return out

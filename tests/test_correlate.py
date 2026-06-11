"""Tests for cross-producer correlation (re-homed from spiderweb's query-hub)."""
from __future__ import annotations

import json
import re

import jsonschema
import pytest

from hub._schemas import load_schema
from hub.aggregate import aggregate
from hub.bridge import write_manifest
from hub.correlate import (
    _dedupe_links,
    _disjoint,
    _haversine_km,
    _link,
    _parse_date,
    _point,
    _to_relationship,
    correlate,
    correlate_by_external_id,
    correlate_entities,
    correlate_spatial,
    correlate_temporal,
    correlator_source,
    derive_relationships,
)

_TS = "2026-01-01T00:00:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": ["a.csv"]}
SRC = "src_0123456789abcdef0123456789abcdef"
ENT_A = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
ENT_B = "ent_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
ENT_C = "ent_cccccccccccccccccccccccccccccccc"


def _entity(entity_id, normalized_name, *, uei=None, lat=None, lon=None,
            producers=None, confidence=0.9):
    ent = {
        "entity_id": entity_id, "source_id": SRC, "name": normalized_name.title(),
        "normalized_name": normalized_name, "entity_type": "recipient",
        "jurisdiction": "PR", "confidence": confidence, "lineage": _LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }
    if uei:
        ent["external_ids"] = {"uei": uei}
    if lat is not None and lon is not None:
        ent["location"] = {"lat": lat, "lon": lon}
    if producers is not None:
        ent["_producers"] = producers
    return ent


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


# ── per-strategy units ───────────────────────────────────────────────────────

def test_entity_name_correlation_cross_producer():
    a = _entity(ENT_A, "ACME RECOVERY LLC", producers=["spiderweb-pr"])
    b = _entity(ENT_B, "ACME RECOVERY LLC", producers=["moneysweep-pr"])
    links = correlate_entities([a, b])
    assert len(links) == 1
    assert links[0]["match_basis"] == "normalized_name"
    assert {links[0]["source_entity_id"], links[0]["target_entity_id"]} == {ENT_A, ENT_B}


def test_external_id_correlation_cross_producer():
    a = _entity(ENT_A, "Acme", uei="ACME123", producers=["p1"])
    b = _entity(ENT_B, "Acme Inc", uei="ACME123", producers=["p2"])
    links = correlate_by_external_id([a, b])
    assert len(links) == 1
    assert links[0]["match_basis"] == "external_id:uei"


def test_spatial_correlation_within_threshold():
    a = _entity(ENT_A, "X", lat=18.4000, lon=-66.10, producers=["p1"])
    b = _entity(ENT_B, "Y", lat=18.4008, lon=-66.10, producers=["p2"])  # ~0.09 km
    far = _entity(ENT_C, "Z", lat=19.0, lon=-66.0, producers=["p3"])
    links = correlate_spatial([a, b, far], threshold_km=1.0)
    assert len(links) == 1
    assert {links[0]["source_entity_id"], links[0]["target_entity_id"]} == {ENT_A, ENT_B}


def test_temporal_correlation_on_awards():
    awd_a = {"recipient_entity_id": ENT_A, "award_date": "2026-03-01", "_producers": ["p1"]}
    awd_b = {"recipient_entity_id": ENT_B, "award_date": "2026-03-05", "_producers": ["p2"]}
    awd_c = {"recipient_entity_id": ENT_C, "award_date": "2026-06-01", "_producers": ["p3"]}
    assert len(correlate_temporal([awd_a, awd_b, awd_c], [], window_days=7)) == 1
    assert len(correlate_temporal([awd_a, awd_b, awd_c], [], window_days=120)) == 3


def test_temporal_empty_without_streams():
    assert correlate_temporal([], []) == []


# ── the _producers-disjoint guard (the central adaptation) ───────────────────

def test_same_producer_pair_not_linked():
    a = _entity(ENT_A, "ACME", uei="X1", producers=["p1"])
    b = _entity(ENT_B, "ACME", uei="X1", producers=["p1"])  # same producer
    assert correlate_entities([a, b]) == []
    assert correlate_by_external_id([a, b]) == []


def test_same_entity_id_not_self_linked():
    a = _entity(ENT_A, "ACME", producers=["p1", "p2"])  # already merged across producers
    assert correlate_entities([a]) == []


# ── emission: schema-validity + determinism + dedup ──────────────────────────

def test_emitted_rows_are_schema_valid():
    a = _entity(ENT_A, "ACME RECOVERY LLC", uei="ACME123", lat=18.40, lon=-66.10, producers=["p1"])
    b = _entity(ENT_B, "ACME RECOVERY LLC", uei="ACME123", lat=18.4008, lon=-66.10, producers=["p2"])
    rels = derive_relationships([a, b])
    assert rels
    rel_validator = jsonschema.Draft7Validator(load_schema("federation_relationship.schema.json"))
    for r in rels:
        rel_validator.validate(r)
        assert re.match(r"^rel_[a-f0-9]{32}$", r["relationship_id"])
    jsonschema.Draft7Validator(load_schema("federation_source.schema.json")).validate(correlator_source())


def test_name_and_external_id_collapse_to_one_edge():
    a = _entity(ENT_A, "ACME", uei="X1", producers=["p1"])
    b = _entity(ENT_B, "ACME", uei="X1", producers=["p2"])
    rels = derive_relationships([a, b])
    ec = [r for r in rels if r["relationship_type"] == "entity_correlation"]
    assert len(ec) == 1  # normalized_name + external_id collapse (max confidence wins)


def test_correlate_is_deterministic(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    ents = [
        _entity(ENT_A, "ACME", uei="X1", lat=18.4, lon=-66.1, producers=["p1"]),
        _entity(ENT_B, "ACME", uei="X1", lat=18.4, lon=-66.1, producers=["p2"]),
    ]
    _write_jsonl(agg / "entities.jsonl", ents)
    correlate(agg, tmp_path / "o1")
    correlate(agg, tmp_path / "o2")
    assert (tmp_path / "o1" / "correlations.jsonl").read_bytes() == \
        (tmp_path / "o2" / "correlations.jsonl").read_bytes()


# ── end-to-end: aggregate two producers, then correlate ──────────────────────

def _mint_package(directory, producer, entity_id, normalized_name, uei):
    directory.mkdir(parents=True, exist_ok=True)
    src = {
        "source_id": SRC, "source_type": "federal_grants", "source_name": "Src",
        "source_ref": "ref", "confidence": 1.0, "lineage": _LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }
    _write_jsonl(directory / "sources.jsonl", [src])
    _write_jsonl(directory / "entities.jsonl", [_entity(entity_id, normalized_name, uei=uei)])
    write_manifest(directory, producer)
    return directory


def test_aggregate_then_correlate_links_cross_producer(tmp_path):
    a = _mint_package(tmp_path / "a", "spiderweb-pr", ENT_A, "ACME RECOVERY LLC", "ACME123")
    b = _mint_package(tmp_path / "b", "moneysweep-pr", ENT_B, "ACME RECOVERY LLC", "ACME123")
    out = tmp_path / "agg"
    aggregate({"spiderweb-pr": a, "moneysweep-pr": b}, out)

    summary = correlate(out, out)
    assert summary["correlations"] >= 1
    assert summary["by_type"].get("entity_correlation") == 1

    lines = (out / "correlations.jsonl").read_text().splitlines()
    assert lines
    rel = json.loads(lines[0])
    assert {rel["source_entity_id"], rel["target_entity_id"]} == {ENT_A, ENT_B}
    assert rel["source_id"] == rel["evidence_source_id"]  # both point at the correlator source


# ── indexing equivalence: grid + sweep must match the naive all-pairs scan ────
#
# The spatial grid (correlate_spatial) and the date-sorted sweep
# (correlate_temporal) are pure optimizations: they must emit a set of links
# whose post-dedupe/post-sort relationship rows are *byte-identical* to the
# original O(n²) all-pairs versions. The reference loops below are verbatim
# copies of that pre-index logic; we run a dataset large enough to span many
# grid cells (in both lat AND lon, including longitude-dominated near-threshold
# pairs and high latitudes where lon cells must widen) and a wide date range
# (most pairs outside the window, so the sweep's early-exit fires) through both
# the indexed function and the reference, then assert the final rows match.

def _naive_spatial(entities, threshold_km=1.0):
    pts = [(e, _point(e)) for e in entities]
    pts = [(e, p) for e, p in pts if p is not None]
    links = []
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


def _naive_temporal(awards, transactions, window_days=7):
    anchored = []
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
    links = []
    for i in range(len(anchored)):
        for j in range(i + 1, len(anchored)):
            ea, da, ra = anchored[i]
            eb, db, rb = anchored[j]
            if ea == eb or not _disjoint(ra, rb):
                continue
            delta = abs((da - db).days)
            if delta > window_days:
                continue
            conf = round(max(0.0, 1.0 - 0.5 * (delta / window_days)), 3)
            links.append(_link(ea, eb, "temporal_proximity", "award_transaction_date",
                               conf, f"Cross-producer funding activity within {delta} day(s)."))
    return links


def _rows(links):
    """Drive links through the real dedupe + emit + sort pipeline → final rows."""
    rels = [_to_relationship(link) for link in _dedupe_links(links)]
    rels.sort(key=lambda r: (r["relationship_type"],
                             r["source_entity_id"], r["target_entity_id"]))
    return rels


def _eid(n):
    return "ent_" + f"{n:032d}"


def test_spatial_grid_matches_naive_allpairs():
    # ~60 points spread over several lat/lon hot-spots, each a tight cluster so
    # many fall inside the 1 km threshold; some clusters are separated mainly in
    # longitude and sit at high latitude (where the lon cell must be widened).
    spots = [
        (0.0, 0.0), (18.4000, -66.1000), (18.4005, -66.0990),  # near-equator + PR
        (45.0000, 7.0000), (45.0000, 7.00010),                  # lon-dominated pair
        (64.0000, -21.9000), (64.00005, -21.89980),             # high-lat lon-dominated
        (-33.8688, 151.2093),                                   # southern hemisphere
    ]
    ents = []
    n = 0
    for si, (blat, blon) in enumerate(spots):
        for k in range(8):
            jitter_lat = blat + (k - 4) * 0.0009          # ~0.1 km steps in lat
            jitter_lon = blon + (k - 4) * 0.0009
            ents.append({"entity_id": _eid(n),
                         "location": {"lat": jitter_lat, "lon": jitter_lon},
                         "_producers": [f"p{(si + k) % 5}"]})
            n += 1

    # A discriminating longitude-dominated pair at high latitude: ~0.90 km apart
    # (well within 1 km) but separated by ~2 *un-widened* lon cells, so it is
    # ONLY found when the grid widens lon cells by 1/cos(lat). Without the
    # widening this pair is missed → the test fails, pinning the trap.
    ents.append({"entity_id": _eid(n),
                 "location": {"lat": 64.0, "lon": 30.00000}, "_producers": ["p0"]})
    n += 1
    ents.append({"entity_id": _eid(n),
                 "location": {"lat": 64.0, "lon": 30.01850}, "_producers": ["p1"]})
    n += 1

    for thr in (0.5, 1.0, 2.0):
        got = _rows(correlate_spatial(ents, threshold_km=thr))
        exp = _rows(_naive_spatial(ents, threshold_km=thr))
        assert got == exp, f"spatial grid != naive at threshold_km={thr}"
    # sanity: the dataset actually produced cross-producer spatial links
    assert _rows(correlate_spatial(ents, threshold_km=1.0))


def test_temporal_sweep_matches_naive_allpairs():
    # ~40 awards across a year so most pairs fall OUTSIDE a 7-day window (the
    # sweep's forward early-exit must fire), with deliberate same-day and
    # within-window clusters that DO link, across multiple producers.
    from datetime import date, timedelta

    base = date(2026, 1, 1)
    day_offsets = []
    # three tight clusters (days 0-4, 100-103, 300-302) + scattered singletons
    day_offsets += [0, 1, 2, 3, 4, 4]
    day_offsets += [100, 101, 102, 103]
    day_offsets += [300, 300, 301, 302]
    day_offsets += list(range(10, 300, 17))  # scattered, mostly isolated
    awards = []
    for k, off in enumerate(day_offsets):
        awards.append({
            "recipient_entity_id": _eid(k % 11),           # reused ids → some self-pairs
            "award_date": (base + timedelta(days=off)).isoformat(),
            "_producers": [f"p{k % 4}"],
        })
    # Pairs landing EXACTLY on each window edge (delta == window_days), distinct
    # ids + disjoint producers, so the boundary comparison (``> window`` vs
    # ``>= window``) is exercised: these must link at the named window.
    for anchor, win in ((500, 7), (600, 30), (700, 120), (900, 365)):
        awards.append({"recipient_entity_id": _eid(50 + win),
                       "award_date": (base + timedelta(days=anchor)).isoformat(),
                       "_producers": ["pa"]})
        awards.append({"recipient_entity_id": _eid(51 + win),
                       "award_date": (base + timedelta(days=anchor + win)).isoformat(),
                       "_producers": ["pb"]})

    for win in (7, 30, 120, 365):
        got = _rows(correlate_temporal(awards, [], window_days=win))
        exp = _rows(_naive_temporal(awards, [], window_days=win))
        assert got == exp, f"temporal sweep != naive at window_days={win}"
    # sanity: the clusters did produce cross-producer temporal links
    assert _rows(correlate_temporal(awards, [], window_days=7))


def test_temporal_sweep_byte_identical_with_mixed_streams():
    """Awards + transactions mixed, wide window — full derive_relationships
    output must be byte-identical to the naive reference end-to-end."""
    from datetime import date, timedelta

    base = date(2026, 5, 1)
    awards = [
        {"recipient_entity_id": _eid(k % 7),
         "award_date": (base + timedelta(days=d)).isoformat(),
         "_producers": [f"p{k % 3}"]}
        for k, d in enumerate([0, 2, 5, 9, 40, 41, 80])
    ]
    txns = [
        {"payee_entity_id": _eid(k % 7),
         "transaction_date": (base + timedelta(days=d)).isoformat(),
         "_producers": [f"q{k % 3}"]}
        for k, d in enumerate([1, 3, 6, 42, 81, 82])
    ]
    got = derive_relationships([], awards, txns, window_days=90)
    exp = _rows(_naive_temporal(awards, txns, window_days=90))
    assert json.dumps(got, sort_keys=True) == json.dumps(exp, sort_keys=True)
    assert got  # the mixed streams produced temporal links

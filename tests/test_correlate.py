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

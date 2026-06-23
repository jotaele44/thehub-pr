"""Tests for graph_report: quality metrics over an aggregate directory."""
from __future__ import annotations

import json
from pathlib import Path


from hub.graph_report import graph_report

_TS = "2026-01-01T00:00:00Z"
_LINEAGE = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}

ENT_A = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0001"
ENT_B = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0002"
ENT_C = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0003"  # orphan (no edges)
REL_AB = "rel_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0001"
SRC = "src_0123456789abcdef0123456789abcdef"


def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _entity(eid, *, external_ids=None, producers=None):
    e = {
        "entity_id": eid, "source_id": SRC, "name": eid, "normalized_name": eid.upper(),
        "entity_type": "recipient", "jurisdiction": "PR", "confidence": 0.9,
        "lineage": _LINEAGE, "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }
    if external_ids:
        e["external_ids"] = external_ids
    if producers:
        e["_producers"] = producers
    return e


def _relationship(rid, src_eid, tgt_eid, *, confidence=0.9):
    return {
        "relationship_id": rid, "source_id": SRC,
        "source_entity_id": src_eid, "target_entity_id": tgt_eid,
        "relationship_type": "received_award_from",
        "evidence_source_id": SRC, "confidence": confidence,
        "lineage": _LINEAGE, "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }


def _correlation(src_eid, tgt_eid, *, match_basis="normalized_name", producers=None, confidence=0.9):
    return {
        "relationship_id": f"rel_{abs(hash(src_eid+tgt_eid)):032x}"[:36],
        "source_id": SRC,
        "source_entity_id": src_eid, "target_entity_id": tgt_eid,
        "entity_a_id": src_eid, "entity_b_id": tgt_eid,
        "relationship_type": "entity_correlation",
        "evidence_source_id": SRC, "confidence": confidence,
        "match_basis": match_basis,
        "lineage": _LINEAGE, "synthetic": True, "created_at": _TS, "extracted_at": _TS,
        "_producers": producers or ["p1", "p2"],
    }


# ── empty aggregate ───────────────────────────────────────────────────────────

def test_empty_directory(tmp_path):
    report = graph_report(tmp_path)
    assert report["entity_count"] == 0
    assert report["orphan_entities"] == 0
    assert report["duplicate_external_ids"] == {}
    assert report["low_confidence_edges"] == 0
    assert report["producer_pair_counts"] == {}
    assert report["match_basis_distribution"] == {}


# ── orphan entities ───────────────────────────────────────────────────────────

def test_orphan_entities_counted(tmp_path):
    _write_jsonl(tmp_path / "entities.jsonl", [
        _entity(ENT_A), _entity(ENT_B), _entity(ENT_C),
    ])
    _write_jsonl(tmp_path / "relationships.jsonl", [
        _relationship(REL_AB, ENT_A, ENT_B),
    ])
    report = graph_report(tmp_path)
    assert report["orphan_entities"] == 1  # ENT_C has no edges
    assert report["entity_count"] == 3
    assert report["relationship_count"] == 1


def test_no_orphans_when_all_referenced(tmp_path):
    _write_jsonl(tmp_path / "entities.jsonl", [_entity(ENT_A), _entity(ENT_B)])
    _write_jsonl(tmp_path / "relationships.jsonl", [_relationship(REL_AB, ENT_A, ENT_B)])
    report = graph_report(tmp_path)
    assert report["orphan_entities"] == 0


def test_correlations_satisfy_orphan_check(tmp_path):
    _write_jsonl(tmp_path / "entities.jsonl", [_entity(ENT_A), _entity(ENT_B)])
    # no relationships.jsonl; entities referenced only in correlations
    _write_jsonl(tmp_path / "correlations.jsonl", [_correlation(ENT_A, ENT_B)])
    report = graph_report(tmp_path)
    assert report["orphan_entities"] == 0


# ── duplicate external IDs ────────────────────────────────────────────────────

def test_duplicate_external_ids_detected(tmp_path):
    _write_jsonl(tmp_path / "entities.jsonl", [
        _entity(ENT_A, external_ids={"uei": "SHARED123"}),
        _entity(ENT_B, external_ids={"uei": "SHARED123"}),
        _entity(ENT_C, external_ids={"uei": "UNIQUE999"}),
    ])
    report = graph_report(tmp_path)
    dupes = report["duplicate_external_ids"]
    assert "SHARED123" in dupes
    assert sorted(dupes["SHARED123"]) == sorted([ENT_A, ENT_B])
    assert "UNIQUE999" not in dupes


def test_no_duplicate_external_ids(tmp_path):
    _write_jsonl(tmp_path / "entities.jsonl", [
        _entity(ENT_A, external_ids={"uei": "AAA"}),
        _entity(ENT_B, external_ids={"uei": "BBB"}),
    ])
    report = graph_report(tmp_path)
    assert report["duplicate_external_ids"] == {}


# ── low-confidence edges ──────────────────────────────────────────────────────

def test_low_confidence_edges_counted(tmp_path):
    _write_jsonl(tmp_path / "relationships.jsonl", [
        _relationship(REL_AB, ENT_A, ENT_B, confidence=0.3),   # low
        _relationship("rel_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0002", ENT_B, ENT_C, confidence=0.8),   # high
        _relationship("rel_aaaaaaaaaaaaaaaaaaaaaaaaaaaa0003", ENT_A, ENT_C, confidence=0.49),  # low
    ])
    report = graph_report(tmp_path)
    assert report["low_confidence_edges"] == 2


def test_no_low_confidence_edges(tmp_path):
    _write_jsonl(tmp_path / "relationships.jsonl", [
        _relationship(REL_AB, ENT_A, ENT_B, confidence=0.9),
    ])
    report = graph_report(tmp_path)
    assert report["low_confidence_edges"] == 0


# ── producer-pair counts ──────────────────────────────────────────────────────

def test_producer_pair_counts(tmp_path):
    _write_jsonl(tmp_path / "correlations.jsonl", [
        _correlation(ENT_A, ENT_B, producers=["moneysweep-pr", "spiderweb-pr"]),
        _correlation(ENT_A, ENT_C, producers=["moneysweep-pr", "spiderweb-pr"]),
        _correlation(ENT_B, ENT_C, producers=["aguayluz-pr", "moneysweep-pr"]),
    ])
    report = graph_report(tmp_path)
    pairs = report["producer_pair_counts"]
    assert pairs["moneysweep-pr+spiderweb-pr"] == 2
    assert pairs["aguayluz-pr+moneysweep-pr"] == 1


def test_producer_pair_counts_empty_without_correlations(tmp_path):
    report = graph_report(tmp_path)
    assert report["producer_pair_counts"] == {}


# ── match-basis distribution ──────────────────────────────────────────────────

def test_match_basis_distribution(tmp_path):
    _write_jsonl(tmp_path / "correlations.jsonl", [
        _correlation(ENT_A, ENT_B, match_basis="normalized_name"),
        _correlation(ENT_A, ENT_C, match_basis="normalized_name"),
        _correlation(ENT_B, ENT_C, match_basis="external_id:uei"),
    ])
    report = graph_report(tmp_path)
    dist = report["match_basis_distribution"]
    assert dist["normalized_name"] == 2
    assert dist["external_id:uei"] == 1


def test_match_basis_unknown_when_field_absent(tmp_path):
    # correlation without match_basis field
    row = _correlation(ENT_A, ENT_B)
    del row["match_basis"]
    _write_jsonl(tmp_path / "correlations.jsonl", [row])
    report = graph_report(tmp_path)
    assert report["match_basis_distribution"].get("unknown") == 1

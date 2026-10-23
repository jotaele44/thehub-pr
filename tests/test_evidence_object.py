"""FEDERATION_EVIDENCE_OBJECT_V1 / FEDERATION_EVIDENCE_LINEAGE_V1 fixtures.

Positive: committed aggregate rows project into schema-valid Evidence Objects.
Negative: invented precision, fabricated lineage, proximity-only edges,
unsupported absence and silently-merged contradictions are all rejected.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hub.evidence_lineage import build_lineage, validate_edge, validate_lineage
from hub.evidence_object import evidence_id, project_evidence_object, row_sha256, validate_evidence_object

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = REPO_ROOT / "data" / "aggregate"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

SOURCES = {"src_1": {"source_id": "src_1", "source_name": "FOIA release", "source_url": "https://example.gov/foia/1"}}


def _obs(**extra):
    row = {
        "observation_id": "obs_1",
        "_producers": ["ovnis-pr"],
        "observation_type": "uap_case",
        "source_id": "src_1",
        "observed_at": "1929-01-01T00:00:00-04:00",
        "date_local": "1929",
        "date_precision": "year",
        "location": {"lat": 18.25, "lon": -67.15, "municipality": "island-wide"},
        "confidence": 0.5,
        "synthetic": False,
        "extracted_at": "2026-07-28T15:43:36Z",
        "lineage": {"extraction_method": "deterministic_case_projection", "producer_phase": "OBSERVATION",
                    "producer_script": "scripts/federation_export.py", "source_inputs": ["data/master/master_cases.jsonl"]},
    }
    row.update(extra)
    return row


def _rows(stream):
    path = AGGREGATE / f"{stream}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── positive ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("stream", ["sources", "entities", "observations", "relationships", "alerts", "correlations"])
def test_committed_aggregate_projects_to_valid_evidence_objects(stream):
    sources = {r["source_id"]: r for r in _rows("sources")}
    for row in _rows(stream):
        obj = project_evidence_object(stream, row, now=NOW, sources_index=sources)
        assert validate_evidence_object(obj) == [], obj["id"]
        assert obj["synthetic"] is bool(row.get("synthetic", False))
        assert obj["audit_metadata"]["row_sha256"] == row_sha256(row)


def test_projection_is_pure_and_deterministic():
    row = _obs()
    before = copy.deepcopy(row)
    first = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    second = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert row == before
    assert first == second
    assert first["id"] == evidence_id("observations", "obs_1") == "evo:observations:obs_1"


def test_source_lineage_resolves_to_documented_edge():
    obj = project_evidence_object("observations", _obs(), now=NOW, sources_index=SOURCES)
    assert obj["source_state"] == "SOURCE_BOUND"
    documents = [e for e in obj["lineage"]["edges"] if e["relationship_type"] == "DOCUMENTS"]
    assert documents and documents[0]["edge_state"] == "DOCUMENTED"
    assert obj["citations"] == [{"source_id": "src_1", "title": "FOIA release", "url": "https://example.gov/foia/1",
                                 "citation_text": None, "source_state": "SOURCE_BOUND"}]


def test_producer_declared_state_flows_through():
    row = _obs(evidence_state={"epistemic_class": "CURATED", "observation_state": "OBSERVED_PRESENT",
                               "geometry_precision": "AREA_REFERENCE"})
    row["location"] = {"municipality": "Guayama"}
    obj = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert (obj["epistemic_class"], obj["epistemic_class_basis"]) == ("CURATED", "PRODUCER_DECLARED")
    assert obj["observation_state"] == "OBSERVED_PRESENT"
    assert obj["geometry_precision"] == "AREA_REFERENCE"
    assert validate_evidence_object(obj) == []


def test_interpretive_object_carries_its_interpretation():
    row = _obs(evidence_state={"epistemic_class": "INTERPRETIVE", "interpretation_basis": "reported-void model"})
    obj = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert obj["interpretations"] == [{"basis": "reported-void model", "author": "ovnis-pr"}]
    assert validate_evidence_object(obj) == []


def test_hub_correlation_is_computed_candidate():
    row = {"relationship_id": "rel_1", "relationship_type": "spatial_proximity", "match_basis": "location",
           "source_entity_id": "ent_a", "target_entity_id": "ent_b", "source_id": "src_1", "synthetic": True,
           "lineage": {"producer_script": "src/hub/correlate.py", "source_inputs": ["entities.jsonl"]}}
    obj = project_evidence_object("correlations", row, now=NOW, sources_index=SOURCES)
    assert obj["producer_repo"] == "thehub-pr"
    assert obj["epistemic_class"] == "COMPUTED"
    assert obj["data_stage"] == "COMPUTATION"
    assert obj["computations"][0]["method"] == "location"
    edge = next(e for e in obj["lineage"]["edges"] if e["relationship_type"] == "spatial_proximity")
    assert edge["edge_state"] == "CANDIDATE"
    assert validate_evidence_object(obj) == []


def test_structured_contradictions_are_preserved():
    row = _obs(contradictions=[{"contradiction_id": "c-date", "claim_a": "1929", "source_a": "src_1",
                                "claim_b": "1931", "source_b": "src_2", "status": "OPEN",
                                "adjudication": None, "rationale": None}])
    obj = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert obj["contradictions"][0]["claim_a"] == "1929"
    assert obj["contradictions"][0]["claim_b"] == "1931"
    assert validate_evidence_object(obj) == []


# ── negative ──────────────────────────────────────────────────────────────────


def test_year_only_observation_never_renders_invented_time():
    obj = project_evidence_object("observations", _obs(), now=NOW, sources_index=SOURCES)
    assert obj["observed_at"] == "1929"
    assert obj["temporal_precision"] == "YEAR_ONLY"
    tampered = dict(obj, observed_at="1929-01-01T00:00:00-04:00")
    assert any("more precision than YEAR_ONLY" in e for e in validate_evidence_object(tampered))


def test_missing_source_does_not_fabricate_lineage():
    obj = project_evidence_object("observations", _obs(source_id=None), now=NOW, sources_index=SOURCES)
    assert obj["source_state"] == "SOURCE_MISSING"
    assert obj["raw_source_ids"] == []
    assert not [e for e in obj["lineage"]["edges"] if e["relationship_type"] == "DOCUMENTS"]
    assert any(n["kind"] == "SOURCE_MISSING" for n in obj["lineage"]["nodes"])


def test_unresolvable_source_edge_is_not_documented():
    obj = project_evidence_object("observations", _obs(source_id="src_unknown"), now=NOW, sources_index=SOURCES)
    edge = next(e for e in obj["lineage"]["edges"] if e["relationship_type"] == "DOCUMENTS")
    assert (obj["source_state"], edge["edge_state"]) == ("SOURCE_REPORTED", "UNKNOWN")


def test_invalid_declarations_are_reported_not_trusted():
    row = _obs(evidence_state={"epistemic_class": "FACT", "observation_state": "OBSERVED_ABSENT"})
    obj = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert obj["epistemic_class"] == "UNCLASSIFIED"
    assert obj["observation_state"] == "NOT_OBSERVED"
    assert any("'FACT' is not a valid value" in e for e in obj["declaration_errors"])


def test_semantic_invariants_reject_tampered_objects():
    obj = project_evidence_object("observations", _obs(), now=NOW, sources_index=SOURCES)
    cases = {
        "requires a point geometry": dict(obj, geometry_precision="OBSERVED_POINT", geometry=None),
        "must not carry a point geometry": dict(obj, geometry_precision="AREA_REFERENCE"),
        "requires a declared absence basis": dict(obj, observation_state="OBSERVED_ABSENT"),
        "requires an interpretation basis": dict(obj, epistemic_class="INTERPRETIVE", epistemic_class_basis="PRODUCER_DECLARED"),
        "basis must be NONE": dict(obj, epistemic_class="MEASURED"),
    }
    for message, tampered in cases.items():
        assert any(message in e for e in validate_evidence_object(tampered)), message


def test_schema_rejects_unknown_axis_values():
    obj = project_evidence_object("observations", _obs(), now=NOW, sources_index=SOURCES)
    errors = validate_evidence_object(dict(obj, geometry_precision="EXACT"))
    assert any(e.startswith("schema: geometry_precision") for e in errors)


def test_malformed_contradiction_is_reported():
    row = _obs(contradictions=[{"claim_a": "1929"}, "text"])
    obj = project_evidence_object("observations", row, now=NOW, sources_index=SOURCES)
    assert obj["contradictions"] == []
    assert len([e for e in obj["declaration_errors"] if "original claims were not recorded" in e]) == 2


def test_unknown_stream_and_missing_id_raise():
    with pytest.raises(ValueError):
        project_evidence_object("tweets", {}, now=NOW)
    with pytest.raises(ValueError):
        project_evidence_object("observations", {"observed_at": "x"}, now=NOW)


def test_source_row_without_locator():
    obj = project_evidence_object("sources", {"source_id": "s", "source_type": "none"}, now=NOW)
    assert obj["source_state"] == "SOURCE_REPORTED"
    assert obj["canonical_type"] == "source:none"


def test_citation_text_is_never_rendered_as_a_locator():
    sources = {"src_t": {"source_id": "src_t", "source_name": "Inexplicata", "source_url": "Inexplicata/Scott Corrales/Freixedo"}}
    obj = project_evidence_object("observations", _obs(source_id="src_t"), now=NOW, sources_index=sources)
    assert obj["source_state"] == "SOURCE_REPORTED"
    assert obj["citations"][0]["url"] is None
    assert obj["citations"][0]["citation_text"] == "Inexplicata/Scott Corrales/Freixedo"
    assert validate_evidence_object(obj) == []


# ── lineage edges ─────────────────────────────────────────────────────────────


def _edge(**extra):
    edge = {"edge_id": "e1", "relationship_type": "FUNDS", "from": "a", "to": "b", "producer": "moneysweep-pr",
            "edge_state": "DOCUMENTED", "derivation_method": "award_record", "evidence_ids": ["src_1"]}
    edge.update(extra)
    return edge


def test_documented_contract_edge_validates():
    assert validate_edge(_edge()) == []


@pytest.mark.parametrize("method", ["location", "spatial_proximity", "temporal_proximity", "normalized_name", "similar_name"])
def test_proximity_timing_or_name_cannot_document_an_edge(method):
    for state in ("DOCUMENTED", "COMPUTED"):
        errors = validate_edge(_edge(edge_state=state, derivation_method=method))
        assert any("cannot rest solely" in e for e in errors)
    assert validate_edge(_edge(edge_state="CANDIDATE", derivation_method=method)) == []


def test_documented_edge_without_evidence_and_bad_state():
    assert "DOCUMENTED edge requires evidence_ids" in validate_edge(_edge(evidence_ids=[]))
    assert any("not valid" in e for e in validate_edge(_edge(edge_state="PROBABLE")))
    assert "edge missing producer" in validate_edge(_edge(producer=""))


def test_lineage_endpoints_and_node_kinds_are_checked():
    lineage = build_lineage("observations", _obs(), "record:x", producer="ovnis-pr", source_state="SOURCE_BOUND")
    assert validate_lineage(lineage) == []
    broken = {"nodes": [{"node_id": "record:x", "kind": "GUESS", "label": ""}], "edges": lineage["edges"]}
    errors = validate_lineage(broken)
    assert any("kind 'GUESS' is not valid" in e for e in errors)
    assert any("is not a node" in e for e in errors)

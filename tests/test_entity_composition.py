"""FEDERATION_ENTITY_COMPOSITION_V1 (hub.entity_composition).

Positive: an entity composes with its edges, linked records, sources and
per-producer sections, and validates against the candidate schema.
Negative: identity is never inferred, proximity correlations stay CANDIDATE,
unresolved counterparts are not fabricated, limits truncate explicitly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hub.entity_composition import compose_entity, validate_entity_composition

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
SOURCES = {"src_1": {"source_id": "src_1", "source_name": "Registry", "source_url": "https://example.gov/r"}}
ANCHOR = {"entity_id": "ent_a", "name": "Laguna Cartagena", "entity_type": "wetland", "source_id": "src_1",
          "_producers": ["spiderweb-pr"], "synthetic": False}
OTHER = {"entity_id": "ent_b", "name": "Lajas", "entity_type": "municipality", "_producers": ["ovnis-pr"]}


def _rel(rid, source, target, **extra):
    row = {"relationship_id": rid, "relationship_type": "located_in", "source_entity_id": source,
           "target_entity_id": target, "source_id": "src_1", "_producers": ["spiderweb-pr"], "synthetic": False}
    row.update(extra)
    return row


def _compose(**kwargs):
    defaults = {
        "now": NOW,
        "edges": [("Relationships", _rel("rel_1", "ent_a", "ent_b")),
                  ("Correlations", _rel("rel_2", "ent_c", "ent_a", relationship_type="spatial_proximity",
                                        match_basis="location", _producers=[]))],
        "linked": [("Observations", {"observation_id": "obs_1", "entity_id": "ent_a", "observation_type": "uap_case",
                                     "_producers": ["ovnis-pr"]}),
                   ("Alerts", {"alert_id": "alrt_1", "entity_id": "ent_a", "alert_type": "outage",
                               "_producers": ["aguayluz-pr"], "synthetic": True})],
        "counterparts": {"ent_b": OTHER},
        "sources": SOURCES,
    }
    defaults.update(kwargs)
    return compose_entity(ANCHOR, **defaults)


def test_composition_validates_and_links_back_to_producers():
    body = _compose()
    assert validate_entity_composition(body) == []
    assert body["anchor"]["id"] == "evo:entities:ent_a"
    assert [r["record_id"] for r in body["relationships"]] == ["rel_2", "rel_1"]
    assert {r["evidence_href"] for r in body["linked_records"]} == {"/evidence/Observations/obs_1",
                                                                     "/evidence/Alerts/alrt_1"}
    assert body["anchor"]["citations"][0]["source_id"] == "src_1"


def test_edge_direction_counterpart_and_state():
    edges = {r["record_id"]: r for r in _compose()["relationships"]}
    documented = edges["rel_1"]
    assert documented["direction"] == "OUTBOUND"
    assert documented["counterpart"] == {"record_id": "ent_b", "title": "Lajas", "resolved": True,
                                         "entity_href": "/entity/ent_b"}
    assert documented["edge_state"] == "DOCUMENTED"
    proximity = edges["rel_2"]
    assert proximity["direction"] == "INBOUND"
    assert proximity["edge_state"] == "CANDIDATE"
    assert proximity["producers"] == ["thehub-pr"]


def test_unresolved_counterpart_is_not_fabricated():
    proximity = next(r for r in _compose()["relationships"] if r["record_id"] == "rel_2")
    assert proximity["counterpart"] == {"record_id": "ent_c", "title": None, "resolved": False, "entity_href": None}


def test_identity_is_reported_not_inferred():
    identity = _compose()["identity"]
    assert identity["identity_state"] == "UNRESOLVED"
    assert identity["identity_scope"] == "PRODUCER_LOCAL"
    assert identity["registry_status"] == "NOT_CONFIGURED"
    assert identity["members"] == [{"producer": "spiderweb-pr", "collection": "Entities", "record_id": "ent_a"}]


def test_registry_membership_is_used_only_when_supplied():
    body = _compose(registry_membership={"state": "RESOLVED", "match_class": "EXACT_IDENTIFIER"})
    assert body["identity"]["registry_status"] == "CONSULTED"
    assert body["identity"]["identity_state"] == "BOUND"
    candidate = _compose(registry_membership={"state": "CANDIDATE"})
    assert candidate["identity"]["identity_state"] == "CANDIDATE"


def test_sections_cover_in_scope_producers_without_inventing_data():
    sections = {s["producer"]: s for s in _compose()["sections"]}
    assert sections["spiderweb-pr"]["status"] == "AVAILABLE"
    assert sections["ovnis-pr"]["linked_record_count"] == 1
    assert sections["thehub-pr"]["relationship_count"] == 1
    assert sections["moneysweep-pr"] == {"producer": "moneysweep-pr", "status": "NO_DATA",
                                         "relationship_count": 0, "linked_record_count": 0}


def test_synthetic_linked_records_stay_flagged():
    alert = next(r for r in _compose()["linked_records"] if r["record_id"] == "alrt_1")
    assert alert["synthetic"] is True


def test_limits_truncate_explicitly():
    edges = [("Relationships", _rel(f"rel_{i:02d}", "ent_a", "ent_b")) for i in range(5)]
    body = _compose(edges=edges, relationship_limit=3, linked_limit=1)
    assert len(body["relationships"]) == 3 and body["truncated"]["relationships"] is True
    assert len(body["linked_records"]) == 1 and body["truncated"]["linked_records"] is True
    assert validate_entity_composition(body) == []


def test_unknown_collections_are_ignored_and_missing_id_raises():
    body = _compose(edges=[("Tweets", {"relationship_id": "x"})], linked=[("Programs", {"id": "p"})])
    assert body["relationships"] == [] and body["linked_records"] == []
    with pytest.raises(ValueError):
        compose_entity({"name": "no id"}, now=NOW)


def test_schema_rejects_a_tampered_composition():
    body = _compose()
    body["identity"]["identity_state"] = "PROBABLY_THE_SAME"
    body["relationships"][0]["edge_state"] = "LIKELY"
    errors = validate_entity_composition(body)
    assert any("identity_state" in e for e in errors)
    assert any("edge_state" in e for e in errors)

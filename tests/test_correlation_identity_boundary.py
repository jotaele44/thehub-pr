"""Regression gates for the correlation/identity boundary."""

from hub.correlate import _to_relationship


ENT_A = "ent_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
ENT_B = "ent_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _link(match_basis: str) -> dict:
    return {
        "source_entity_id": ENT_A,
        "target_entity_id": ENT_B,
        "relationship_type": "entity_correlation",
        "match_basis": match_basis,
        "confidence": 0.9,
        "explanation": "test candidate",
    }


def test_normalized_name_relationship_is_candidate_not_identity():
    row = _to_relationship(_link("normalized_name"))
    assert row["identity_assertion"] is False
    assert row["identity_adjudication_state"] == "CANDIDATE"
    assert row["identity_cardinality"] == "UNRESOLVED"
    assert row["identity_evidence_class"] == "WEAK_CORRELATION"


def test_location_relationship_is_candidate_not_identity():
    row = _to_relationship(_link("location"))
    assert row["identity_assertion"] is False
    assert row["identity_adjudication_state"] == "CANDIDATE"
    assert row["identity_cardinality"] == "UNRESOLVED"
    assert row["identity_evidence_class"] == "WEAK_CORRELATION"


def test_external_identifier_is_still_only_a_candidate():
    row = _to_relationship(_link("external_id:uei"))
    assert row["identity_assertion"] is False
    assert row["identity_adjudication_state"] == "CANDIDATE"
    assert row["identity_cardinality"] == "UNRESOLVED"
    assert row["identity_evidence_class"] == "HARD_IDENTIFIER_CANDIDATE"

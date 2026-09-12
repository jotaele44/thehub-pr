from __future__ import annotations

from scripts.authority_boundary_validator import AUTHORITY, validate_relationship_census


def _ids(blockers: list[dict]) -> set[str]:
    return {row["id"] for row in blockers}


def test_unknown_literal_fails() -> None:
    registry = {"shared_relationships": [], "domain_registries": [], "hub_derived": {}}
    blockers, _ = validate_relationship_census({"spiderweb-pr": {"mystery_link": {"scripts/export.py"}}}, registry)
    assert "AB-004-UNKNOWN-RELATIONSHIP-LITERAL" in _ids(blockers)


def test_two_domain_owners_are_ambiguous() -> None:
    registry = {"shared_relationships": [], "domain_registries": [
        {"owner": "spiderweb-pr", "scope": "DOMAIN_ONLY", "types": ["linked_to"]},
        {"owner": "aguayluz-pr", "scope": "DOMAIN_ONLY", "types": ["linked_to"]}], "hub_derived": {}}
    blockers, _ = validate_relationship_census({"spiderweb-pr": {"linked_to": {"scripts/export.py"}}}, registry)
    assert "AB-004-AMBIGUOUS-RELATIONSHIP-LITERAL" in _ids(blockers)


def test_cross_producer_literal_requires_shared_registration() -> None:
    registry = {"shared_relationships": [], "domain_registries": [
        {"owner": "spiderweb-pr", "scope": "DOMAIN_ONLY", "types": ["located_in"]}], "hub_derived": {}}
    census = {"spiderweb-pr": {"located_in": {"scripts/export.py"}}, "ovnis-pr": {"located_in": {"scripts/export.py"}}}
    blockers, _ = validate_relationship_census(census, registry)
    assert "AB-004-CROSS-PRODUCER-COLLISION" in _ids(blockers)


def test_producer_cannot_emit_another_domain_owner_literal() -> None:
    registry = {"shared_relationships": [], "domain_registries": [
        {"owner": "moneysweep-pr", "scope": "DOMAIN_ONLY", "types": ["owns"]}], "hub_derived": {}}
    blockers, _ = validate_relationship_census({"aguayluz-pr": {"owns": {"scripts/export.py"}}}, registry)
    assert "AB-004-RELATIONSHIP-OWNER-MISMATCH" in _ids(blockers)


def test_hub_correlation_does_not_become_identity_authority() -> None:
    registry = {"shared_relationships": [], "domain_registries": [], "hub_derived": {
        "owner": "thehub-pr", "scope": "SHARED_DERIVED_CANDIDATE", "types": ["spatial_proximity"]}}
    blockers, resolutions = validate_relationship_census({"thehub-pr": {"spatial_proximity": {"src/hub/correlate.py"}}}, registry)
    assert blockers == []
    candidate = resolutions["thehub-pr"]["spatial_proximity"]["candidates"][0]
    assert candidate["scope"] == "SHARED_DERIVED_CANDIDATE"
    assert candidate["owner"] == "thehub-pr"


def test_shared_relationship_requires_federation_owner() -> None:
    registry = {"shared_relationships": [{"id": "located_in", "authority_owner": "ovnis-pr", "scope": "SHARED"}], "domain_registries": [], "hub_derived": {}}
    census = {"ovnis-pr": {"located_in": {"scripts/export.py"}}, "centinelas-pr": {"located_in": {"scripts/export.py"}}}
    blockers, _ = validate_relationship_census(census, registry)
    assert {"AB-004-RELATIONSHIP-OWNER-MISMATCH", "AB-004-CROSS-PRODUCER-COLLISION"}.issubset(_ids(blockers))


def test_shared_semantic_registration_does_not_prove_specific_identity() -> None:
    registry = {"shared_relationships": [
        {"id": "duplicate_of", "authority_owner": AUTHORITY, "scope": "SHARED", "identity_bearing": True},
        {"id": "located_in", "authority_owner": AUTHORITY, "scope": "SHARED", "identity_bearing": False},
        {"id": "reported_by", "authority_owner": AUTHORITY, "scope": "SHARED", "identity_bearing": False}], "domain_registries": [], "hub_derived": {}}
    census = {"aguayluz-pr": {"duplicate_of": {"scripts/export.py"}, "located_in": {"scripts/export.py"}}, "ovnis-pr": {"duplicate_of": {"scripts/export.py"}, "reported_by": {"scripts/export.py"}}}
    blockers, resolutions = validate_relationship_census(census, registry)
    assert blockers == []
    assert resolutions["aguayluz-pr"]["duplicate_of"]["candidates"][0]["owner"] == AUTHORITY


def test_consumer_projection_is_not_a_second_emitter() -> None:
    registry = {"shared_relationships": [], "domain_registries": [
        {"owner": "moneysweep-pr", "scope": "DOMAIN_ONLY", "types": ["parent_of"]}], "hub_derived": {}}
    census = {"moneysweep-pr": {"parent_of": {"src/export.py"}}, "thehub-pr": {"parent_of": {"data/aggregate/relationships.jsonl"}}}
    blockers, resolutions = validate_relationship_census(census, registry)
    assert blockers == []
    assert resolutions["thehub-pr"]["parent_of"]["evidence_class"] == "CONSUMER_PROJECTION_ONLY"

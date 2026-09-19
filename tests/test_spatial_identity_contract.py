from __future__ import annotations

import copy

import pytest

from hub.spatial_identity_contract import identity_decision_sha256, validate_identity_decision

PRODUCERS = [
    "moneysweep-pr",
    "spiderweb-pr",
    "aguayluz-pr",
    "skywatcher-pr",
    "ovnis-pr",
    "centinelas-pr",
]


def member(producer: str, record_id: str) -> dict[str, str]:
    return {"source_producer": producer, "local_record_id": record_id}


def evidence(evidence_class: str, ref: str, disposition: str = "SUPPORTS") -> dict[str, str]:
    return {
        "evidence_class": evidence_class,
        "evidence_ref": ref,
        "disposition": disposition,
    }


def decision(**overrides):
    row = {
        "schema_version": "1.1.0",
        "authority_plane": "prii-federation-spatial-identity",
        "decision_id": "fid-decision-1",
        "decision_type": "IDENTITY_EQUIVALENCE",
        "outcome": "MERGE",
        "resolution_state": "RESOLVED",
        "identity_cardinality": "1:1",
        "frozen_scope_id": "scope-2026-09-09",
        "candidate_set_complete": True,
        "top_evidence_tie_count": 1,
        "left_members": [member("moneysweep-pr", "entity raw A")],
        "right_members": [member("spiderweb-pr", "ENTITY_RAW_B")],
        "evidence": [evidence("STABLE_ID", "uei:EXAMPLE123")],
        "decision_basis": "authoritative stable identifier",
        "decided_by": "identity-reviewer",
        "created_at": "2026-09-09T12:00:00Z",
        "federation_entity_id": "FED-SPATIAL-PR-00000001",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("left", "right", "cardinality"),
    [
        ([member(PRODUCERS[0], "1")], [member(PRODUCERS[1], "1")], "1:1"),
        (
            [member(PRODUCERS[0], "1")],
            [member(PRODUCERS[1], "1"), member(PRODUCERS[2], "1")],
            "1:N",
        ),
        (
            [member(PRODUCERS[0], "1"), member(PRODUCERS[1], "1")],
            [member(PRODUCERS[2], "1")],
            "N:1",
        ),
        (
            [member(PRODUCERS[0], "1"), member(PRODUCERS[1], "1")],
            [member(PRODUCERS[2], "1"), member(PRODUCERS[3], "1")],
            "N:N",
        ),
    ],
)
def test_binding_identity_cardinality_shapes_are_computed(left, right, cardinality):
    assert validate_identity_decision(
        decision(left_members=left, right_members=right, identity_cardinality=cardinality)
    )["identity_cardinality"] == cardinality


def test_zero_to_one_is_non_identity_crosswalk_shape_not_identity_cardinality():
    row = decision(
        decision_type="CROSSWALK_ONLY",
        outcome="DEFER",
        resolution_state="NON_IDENTITY",
        left_members=[],
        right_members=[member("aguayluz-pr", "RSV_001")],
        crosswalk_cardinality="0:1",
        evidence=[evidence("SOURCE_ABSENCE", "snapshot:left", "NEUTRAL")],
    )
    row.pop("identity_cardinality")
    row.pop("federation_entity_id")
    assert validate_identity_decision(row)["crosswalk_cardinality"] == "0:1"

    identity_bearing = copy.deepcopy(row)
    identity_bearing["decision_type"] = "IDENTITY_EQUIVALENCE"
    with pytest.raises(ValueError, match="crosswalk_cardinality"):
        validate_identity_decision(identity_bearing)


def test_unresolved_is_state_not_identity_cardinality():
    row = decision(
        outcome="DEFER",
        resolution_state="UNRESOLVED",
        top_evidence_tie_count=2,
        evidence=[evidence("STABLE_ID", "stable:tie")],
    )
    row.pop("identity_cardinality")
    row.pop("federation_entity_id")
    assert validate_identity_decision(row)["resolution_state"] == "UNRESOLVED"

    bad = copy.deepcopy(row)
    bad["identity_cardinality"] = "UNRESOLVED"
    with pytest.raises(ValueError, match="UNRESOLVED identity decision cannot claim"):
        validate_identity_decision(bad)


@pytest.mark.parametrize(
    "evidence_class",
    [
        "NAME_ONLY",
        "NORMALIZED_NAME_ONLY",
        "COUNT_EQUALITY",
        "NEAREST_ONLY",
        "PROXIMITY_ONLY",
        "SAME_CATEGORY",
        "SOURCE_ABSENCE",
    ],
)
def test_discovery_only_signal_cannot_prove_merge(evidence_class):
    with pytest.raises(ValueError, match="binding SUPPORTS evidence"):
        validate_identity_decision(decision(evidence=[evidence(evidence_class, "weak:1")]))


def test_tied_top_evidence_forces_defer_and_unresolved_state():
    row = decision(
        outcome="DEFER",
        resolution_state="UNRESOLVED",
        top_evidence_tie_count=2,
        evidence=[evidence("STABLE_ID", "stable:tie")],
    )
    row.pop("identity_cardinality")
    row.pop("federation_entity_id")
    assert validate_identity_decision(row)["outcome"] == "DEFER"

    bad = copy.deepcopy(row)
    bad["outcome"] = "MERGE"
    bad["resolution_state"] = "RESOLVED"
    bad["identity_cardinality"] = "1:1"
    bad["federation_entity_id"] = "FED-SPATIAL-PR-00000002"
    with pytest.raises(ValueError, match="tied top evidence"):
        validate_identity_decision(bad)


def test_incomplete_candidate_set_forces_defer_and_unresolved_state():
    bad = decision(candidate_set_complete=False)
    with pytest.raises(ValueError, match="incomplete candidate set"):
        validate_identity_decision(bad)

    deferred = decision(
        candidate_set_complete=False,
        outcome="DEFER",
        resolution_state="UNRESOLVED",
    )
    deferred.pop("identity_cardinality")
    deferred.pop("federation_entity_id")
    assert validate_identity_decision(deferred)["resolution_state"] == "UNRESOLVED"


def test_declared_identity_cardinality_must_match_whole_member_sets():
    with pytest.raises(ValueError, match="does not match computed"):
        validate_identity_decision(decision(identity_cardinality="1:N"))


def test_duplicate_cross_side_and_unknown_producer_fail_closed():
    duplicate = decision(
        left_members=[member("moneysweep-pr", "1"), member("moneysweep-pr", "1")],
        right_members=[member("spiderweb-pr", "1")],
        identity_cardinality="N:1",
    )
    with pytest.raises(ValueError, match="duplicate identity member"):
        validate_identity_decision(duplicate)

    overlap = decision(
        left_members=[member("moneysweep-pr", "1")],
        right_members=[member("moneysweep-pr", "1")],
    )
    with pytest.raises(ValueError, match="both sides"):
        validate_identity_decision(overlap)

    unknown = decision(left_members=[member("unknown-repo", "1")])
    with pytest.raises(ValueError, match="canonical producer"):
        validate_identity_decision(unknown)


def test_wrong_authority_and_id_shortcuts_are_not_accepted():
    with pytest.raises(ValueError, match="authority_plane mismatch"):
        validate_identity_decision(decision(authority_plane="thehub-pr"))

    no_authority_id = decision()
    no_authority_id.pop("federation_entity_id")
    with pytest.raises(ValueError, match="authority-supplied federation_entity_id"):
        validate_identity_decision(no_authority_id)

    with pytest.raises(ValueError, match="invalid authority-supplied"):
        validate_identity_decision(decision(federation_entity_id="fed_" + "a" * 32))


def test_distinct_requires_binding_contradiction_not_name_difference():
    weak = decision(
        outcome="DISTINCT",
        evidence=[evidence("NAME_ONLY", "names:differ", "CONTRADICTS")],
    )
    weak.pop("federation_entity_id")
    with pytest.raises(ValueError, match="binding CONTRADICTS evidence"):
        validate_identity_decision(weak)

    strong = decision(
        outcome="DISTINCT",
        evidence=[evidence("AUTHORITATIVE_BINDING", "registry:distinct", "CONTRADICTS")],
    )
    strong.pop("federation_entity_id")
    assert validate_identity_decision(strong)["outcome"] == "DISTINCT"


def test_equal_or_stronger_opposing_hard_evidence_forces_defer():
    merge_conflict = decision(
        evidence=[
            evidence("AUTHORITATIVE_BINDING", "support:1", "SUPPORTS"),
            evidence("STABLE_ID", "contradict:1", "CONTRADICTS"),
        ]
    )
    with pytest.raises(ValueError, match="contradictory evidence requires DEFER"):
        validate_identity_decision(merge_conflict)

    distinct_conflict = decision(
        outcome="DISTINCT",
        evidence=[
            evidence("STABLE_ID", "support:1", "SUPPORTS"),
            evidence("AUTHORITATIVE_BINDING", "contradict:1", "CONTRADICTS"),
        ],
    )
    distinct_conflict.pop("federation_entity_id")
    with pytest.raises(ValueError, match="supporting evidence requires DEFER"):
        validate_identity_decision(distinct_conflict)


def test_weaker_heuristic_contradiction_cannot_override_hard_merge_evidence():
    row = decision(
        evidence=[
            evidence("STABLE_ID", "support:stable", "SUPPORTS"),
            evidence("PROXIMITY_ONLY", "contradict:proximity", "CONTRADICTS"),
        ]
    )
    assert validate_identity_decision(row)["outcome"] == "MERGE"


def test_canonical_hash_is_order_independent_but_raw_strings_are_preserved():
    row = decision(
        left_members=[
            member("spiderweb-pr", " raw ID  "),
            member("moneysweep-pr", "Áccent-ID"),
        ],
        right_members=[member("aguayluz-pr", "3")],
        identity_cardinality="N:1",
        evidence=[
            evidence("AUTHORITATIVE_BINDING", "ref:b"),
            evidence("STABLE_ID", "ref:a"),
        ],
    )
    permuted = copy.deepcopy(row)
    permuted["left_members"].reverse()
    permuted["evidence"].reverse()

    canonical = validate_identity_decision(row)
    assert {m["local_record_id"] for m in canonical["left_members"]} == {
        " raw ID  ",
        "Áccent-ID",
    }
    assert identity_decision_sha256(row) == identity_decision_sha256(permuted)


def test_deterministic_serialization_does_not_substitute_for_evidence():
    row = decision(evidence=[evidence("NORMALIZED_NAME_ONLY", "name:x")])
    for _ in range(2):
        with pytest.raises(ValueError, match="binding SUPPORTS evidence"):
            identity_decision_sha256(row)


def test_timestamp_and_evidence_disposition_are_strict():
    with pytest.raises(ValueError, match="RFC3339 UTC"):
        validate_identity_decision(decision(created_at="2026-09-09 12:00"))
    with pytest.raises(ValueError, match="evidence disposition"):
        validate_identity_decision(
            decision(evidence=[evidence("STABLE_ID", "x", "MAYBE")])
        )

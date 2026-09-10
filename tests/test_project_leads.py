import pytest

from hub.project_leads import adjudicate_project


def _lead():
    return {
        "lead_id": "prjlead_los_rosales_fixture",
        "source_title_raw": "RESIDENCIAL LOS ROSALES",
        "municipality_candidates": ["Yabucoa"],
        "identity_effect": "NONE",
    }


def _fiscal(evidence=None, contradictions=None, assertion_id="prjfis_fixture"):
    return {
        "assertion_id": assertion_id,
        "lead_id": _lead()["lead_id"],
        "producer": "moneysweep-pr",
        "candidates": [
            {
                "request_id_raw": "2025-000139",
                "fema_disaster_raw": "4339",
                "pw_raw": "9663",
                "amount_claim": 56432.84,
            }
        ],
        "independent_binding_evidence": evidence or [],
        "contradictions": contradictions or [],
    }


def _physical(evidence=None, contradictions=None, assertion_id="prjphy_fixture"):
    return {
        "assertion_id": assertion_id,
        "lead_id": _lead()["lead_id"],
        "producer": "spiderweb-pr",
        "candidates": [
            {
                "name_raw": "RESIDENCIAL LOS ROSALES",
                "municipality_raw": "Yabucoa",
                "spatial_state": "UNRESOLVED",
            }
        ],
        "independent_binding_evidence": evidence or [],
        "contradictions": contradictions or [],
    }


def _binding(value="AUTH-2025-139"):
    return {
        "evidence_type": "stable_project_id",
        "value": value,
        "authoritative": True,
        "identity_effect": "BINDING",
    }


def test_los_rosales_observations_do_not_prove_identity():
    result = adjudicate_project(_lead(), [_fiscal()], [_physical()])
    assert result["state"] == "CROSS_DOMAIN_CANDIDATE"
    assert result["banner"] is None
    assert result["identity_effect"] == "NONE"


def test_lead_id_name_municipality_and_proximity_cannot_bind():
    weak = [
        {"evidence_type": "name", "value": "RESIDENCIAL LOS ROSALES", "authoritative": True,
         "identity_effect": "BINDING"},
        {"evidence_type": "municipality", "value": "YABUCOA", "authoritative": True,
         "identity_effect": "BINDING"},
        {"evidence_type": "proximity", "value": "12m", "authoritative": True,
         "identity_effect": "BINDING"},
    ]
    result = adjudicate_project(_lead(), [_fiscal(weak)], [_physical(weak)])
    assert result["state"] == "CROSS_DOMAIN_CANDIDATE"
    assert result["banner"] is None


def test_one_shared_authoritative_binding_is_banner_eligible():
    result = adjudicate_project(_lead(), [_fiscal([_binding()])], [_physical([_binding()])])
    assert result["state"] == "BANNER_ELIGIBLE"
    assert result["identity_effect"] == "BINDING"
    assert result["banner"]["schema"] == "project_banner/v1"
    assert result["banner"]["binding"]["value"] == "AUTH-2025-139"


def test_tied_top_bindings_force_review():
    evidence = [_binding("AUTH-A"), _binding("AUTH-B")]
    result = adjudicate_project(_lead(), [_fiscal(evidence)], [_physical(evidence)])
    assert result["state"] == "REVIEW"
    assert result["banner"] is None


def test_conflicting_authoritative_bindings_force_review():
    result = adjudicate_project(
        _lead(), [_fiscal([_binding("AUTH-A")])], [_physical([_binding("AUTH-B")])]
    )
    assert result["state"] == "REVIEW"
    assert result["banner"] is None
    assert result["contradictions"]


def test_partial_states_are_explicit():
    assert adjudicate_project(_lead(), [], [])["state"] == "LEAD_ONLY"
    assert adjudicate_project(_lead(), [_fiscal()], [])["state"] == "FISCAL_ONLY"
    assert adjudicate_project(_lead(), [], [_physical()])["state"] == "PHYSICAL_ONLY"


def test_join_cardinality_and_full_candidate_pairs_are_preserved():
    physicals = [
        _physical([_binding()], assertion_id="prjphy_a"),
        _physical([_binding()], assertion_id="prjphy_b"),
    ]
    result = adjudicate_project(_lead(), [_fiscal([_binding()])], physicals)
    assert result["join_cardinality"] == "1:N"
    assert result["state"] == "BANNER_ELIGIBLE"
    assert len(result["binding_candidates"]) == 2


def test_duplicate_or_missing_assertion_ids_fail_closed():
    duplicate = [_fiscal(assertion_id="dup"), _fiscal(assertion_id="dup")]
    with pytest.raises(ValueError, match="duplicate fiscal assertion_id"):
        adjudicate_project(_lead(), duplicate, [_physical()])

    with pytest.raises(ValueError, match="fiscal assertion_id required"):
        adjudicate_project(_lead(), [_fiscal(assertion_id="")], [_physical()])


def test_whitespace_only_lead_id_fails_closed():
    with pytest.raises(ValueError, match="lead_id required"):
        adjudicate_project(None, [], [], lead_id="   ")


def test_n_to_n_contradictions_are_preserved_once_per_assertion():
    fiscal_contradiction = {"type": "COUNT", "detail": "fiscal mismatch"}
    physical_contradiction = {"type": "NAME", "detail": "physical mismatch"}
    fiscals = [
        _fiscal(contradictions=[fiscal_contradiction], assertion_id="fiscal-a"),
        _fiscal(assertion_id="fiscal-b"),
    ]
    physicals = [
        _physical(contradictions=[physical_contradiction], assertion_id="physical-a"),
        _physical(assertion_id="physical-b"),
    ]

    result = adjudicate_project(_lead(), fiscals, physicals)

    assert result["join_cardinality"] == "N:N"
    assert result["contradictions"].count(fiscal_contradiction) == 1
    assert result["contradictions"].count(physical_contradiction) == 1

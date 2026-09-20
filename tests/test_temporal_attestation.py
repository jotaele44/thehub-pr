from src.hub.temporal_attestation import (
    TemporalAttestationError, coexist_without_contradiction, may_inherit_pass,
    validate_temporal_attestation,
)

BASE = {
    "manifestation_id": "ci-run-a",
    "source_sha": "a" * 40,
    "environment": "CI",
    "valid_at": "2026-09-06T00:00:00Z",
    "certification_scope": "exact-sha-ci",
    "execution_state": "EXECUTED",
    "test_state": "PASS",
}

def test_later_same_sha_nonexecuted_does_not_erase_historical_pass():
    later = {**BASE, "manifestation_id": "ci-run-b", "valid_at": "2026-09-08T00:00:00Z",
             "execution_state": "NONEXECUTED", "test_state": "NOT_RUN"}
    validate_temporal_attestation(later)
    assert BASE["test_state"] == "PASS"
    assert not may_inherit_pass(later, BASE)

def test_old_sha_pass_cannot_certify_new_head():
    current = {**BASE, "manifestation_id": "new-head", "source_sha": "b" * 40,
               "execution_state": "UNKNOWN", "test_state": "UNKNOWN"}
    assert not may_inherit_pass(BASE, current)

def test_development_blocked_and_production_open_are_not_contradiction():
    dev = {**BASE, "manifestation_id": "dev", "environment": "DEVELOPMENT"}
    prod = {**BASE, "manifestation_id": "prod", "environment": "PRODUCTION"}
    assert coexist_without_contradiction(dev, prod)

def test_nonexecuted_cannot_claim_test_failure():
    bad = {**BASE, "execution_state": "NONEXECUTED", "test_state": "FAIL"}
    try:
        validate_temporal_attestation(bad)
    except TemporalAttestationError:
        pass
    else:
        raise AssertionError("NONEXECUTED+FAIL must fail closed")

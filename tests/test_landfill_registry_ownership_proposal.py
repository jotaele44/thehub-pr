"""Fail-closed checks for a non-binding cross-repo landfill ownership proposal."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/governance/landfill_registry_ownership_proposal.v1.json"
if not PROPOSAL.exists():
    PROPOSAL = ROOT / "docs/landfill_registry_ownership_proposal.v1.json"


def validate(candidate):
    expected = {
        "schema": "thehub-landfill-ownership-decision-proposal/1",
        "status": "PROPOSED",
        "accepted": False,
        "policy_authority": "jotaele44/thehub-pr",
        "candidate_registry_producer": "jotaele44/aguayluz-pr",
        "certification": "WITHHELD",
    }
    for key, value in expected.items():
        if type(candidate.get(key)) is not type(value) or candidate[key] != value:
            raise ValueError("unapproved or contradictory proposal: " + key)
    if candidate["proposal_reference"] != {
        "repository": "jotaele44/aguayluz-pr",
        "pull_request": 403,
        "head_sha": "93725524a4f48a884eef1c34bc78b5e09d218263",
    }:
        raise ValueError("source proposal identity mismatch")
    downstream = candidate["downstream_integration"]
    if downstream.get("pull_request") != 404 or downstream.get("status") != "DEPENDENCY_BLOCKED":
        raise ValueError("unapproved downstream promotion")
    dependencies = candidate["authority_dependencies"]
    if dependencies != {
        "thehub_identity_adr_0009": "PROPOSED",
        "thehub_imagery_adr_0006": "ACCEPTED_SCOPED_THEHUB_SKYWATCHER",
        "spiderweb_imagery_boundary": "PROVISIONAL_UNADJUDICATED",
        "solid_waste_denominator": "REGISTERED_NOT_EXHAUSTED",
    }:
        raise ValueError("authority or coverage contradiction")
    if set(candidate["candidate_responsibilities"]) != {
        "landfill_site_registry", "geospatial_discovery", "contracts_and_funding",
        "cross_producer_coordination",
    }:
        raise ValueError("duplicate or missing authority domain")
    actions = candidate["authorization"]
    if set(actions) != {"canonical_promotion", "cross_producer_identity_merge", "merge", "deploy", "release", "source_ownership_transfer"}:
        raise ValueError("unknown protected authorization")
    if any(value is not False for value in actions.values()):
        raise ValueError("protected operation authorized")
    if set(candidate["required_gates"]) != {
        "HUB_ARCHITECTURE_DISPOSITION", "AUTHORITATIVE_SOURCE_AND_IDENTITY_PROVENANCE",
        "CRS_TEMPORAL_BYTE_RECEIPTS", "REPOSITORY_SPECIFIC_REVIEWS",
        "EXACT_HEAD_CI_SECURITY_GUI", "QUALIFIED_MERGED_HEAD_REPLAY",
        "SIX_CONSUMER_PIN_RECONCILIATION", "THEHUB_LOCKSTEP",
    }:
        raise ValueError("mandatory gate missing")
    return True


class OwnershipProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = json.loads(PROPOSAL.read_text(encoding="utf-8"))

    def test_valid_proposal(self):
        self.assertTrue(validate(self.valid))

    def check_rejection(self, path, value):
        test = json.loads(json.dumps(self.valid))
        obj = test
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = value
        with self.assertRaises(ValueError):
            validate(test)

    def test_cannot_accept_without_governance(self):
        self.check_rejection(["accepted"], True)

    def test_cannot_change_certification(self):
        self.check_rejection(["certification"], "PASS")

    def test_cannot_promote_canonical_registry(self):
        self.check_rejection(["authorization", "canonical_promotion"], True)

    def test_cannot_merge_cross_producer_identity(self):
        self.check_rejection(["authorization", "cross_producer_identity_merge"], True)

    def test_cannot_merge_pull_request(self):
        self.check_rejection(["authorization", "merge"], True)

    def test_cannot_deploy(self):
        self.check_rejection(["authorization", "deploy"], True)

    def test_cannot_release(self):
        self.check_rejection(["authorization", "release"], True)

    def test_cannot_transfer_ownership(self):
        self.check_rejection(["authorization", "source_ownership_transfer"], True)

    def test_cannot_fake_hub_identity_ratification(self):
        self.check_rejection(["authority_dependencies", "thehub_identity_adr_0009"], "ACCEPTED")

    def test_cannot_generalize_imagery_adr(self):
        self.check_rejection(["authority_dependencies", "thehub_imagery_adr_0006"], "ACCEPTED_ALL_REPOS")

    def test_cannot_claim_exhausted_sources(self):
        self.check_rejection(["authority_dependencies", "solid_waste_denominator"], "COMPLETE")

    def test_cannot_promote_downstream_404(self):
        self.check_rejection(["downstream_integration", "status"], "READY")

    def test_cannot_remove_required_gate(self):
        self.check_rejection(["required_gates"], ["HUB_ARCHITECTURE_DISPOSITION"])

    def test_cannot_substitute_proposal_sha(self):
        self.check_rejection(["proposal_reference", "head_sha"], "a" * 40)


if __name__ == "__main__":
    unittest.main()

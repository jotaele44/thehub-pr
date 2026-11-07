"""Adversarial contract tests and a separately computed milestone oracle."""

import copy
import hashlib
import importlib.util
import itertools
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ecpaf_v21", ROOT / "scripts/ecpaf_v21.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


class EcpafV21Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = json.loads((ROOT / "governance/ecpaf/v2.1/policy.json").read_text())
        self.contract = {
            "schema_version": "ecpaf-checkpoints/2.1", "policy_sha256": engine.canonical_sha(self.policy),
            "authorities": {name: "a" * 40 for name in engine.CORE | engine.ADJACENT},
            "declared_requirement_ids": ["build", "integration", "operational"],
            "requirements": [self.leaf(name, name) for name in engine.PHASES],
        }
        (self.root / "proof.txt").write_bytes(b"observed proof fixture\n")
        self.observations = {"schema_version": "ecpaf-observations/2.1", "checkpoints": [
            {"id": name, "state": "PASS", "evidence": self.proof()} for name in engine.PHASES
        ]}
        self.bind()

    def leaf(self, name, phase, mandatory=True, weight=1):
        return {"id": name, "phase": phase, "mandatory": mandatory, "weight": weight,
                "domain": "engineering", "execution_class": "AI_AUTO", "depends_on": []}

    def proof(self):
        return {"path": "proof.txt", "sha256": hashlib.sha256(b"observed proof fixture\n").hexdigest(),
                "policy_sha256": engine.canonical_sha(self.policy), "authorities": self.contract["authorities"].copy(),
                "verifier": "unittest-fixture", "method": "byte comparison fixture; not real repository proof"}

    def bind(self):
        self.contract["policy_sha256"] = engine.canonical_sha(self.policy)
        self.observations["contract_sha256"] = engine.canonical_sha(self.contract)
        self.expected_contract_sha256 = engine.canonical_sha(self.contract)

    def run_eval(self):
        return engine.evaluate(self.policy, self.contract, self.observations, self.root,
                               self.expected_contract_sha256)

    def rejects(self):
        with self.assertRaises((engine.ContractError, OSError)):
            self.run_eval()

    def test_all_pass_never_authorizes_or_certifies(self):
        result = self.run_eval()
        self.assertTrue(all(s["structurally_eligible"] for s in result["milestones"].values()))
        self.assertFalse(result["release_authorized"])
        self.assertEqual(result["protected_operations_authorized"], [])
        self.assertEqual(result["certification"], "WITHHELD")
        self.assertEqual(result["independent_review"], "OPEN")

    def test_optional_residue_can_meet_95_without_certification(self):
        self.contract["requirements"][0]["weight"] = 18
        self.contract["requirements"][2]["mandatory"] = False
        self.observations["checkpoints"][2] = {"id": "operational", "state": "OPEN"}
        self.bind()
        stage = self.run_eval()["milestones"]["operational"]
        self.assertEqual(stage["percent"], 95)
        self.assertTrue(stage["structurally_eligible"])

    def test_95_does_not_waive_mandatory(self):
        self.contract["requirements"][0]["weight"] = 18
        self.observations["checkpoints"][2] = {"id": "operational", "state": "BLOCKED"}
        self.bind()
        stage = self.run_eval()["milestones"]["operational"]
        self.assertTrue(stage["threshold_met"])
        self.assertFalse(stage["structurally_eligible"])
        self.assertEqual(stage["mandatory_not_pass"], ["operational"])

    def test_exact_thresholds_against_independent_fraction_oracle(self):
        # Exhaustively compute numerator/denominator and mandatory predicate here;
        # do not call any production scoring helpers to produce expected values.
        for weights in itertools.product((1, 4, 19), repeat=3):
            for passed in itertools.product((False, True), repeat=3):
                for i, leaf in enumerate(self.contract["requirements"]):
                    leaf["weight"] = weights[i]
                    self.observations["checkpoints"][i]["state"] = "PASS" if passed[i] else "OPEN"
                self.bind()
                result = self.run_eval()
                for i, phase in enumerate(("build", "integration", "operational")):
                    num = sum(w for w, ok in zip(weights[:i + 1], passed[:i + 1]) if ok)
                    den = sum(weights[:i + 1])
                    stage = result["milestones"][phase]
                    expected = num * 100 >= (80, 90, 95)[i] * den
                    self.assertEqual(stage["threshold_met"], expected)
                    self.assertEqual(stage["structurally_eligible"], expected and all(passed[:i + 1]))
                    self.assertEqual(stage["passed_weight"], num)
                    self.assertEqual(stage["total_weight"], den)

    def test_missing_checkpoint(self):
        self.observations["checkpoints"].pop()
        self.rejects()

    def test_extra_checkpoint(self):
        self.observations["checkpoints"].append({"id": "invented", "state": "PASS"})
        self.rejects()

    def test_duplicate_checkpoint(self):
        self.observations["checkpoints"].append(copy.deepcopy(self.observations["checkpoints"][0]))
        self.rejects()

    def test_duplicate_requirement(self):
        self.contract["requirements"].append(copy.deepcopy(self.contract["requirements"][0]))
        self.bind()
        self.rejects()

    def test_silent_denominator_reduction(self):
        self.contract["requirements"].pop()
        self.bind()
        self.rejects()

    def test_coordinated_denominator_reduction_against_frozen_contract(self):
        self.contract["requirements"].pop()
        self.contract["declared_requirement_ids"].pop()
        self.observations["checkpoints"].pop()
        self.observations["contract_sha256"] = engine.canonical_sha(self.contract)
        self.rejects()

    def test_missing_external_contract_digest(self):
        self.expected_contract_sha256 = None
        self.rejects()

    def test_contract_hash_change(self):
        self.contract["requirements"][0]["weight"] = 2
        self.rejects()

    def test_wrong_policy_hash(self):
        self.contract["policy_sha256"] = "0" * 64
        self.rejects()

    def test_stale_authority(self):
        self.contract["authorities"]["jotaele44/thehub-pr"] = "b" * 40
        self.bind()
        self.rejects()

    def test_core_membership_not_silently_eight(self):
        self.policy["core_repositories"].append("jotaele44/mucaro-ai")
        self.bind()
        self.rejects()

    def test_missing_authority(self):
        self.contract["authorities"].pop("jotaele44/mucaro-ai")
        self.bind()
        self.rejects()

    def test_branch_name_not_commit(self):
        self.contract["authorities"]["jotaele44/thehub-pr"] = "main"
        self.bind()
        self.rejects()

    def test_critical_optional_rejected(self):
        self.contract["requirements"][0].update(domain="security", mandatory=False)
        self.bind()
        self.rejects()

    def test_missing_classification(self):
        del self.contract["requirements"][0]["execution_class"]
        self.bind()
        self.rejects()

    def test_unknown_state(self):
        for state in ("PROVISIONAL", "NOT_APPLICABLE", "SUPERSEDED", "success", None):
            self.observations["checkpoints"][0]["state"] = state
            self.rejects()

    def test_missing_evidence(self):
        del self.observations["checkpoints"][0]["evidence"]
        self.rejects()

    def test_changed_evidence_bytes(self):
        (self.root / "proof.txt").write_bytes(b"tampered")
        self.rejects()

    def test_path_escape(self):
        self.observations["checkpoints"][0]["evidence"]["path"] = "../proof.txt"
        self.rejects()

    def test_absolute_evidence_path(self):
        self.observations["checkpoints"][0]["evidence"]["path"] = str(self.root / "proof.txt")
        self.rejects()

    def test_symlink_evidence(self):
        (self.root / "link").symlink_to(self.root / "proof.txt")
        self.observations["checkpoints"][0]["evidence"]["path"] = "link"
        self.rejects()

    def test_parent_symlink_evidence(self):
        (self.root / "real").mkdir()
        (self.root / "real/proof.txt").write_bytes(b"observed proof fixture\n")
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        self.observations["checkpoints"][0]["evidence"]["path"] = "alias/proof.txt"
        self.rejects()

    def test_missing_evidence_file(self):
        (self.root / "proof.txt").unlink()
        self.rejects()

    def test_cyclic_dependencies(self):
        for leaf in self.contract["requirements"]:
            leaf["phase"] = "build"
        self.contract["requirements"][0]["depends_on"] = ["integration"]
        self.contract["requirements"][1]["depends_on"] = ["build"]
        self.bind()
        self.rejects()

    def test_unknown_dependency(self):
        self.contract["requirements"][0]["depends_on"] = ["absent"]
        self.bind()
        self.rejects()

    def test_unsatisfied_dependency(self):
        self.contract["requirements"][1]["depends_on"] = ["build"]
        self.observations["checkpoints"][0]["state"] = "OPEN"
        self.bind()
        self.rejects()

    def test_dependency_phase_reversal(self):
        self.contract["requirements"][0]["depends_on"] = ["operational"]
        self.bind()
        self.rejects()

    def test_budget_cannot_be_unbounded(self):
        for value in (0, -1, 999, True, None):
            self.policy["limits"]["max_epochs"] = value
            self.bind()
            self.rejects()

    def test_duplicate_json_keys(self):
        path = self.root / "bad.json"
        path.write_text('{"id":1,"id":2}')
        with self.assertRaises(engine.ContractError):
            engine.load_json(path)

    def test_nonfinite_json(self):
        path = self.root / "bad.json"
        for value in ("NaN", "Infinity", "-Infinity"):
            path.write_text('{"weight":' + value + '}')
            with self.assertRaises(engine.ContractError):
                engine.load_json(path)

    def test_security_semantics_cannot_be_flipped(self):
        for key in self.policy["semantics"]:
            policy = copy.deepcopy(self.policy)
            policy["semantics"][key] = True
            with self.assertRaises(engine.ContractError):
                engine.validate_policy(policy)

    def test_release_policy_cannot_change(self):
        for key, value in (("mode", "PRODUCTION"), ("certification", "CERTIFIED"),
                           ("protected_release_behavior", "BYPASS")):
            policy = copy.deepcopy(self.policy)
            policy[key] = value
            with self.assertRaises(engine.ContractError):
                engine.validate_policy(policy)

    def test_rounding_cannot_promote_threshold(self):
        self.contract["requirements"][0]["weight"] = 94
        self.contract["requirements"][1]["weight"] = 1
        self.contract["requirements"][2]["weight"] = 6
        self.observations["checkpoints"][2]["state"] = "OPEN"
        self.bind()
        self.assertFalse(self.run_eval()["milestones"]["operational"]["threshold_met"])


if __name__ == "__main__":
    unittest.main()

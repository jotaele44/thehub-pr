"""Mutation regressions for PR 239's frozen-receipt contract.

Only temporary copies are edited. These tests validate receipt enforcement, not
source authenticity, artifact payloads, or relationship resolution.
"""
from __future__ import annotations

import copy
import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_htr_v3_road_recurrence_receipt.py"
RECEIPT = ROOT / "data/htr/runs/2026-09-02_htr_v3_frozen_road_recurrence_receipt.json"


class TestHTRV3ReceiptContract(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.validator = runpy.run_path(str(SCRIPT))

    def invoke(self, doc):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            target.write_text(json.dumps(doc), encoding="utf-8")
            with patch.object(sys, "argv", [str(SCRIPT), str(target)]):
                with redirect_stdout(io.StringIO()):
                    return self.validator["main"]()

    def assert_mutation_fails(self, path, value, message):
        mutated = copy.deepcopy(self.receipt)
        parent = mutated
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        with self.assertRaisesRegex(self.validator["ContractError"], message):
            self.invoke(mutated)

    def test_frozen_receipt_passes_without_mutation(self):
        before = RECEIPT.read_bytes()
        self.assertEqual(self.invoke(self.receipt), 0)
        self.assertEqual(RECEIPT.read_bytes(), before)

    def test_json_object_order_is_not_an_identity_or_drift_signal(self):
        reordered = dict(reversed(list(self.receipt.items())))
        self.assertEqual(self.invoke(reordered), 0)

    def test_all_top_level_certification_states_are_pinned(self):
        for key, value in self.receipt["certification"].items():
            with self.subTest(field=key):
                replacement = "PASS" if value == "OPEN" else "OPEN"
                self.assert_mutation_fails(
                    ("certification", key), replacement, "top-level certification drift"
                )

    def test_execution_artifact_identifiers_are_pinned(self):
        cases = (
            ("bundle_sha256", "0" * 64, "execution bundle SHA256 drift"),
            ("bundle_size_bytes", 608772, "execution bundle size drift"),
            ("executor_sha256", "0" * 64, "executor SHA256 drift"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                self.assert_mutation_fails(("execution_artifact", field), value, message)

    def test_each_output_digest_is_pinned(self):
        for key in self.receipt["execution_artifact"]["output_hashes"]:
            with self.subTest(member=key):
                self.assert_mutation_fails(
                    ("execution_artifact", "output_hashes", key),
                    "0" * 64,
                    "output hash ledger drift",
                )

    def test_each_frozen_input_digest_is_pinned(self):
        for key in self.receipt["frozen_inputs"]:
            with self.subTest(source=key):
                self.assert_mutation_fails(
                    ("frozen_inputs", key), "0" * 64, "frozen input hash drift"
                )

    def test_redundant_matcher_denominators_are_cross_checked(self):
        cases = (
            ("unique_road_core_count", 24437, "matcher road-core denominator drift"),
            ("unique_hydro_core_count", 213, "matcher hydro-core denominator drift"),
            ("road_observation_count", 168907, "matcher road-observation denominator drift"),
            ("eligible_hydro_manifestation_count", 266, "matcher hydro-manifestation denominator drift"),
            ("full_core_pair_space", 5180433, "pair-space arithmetic failed"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                self.assert_mutation_fails(("matcher_equivalence", field), value, message)

    def test_matcher_set_difference_fields_cannot_drift(self):
        for key in ("a_only", "b_only", "symmetric_difference"):
            with self.subTest(field=key):
                self.assert_mutation_fails(
                    ("matcher_equivalence", key), 1, "matcher equivalence failed"
                )

    def test_discovery_cannot_claim_identity_connectivity_or_pair_binding(self):
        cases = (
            ("identity_promotions", "identity promotion detected"),
            ("connectivity_promotions", "connectivity promotion detected"),
            ("pair_binding_promotions", "pair-binding promotion detected"),
            ("transitive_context_inheritance", "transitive context detected"),
        )
        for field, message in cases:
            with self.subTest(field=field):
                self.assert_mutation_fails(("v3_incremental_recurrence", field), 1, message)

    def test_unsupported_contradiction_and_merge_semantics_stay_separate(self):
        cases = (
            (("state_semantics", "unsupported_is_false_or_rejected"), "UNSUPPORTED semantic drift"),
            (("state_semantics", "contradiction_is_disjoint_arithmetic_bucket"), "contradiction arithmetic semantic drift"),
            (("invariants", "green_code_equals_merge_authorized"), "merge-authorization semantic drift"),
            (("exact_heads", "merge_authorized"), "unauthorized merge state"),
        )
        for path, message in cases:
            with self.subTest(field=path):
                self.assert_mutation_fails(path, True, message)

    def test_targeted_search_cannot_be_promoted_to_binding_or_exhaustion(self):
        cases = (
            ("receipt_sha256", "0" * 64, "targeted-search receipt hash drift"),
            ("direct_pair_binding_found", 1, "targeted-search disposition drift"),
            ("universal_public_search_exhaustion_claimed", True, "unbounded targeted-search exhaustion claim"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                self.assert_mutation_fails(("targeted_public_pair_binding_search", field), value, message)

    def test_combined_v2_v3_counts_cannot_be_rewritten(self):
        cases = (
            ("candidate_rows", 9303, "combined candidate arithmetic failed"),
            ("unsupported_rows", 3856, "combined unsupported arithmetic failed"),
            ("candidate_not_identity_rows", 5448, "combined retained arithmetic failed"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                self.assert_mutation_fails(("combined_v2_plus_v3_recurrence", field), value, message)


if __name__ == "__main__":
    unittest.main()

"""Negative controls for the frozen receipt; no source I/O or optional packages."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("htr_receipt_guard", ROOT / "scripts/htr_v3_receipt_guard.py")
assert SPEC is not None and SPEC.loader is not None
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def leaves(doc, prefix=()):
    for key, value in doc.items():
        if isinstance(value, dict):
            yield from leaves(value, prefix + (key,))
        else:
            yield prefix + (key,), value


def parent(doc, path):
    for part in path[:-1]:
        doc = doc[part]
    return doc


class FrozenReceiptGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / GUARD.RECEIPT).read_bytes()
        cls.doc = GUARD.load_document(cls.raw)

    def test_frozen_receipt_passes(self):
        self.assertEqual(GUARD.validate_document(self.doc), GUARD.EXPECTED_LOGICAL_SHA256)

    def test_order_and_whitespace_do_not_change_logical_identity(self):
        reordered = dict(reversed(list(self.doc.items())))
        encoded = json.dumps(reordered, indent=7, ensure_ascii=True).encode()
        self.assertEqual(GUARD.validate_document(GUARD.load_document(encoded)), GUARD.EXPECTED_LOGICAL_SHA256)

    def test_every_scalar_mutation_fails(self):
        for path, value in leaves(self.doc):
            with self.subTest(path=".".join(path)):
                mutated = copy.deepcopy(self.doc)
                replacement = (not value) if type(value) is bool else value + 1 if type(value) is int else str(value) + "__DRIFT__"
                parent(mutated, path)[path[-1]] = replacement
                with self.assertRaises(GUARD.ReceiptGuardError):
                    GUARD.validate_document(mutated)

    def test_every_scalar_deletion_fails(self):
        for path, _ in leaves(self.doc):
            with self.subTest(path=".".join(path)):
                mutated = copy.deepcopy(self.doc)
                del parent(mutated, path)[path[-1]]
                with self.assertRaises(GUARD.ReceiptGuardError):
                    GUARD.validate_document(mutated)

    def test_numeric_type_substitution_fails(self):
        for path, value in leaves(self.doc):
            if type(value) is int:
                with self.subTest(path=".".join(path)):
                    mutated = copy.deepcopy(self.doc)
                    parent(mutated, path)[path[-1]] = float(value)
                    with self.assertRaises(GUARD.ReceiptGuardError):
                        GUARD.validate_document(mutated)

    def test_false_cannot_replace_zero(self):
        mutated = copy.deepcopy(self.doc)
        mutated["v2_pair_binding_continuation"]["pair_binding_promotions"] = False
        with self.assertRaises(GUARD.ReceiptGuardError):
            GUARD.validate_document(mutated)

    def test_balanced_context_redistribution_is_not_equivalent(self):
        mutated = copy.deepcopy(self.doc)
        block = mutated["v2_pair_binding_continuation"]
        block["groups_with_independent_v3_hydro_manifestation_context"] += 1
        block["groups_without_new_v3_lexical_hydro_context"] -= 1
        with self.assertRaises(GUARD.ReceiptGuardError):
            GUARD.validate_document(mutated)

    def test_unknown_field_requires_a_new_contract(self):
        mutated = copy.deepcopy(self.doc)
        mutated["identity_certified"] = True
        with self.assertRaises(GUARD.ReceiptGuardError):
            GUARD.validate_document(mutated)

    def test_duplicate_keys_rejected_at_any_depth(self):
        for raw in (b'{"a":1,"a":1}', b'{"nested":{"a":1,"a":2}}'):
            with self.subTest(raw=raw), self.assertRaises(GUARD.ReceiptGuardError):
                GUARD.load_document(raw)

    def test_invalid_json_utf8_and_nonfinite_values_fail(self):
        for raw in (b'{', b'[]', b'null', b'\xff', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(GUARD.ReceiptGuardError):
                GUARD.load_document(raw)
        with self.assertRaises(GUARD.ReceiptGuardError):
            GUARD.validate_document({"x": float("inf")})

    def test_truncated_bundle_fails_before_zip_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.zip"
            path.write_bytes(b"PK")
            with self.assertRaises(GUARD.ReceiptGuardError):
                GUARD.verify_bundle(path, self.doc)

    def test_same_size_wrong_bytes_fail_before_zip_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.zip"
            path.write_bytes(b"X" * self.doc["execution_artifact"]["bundle_size_bytes"])
            with self.assertRaises(GUARD.ReceiptGuardError):
                GUARD.verify_bundle(path, self.doc)


if __name__ == "__main__":
    unittest.main()

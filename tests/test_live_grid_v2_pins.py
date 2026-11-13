import base64
import json
import unittest
from scripts.check_live_grid_v2_pins import Observation, RetrievalError, evaluate, read_live_pin

A = "0" * 40
B = "1" * 40
H = "a" * 64

class LivePinTests(unittest.TestCase):
    def ref(self):
        return Observation("thehub-pr", "LOCAL", A, H, "2.0.0-rc1", "REFERENCE")

    def row(self, authority=A, digest=H):
        return Observation("aguayluz-pr", B, authority, digest, "2.0.0-rc1", "OBSERVED")

    def test_match(self):
        self.assertEqual(evaluate(self.ref(), [self.row()])[0], 0)

    def test_authority_drift(self):
        self.assertEqual(evaluate(self.ref(), [self.row(authority=B)])[0], 1)

    def test_hash_drift(self):
        self.assertEqual(evaluate(self.ref(), [self.row(digest="b" * 64)])[0], 1)

    def test_live_sha_pinned_retrieval(self):
        visited = []
        pin = {"consumer": "aguayluz-pr", "authority_commit": A, "grid_manifest_sha256": H, "grid_version": "2.0.0-rc1"}
        def fake(url):
            visited.append(url)
            if url.endswith("/branches/main"):
                return {"commit": {"sha": B}}
            return {"encoding": "base64", "content": base64.b64encode(json.dumps(pin).encode()).decode()}
        self.assertEqual(read_live_pin("aguayluz-pr", fake).commit, B)
        self.assertTrue(visited[-1].endswith("?ref=" + B))

    def test_missing_pin_fails_closed(self):
        def fake(url):
            return {"commit": {"sha": B}} if url.endswith("/branches/main") else {"encoding": "none"}
        with self.assertRaises(RetrievalError):
            read_live_pin("aguayluz-pr", fake)

    def test_consumer_identity_mismatch(self):
        pin = {"consumer": "skywatcher-pr", "authority_commit": A, "grid_manifest_sha256": H, "grid_version": "2.0.0-rc1"}
        def fake(url):
            return {"commit": {"sha": B}} if url.endswith("/branches/main") else {"encoding": "base64", "content": base64.b64encode(json.dumps(pin).encode()).decode()}
        with self.assertRaises(RetrievalError):
            read_live_pin("aguayluz-pr", fake)

if __name__ == "__main__":
    unittest.main()

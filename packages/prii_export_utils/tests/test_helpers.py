import hashlib

from prii_export_utils import fid, norm, sha256


def test_fid_is_deterministic():
    assert fid("src", "a", "b") == fid("src", "a", "b")


def test_fid_matches_reference_algorithm():
    digest = hashlib.sha256("|".join(["a", "b", "c"]).encode()).hexdigest()[:32]
    assert fid("src", "a", "b", "c") == f"src_{digest}"


def test_fid_distinguishes_prefix_and_parts():
    assert fid("src", "a") != fid("ent", "a")
    assert fid("src", "a") != fid("src", "b")


def test_norm_collapses_whitespace_and_uppercases():
    assert norm("  Rio  Piedras  ") == "RIO PIEDRAS"


def test_norm_is_idempotent():
    assert norm(norm("San Juan")) == norm("San Juan")


def test_sha256_matches_reference_algorithm(tmp_path):
    p = tmp_path / "sample.jsonl"
    p.write_bytes(b'{"a": 1}\n')
    assert sha256(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_sha256_changes_with_content(tmp_path):
    p1 = tmp_path / "one.jsonl"
    p2 = tmp_path / "two.jsonl"
    p1.write_bytes(b"one")
    p2.write_bytes(b"two")
    assert sha256(p1) != sha256(p2)

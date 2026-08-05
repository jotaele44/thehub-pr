"""Tests for the bounded-fixture sampler.

`scripts/build_hub_fixture.py` had no coverage, and the two bugs these tests pin
were both invisible without it — the fixture looked healthy (18 collections, real
records) while two collections were silently empty.

Both failures are about *shape*, not size. Raising the cap masks the first and
does not fix the second at any practical value, so the tests assert on which
records survive rather than how many.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loaded by path: scripts/ is not a package, so a plain import will not find it.
_spec = importlib.util.spec_from_file_location(
    "build_hub_fixture", REPO_ROOT / "scripts" / "build_hub_fixture.py"
)
bhf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bhf)


def _write(path: Path, records) -> Path:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
    return path


def _read(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ── Stratification ────────────────────────────────────────────────────────────

def test_rare_type_survives_a_dominant_producer(tmp_path):
    """The Contracts case: 3 records at the tail of one producer's export.

    Stratified by producer alone, moneysweep's slice is filled by whatever sorts
    first and the contracts never surface. Splitting on entity_type drains the
    three-row bucket long before the bulk ones.
    """
    records = (
        [{"entity_id": f"p{i}", "entity_type": "person", "_producers": ["money"]}
         for i in range(150)]
        + [{"entity_id": f"c{i}", "entity_type": "contract", "_producers": ["money"]}
           for i in range(3)]
    )
    path = _write(tmp_path / "entities.jsonl", records)

    kept, original = bhf.cap_stream(path, 40, "entities")

    assert original == 153
    assert kept == 40
    types = {r["entity_type"] for r in _read(path)}
    assert "contract" in types, "the rare type must survive the sample"


def test_producer_only_stratification_would_have_missed_it(tmp_path):
    """Pin the regression: the old bucket key drops the rare type at this cap."""
    records = (
        [{"entity_id": f"p{i}", "entity_type": "person", "_producers": ["money"]}
         for i in range(150)]
        + [{"entity_id": f"c{i}", "entity_type": "contract", "_producers": ["money"]}
           for i in range(3)]
    )
    path = _write(tmp_path / "entities.jsonl", records)

    # stream="" reproduces the producer-only key the sampler used before.
    bhf.cap_stream(path, 40, "")

    assert {r["entity_type"] for r in _read(path)} == {"person"}


def test_rare_relationship_type_survives(tmp_path):
    """The ContinuityRisks case: `energized_by` is appended behind bulk edges."""
    records = (
        [{"source_entity_id": f"a{i}", "target_entity_id": f"b{i}",
          "relationship_type": "located_in", "_producers": ["agua"]}
         for i in range(500)]
        + [{"source_entity_id": f"w{i}", "target_entity_id": f"p{i}",
            "relationship_type": "energized_by", "_producers": ["agua"]}
           for i in range(20)]
    )
    path = _write(tmp_path / "relationships.jsonl", records)

    bhf.cap_stream(path, 50, "relationships")

    assert "energized_by" in {r["relationship_type"] for r in _read(path)}


def test_every_producer_type_pair_is_represented(tmp_path):
    records = []
    for producer in ("a", "b"):
        for etype in ("x", "y", "z"):
            records += [{"entity_id": f"{producer}{etype}{i}", "entity_type": etype,
                         "_producers": [producer]} for i in range(30)]
    path = _write(tmp_path / "entities.jsonl", records)

    bhf.cap_stream(path, 30, "entities")

    pairs = {(r["_producers"][0], r["entity_type"]) for r in _read(path)}
    assert len(pairs) == 6


def test_stream_under_cap_is_untouched(tmp_path):
    records = [{"entity_id": "a", "entity_type": "t", "_producers": ["p"]}]
    path = _write(tmp_path / "entities.jsonl", records)

    assert bhf.cap_stream(path, 400, "entities") == (1, 1)
    assert _read(path) == records


def test_unparseable_lines_do_not_crash_the_sampler(tmp_path):
    path = tmp_path / "entities.jsonl"
    path.write_text('{"entity_id": "a", "entity_type": "t"}\nnot json\n')

    kept, original = bhf.cap_stream(path, 1, "entities")
    assert (kept, original) == (1, 2)


# ── Referential closure ───────────────────────────────────────────────────────

def test_closure_readmits_entities_a_relationship_needs(tmp_path):
    """Without this, `energized_by` survives but the projection still drops it.

    `project_continuity_risks` requires the water asset the edge names; each
    stream is capped independently, so the edge can outlive its endpoint.
    """
    entities = [
        {"entity_id": "water-1", "entity_type": "utility_asset", "_producers": ["agua"]},
        {"entity_id": "power-1", "entity_type": "utility_asset", "_producers": ["agua"]},
    ]
    full = _write(tmp_path / "entities.jsonl", entities)
    index = bhf._entity_lines(full)

    # The sample kept neither endpoint, but kept the edge between them.
    _write(tmp_path / "entities.jsonl", [
        {"entity_id": "other", "entity_type": "utility_asset", "_producers": ["agua"]},
    ])
    _write(tmp_path / "relationships.jsonl", [
        {"source_entity_id": "water-1", "target_entity_id": "power-1",
         "relationship_type": "energized_by", "_producers": ["agua"]},
    ])

    added = bhf.close_entity_references(tmp_path, index)

    assert added == 2
    assert {r["entity_id"] for r in _read(tmp_path / "entities.jsonl")} == {
        "other", "water-1", "power-1"
    }


def test_closure_readmits_entities_an_alert_anchors(tmp_path):
    entities = [{"entity_id": "asset-1", "entity_type": "utility_asset",
                 "_producers": ["agua"]}]
    full = _write(tmp_path / "entities.jsonl", entities)
    index = bhf._entity_lines(full)

    _write(tmp_path / "entities.jsonl", [])
    _write(tmp_path / "alerts.jsonl", [
        {"alert_id": "al-1", "module": "CONTAMINATION", "entity_id": "asset-1",
         "_producers": ["agua"]},
    ])

    assert bhf.close_entity_references(tmp_path, index) == 1


def test_closure_is_a_noop_when_references_already_resolve(tmp_path):
    entities = [
        {"entity_id": "a", "entity_type": "t", "_producers": ["p"]},
        {"entity_id": "b", "entity_type": "t", "_producers": ["p"]},
    ]
    full = _write(tmp_path / "entities.jsonl", entities)
    index = bhf._entity_lines(full)
    _write(tmp_path / "relationships.jsonl", [
        {"source_entity_id": "a", "target_entity_id": "b",
         "relationship_type": "r", "_producers": ["p"]},
    ])

    assert bhf.close_entity_references(tmp_path, index) == 0
    assert len(_read(tmp_path / "entities.jsonl")) == 2


def test_closure_ignores_references_with_no_known_entity(tmp_path):
    """A dangling id in the source corpus must not invent a record."""
    full = _write(tmp_path / "entities.jsonl", [
        {"entity_id": "a", "entity_type": "t", "_producers": ["p"]},
    ])
    index = bhf._entity_lines(full)
    _write(tmp_path / "entities.jsonl", [])
    _write(tmp_path / "relationships.jsonl", [
        {"source_entity_id": "ghost", "target_entity_id": "a",
         "relationship_type": "r", "_producers": ["p"]},
    ])

    assert bhf.close_entity_references(tmp_path, index) == 1
    assert {r["entity_id"] for r in _read(tmp_path / "entities.jsonl")} == {"a"}


def test_closure_without_an_entities_file_is_safe(tmp_path):
    assert bhf.close_entity_references(tmp_path, {}) == 0


# ── The committed fixture ─────────────────────────────────────────────────────

@pytest.mark.parametrize("collection", ["Contracts", "ContinuityRisks"])
def test_committed_fixture_carries_the_recovered_collections(collection):
    """Both were silently absent; the manifest is what makes that visible."""
    manifest = json.loads((REPO_ROOT / "data" / "fixture.json").read_text())
    assert manifest["collections"].get(collection, 0) > 0


def test_committed_fixture_records_its_closure_overage():
    """Closure exceeds the cap on purpose, so the manifest must say by how much."""
    manifest = json.loads((REPO_ROOT / "data" / "fixture.json").read_text())
    entities = manifest["streams"]["entities"]
    assert entities.get("closure_added", 0) > 0
    assert entities["sampled"] > manifest["cap_per_stream"]

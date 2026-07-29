"""Tests for the substantive-drift check behind the fixture-refresh PR.

The helper exists to answer one question: did producer *data* change, or did the
exporters just rewrite their timestamps again? Getting that wrong in either
direction is bad in a specific way — too loose and the workflow opens a
~2,000-line PR on every dispatch forever, too tight and a real data change never
reaches the fixture. Both directions are covered here.

The volatile field set is not a guess: exporting aguayluz twice with nothing
changed upstream showed `created_at` and `extracted_at` differing on 100% of
records across entities, relationships, sources and alerts, and nothing else
differing at all.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "fixture_drift", REPO_ROOT / "scripts" / "fixture_drift.py"
)
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


def _entity(entity_id: str, name: str, stamp: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "entity_type": "utility_asset",
        "confidence": 0.9,
        "created_at": stamp,
        "extracted_at": stamp,
        "lineage": {"producer_script": "x.py", "extracted_at": stamp},
    }


def _write(directory: Path, name: str, records) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    )


# ── The no-op case: only timestamps moved ─────────────────────────────────────

def test_timestamp_only_churn_is_not_drift(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _write(old, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    _write(new, "entities.jsonl", [_entity("a", "Pump", "2026-07-28T16:45:16Z")])

    assert (old / "entities.jsonl").read_bytes() != (new / "entities.jsonl").read_bytes()
    assert drift.compare(old, new)["entities.jsonl"] is False


def test_volatile_fields_are_stripped_from_nested_structures(tmp_path):
    """`lineage` carries its own extracted_at; a nested stamp is still churn."""
    record = _entity("a", "Pump", "2026-01-01T00:00:00Z")
    stripped = drift.strip_volatile(record)
    assert "created_at" not in stripped
    assert "extracted_at" not in stripped
    assert "extracted_at" not in stripped["lineage"]
    assert stripped["lineage"]["producer_script"] == "x.py"
    assert stripped["name"] == "Pump"


def test_record_order_is_not_drift(tmp_path):
    """The aggregate concatenates producers; a reshuffle loses nothing."""
    old, new = tmp_path / "old", tmp_path / "new"
    a = _entity("a", "Pump", "2026-01-01T00:00:00Z")
    b = _entity("b", "Tank", "2026-01-01T00:00:00Z")
    _write(old, "entities.jsonl", [a, b])
    _write(new, "entities.jsonl", [b, a])

    assert drift.compare(old, new)["entities.jsonl"] is False


# ── The change cases ──────────────────────────────────────────────────────────

def test_a_changed_field_is_drift(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _write(old, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    _write(new, "entities.jsonl", [_entity("a", "Pump Station 4", "2026-01-01T00:00:00Z")])

    assert drift.compare(old, new)["entities.jsonl"] is True


def test_an_added_record_is_drift(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    a = _entity("a", "Pump", "2026-01-01T00:00:00Z")
    _write(old, "entities.jsonl", [a])
    _write(new, "entities.jsonl", [a, _entity("b", "Tank", "2026-01-01T00:00:00Z")])

    assert drift.compare(old, new)["entities.jsonl"] is True


def test_a_removed_record_is_drift(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    a = _entity("a", "Pump", "2026-01-01T00:00:00Z")
    _write(old, "entities.jsonl", [a, _entity("b", "Tank", "2026-01-01T00:00:00Z")])
    _write(new, "entities.jsonl", [a])

    assert drift.compare(old, new)["entities.jsonl"] is True


def test_drift_is_reported_per_stream(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    for directory in (old, new):
        _write(directory, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    _write(old, "alerts.jsonl", [{"alert_id": "x", "severity": 1}])
    _write(new, "alerts.jsonl", [{"alert_id": "x", "severity": 3}])

    changed = drift.compare(old, new)
    assert changed["alerts.jsonl"] is True
    assert changed["entities.jsonl"] is False


def test_a_vanished_stream_is_drift(tmp_path):
    """An empty digest for a missing file must not read as 'unchanged'."""
    old, new = tmp_path / "old", tmp_path / "new"
    _write(old, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    new.mkdir(parents=True)

    assert drift.compare(old, new)["entities.jsonl"] is True


def test_corrupt_lines_count_as_drift_rather_than_being_skipped(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _write(old, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    new.mkdir(parents=True)
    (new / "entities.jsonl").write_text("{truncated\n")

    assert drift.compare(old, new)["entities.jsonl"] is True


def test_graph_summary_is_compared_as_json(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "graph_summary.json").write_text(json.dumps(
        {"entities": 34671, "created_at": "2026-01-01T00:00:00Z"}))
    (new / "graph_summary.json").write_text(json.dumps(
        {"entities": 34671, "created_at": "2026-07-28T16:45:16Z"}))
    assert drift.compare(old, new)["graph_summary.json"] is False

    (new / "graph_summary.json").write_text(json.dumps(
        {"entities": 35888, "created_at": "2026-07-28T16:45:16Z"}))
    assert drift.compare(old, new)["graph_summary.json"] is True


# ── CLI contract the workflow depends on ──────────────────────────────────────

@pytest.mark.parametrize("same,expected", [(True, "drift=false"), (False, "drift=true")])
def test_cli_prints_the_github_output_line(tmp_path, capsys, same, expected):
    old, new = tmp_path / "old", tmp_path / "new"
    _write(old, "entities.jsonl", [_entity("a", "Pump", "2026-01-01T00:00:00Z")])
    _write(new, "entities.jsonl",
           [_entity("a", "Pump" if same else "Renamed", "2026-07-28T16:45:16Z")])

    assert drift.main([str(old), str(new)]) == 0
    assert capsys.readouterr().out.strip() == expected


def test_cli_fails_loudly_when_the_candidate_is_missing(tmp_path, capsys):
    """A silent 'no drift' on a broken build would quietly stop all refreshes."""
    assert drift.main([str(tmp_path), str(tmp_path / "absent")]) == 2
    assert "drift=" not in capsys.readouterr().out

"""Tests for the `source_monitors` federation stream (ADR 0013).

Covers the frozen contract (schema + export-manifest enum), package validation
through the bridge's own manifest writer, and how ingest projects stream rows into
MonitoredSources, flagging any expected producer the stream has no rows from.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import hashlib

import jsonschema
import pytest

from hub._schemas import STREAM_ID_FIELD, STREAM_SCHEMA, load_schema
from hub.aggregate import aggregate
from hub.bridge import write_manifest
from hub.ingest import (
    MONITOR_COLLECTION,
    MONITOR_STREAM_GAP_ERROR,
    MONITOR_STREAM_PRODUCERS,
    MONITOR_SUMMARY_COLLECTION,
    STREAM_TO_COLLECTION,
    ingest_aggregate,
    project_source_monitors,
)
from hub.validate import validate_package

LINEAGE = {"producer_script": "scripts/federation_export.py", "producer_phase": "SOURCE_MONITOR",
           "source_inputs": ["config/hydromet_sources.v1.json"]}
TS = "2026-11-11T00:00:00Z"


def _stream_row(source_ref, *, basis="OUTPUT_DERIVED", at="2026-11-08T15:47:31Z", producer="aguayluz-pr"):
    # Same shape as prii_export_utils.source_monitor_row (whose own tests validate it
    # against this schema); built locally because the Hub test job does not install
    # that package. monitor_id follows fid("mon", producer, source_ref).
    digest = hashlib.sha256(f"{producer}|{source_ref}".encode()).hexdigest()[:32]
    return {
        "monitor_id": f"mon_{digest}", "source_ref": source_ref, "name": source_ref,
        "producer_family": "HYDROMETEOROLOGY", "evidence_tier": None, "declared_status": "unknown",
        "cadence": "realtime", "cadence_window_seconds": 7200, "last_success_basis": basis,
        "last_success_at": None if basis == "NOT_RECORDED" else at, "last_attempt_at": None,
        "last_attempt_status": None, "source_url": None, "registry_path": "config/hydromet_sources.v1.json",
        "lineage": LINEAGE, "synthetic": False, "created_at": TS, "extracted_at": TS,
    }


def _validator():
    return jsonschema.Draft7Validator(load_schema("federation_source_monitor.schema.json"),
                                      format_checker=jsonschema.FormatChecker())


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _rows(db, collection):
    conn = sqlite3.connect(db)
    try:
        return {r[0]: json.loads(r[1]) for r in conn.execute(
            "SELECT entity_id, data FROM entities WHERE entity_type=?", (collection,))}
    finally:
        conn.close()


# ── contract ──────────────────────────────────────────────────────────────────

def test_stream_is_registered_end_to_end():
    assert STREAM_SCHEMA["source_monitors"] == "federation_source_monitor.schema.json"
    assert STREAM_ID_FIELD["source_monitors"] == "monitor_id"
    assert STREAM_TO_COLLECTION["source_monitors"] == "SourceMonitors"
    manifest = load_schema("federation_export_manifest.schema.json")
    assert "source_monitors" in manifest["properties"]["files"]["items"]["properties"]["stream"]["enum"]


@pytest.mark.parametrize("basis", ["RUN_RECEIPT", "OUTPUT_DERIVED", "NOT_RECORDED"])
def test_rows_for_every_basis_validate(basis):
    errors = list(_validator().iter_errors(_stream_row("nwps_gauges", basis=basis)))
    assert errors == []


def test_schema_rejects_a_time_without_a_basis_and_a_basis_without_a_time():
    v = _validator()
    not_recorded_with_time = {**_stream_row("x", basis="NOT_RECORDED"), "last_success_at": "2026-11-08T00:00:00Z"}
    derived_without_time = {**_stream_row("x"), "last_success_at": None}
    derived_missing_time = {k: val for k, val in _stream_row("x").items() if k != "last_success_at"}
    for row in (not_recorded_with_time, derived_without_time, derived_missing_time):
        assert list(v.iter_errors(row)), row


def test_schema_rejects_bad_ids_and_vocabularies():
    v = _validator()
    for bad in ({"monitor_id": "src_" + "0" * 32}, {"declared_status": "healthy"},
                {"cadence": "fortnightly"}, {"last_success_basis": "GUESSED"}):
        assert list(v.iter_errors({**_stream_row("x"), **bad})), bad


# ── package validation ────────────────────────────────────────────────────────

def test_package_with_source_monitors_validates_and_bad_rows_fail(tmp_path):
    pkg = tmp_path / "pkg"
    _write_jsonl(pkg / "source_monitors.jsonl", [_stream_row("nwps_gauges"), _stream_row("x", basis="NOT_RECORDED")])
    manifest = write_manifest(pkg, "aguayluz-pr", created_at=TS)
    assert [f["stream"] for f in manifest["files"]] == ["source_monitors"]
    assert validate_package(pkg) == []

    bad = tmp_path / "bad"
    _write_jsonl(bad / "source_monitors.jsonl",
                 [{**_stream_row("x", basis="NOT_RECORDED"), "last_success_at": "2026-11-08T00:00:00Z"}])
    write_manifest(bad, "aguayluz-pr", created_at=TS)
    assert validate_package(bad)


# ── ingest projection ─────────────────────────────────────────────────────────

def _all_producers_stream(agg: Path, extra=()):
    # One stream row from every expected producer, plus any extra rows.
    rows = [{**_stream_row("seed", producer=pid), "_producers": [pid]} for pid in MONITOR_STREAM_PRODUCERS]
    _write_jsonl(agg / "source_monitors.jsonl", [*rows, *extra])


def test_expected_producers_match_the_registry():
    from hub.registry import load_registry

    reg = load_registry(str(Path(__file__).resolve().parents[1] / "registry" / "producers.yaml"))
    assert sorted(MONITOR_STREAM_PRODUCERS) == sorted(p.program_id for p in reg.producers)


def test_project_returns_none_without_inputs(tmp_path):
    assert project_source_monitors(tmp_path) is None


def test_stream_rows_project_into_monitored_sources(tmp_path):
    agg = tmp_path / "agg"
    _all_producers_stream(agg, [
        {**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]},
        {**_stream_row("stage_iv_pr", basis="NOT_RECORDED"), "_producers": ["aguayluz-pr"]},
    ])

    pairs, summary = project_source_monitors(agg, now=TS)
    rows = dict(pairs)
    assert "aguayluz-pr:nwps_gauges" in rows and "aguayluz-pr:stage_iv_pr" in rows
    assert "moneysweep-pr:seed" in rows and len(rows) == len(MONITOR_STREAM_PRODUCERS) + 2
    assert all(r["origin"] == "stream" for r in rows.values())
    nwps = rows["aguayluz-pr:nwps_gauges"]
    assert nwps["source_id"] == "nwps_gauges"
    assert nwps["stream_monitor_id"].startswith("mon_") and nwps["last_success_basis"] == "OUTPUT_DERIVED"
    assert nwps["lineage"]["registry_path"] == "config/hydromet_sources.v1.json"

    assert summary["stream_producers"] == sorted(MONITOR_STREAM_PRODUCERS)
    assert summary["producers"]["aguayluz-pr"]["origin"] == "stream"
    assert summary["producers"]["aguayluz-pr"]["count"] == 3
    assert summary["producers"]["moneysweep-pr"] == {
        "origin": "stream", "count": 1, "package_created_at": TS,
        "registries": ["config/hydromet_sources.v1.json"], "excluded": {}, "errors": [],
    }
    assert summary["error_count"] == 0 and summary["total"] == len(rows)
    assert "adapter" not in summary and "root" not in summary


def test_an_expected_producer_without_stream_rows_is_flagged_not_dropped(tmp_path):
    # Every producer reports through the stream; an aggregate without one
    # producer's rows must show the gap, not hide it.
    agg = tmp_path / "agg"
    _write_jsonl(agg / "source_monitors.jsonl", [
        {**_stream_row("seed", producer=pid), "_producers": [pid]}
        for pid in MONITOR_STREAM_PRODUCERS if pid != "moneysweep-pr"
    ])
    _, summary = project_source_monitors(agg, now=TS)
    gap = summary["producers"]["moneysweep-pr"]
    assert gap == {"origin": "stream", "count": 0, "package_created_at": None, "registries": [],
                   "excluded": {}, "errors": [MONITOR_STREAM_GAP_ERROR]}
    assert MONITOR_STREAM_GAP_ERROR == (
        "reports through the source_monitors stream, but this aggregate has no rows from it")
    assert summary["error_count"] == 1 and "moneysweep-pr" not in summary["stream_producers"]

    _all_producers_stream(agg)
    _, summary = project_source_monitors(agg, now=TS)
    assert summary["producers"]["moneysweep-pr"]["errors"] == [] and summary["error_count"] == 0
    assert "moneysweep-pr" in summary["stream_producers"]


def test_stream_only_aggregate_builds_its_own_summary(tmp_path):
    agg = tmp_path / "agg"
    _write_jsonl(agg / "source_monitors.jsonl", [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]}])
    pairs, summary = project_source_monitors(agg, now=TS)
    assert [k for k, _ in pairs] == ["aguayluz-pr:nwps_gauges"]
    assert summary["schema_version"] == "prii_source_monitor_v1"
    assert summary["generated_at"] == TS and summary["total"] == 1
    assert summary["producers"]["aguayluz-pr"]["package_created_at"] == TS
    # The other expected producers are reported as gaps.
    assert summary["error_count"] == len(MONITOR_STREAM_PRODUCERS) - 1


def test_aggregate_and_ingest_carry_the_stream_into_both_collections(tmp_path):
    pkg = tmp_path / "pkg"
    _write_jsonl(pkg / "source_monitors.jsonl", [_stream_row("nwps_gauges"), _stream_row("x", basis="NOT_RECORDED")])
    write_manifest(pkg, "aguayluz-pr", created_at=TS)
    agg = tmp_path / "agg"
    aggregate({"aguayluz-pr": pkg}, agg)
    db = tmp_path / "hub.db"

    summary = ingest_aggregate(agg, db)
    assert summary["collections"]["SourceMonitors"] == 2
    canonical = _rows(db, "SourceMonitors")
    assert all(k.startswith("mon_") for k in canonical)
    monitored = _rows(db, MONITOR_COLLECTION)
    assert set(monitored) == {"aguayluz-pr:nwps_gauges", "aguayluz-pr:x"}
    assert all(r["origin"] == "stream" for r in monitored.values())
    assert monitored["aguayluz-pr:x"]["last_success_basis"] == "NOT_RECORDED"
    stored_summary = _rows(db, MONITOR_SUMMARY_COLLECTION)["source_monitor_summary"]
    assert stored_summary["stream_producers"] == ["aguayluz-pr"]

    # The producer drops a source: the projected view loses it on the next ingest.
    _write_jsonl(agg / "source_monitors.jsonl",
                 [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]}])
    ingest_aggregate(agg, db)
    assert set(_rows(db, MONITOR_COLLECTION)) == {"aguayluz-pr:nwps_gauges"}

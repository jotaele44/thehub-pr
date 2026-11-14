"""Tests for the `source_monitors` federation stream (ADR 0013).

Covers the frozen contract (schema + export-manifest enum), package validation
through the bridge's own manifest writer, and how ingest merges stream rows with
the hub-side adapter's rows (ADR 0012) into MonitoredSources.
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


# ── ingest merge ──────────────────────────────────────────────────────────────

def _adapter_files(agg: Path):
    _write_jsonl(agg / "monitored_sources.jsonl", [
        {"monitor_id": "aguayluz-pr:nwps_gauges", "producer": "aguayluz-pr", "source_id": "nwps_gauges"},
        {"monitor_id": "ovnis-pr:SRC-0001", "producer": "ovnis-pr", "source_id": "SRC-0001"},
    ])
    (agg / "monitored_sources_summary.json").write_text(json.dumps({
        "schema_version": "prii_source_monitor_v1", "generated_at": TS, "total": 2, "error_count": 1,
        "producers": {
            "aguayluz-pr": {"count": 1, "errors": ["config/x.json: file not found"], "excluded": {}},
            "ovnis-pr": {"count": 1, "errors": [], "excluded": {}},
        },
    }))


def test_project_returns_none_without_inputs(tmp_path):
    assert project_source_monitors(tmp_path) is None


def test_stream_rows_replace_a_producers_adapter_rows(tmp_path):
    agg = tmp_path / "agg"
    _adapter_files(agg)
    stream = [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]},
              {**_stream_row("stage_iv_pr", basis="NOT_RECORDED"), "_producers": ["aguayluz-pr"]}]
    _write_jsonl(agg / "source_monitors.jsonl", stream)

    pairs, summary = project_source_monitors(agg, now=TS)
    rows = dict(pairs)
    assert sorted(rows) == ["aguayluz-pr:nwps_gauges", "aguayluz-pr:stage_iv_pr", "ovnis-pr:SRC-0001"]
    nwps = rows["aguayluz-pr:nwps_gauges"]
    assert nwps["origin"] == "stream" and nwps["source_id"] == "nwps_gauges"
    assert nwps["stream_monitor_id"].startswith("mon_") and nwps["last_success_basis"] == "OUTPUT_DERIVED"
    assert nwps["lineage"]["registry_path"] == "config/hydromet_sources.v1.json"
    assert rows["ovnis-pr:SRC-0001"]["origin"] == "hub_adapter"

    assert summary["stream_producers"] == ["aguayluz-pr"]
    assert summary["producers"]["aguayluz-pr"]["origin"] == "stream"
    assert summary["producers"]["aguayluz-pr"]["count"] == 2
    # The adapter's error for a producer now read from the stream no longer applies.
    assert summary["producers"]["aguayluz-pr"]["errors"] == [] and summary["error_count"] == 0
    assert summary["producers"]["ovnis-pr"]["origin"] == "hub_adapter"
    assert summary["total"] == 3


def test_a_stream_producer_without_stream_rows_is_flagged_not_dropped(tmp_path):
    # The registry reader marks producers it no longer reads (STREAM_PRODUCERS);
    # an aggregate without their stream rows must show the gap, not hide them.
    agg = tmp_path / "agg"
    _write_jsonl(agg / "monitored_sources.jsonl", [
        {"monitor_id": "ovnis-pr:SRC-0001", "producer": "ovnis-pr", "source_id": "SRC-0001"},
    ])
    (agg / "monitored_sources_summary.json").write_text(json.dumps({
        "schema_version": "prii_source_monitor_v1", "generated_at": TS, "total": 1, "error_count": 0,
        "producers": {
            "aguayluz-pr": {"count": 0, "errors": [], "excluded": {}, "reports_via_stream": True},
            "ovnis-pr": {"count": 1, "errors": [], "excluded": {}},
        },
    }))
    _, summary = project_source_monitors(agg, now=TS)
    gap = summary["producers"]["aguayluz-pr"]
    assert gap["origin"] == "stream" and gap["count"] == 0
    assert gap["errors"] == ["reports through the source_monitors stream, but this aggregate has no rows from it"]
    assert summary["error_count"] == 1 and summary["stream_producers"] == []

    _write_jsonl(agg / "source_monitors.jsonl", [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]}])
    _, summary = project_source_monitors(agg, now=TS)
    assert summary["producers"]["aguayluz-pr"]["errors"] == [] and summary["error_count"] == 0
    assert summary["stream_producers"] == ["aguayluz-pr"]


def test_stream_only_aggregate_builds_its_own_summary(tmp_path):
    agg = tmp_path / "agg"
    _write_jsonl(agg / "source_monitors.jsonl", [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]}])
    pairs, summary = project_source_monitors(agg, now=TS)
    assert [k for k, _ in pairs] == ["aguayluz-pr:nwps_gauges"]
    assert summary["generated_at"] == TS and summary["total"] == 1
    assert summary["producers"]["aguayluz-pr"]["package_created_at"] == TS


def test_aggregate_and_ingest_carry_the_stream_into_both_collections(tmp_path):
    pkg = tmp_path / "pkg"
    _write_jsonl(pkg / "source_monitors.jsonl", [_stream_row("nwps_gauges"), _stream_row("x", basis="NOT_RECORDED")])
    write_manifest(pkg, "aguayluz-pr", created_at=TS)
    agg = tmp_path / "agg"
    aggregate({"aguayluz-pr": pkg}, agg)
    _adapter_files(agg)
    db = tmp_path / "hub.db"

    summary = ingest_aggregate(agg, db)
    assert summary["collections"]["SourceMonitors"] == 2
    canonical = _rows(db, "SourceMonitors")
    assert all(k.startswith("mon_") for k in canonical)
    monitored = _rows(db, MONITOR_COLLECTION)
    assert set(monitored) == {"aguayluz-pr:nwps_gauges", "aguayluz-pr:x", "ovnis-pr:SRC-0001"}
    assert monitored["aguayluz-pr:x"]["last_success_basis"] == "NOT_RECORDED"
    stored_summary = _rows(db, MONITOR_SUMMARY_COLLECTION)["source_monitor_summary"]
    assert stored_summary["stream_producers"] == ["aguayluz-pr"]

    # The producer drops a source: the merged view loses it on the next ingest.
    _write_jsonl(agg / "source_monitors.jsonl",
                 [{**_stream_row("nwps_gauges"), "_producers": ["aguayluz-pr"]}])
    ingest_aggregate(agg, db)
    assert set(_rows(db, MONITOR_COLLECTION)) == {"aguayluz-pr:nwps_gauges", "ovnis-pr:SRC-0001"}

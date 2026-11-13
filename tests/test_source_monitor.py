"""Tests for the hub-side source monitor (hub.source_monitor, ADR 0012).

The fixture workspace reproduces each producer's registry with its real header
row / top-level shape as of 2026-11, so a producer reshaping its registry shows
up here as a failing adapter rather than as a silently empty dashboard.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hub.registry import Producer, Registry
from hub.source_monitor import (
    CADENCES,
    STATUSES,
    build_monitor,
    cadence_from_seconds,
    normalize_cadence,
    normalize_status,
    normalize_tier,
    write_monitor,
)

NOW = "2026-11-08T00:00:00Z"

_MONEYSWEEP_CSV = (
    "source_id,family,required,authentication,producer_script,expected_outputs,"
    "update_cadence,pipeline_status,blocker_notes\n"
    "usaspending_prime,federal,True,none,scripts/a.py,out.csv,weekly,partially_materialized,\"API, bulk\"\n"
    "usaspending_subawards,federal,True,none,scripts/b.py,out.csv,weekly,fully_materialized,\n"
    "pr_ocpr_contracts,commonwealth,False,none,scripts/c.py,out.csv,ad_hoc,not_materialized,manual export\n"
)
_CENTINELAS_CSV = (
    "source_id,name,language,source_family,reliability_default,scrape_method,active,notes\n"
    "CENT-SRC-RSS-SPACE-NEWS,SpaceNews,en,space_media,0.8,rss,active,\n"
    "CENT-SRC-MANUAL-GACETA,Gaceta Oficial,es,official_gazette,0.95,manual,manual,\n"
)
_OVNIS_CSV = (
    "source_id,name,language,source_family,reliability_default,scrape_method,active,"
    "retrieval_cadence,robots_policy,notes\n"
    "SRC-0000,Placeholder Source,unknown,placeholder,T4,manual,no,none,not_applicable,\n"
    "SRC-0001,AARO Case Archive,en,USAF,T1,html,yes,quarterly,allowed,\n"
)
_SPIDERWEB_CSV = (
    "source_id,authority,universe,endpoint,mutable,refresh_policy,evidence_tier,adapter,"
    "expected_content,notes\n"
    "TIGER_PR_BOUNDARY,U.S. Census Bureau,JURISDICTION_BOUNDARY,https://example.org/tiger.zip,"
    "False,PIN_BY_VINTAGE,T1,tiger,zip,\n"
)
_SPIDERWEB_MISSING_PERSONS = """\
version: missing_persons_sources_v1
sources:
  namus:
    operator: "NIJ"
    url: "https://namus.nij.ojp.gov"
    federation_eligible: aggregate_only
    refresh_cadence_days: 90
    stratum: A
    status: harvester_landed
  gwu_maria_mortality_study:
    operator: "GWU"
    federation_eligible: aggregate_only
    refresh_cadence_days: 0
    stratum: B
    status: harvester_planned
  tip_line:
    operator: "Tip stream"
    federation_eligible: false
    refresh_cadence_days: 1
    stratum: C
    status: manual_pull
"""
_SKYWATCHER_YAML = """\
airspace:
  - id: adsb_exchange
    tier: T1
    mode: delayed_or_rate_limited
    use: aircraft event ingestion
maritime:
  - id: public_port_authority_updates
    tier: T2
    mode: periodic_context
    use: port context enrichment
"""
_PRODUCERS = ["moneysweep-pr", "centinelas-pr", "ovnis-pr", "spiderweb-pr", "skywatcher-pr", "aguayluz-pr"]


def _registry() -> Registry:
    producers = [
        Producer(program_id=pid, repo=f"jotaele44/{pid}", role="test",
                 export_path="data/exports/canonical_v1_federation" if pid == "moneysweep-pr"
                 else "exports/federation")
        for pid in _PRODUCERS
    ]
    return Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=producers)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    _write(ws / "moneysweep-pr/reports/source_registry_status.csv", _MONEYSWEEP_CSV)
    _write(ws / "moneysweep-pr/data/exports/canonical_v1_federation/manifest.json",
           json.dumps({"created_at": "2026-09-01T02:29:04Z"}))
    _write(ws / "centinelas-pr/data/reference/source_registry.csv", _CENTINELAS_CSV)
    _write(ws / "ovnis-pr/data/reference/source_registry.csv", _OVNIS_CSV)
    _write(ws / "spiderweb-pr/manifests/pr_hydrography/source_registry.csv", _SPIDERWEB_CSV)
    _write(ws / "spiderweb-pr/configs/missing_persons_sources.yaml", _SPIDERWEB_MISSING_PERSONS)
    _write(ws / "skywatcher-pr/registry/source_registry.yaml", _SKYWATCHER_YAML)
    _write(ws / "skywatcher-pr/exports/federation/manifest.json",
           json.dumps({"created_at": "2026-08-28T00:11:41Z"}))
    # aguayluz-pr reports through the source_monitors stream (ADR 0013); its
    # registry files are present but must not be read.
    _write(ws / "aguayluz-pr/config/hydromet_sources.v1.json", '{"sources": [{"source_id": "x"}]}')
    return ws


def _by_id(rows):
    return {r["monitor_id"]: r for r in rows}


def test_every_producer_shape_is_normalized(workspace):
    rows, summary = build_monitor(_registry(), workspace, now=NOW)
    counts = {pid: info["count"] for pid, info in summary["producers"].items()}
    assert counts == {
        "moneysweep-pr": 3, "centinelas-pr": 2, "ovnis-pr": 2,
        "spiderweb-pr": 3, "skywatcher-pr": 2, "aguayluz-pr": 0,
    }
    assert summary["total"] == 12 == len(rows)
    assert summary["error_count"] == 0
    # A stream producer is marked, not read and not reported as an error.
    aguayluz = summary["producers"]["aguayluz-pr"]
    assert aguayluz["reports_via_stream"] is True
    assert (aguayluz["registries"], aguayluz["errors"]) == ([], [])

    r = _by_id(rows)
    ms = r["moneysweep-pr:usaspending_prime"]
    assert (ms["producer_family"], ms["cadence"], ms["status"]) == ("federal", "weekly", "partial")
    assert ms["cadence_window_seconds"] == 7 * 86400
    assert ms["raw"]["blocker_notes"] == "API, bulk"
    assert r["moneysweep-pr:pr_ocpr_contracts"]["cadence"] == "event"
    assert r["moneysweep-pr:pr_ocpr_contracts"]["status"] == "not_active"

    cent = r["centinelas-pr:CENT-SRC-MANUAL-GACETA"]
    # Centinelas reliability is a 0..1 score, never coerced into a T-tier.
    assert cent["evidence_tier"] is None and cent["raw"]["reliability_default"] == "0.95"
    assert (cent["cadence"], cent["status"]) == ("manual", "manual")

    assert r["ovnis-pr:SRC-0000"]["status"] == "inactive"
    assert r["ovnis-pr:SRC-0001"]["evidence_tier"] == "T1"

    hydro = r["spiderweb-pr:TIGER_PR_BOUNDARY"]
    assert (hydro["cadence"], hydro["evidence_tier"]) == ("static", "T1")
    assert hydro["url"] == "https://example.org/tiger.zip"
    namus = r["spiderweb-pr:namus"]
    assert (namus["cadence"], namus["status"]) == ("quarterly", "active")
    assert namus["cadence_window_seconds"] == 90 * 86400
    assert r["spiderweb-pr:gwu_maria_mortality_study"]["cadence"] == "static"

    assert r["skywatcher-pr:adsb_exchange"]["cadence"] == "realtime"
    assert r["skywatcher-pr:public_port_authority_updates"]["cadence"] == "unknown"
    assert r["skywatcher-pr:public_port_authority_updates"]["producer_family"] == "maritime"

    assert not any(row["producer"] == "aguayluz-pr" for row in rows)

    for row in rows:
        assert row["cadence"] in CADENCES and row["status"] in STATUSES
        assert row["monitor_id"] == f"{row['producer']}:{row['source_id']}"
        assert row["observed_at"] == NOW
        assert row["lineage"]["registry_path"]


def test_rows_sorted_and_ids_unique(workspace):
    rows, _ = build_monitor(_registry(), workspace, now=NOW)
    ids = [r["monitor_id"] for r in rows]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_not_federation_eligible_sources_are_counted_not_surfaced(workspace):
    rows, summary = build_monitor(_registry(), workspace, now=NOW)
    assert "spiderweb-pr:tip_line" not in _by_id(rows)
    assert summary["producers"]["spiderweb-pr"]["excluded"] == {"not_federation_eligible": 1}


def test_freshness_is_producer_level_package_timestamp(workspace):
    rows, summary = build_monitor(_registry(), workspace, now=NOW)
    r = _by_id(rows)
    assert r["moneysweep-pr:usaspending_prime"]["producer_last_package_at"] == "2026-09-01T02:29:04Z"
    assert r["skywatcher-pr:adsb_exchange"]["producer_last_package_at"] == "2026-08-28T00:11:41Z"
    assert r["ovnis-pr:SRC-0001"]["producer_last_package_at"] is None
    assert summary["producers"]["ovnis-pr"]["package_created_at"] is None


def test_output_is_deterministic(workspace, tmp_path):
    a = write_monitor(*build_monitor(_registry(), workspace, now=NOW), tmp_path / "a")
    b = write_monitor(*build_monitor(_registry(), workspace, now=NOW), tmp_path / "b")
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]
    lines = a[0].read_text().splitlines()
    assert len(lines) == 12 and all(json.loads(line)["monitor_id"] for line in lines)


def test_missing_file_and_drifted_columns_fail_soft(workspace):
    (workspace / "ovnis-pr/data/reference/source_registry.csv").unlink()
    _write(workspace / "centinelas-pr/data/reference/source_registry.csv", "source_id,title\nX,Y\n")
    _write(workspace / "skywatcher-pr/registry/source_registry.yaml", "airspace:\n  - tier: T1\n")
    rows, summary = build_monitor(_registry(), workspace, now=NOW)

    errs = {pid: info["errors"] for pid, info in summary["producers"].items()}
    assert errs["ovnis-pr"] == ["data/reference/source_registry.csv: file not found"]
    assert "missing column(s)" in errs["centinelas-pr"][0]
    assert "entry without 'id'" in errs["skywatcher-pr"][0]
    assert summary["error_count"] == 3
    # The other producers are unaffected.
    assert summary["producers"]["moneysweep-pr"]["count"] == 3
    assert {r["producer"] for r in rows} == {"moneysweep-pr", "spiderweb-pr"}


def test_missing_checkout_and_unknown_producer_are_reported(tmp_path):
    reg = Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=[
        Producer(program_id="ovnis-pr", repo="jotaele44/ovnis-pr", role="test"),
        Producer(program_id="new-pr", repo="jotaele44/new-pr", role="test"),
    ])
    (tmp_path / "new-pr").mkdir()
    rows, summary = build_monitor(reg, tmp_path, now=NOW)
    assert rows == []
    assert summary["producers"]["ovnis-pr"]["checkout_present"] is False
    assert summary["producers"]["ovnis-pr"]["errors"][0].startswith("checkout not found")
    assert summary["producers"]["new-pr"]["errors"] == ["no registry adapter for this producer"]


def test_duplicate_source_ids_within_a_producer_are_skipped(workspace):
    _write(workspace / "ovnis-pr/data/reference/source_registry.csv",
           _OVNIS_CSV + "SRC-0001,Duplicate,en,USAF,T2,html,yes,weekly,allowed,\n")
    rows, summary = build_monitor(_registry(), workspace, now=NOW)
    assert _by_id(rows)["ovnis-pr:SRC-0001"]["name"] == "AARO Case Archive"
    assert any("duplicate source id 'SRC-0001'" in e for e in summary["producers"]["ovnis-pr"]["errors"])


# Raw vocabularies pinned from the producer registries (2026-11). A new raw value
# normalizes to "unknown" (raw kept) until it is added to the tables.
@pytest.mark.parametrize("raw,expected", [
    ("weekly", "weekly"), ("monthly", "monthly"), ("quarterly", "quarterly"), ("yearly", "yearly"),
    ("annual", "yearly"), ("ad_hoc", "event"), ("one_time", "static"), ("on_drop", "event"),
    ("none", "static"), ("on_foia_release", "event"), ("on_legacy_consolidation", "event"),
    ("PIN_BY_VINTAGE", "static"), ("PROBE_SERVICE_THEN_SNAPSHOT_IF_CHANGED", "event"),
    ("PROBE_SCIENCEBASE_ITEM_THEN_SNAPSHOT_IF_CHANGED", "event"),
    ("delayed_or_rate_limited", "realtime"), ("batch_file", "event"),
    ("historical_baseline", "static"), ("periodic_context", "unknown"), (None, "unknown"),
])
def test_named_cadence_table(raw, expected):
    assert normalize_cadence(raw) == expected


@pytest.mark.parametrize("seconds,expected", [
    (900, "realtime"), (3600, "hourly"), (86400, "daily"), (7 * 86400, "weekly"),
    (30 * 86400, "monthly"), (90 * 86400, "quarterly"), (180 * 86400, "quarterly"),
    (365 * 86400, "yearly"), (0, "unknown"), (None, "unknown"), ("x", "unknown"),
])
def test_cadence_from_seconds(seconds, expected):
    assert cadence_from_seconds(seconds) == expected


@pytest.mark.parametrize("raw,expected", [
    ("fully_materialized", "active"), ("partially_materialized", "partial"),
    ("not_materialized", "not_active"), ("active", "active"), ("manual", "manual"),
    ("yes", "active"), ("no", "inactive"), ("harvester_landed", "active"),
    ("harvester_planned", "not_active"), ("manual_pull", "manual"),
    ("aggregate_only", "partial"), ("cannot_reach", "inactive"), ("something_new", "unknown"),
])
def test_declared_status_table(raw, expected):
    assert normalize_status(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("T1", "T1"), (" t3 ", "T3"), ("T5", None), ("0.9", None), (None, None),
])
def test_normalize_tier(raw, expected):
    assert normalize_tier(raw) == expected


def test_cli_writes_monitor_files(workspace, tmp_path):
    from hub.cli import main

    reg_path = tmp_path / "producers.yaml"
    reg_path.write_text(
        "schema_version: hub_registry_v1\nhub: thehub-pr\nproducers:\n"
        + "".join(
            f"  - program_id: {pid}\n    repo: jotaele44/{pid}\n    role: test\n"
            + ("    export_path: data/exports/canonical_v1_federation\n" if pid == "moneysweep-pr" else "")
            for pid in _PRODUCERS
        )
    )
    out = tmp_path / "agg"
    assert main(["source-monitor", "--registry", str(reg_path), "--root", str(workspace), "--out", str(out)]) == 0
    assert len((out / "monitored_sources.jsonl").read_text().splitlines()) == 12
    summary = json.loads((out / "monitored_sources_summary.json").read_text())
    assert summary["schema_version"] == "prii_source_monitor_v1" and summary["total"] == 12

    empty = tmp_path / "empty-ws"
    empty.mkdir()
    assert main(["source-monitor", "--registry", str(reg_path), "--root", str(empty),
                 "--out", str(tmp_path / "agg2")]) == 1


def test_declared_window_wins_and_bad_values_fall_back_to_cadence():
    from hub.source_monitor import CADENCE_WINDOW_SECONDS, _window

    assert _window("daily", 7200) == 7200
    assert _window("daily", "7200") == 7200
    assert _window("daily", "not a number") == CADENCE_WINDOW_SECONDS["daily"]
    assert _window("daily", 0) == CADENCE_WINDOW_SECONDS["daily"]
    assert _window("event", None) is None

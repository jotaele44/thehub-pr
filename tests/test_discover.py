import json

from hub.aggregate import (
    discover_packages,
    discovery_status,
    dry_run_warnings,
)
from hub.registry import Producer, Registry


def _registry(*producers):
    return Registry(hub="thehub-pr", schema_version="hub_registry_v1", producers=list(producers))


def test_discover_auto_wraps_raw_streams(tmp_path, package_factory):
    """A producer dir with raw canonical streams (no manifest) is auto-wrapped."""
    streams = tmp_path / "moneysweep-pr" / "data" / "exports" / "canonical_v1_federation"
    package_factory(streams)
    (streams / "manifest.json").unlink()  # leave only the raw streams

    reg = _registry(Producer(
        program_id="moneysweep-pr", repo="jotaele44/moneysweep-pr", role="x",
        export_path="data/exports/canonical_v1_federation",
    ))
    found = discover_packages(reg, tmp_path)
    assert "moneysweep-pr" in found
    assert (found["moneysweep-pr"] / "manifest.json").exists()  # generated on the fly


def test_discover_uses_existing_manifest(tmp_path, package_factory):
    package_factory(tmp_path / "aguayluz-pr" / "exports" / "federation")
    reg = _registry(Producer(program_id="aguayluz-pr", repo="jotaele44/aguayluz-pr", role="x"))
    assert "aguayluz-pr" in discover_packages(reg, tmp_path)


def test_discover_skips_unready_producer(tmp_path, package_factory):
    repo = tmp_path / "skywatcher-pr"
    package_factory(repo / "exports" / "federation")
    (repo / "federation.json").write_text(json.dumps(
        {"federation_readiness_gate": {"ready_for_hub_discovery": False}}
    ))
    reg = _registry(Producer(program_id="skywatcher-pr", repo="jotaele44/skywatcher-pr", role="x"))
    assert discover_packages(reg, tmp_path) == {}
    assert "skywatcher-pr" in discover_packages(reg, tmp_path, enforce_readiness=False)


def test_discover_honors_local_path(tmp_path, package_factory):
    custom = tmp_path / "anywhere" / "pkgdir"
    package_factory(custom / "exports" / "federation")
    reg = _registry(Producer(
        program_id="ovnis-pr", repo="jotaele44/ovnis-pr", role="x",
        local_path=str(custom),
    ))
    assert "ovnis-pr" in discover_packages(reg, tmp_path)


def test_discover_auto_wraps_observations_only(tmp_path):
    """A producer dir with only observations.jsonl (no manifest) is discovered."""
    _TS = "2026-01-01T00:00:00Z"
    lineage = {"producer_script": "x.py", "producer_phase": "TEST", "source_inputs": []}
    obs = {
        "observation_id": "obs_" + "0" * 32, "source_id": "src_" + "0" * 32,
        "observation_type": "aircraft_transit", "observed_at": _TS,
        "confidence": 0.9, "lineage": lineage, "synthetic": True,
        "created_at": _TS, "extracted_at": _TS,
    }
    pkg = tmp_path / "skywatcher-pr" / "exports" / "federation"
    pkg.mkdir(parents=True)
    (pkg / "observations.jsonl").write_text(json.dumps(obs, sort_keys=True) + "\n")
    reg = _registry(Producer(program_id="skywatcher-pr", repo="jotaele44/skywatcher-pr", role="x"))
    found = discover_packages(reg, tmp_path)
    assert "skywatcher-pr" in found
    assert (found["skywatcher-pr"] / "manifest.json").exists()


# ── discovery_status + dry_run_warnings (operator-facing diagnostics) ─────────

def test_discovery_status_found_on_canonical_path(tmp_path, package_factory):
    package_factory(tmp_path / "aguayluz-pr" / "exports" / "federation")
    reg = _registry(Producer(program_id="aguayluz-pr", repo="jotaele44/aguayluz-pr", role="x"))
    status = discovery_status(reg, tmp_path)
    assert status["aguayluz-pr"]["status"] == "found"
    assert status["aguayluz-pr"]["on_canonical_path"] is True
    assert status["aguayluz-pr"]["canonical_dir_present"] is True
    assert dry_run_warnings(status) == []


def test_discovery_status_missing_warns(tmp_path):
    reg = _registry(Producer(program_id="ovnis-pr", repo="jotaele44/ovnis-pr", role="x"))
    status = discovery_status(reg, tmp_path)
    assert status["ovnis-pr"]["status"] == "missing"
    warnings = dry_run_warnings(status)
    assert any("ovnis-pr" in w and "contributes nothing" in w for w in warnings)


def test_discovery_status_precursor_path_warns(tmp_path, package_factory):
    # package lives at a non-canonical export_path; exports/federation is absent
    package_factory(tmp_path / "moneysweep-pr" / "data" / "exports" / "canonical_v1_federation")
    reg = _registry(Producer(
        program_id="moneysweep-pr", repo="jotaele44/moneysweep-pr", role="x",
        export_path="data/exports/canonical_v1_federation",
    ))
    status = discovery_status(reg, tmp_path)
    assert status["moneysweep-pr"]["status"] == "found"
    assert status["moneysweep-pr"]["on_canonical_path"] is False
    assert status["moneysweep-pr"]["canonical_dir_present"] is False
    warnings = dry_run_warnings(status)
    assert any("moneysweep-pr" in w and "precursor" in w for w in warnings)


def test_discovery_status_unready_warns(tmp_path, package_factory):
    repo = tmp_path / "skywatcher-pr"
    package_factory(repo / "exports" / "federation")
    (repo / "federation.json").write_text(json.dumps(
        {"federation_readiness_gate": {"ready_for_hub_discovery": False}}
    ))
    reg = _registry(Producer(program_id="skywatcher-pr", repo="jotaele44/skywatcher-pr", role="x"))
    status = discovery_status(reg, tmp_path)
    assert status["skywatcher-pr"]["status"] == "skipped_unready"
    assert any("skywatcher-pr" in w for w in dry_run_warnings(status))

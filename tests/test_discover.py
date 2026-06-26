import json

from hub.aggregate import discover_packages
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

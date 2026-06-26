from pathlib import Path

from hub.registry import load_registry

REGISTRY = Path(__file__).resolve().parents[1] / "registry" / "producers.yaml"


def test_registry_loads_and_includes_moneysweep():
    reg = load_registry(REGISTRY)
    assert reg.hub == "thehub-pr"
    ids = {p.program_id for p in reg.producers}
    assert "moneysweep-pr" in ids
    cs = reg.by_id("moneysweep-pr")
    assert cs.repo == "jotaele44/moneysweep-pr"
    assert cs.repo_name == "moneysweep-pr"


def test_every_producer_targets_this_hub():
    reg = load_registry(REGISTRY)
    assert reg.producers, "registry must declare at least one producer"
    for p in reg.producers:
        assert "/" in p.repo, f"{p.program_id} repo must be owner/name"
        assert p.federation_manifest == "federation.json"

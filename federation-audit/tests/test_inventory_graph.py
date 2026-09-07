import json
from pathlib import Path

from federation_audit.inventory_graph import build_inventory_graph

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_graph_covers_all_repositories_and_edges():
    manifest = json.loads((ROOT / "manifests/federation.json").read_text())
    graph = build_inventory_graph(manifest, "manifests/federation.json")
    assert graph["coverage"]["repositories"] == 7
    assert graph["coverage"]["entry_points"] == sum(
        len(repo["entry_points"]) for repo in manifest["repositories"]
    )
    assert len(graph["edges"]) == len(graph["nodes"]) - 7
    assert graph["evidence_basis"]["runtime_execution"] is False

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def build_inventory_graph(manifest: dict[str, Any], manifest_locator: str) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def add_node(repo: str, kind: str, label: str, attributes: dict[str, Any]) -> str:
        node_id = _id(repo, kind, label, str(len(nodes)))
        nodes.append({"node_id": node_id, "kind": kind, "repository": repo, "label": label, "attributes": attributes})
        counts[kind] += 1
        return node_id

    def add_edge(source: str, target: str, relation: str, confidence: float) -> None:
        edges.append({
            "edge_id": _id(source, target, relation),
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": confidence,
        })

    for repo in manifest["repositories"]:
        name = repo["repository"]
        repo_node = add_node(name, "repository", name, {
            "commit": repo["commit"],
            "workspace_directory": repo["workspace_directory"],
            "application_types": repo["application_types"],
            "confidence": repo["confidence"],
        })
        for entry in repo["entry_points"]:
            target = add_node(name, "entry-point", f"{entry['kind']}:{entry['path']}", entry)
            add_edge(repo_node, target, "HAS_ENTRY_POINT", entry["confidence"])
        for category, values in repo["frameworks"].items():
            for framework in values:
                target = add_node(name, "framework", framework, {"category": category})
                add_edge(repo_node, target, "USES_FRAMEWORK", repo["confidence"])
        for engine in repo["workflow_engines"]:
            target = add_node(name, "workflow-engine", engine, {})
            add_edge(repo_node, target, "USES_WORKFLOW_ENGINE", repo["confidence"])
        auth = repo["authentication"]
        target = add_node(name, "authentication", auth["model"], auth)
        add_edge(repo_node, target, "DECLARES_AUTH_MODEL", auth["confidence"])
        for boundary in repo["destructive_boundaries"]:
            target = add_node(name, "destructive-boundary", boundary["kind"], boundary)
            add_edge(repo_node, target, "HAS_DESTRUCTIVE_BOUNDARY", boundary["confidence"])
        for gap in repo["gaps"]:
            target = add_node(name, "gap", gap, {})
            add_edge(repo_node, target, "HAS_GAP", repo["confidence"])

    return {
        "schema_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph_type": "federation-static-inventory",
        "nodes": nodes,
        "edges": edges,
        "coverage": {
            "repositories": counts["repository"],
            "entry_points": counts["entry-point"],
            "frameworks": counts["framework"],
            "workflow_engines": counts["workflow-engine"],
            "destructive_boundaries": counts["destructive-boundary"],
            "gaps": counts["gap"],
        },
        "evidence_basis": {
            "manifest": manifest_locator,
            "repository_commits_pinned": True,
            "runtime_execution": False,
        },
    }

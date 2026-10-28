"""Federation Constellation: the apps, their code and their content as one graph.

Pure and read-only. ``registry/constellation.v1.json`` declares the stage tour,
the code components of each app and the edges between them. This module joins
that spec with what the Hub store actually holds and returns two lenses on the
same graph:

* **code**: the declared components. CALL edges stay inside one app, RESULT
  edges write an artifact, HANDOFF edges carry an artifact across an app
  boundary (runtime RPC between producers is forbidden by governance).
* **content**: the canonical streams each producer exported, with the real
  totals from ``graph_summary`` and the rows this store holds; the Hub's
  aggregate streams; the correlation candidates by strategy; and the UI
  collections ingest projects. Seams with no rows in the store are shown as
  declared, with their status, never as data.

Nothing is inferred. Counts come from the store, sample rows are stored rows,
and the two lenses are linked only through ``lineage.producer_script`` or a
component's declared ``produces``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import epistemic as ep
from .ingest import STREAM_TO_COLLECTION

SCHEMA_VERSION = "prii_constellation_v1"
CONTRACT_ID = "federation-constellation-v1"
SPEC_FILE = "constellation.v1.json"
SAMPLE_LIMIT = 5
HUB_APP = "thehub"

CODE_KINDS = frozenset({"command", "config", "module", "script", "function", "artifact", "route", "ui"})
CODE_EDGE_KINDS = ("call", "handoff", "result")
CONTENT_EDGE_KINDS = ("flow", "correlation", "projection")
EDGE_STATUSES = frozenset({"dormant", "manual"})
# The canonical streams in aggregate order (schemas/federation_*.schema.json).
STREAMS = ("sources", "entities", "relationships", "funding_awards", "transactions", "observations", "alerts")
# Hub-side content node kinds, each placed at the stage the spec's content_stages names.
HUB_CONTENT_KINDS = ("hub_stream", "correlation", "collection")
_CORRELATIONS_COLLECTION = STREAM_TO_COLLECTION["correlations"]

# (producer program_id, stream)
StreamKey = Tuple[str, str]


class ConstellationSpecError(ValueError):
    """The constellation spec is inconsistent with itself."""


@dataclass
class CorrelationRow:
    """One stored correlation, its endpoints resolved to (producer, stream)."""

    relationship_id: str
    relationship_type: str
    match_basis: str
    synthetic: bool
    explanation: str = ""
    source: Optional[StreamKey] = None
    target: Optional[StreamKey] = None


@dataclass
class StoreSnapshot:
    """What the Hub store holds, gathered by the API and handed over as plain data."""

    summary: Optional[Mapping[str, Any]] = None
    collections: Dict[str, int] = field(default_factory=dict)
    stored: Dict[StreamKey, int] = field(default_factory=dict)
    lineage: Dict[StreamKey, List[Dict[str, Any]]] = field(default_factory=dict)
    samples: Dict[StreamKey, List[Dict[str, Any]]] = field(default_factory=dict)
    correlations: List[CorrelationRow] = field(default_factory=list)


def load_spec(path: str | Path) -> Dict[str, Any]:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_spec(spec)
    return spec


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConstellationSpecError(message)


def validate_spec(spec: Mapping[str, Any]) -> None:
    _require(spec.get("schema_version") == SCHEMA_VERSION, f"schema_version must be {SCHEMA_VERSION}")
    apps = {a["id"]: a for a in spec["apps"]}
    _require(len(apps) == len(spec["apps"]), "duplicate app id")
    _require(HUB_APP in apps, f"the {HUB_APP} app must be declared")
    stages = [s["id"] for s in spec["stages"]]
    _require(len(set(stages)) == len(stages), "duplicate stage id")
    for stage in spec["stages"]:
        _require(bool(stage.get("title", {}).get("accent")), f"stage {stage['id']} needs a highlighted title word")
        _require(bool(stage.get("subtitle_es")), f"stage {stage['id']} needs a Spanish subtitle")
        _require(all(a in apps for a in stage["apps"]), f"stage {stage['id']} names an unknown app")
        _require(bool(stage.get("content_focus")), f"stage {stage['id']} has no content focus")

    components = {c["id"]: c for c in spec["components"]}
    _require(len(components) == len(spec["components"]), "duplicate component id")
    for comp in spec["components"]:
        cid = comp["id"]
        _require(comp["app"] in apps, f"{cid}: unknown app {comp['app']}")
        _require(comp["stage"] in stages, f"{cid}: unknown stage {comp['stage']}")
        _require(comp["kind"] in CODE_KINDS, f"{cid}: unknown kind {comp['kind']}")
        if comp["app"] != HUB_APP:
            cites = comp.get("cites") or {}
            _require(bool(cites.get("doc") and cites.get("mentions")), f"{cid}: a sibling-repo component must cite a Hub doc")
        for pattern in comp.get("produces", []):
            _require(pattern.startswith("content:"), f"{cid}: produces must name content ids")
    for stage in spec["stages"]:
        for cid in stage.get("code_focus_extra", []):
            _require(cid in components, f"stage {stage['id']}: unknown component {cid}")

    for edge in spec["code_edges"]:
        src, dst = components.get(edge["from"]), components.get(edge["to"])
        _require(src is not None and dst is not None, f"edge {edge['from']} -> {edge['to']} names an unknown component")
        assert src is not None and dst is not None
        _require(edge["kind"] in CODE_EDGE_KINDS, f"edge {edge['from']} -> {edge['to']}: unknown kind")
        crosses = src["app"] != dst["app"]
        _require(crosses == (edge["kind"] == "handoff"),
                 f"edge {edge['from']} -> {edge['to']}: only a handoff may cross apps, and a handoff must")
        if "status" in edge:
            _require(edge["status"] in EDGE_STATUSES, f"edge {edge['from']} -> {edge['to']}: unknown status")

    content_stages = spec.get("content_stages") or {}
    _require(set(content_stages) == set(HUB_CONTENT_KINDS), f"content_stages must place exactly {HUB_CONTENT_KINDS}")
    _require(all(s in stages for s in content_stages.values()), "content_stages names an unknown stage")

    strategies = [s["id"] for s in spec["correlation_strategies"]]
    _require(len(set(strategies)) == len(strategies), "duplicate correlation strategy")
    for strategy in spec["correlation_strategies"]:
        _require(all(s in STREAMS for s in strategy["inputs"]), f"strategy {strategy['id']}: unknown input stream")
    collections = [p["collection"] for p in spec["projections"]]
    _require(len(set(collections)) == len(collections), "duplicate projection collection")
    for seam in spec["content_seams"]:
        _require(seam["from_app"] in apps and seam["to_app"] in apps, f"seam {seam['id']}: unknown app")
        _require(seam["stage"] in stages, f"seam {seam['id']}: unknown stage")
        _require(seam["status"] in EDGE_STATUSES, f"seam {seam['id']}: unknown status")


# ── store rows → display ──────────────────────────────────────────────────────

def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first(*values: Any) -> str:
    return next((t for t in (_text(v) for v in values) if t), "")


def sample_view(collection: str, row: Mapping[str, Any], record_id: str) -> Dict[str, Any]:
    """A stored row trimmed to what a sample list shows, linked to its Evidence Object."""
    attrs = ep.as_mapping(row.get("attributes"))
    loc = ep.as_mapping(row.get("location"))
    rtype = _first(row.get("entity_type"), row.get("source_type"), row.get("relationship_type"),
                   row.get("observation_type"), row.get("alert_type"))
    return {
        "id": record_id,
        "label": _first(row.get("name"), row.get("title"), row.get("source_name"), attrs.get("title"),
                        attrs.get("asset_name"), attrs.get("description_summary"), row.get("location_name"),
                        row.get("explanation"), rtype, record_id),
        "type": rtype or None,
        "municipality": _first(loc.get("municipality"), row.get("municipality"), row.get("location_name")) or None,
        "date": _first(row.get("observed_at"), row.get("date_local"), row.get("award_date")) or None,
        "synthetic": bool(row.get("synthetic")),
        "href": f"/evidence/{collection}/{record_id}",
    }


def strategy_for(strategies: Sequence[Mapping[str, Any]], relationship_type: str, match_basis: str) -> Optional[str]:
    for strategy in strategies:
        if strategy["relationship_type"] != relationship_type:
            continue
        if "match_basis" in strategy and strategy["match_basis"] != match_basis:
            continue
        if "match_basis_prefix" in strategy and not match_basis.startswith(strategy["match_basis_prefix"]):
            continue
        return str(strategy["id"])
    return None


# ── graph assembly ────────────────────────────────────────────────────────────

def _home_stages(spec: Mapping[str, Any]) -> Dict[str, str]:
    """Each app's anchor sits at the first (non-overview) stage that names it."""
    homes: Dict[str, str] = {}
    for stage in spec["stages"]:
        if stage.get("overview"):
            continue
        for app in stage["apps"]:
            homes.setdefault(app, stage["id"])
    return homes


def _edge(kind: str, src: str, dst: str, **extra: Any) -> Dict[str, Any]:
    return {"id": f"{kind}:{src}->{dst}", "kind": kind, "from": src, "to": dst, **extra}


def _matches(node_id: str, patterns: Iterable[str]) -> bool:
    return any(fnmatchcase(node_id, p) for p in patterns)


def _app_nodes(spec: Mapping[str, Any], homes: Mapping[str, str],
               registry_status: Mapping[str, str]) -> List[Dict[str, Any]]:
    return [{
        "id": f"app:{app['id']}",
        "kind": "app",
        "app": app["id"],
        "stage": homes.get(app["id"], spec["stages"][-1]["id"]),
        "label": app["name"],
        "sublabel": f"{app['program_id']} · {app['domain']}",
        "summary": app["domain"],
        "registry_status": registry_status.get(app["program_id"]),
    } for app in spec["apps"]]


def _code_lens(spec: Mapping[str, Any], apps: Mapping[str, Mapping[str, Any]],
               app_nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes = [dict(n) for n in app_nodes]
    edges: List[Dict[str, Any]] = []
    for comp in spec["components"]:
        program = apps[comp["app"]]["program_id"]
        nodes.append({
            "id": comp["id"],
            "kind": comp["kind"],
            "app": comp["app"],
            "stage": comp["stage"],
            "label": comp["name"],
            "sublabel": f"{program} · {comp['path'] or comp['kind']}",
            "summary": comp["summary"],
            "path": comp["path"],
            "generated": bool(comp.get("generated")),
        })
        edges.append(_edge("member", f"app:{comp['app']}", comp["id"]))
    for edge in spec["code_edges"]:
        extra = {k: edge[k] for k in ("artifact", "contract", "status", "seam") if k in edge}
        edges.append(_edge(edge["kind"], edge["from"], edge["to"], **extra))
    return nodes, edges


def _round_robin(groups: Sequence[Sequence[Dict[str, Any]]], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(max((len(g) for g in groups), default=0)):
        out.extend(g[i] for g in groups if i < len(g))
    return out[:limit]


def _content_lens(spec: Mapping[str, Any], store: StoreSnapshot, apps: Mapping[str, Mapping[str, Any]],
                  homes: Mapping[str, str], app_nodes: List[Dict[str, Any]],
                  ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes = [dict(n) for n in app_nodes]
    edges: List[Dict[str, Any]] = []
    summary = store.summary or {}
    totals = summary.get("producers") or {}
    stream_totals = summary.get("streams") or {}
    placed = spec["content_stages"]

    # Producer streams: one node per producer x stream that exported or stored rows.
    producer_samples: Dict[str, List[List[Dict[str, Any]]]] = {s: [] for s in STREAMS}
    stream_ids: Dict[StreamKey, str] = {}
    for app in spec["apps"]:
        if app["id"] == HUB_APP:
            continue
        program = app["program_id"]
        exported = totals.get(program) or {}
        for stream in STREAMS:
            key = (program, stream)
            total = int(exported.get(stream) or 0)
            stored = int(store.stored.get(key, 0))
            if not total and not stored:
                continue
            node_id = f"content:{app['id']}:{stream}"
            stream_ids[key] = node_id
            samples = store.samples.get(key, [])
            producer_samples[stream].append(samples)
            nodes.append({
                "id": node_id, "kind": "stream", "app": app["id"], "stage": homes[app["id"]],
                "label": stream, "sublabel": f"{program} · {stream}.jsonl",
                "summary": f"{app['name']} exported {total:,} {stream} rows; this store holds {stored:,} of them.",
                "stream": stream, "total": total, "stored": stored,
                "lineage": store.lineage.get(key, []), "samples": samples,
            })
            edges.append(_edge("member", f"app:{app['id']}", node_id))

    # The Hub's aggregate streams.
    for stream in STREAMS:
        node_id = f"content:thehub:stream:{stream}"
        collection = STREAM_TO_COLLECTION[stream]
        nodes.append({
            "id": node_id, "kind": "hub_stream", "app": HUB_APP, "stage": placed["hub_stream"],
            "label": stream, "sublabel": f"thehub-pr · data/aggregate/{stream}.jsonl",
            "summary": f"The aggregate {stream} stream: every producer's rows, deduped by id.",
            "stream": stream, "total": int(stream_totals.get(stream) or 0),
            "stored": int(store.collections.get(collection, 0)),
            "samples": _round_robin(producer_samples[stream], SAMPLE_LIMIT),
        })
        edges.append(_edge("member", f"app:{HUB_APP}", node_id))
    for (program, stream), node_id in stream_ids.items():
        total = int((totals.get(program) or {}).get(stream) or 0)
        edges.append(_edge("flow", node_id, f"content:thehub:stream:{stream}", weight=total))

    # Correlation candidates, bucketed by strategy and by producer-stream pair.
    strategies = spec["correlation_strategies"]
    counts: Dict[str, int] = {s["id"]: 0 for s in strategies}
    samples_by: Dict[str, List[CorrelationRow]] = {s["id"]: [] for s in strategies}
    pairs: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in sorted(store.correlations, key=lambda r: r.relationship_id):
        sid = strategy_for(strategies, row.relationship_type, row.match_basis)
        if sid is None:
            continue
        counts[sid] += 1
        samples_by[sid].append(row)
        src = stream_ids.get(row.source) if row.source else None
        dst = stream_ids.get(row.target) if row.target else None
        if src and dst and src != dst:
            a, b = sorted((src, dst))
            pair = pairs.setdefault((a, b), {"weight": 0, "strategies": []})
            pair["weight"] += 1
            if sid not in pair["strategies"]:
                pair["strategies"].append(sid)
    for strategy in strategies:
        node_id = f"content:thehub:correlation:{strategy['id']}"
        rows = samples_by[strategy["id"]]
        nodes.append({
            "id": node_id, "kind": "correlation", "app": HUB_APP, "stage": placed["correlation"],
            "label": strategy["label"], "sublabel": f"thehub-pr · {strategy['relationship_type']}",
            "summary": f"{counts[strategy['id']]:,} candidate links from the {strategy['label']} strategy.",
            "total": counts[strategy["id"]], "stored": counts[strategy["id"]], "synthetic": True,
            "samples": [{
                "id": r.relationship_id, "label": r.explanation or r.relationship_type, "type": r.relationship_type,
                "municipality": None, "date": None, "synthetic": r.synthetic,
                "href": f"/evidence/{_CORRELATIONS_COLLECTION}/{r.relationship_id}",
            } for r in rows[:SAMPLE_LIMIT]],
        })
        edges.append(_edge("member", f"app:{HUB_APP}", node_id))
        for stream in strategy["inputs"]:
            edges.append(_edge("flow", f"content:thehub:stream:{stream}", node_id, weight=counts[strategy["id"]]))
    for (a, b), pair in sorted(pairs.items()):
        edges.append(_edge("correlation", a, b, weight=pair["weight"], strategies=pair["strategies"], synthetic=True))

    # UI collections projected by ingest.
    content_ids = {n["id"] for n in nodes}
    for projection in spec["projections"]:
        collection = projection["collection"]
        node_id = f"content:thehub:ui:{collection}"
        stored = int(store.collections.get(collection, 0))
        nodes.append({
            "id": node_id, "kind": "collection", "app": HUB_APP, "stage": placed["collection"],
            "label": collection, "sublabel": "thehub-pr · data/hub.db",
            "summary": f"{stored:,} rows projected for TheHub's pages.",
            "total": None, "stored": stored,
        })
        edges.append(_edge("member", f"app:{HUB_APP}", node_id))
        for src in sorted(i for i in content_ids if _matches(i, projection["from"])):
            edges.append(_edge("projection", src, node_id, weight=stored))

    # Declared seams with no rows in the store.
    for seam in spec["content_seams"]:
        nodes.append({
            "id": seam["id"], "kind": "seam", "app": seam["from_app"], "stage": seam["stage"],
            "label": seam["name"], "sublabel": seam["sublabel"], "summary": seam["summary"],
            "total": None, "stored": None, "status": seam["status"], "seam": seam["seam"],
        })
        edges.append(_edge("flow", f"app:{seam['from_app']}", seam["id"], status=seam["status"], seam=seam["seam"]))
        edges.append(_edge("flow", seam["id"], f"app:{seam['to_app']}", status=seam["status"], seam=seam["seam"]))
    return nodes, edges


def _links(spec: Mapping[str, Any], content_nodes: Sequence[Mapping[str, Any]],
           apps: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    seen = set()

    def add(code_id: str, content_id: str) -> None:
        if (code_id, content_id) not in seen:
            seen.add((code_id, content_id))
            links.append({"code": code_id, "content": content_id})

    by_app_path: Dict[Tuple[str, str], List[str]] = {}
    for comp in spec["components"]:
        if comp["path"]:
            by_app_path.setdefault((comp["app"], comp["path"]), []).append(comp["id"])
    for node in content_nodes:
        for entry in node.get("lineage") or []:
            for code_id in by_app_path.get((node["app"], entry.get("script") or ""), []):
                add(code_id, node["id"])
    content_ids = [n["id"] for n in content_nodes if n["kind"] != "app"]
    for comp in spec["components"]:
        for content_id in content_ids:
            if _matches(content_id, comp.get("produces", [])):
                add(comp["id"], content_id)
    return links


def _focus(spec: Mapping[str, Any], stage: Mapping[str, Any], code_nodes: Sequence[Mapping[str, Any]],
           content_nodes: Sequence[Mapping[str, Any]]) -> Dict[str, List[str]]:
    anchors = [f"app:{a}" for a in stage["apps"]]
    if stage.get("overview"):
        return {"code": [n["id"] for n in code_nodes], "content": [n["id"] for n in content_nodes]}
    code = anchors + [n["id"] for n in code_nodes if n["kind"] != "app" and n["stage"] == stage["id"]]
    code += [c for c in stage.get("code_focus_extra", []) if c not in code]
    content = anchors + [n["id"] for n in content_nodes
                         if n["kind"] != "app" and _matches(n["id"], stage["content_focus"])]
    return {"code": code, "content": content}


def build_constellation(spec: Mapping[str, Any], store: StoreSnapshot,
                        registry_status: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    apps = {a["id"]: a for a in spec["apps"]}
    homes = _home_stages(spec)
    app_nodes = _app_nodes(spec, homes, registry_status or {})
    code_nodes, code_edges = _code_lens(spec, apps, app_nodes)
    content_nodes, content_edges = _content_lens(spec, store, apps, homes, app_nodes)

    stored_rows = sum(int(store.collections.get(STREAM_TO_COLLECTION[s], 0)) for s in STREAMS)
    stages = [{
        "id": stage["id"], "index": i, "title": stage["title"], "subtitle_es": stage["subtitle_es"],
        "apps": stage["apps"], "summary": stage["summary"], "overview": bool(stage.get("overview")),
        "focus": _focus(spec, stage, code_nodes, content_nodes),
    } for i, stage in enumerate(spec["stages"])]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "store_status": "AVAILABLE" if stored_rows else "EMPTY",
        "apps": [{**app, "home_stage": homes.get(app["id"]),
                  "registry_status": (registry_status or {}).get(app["program_id"])} for app in spec["apps"]],
        "stages": stages,
        "lenses": {
            "code": {"legend": spec["edge_kinds"]["code"], "nodes": code_nodes, "edges": code_edges},
            "content": {"legend": spec["edge_kinds"]["content"], "nodes": content_nodes, "edges": content_edges},
        },
        "links": _links(spec, content_nodes, apps),
        "totals": {
            "exported": int(sum(int(v or 0) for v in ((store.summary or {}).get("streams") or {}).values())),
            "stored": stored_rows,
            "correlations": len(store.correlations),
        },
    }


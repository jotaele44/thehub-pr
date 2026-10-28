"""Federation Constellation spec and builder: the spec stays true to the repo."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from hub import correlate, ingest
from hub.constellation import (
    SAMPLE_LIMIT,
    ConstellationSpecError,
    CorrelationRow,
    StoreSnapshot,
    build_constellation,
    load_spec,
    sample_view,
    strategy_for,
    validate_spec,
)
from hub.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "registry" / "constellation.v1.json"
SPEC = load_spec(SPEC_PATH)
COMPONENTS = {c["id"]: c for c in SPEC["components"]}
APPS = {a["id"]: a for a in SPEC["apps"]}


def _rejects(mutate, match):
    spec = copy.deepcopy(SPEC)
    mutate(spec)
    with pytest.raises(ConstellationSpecError, match=match):
        validate_spec(spec)


# ── the spec against the repo ────────────────────────────────────────────────

def test_apps_match_the_manager_catalog_and_the_registry():
    pytest.importorskip("jsonschema")
    from server.backend.federation_manager import APP_DISPLAY_NAMES, APP_IDS

    assert set(APPS) == set(APP_IDS)
    assert {a["id"]: a["name"] for a in SPEC["apps"]} == APP_DISPLAY_NAMES
    registry = load_registry(ROOT / "registry" / "producers.yaml")
    producers = {p.program_id for p in registry.producers}
    assert {a["program_id"] for a in SPEC["apps"] if a["id"] != "thehub"} == producers


def test_hub_components_exist_on_disk():
    hub = [c for c in SPEC["components"] if c["app"] == "thehub" and c["path"] and not c.get("generated")]
    assert hub
    missing = [c["path"] for c in hub if not (ROOT / c["path"]).exists()]
    assert missing == []


def test_generated_hub_artifacts_are_not_committed():
    generated = [c for c in SPEC["components"] if c.get("generated")]
    assert [c["path"] for c in generated] == ["data/hub.db"]


def test_sibling_components_cite_a_hub_doc_that_names_them():
    for comp in SPEC["components"]:
        if comp["app"] == "thehub":
            continue
        doc = ROOT / comp["cites"]["doc"]
        assert doc.exists(), comp["id"]
        assert comp["cites"]["mentions"] in doc.read_text(encoding="utf-8"), comp["id"]


def test_every_cross_app_handoff_is_a_declared_dependency():
    graph = yaml.safe_load((ROOT / "governance" / "federation_dependencies.yaml").read_text())
    declared = {(e["from"], e["to"]) for e in graph["edges"]}
    program = {a["id"]: a["program_id"] for a in SPEC["apps"]}
    handoffs = [e for e in SPEC["code_edges"] if e["kind"] == "handoff"]
    assert handoffs
    for edge in handoffs:
        pair = (program[COMPONENTS[edge["from"]]["app"]], program[COMPONENTS[edge["to"]]["app"]])
        assert pair in declared, edge
    seams = {(program[s["from_app"]], program[s["to_app"]]) for s in SPEC["content_seams"]}
    assert seams <= declared


def test_package_paths_follow_the_registry_export_path():
    registry = {p.program_id: p.export_path for p in load_registry(ROOT / "registry" / "producers.yaml").producers}
    for app in SPEC["apps"]:
        if app["id"] == "thehub":
            continue
        package = COMPONENTS[f"{app['id']}.package"]
        assert package["path"].rstrip("/") == registry[app["program_id"]], app["id"]


def test_correlation_components_name_real_strategy_functions():
    for comp in SPEC["components"]:
        if comp["kind"] == "function" and comp["path"] == "src/hub/correlate.py":
            assert callable(getattr(correlate, comp["name"])), comp["name"]


def test_every_committed_correlation_has_a_strategy():
    strategies = SPEC["correlation_strategies"]
    rows = [json.loads(line) for line in (ROOT / "data" / "aggregate" / "correlations.jsonl").read_text().splitlines()]
    assert rows
    assert all(strategy_for(strategies, r["relationship_type"], r["match_basis"]) for r in rows)


def test_projections_agree_with_ingest():
    spec = {p["collection"]: set(p["from"]) for p in SPEC["projections"]}
    expected = {collection: {f"content:thehub:stream:{stream}"} for stream, _, collection, _ in ingest._UI_PROJECTIONS}
    app_of = {a["program_id"]: a["id"] for a in SPEC["apps"]}
    for (program, _entity_type), collection in ingest._PRODUCER_LEDGER.items():
        expected[collection] = {f"content:{app_of[program]}:entities"}
    for collection, alias in ingest._LEDGER_ALIAS.items():
        expected[alias] = expected[collection]
    for collection, sources in expected.items():
        assert spec.get(collection) == sources, collection
    assert set(spec) - set(expected) == {ingest._CROSSOVER_COLLECTION, "ContinuityRisks", "LiveFeedItems"}


# ── validation rejects inconsistent specs ────────────────────────────────────

def test_rejects_a_call_across_apps():
    def mutate(spec):
        spec["code_edges"].append({"from": "centinelas.dispatch", "to": "moneysweep.geo", "kind": "call"})
    _rejects(mutate, "only a handoff may cross apps")


def test_rejects_a_handoff_inside_one_app():
    def mutate(spec):
        spec["code_edges"].append({"from": "thehub.cli", "to": "thehub.fetch", "kind": "handoff"})
    _rejects(mutate, "only a handoff may cross apps")


def test_rejects_unknown_references():
    _rejects(lambda s: s["code_edges"].append({"from": "nope", "to": "thehub.cli", "kind": "call"}), "unknown component")
    _rejects(lambda s: s["components"][0].update(stage="nope"), "unknown stage")
    _rejects(lambda s: s["stages"][0]["apps"].append("nope"), "unknown app")
    _rejects(lambda s: s["content_stages"].update(collection="nope"), "unknown stage")


def test_rejects_an_uncited_sibling_component():
    _rejects(lambda s: s["components"][0].pop("cites"), "must cite a Hub doc")


def test_rejects_a_stage_without_a_highlighted_word():
    _rejects(lambda s: s["stages"][0]["title"].update(accent=""), "highlighted title word")


# ── building the graph ───────────────────────────────────────────────────────

def _snapshot():
    return StoreSnapshot(
        summary={"producers": {"aguayluz-pr": {"entities": 900, "alerts": 40}, "ovnis-pr": {"entities": 70}},
                 "streams": {"entities": 970, "alerts": 40}},
        collections={"Entities": 12, "Alerts": 4, "GraphNodes": 12, "Correlations": 3},
        stored={("aguayluz-pr", "entities"): 8, ("aguayluz-pr", "alerts"): 4, ("ovnis-pr", "entities"): 4},
        lineage={("aguayluz-pr", "entities"): [{"script": "scripts/federation_export.py", "phase": "ASSET_ENTITY",
                                                "count": 8, "inputs": ["data/utility_assets.jsonl"]}]},
        samples={("aguayluz-pr", "entities"): [{"id": "ent_a", "label": "AAA/PRASA"}],
                 ("ovnis-pr", "entities"): [{"id": "ent_o", "label": "Vieques"}]},
        correlations=[
            CorrelationRow("rel_1", "entity_correlation", "normalized_name", True, "Shared name 'vieques'.",
                           ("aguayluz-pr", "entities"), ("ovnis-pr", "entities")),
            CorrelationRow("rel_2", "entity_correlation", "normalized_name", True, "",
                           ("ovnis-pr", "entities"), ("aguayluz-pr", "entities")),
            CorrelationRow("rel_3", "alert_affects_entity", "location", True, "", ("aguayluz-pr", "entities"), None),
        ],
    )


def _by_id(items):
    return {item["id"]: item for item in items}


def test_content_nodes_carry_exported_totals_and_stored_rows():
    out = build_constellation(SPEC, _snapshot(), {"aguayluz-pr": "ready_for_live"})
    nodes = _by_id(out["lenses"]["content"]["nodes"])
    entities = nodes["content:aguayluz:entities"]
    assert (entities["total"], entities["stored"]) == (900, 8)
    assert entities["lineage"][0]["script"] == "scripts/federation_export.py"
    assert nodes["content:thehub:stream:entities"]["total"] == 970
    assert nodes["content:thehub:stream:entities"]["stored"] == 12
    assert [s["id"] for s in nodes["content:thehub:stream:entities"]["samples"]] == ["ent_o", "ent_a"]  # spec app order
    assert "content:centinelas:entities" not in nodes
    assert nodes["app:aguayluz"]["registry_status"] == "ready_for_live"
    assert out["store_status"] == "AVAILABLE"
    assert out["totals"] == {"exported": 1010, "stored": 16, "correlations": 3}


def test_flows_are_weighted_by_the_exported_total():
    edges = _by_id(build_constellation(SPEC, _snapshot())["lenses"]["content"]["edges"])
    flow = edges["flow:content:aguayluz:entities->content:thehub:stream:entities"]
    assert flow["weight"] == 900


def test_correlations_bucket_by_strategy_and_pair_producer_streams():
    out = build_constellation(SPEC, _snapshot())
    nodes = _by_id(out["lenses"]["content"]["nodes"])
    assert nodes["content:thehub:correlation:normalized_name"]["total"] == 2
    assert nodes["content:thehub:correlation:alerts"]["total"] == 1
    assert nodes["content:thehub:correlation:normalized_name"]["synthetic"] is True
    pairs = [e for e in out["lenses"]["content"]["edges"] if e["kind"] == "correlation"]
    assert [(p["from"], p["to"], p["weight"], p["strategies"]) for p in pairs] == [
        ("content:aguayluz:entities", "content:ovnis:entities", 2, ["normalized_name"])]
    sample = nodes["content:thehub:correlation:normalized_name"]["samples"][0]
    assert sample["href"] == "/evidence/Correlations/rel_1"


def test_links_join_code_and_content_through_lineage_and_produces():
    links = {(link["code"], link["content"]) for link in build_constellation(SPEC, _snapshot())["links"]}
    assert ("aguayluz.export", "content:aguayluz:entities") in links
    assert ("thehub.correlate.names", "content:thehub:correlation:normalized_name") in links
    assert ("thehub.ingest", "content:thehub:ui:GraphNodes") in links
    assert ("centinelas.dispatch", "content:seam:intake-drops") in links
    assert not any(code == "ovnis.export" for code, _ in links)  # no ovnis lineage in this store


def test_stage_focus_covers_its_apps_and_patterns():
    stages = _by_id(build_constellation(SPEC, _snapshot())["stages"])
    domain = stages["domain-producers"]["focus"]
    assert {"app:ovnis", "app:aguayluz", "app:skywatcher"} <= set(domain["code"])
    assert {"content:aguayluz:entities", "content:aguayluz:alerts", "content:ovnis:entities"} <= set(domain["content"])
    assert "thehub.fetch" not in stages["canonical-exports"]["focus"]["code"]  # handoffs arrive from off-screen
    assert "app:thehub" not in stages["correlation"]["focus"]["code"]  # the anchor lives at hub-aggregate
    overview = stages["federation"]
    assert overview["overview"] is True
    assert len(overview["focus"]["code"]) == len(SPEC["components"]) + len(SPEC["apps"])


def test_an_empty_store_still_draws_the_code_lens():
    out = build_constellation(SPEC, StoreSnapshot())
    assert out["store_status"] == "EMPTY"
    assert len(out["lenses"]["code"]["nodes"]) == len(SPEC["components"]) + len(SPEC["apps"])
    content = out["lenses"]["content"]["nodes"]
    assert not [n for n in content if n["kind"] == "stream"]
    assert {n["total"] for n in content if n["kind"] == "hub_stream"} == {0}
    seams = [n for n in content if n["kind"] == "seam"]
    assert {(n["status"], n["total"]) for n in seams} == {("dormant", None), ("manual", None)}


def test_code_edges_keep_their_seam_status():
    edges = _by_id(build_constellation(SPEC, StoreSnapshot())["lenses"]["code"]["edges"])
    bundle = edges["handoff:moneysweep.bundle->spiderweb.finance_layer"]
    assert bundle["status"] == "manual" and bundle["contract"] == "contract_finance_bundle"


# ── row display ──────────────────────────────────────────────────────────────

def test_sample_view_prefers_a_human_label_and_links_its_evidence():
    row = {"entity_type": "utility_asset", "name": "", "attributes": {"asset_name": "Access road"},
           "location": {"municipality": "Utuado"}, "synthetic": True}
    view = sample_view("Entities", row, "ent_x")
    assert view == {"id": "ent_x", "label": "Access road", "type": "utility_asset", "municipality": "Utuado",
                    "date": None, "synthetic": True, "href": "/evidence/Entities/ent_x"}
    assert sample_view("Alerts", {"alert_type": "failure"}, "alrt_1")["label"] == "failure"
    assert sample_view("Sources", {}, "src_1")["label"] == "src_1"


def test_strategy_for_honours_exact_and_prefix_match_basis():
    strategies = SPEC["correlation_strategies"]
    assert strategy_for(strategies, "entity_correlation", "normalized_name") == "normalized_name"
    assert strategy_for(strategies, "entity_correlation", "external_id:uei") == "external_id"
    assert strategy_for(strategies, "entity_correlation", "co_occurrence") is None
    assert strategy_for(strategies, "unknown", "location") is None


def test_sample_limit_is_small():
    assert 1 <= SAMPLE_LIMIT <= 10

"""Tests for the aggregate -> entity-store ingest bridge (hub.ingest)."""
import json
import sqlite3

from hub.aggregate import aggregate
from hub.ingest import ingest_aggregate


def _ids(path):
    """entity ids present in an aggregate JSONL stream file."""
    field = {"entities": "entity_id", "sources": "source_id",
             "relationships": "relationship_id"}[path.stem]
    return {json.loads(line)[field]
            for line in path.read_text().splitlines() if line.strip()}


def _rows(db, collection):
    """{entity_id: parsed data} for one store collection."""
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT entity_id, data FROM entities WHERE entity_type=?", (collection,)
        )
        return {r[0]: json.loads(r[1]) for r in cur.fetchall()}
    finally:
        conn.close()


def _count(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    finally:
        conn.close()


def test_ingest_loads_streams_into_collections(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    expected_entities = _ids(agg / "entities.jsonl")
    expected_sources = _ids(agg / "sources.jsonl")
    expected_rels = _ids(agg / "relationships.jsonl")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    # Canonical collections + the per-domain UI projections alongside them.
    assert summary["collections"] == {
        "Sources": 1, "Entities": 2, "Relationships": 1, "FederationSummary": 1,
        "UnifiedSources": 1, "GraphNodes": 2, "GraphEdges": 1,
    }
    assert summary["skipped"] == {}

    # Entities keyed by canonical entity_id, full payload + provenance preserved.
    entities = _rows(db, "Entities")
    assert set(entities) == expected_entities
    row = next(iter(entities.values()))
    assert row["id"] in expected_entities        # id injected for the server read path
    assert "name" in row                         # canonical payload intact
    assert row["_producers"] == ["moneysweep-pr"]

    assert set(_rows(db, "Sources")) == expected_sources
    assert set(_rows(db, "Relationships")) == expected_rels
    # graph_summary folded into a single FederationSummary row.
    summary_rows = _rows(db, "FederationSummary")
    assert set(summary_rows) == {"graph_summary"}
    assert "streams" in summary_rows["graph_summary"]


def test_ingest_projects_ui_collections(valid_package, tmp_path):
    """Streams also project into the UI's per-domain collections with alias fields,
    keeping the canonical payload + provenance."""
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    expected_nodes = _ids(agg / "entities.jsonl")
    expected_sources = _ids(agg / "sources.jsonl")
    expected_edges = _ids(agg / "relationships.jsonl")

    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)

    # entities -> GraphNodes
    nodes = _rows(db, "GraphNodes")
    assert set(nodes) == expected_nodes
    node = nodes[next(iter(expected_nodes))]
    assert node["node_id"] == node["id"]
    assert node["label"] == node["name"]                 # UI alias of canonical name
    assert node["node_type"] == node["entity_type"]
    assert node["confidence"] in {"Low", "Medium", "High"}   # banded from 0..1
    assert node["_producers"] == ["moneysweep-pr"]           # provenance preserved

    # sources -> UnifiedSources
    src = next(iter(_rows(db, "UnifiedSources").values()))
    assert set(_rows(db, "UnifiedSources")) == expected_sources
    assert src["title"] == src["source_name"]
    assert src["program_id"] == "moneysweep-pr"

    # relationships -> GraphEdges
    edges = _rows(db, "GraphEdges")
    assert set(edges) == expected_edges
    edge = next(iter(edges.values()))
    assert edge["edge_id"] == edge["id"]
    assert edge["source_node_id"] == edge["source_entity_id"]
    assert edge["target_node_id"] == edge["target_entity_id"]


def test_ingest_projects_governance_alerts(tmp_path):
    """alerts -> GovernanceAlerts with canonical status normalized to the UI's
    open/closed review vocabulary."""
    agg = tmp_path / "agg"
    agg.mkdir()
    alert = {
        "alert_id": "alrt_0123456789abcdef0123456789abcdef",
        "module": "HYDRO_OPS", "alert_type": "maintenance", "severity": 3,
        "status": "active", "observed_at": "2026-01-01T00:00:00Z",
        "entity_id": "ent_0123456789abcdef0123456789abce01",
    }
    (agg / "alerts.jsonl").write_text(json.dumps(alert) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["GovernanceAlerts"] == 1
    ga = _rows(db, "GovernanceAlerts")["alrt_0123456789abcdef0123456789abcdef"]
    assert ga["review_status"] == "Open"          # canonical "active" -> UI open state
    assert ga["occurred_at"] == "2026-01-01T00:00:00Z"
    assert ga["record_id"] == "ent_0123456789abcdef0123456789abce01"
    assert ga["severity"] == 3


def test_ingest_is_idempotent(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    db = tmp_path / "hub.db"

    first = ingest_aggregate(agg, db)
    total_after_first = _count(db)
    second = ingest_aggregate(agg, db)

    # INSERT OR REPLACE on (entity_type, entity_id) -> no duplicate rows.
    assert first["collections"] == second["collections"]
    assert _count(db) == total_after_first


def test_ingest_maps_correlations_by_relationship_id(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    # Hand-write a correlation row (federation_relationship shape) as correlate would.
    rel_id = "rel_ffffffffffffffffffffffffffffffff"
    corr = {
        "relationship_id": rel_id,
        "source_id": "src_0123456789abcdef0123456789abcdef",
        "source_entity_id": "ent_0123456789abcdef0123456789abce01",
        "target_entity_id": "ent_0123456789abcdef0123456789abce02",
        "relationship_type": "entity_correlation",
        "evidence_source_id": "src_0123456789abcdef0123456789abcdef",
        "confidence": 0.8,
        "lineage": {"producer_script": "src/hub/correlate.py",
                    "producer_phase": "HUB_CORRELATE", "source_inputs": []},
        "synthetic": True, "created_at": "1970-01-01T00:00:00Z",
        "extracted_at": "1970-01-01T00:00:00Z",
    }
    (agg / "correlations.jsonl").write_text(json.dumps(corr) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["Correlations"] == 1
    assert set(_rows(db, "Correlations")) == {rel_id}


def test_ingest_skips_rows_missing_canonical_id(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    good_id = "ent_0123456789abcdef0123456789abce01"
    good = {"entity_id": good_id, "name": "FEMA"}
    bad = {"name": "no id here"}
    (agg / "entities.jsonl").write_text(
        json.dumps(good) + "\n" + json.dumps(bad) + "\n"
    )

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["Entities"] == 1
    assert summary["skipped"] == {"Entities": 1}
    assert set(_rows(db, "Entities")) == {good_id}


def test_ingest_projects_crossover_links(tmp_path):
    """correlations.jsonl -> the workspace's explicit CrossoverLinks collection.

    Covers the reshape (module/type/band mapping) and the curation: entity-name
    links are always kept; spatial links collapse to the nearest cross-producer
    match per minority-producer entity.
    """
    agg = tmp_path / "agg"
    agg.mkdir()
    ents = [
        {"entity_id": "ent_agua1", "name": "Ceiba WTP", "_producers": ["aguayluz-pr"]},
        {"entity_id": "ent_ovni1", "name": "Ceiba sighting", "_producers": ["ovnis-pr"]},
        {"entity_id": "ent_ovni2", "name": "Ceiba sighting B", "_producers": ["ovnis-pr"]},
    ]
    (agg / "entities.jsonl").write_text("\n".join(json.dumps(e) for e in ents) + "\n")
    corrs = [
        # two spatial links to the SAME minority (ovnis) entity -> keep higher confidence
        {"relationship_id": "rel_s1", "source_entity_id": "ent_agua1", "target_entity_id": "ent_ovni1",
         "relationship_type": "spatial_proximity", "match_basis": "location", "confidence": 0.9,
         "explanation": "within 0.1 km"},
        {"relationship_id": "rel_s2", "source_entity_id": "ent_agua1", "target_entity_id": "ent_ovni1",
         "relationship_type": "spatial_proximity", "match_basis": "location", "confidence": 0.5,
         "explanation": "within 0.5 km"},
        # entity-name correlation -> always kept
        {"relationship_id": "rel_e1", "source_entity_id": "ent_agua1", "target_entity_id": "ent_ovni2",
         "relationship_type": "entity_correlation", "match_basis": "normalized_name", "confidence": 0.5,
         "explanation": "shared name"},
    ]
    (agg / "correlations.jsonl").write_text("\n".join(json.dumps(c) for c in corrs) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    xlinks = _rows(db, "CrossoverLinks")
    assert summary["collections"]["CrossoverLinks"] == 2
    assert set(xlinks) == {"rel_s1", "rel_e1"}  # rel_s2 collapsed into rel_s1 (same ovnis entity)

    s1 = xlinks["rel_s1"]
    assert s1["source_module"] == "AguaYLuz-PR"      # from _producers -> CROSSOVER_MODULES string
    assert s1["target_module"] == "Ovnis-PR"
    assert s1["correlation_type"] == "Geography"     # spatial_proximity -> Geography
    assert s1["confidence_score"] == 90 and s1["confidence_band"] == "High"
    assert s1["status"] == "Candidate"
    assert s1["source_label"] == "Ceiba WTP"         # entity name resolved
    assert xlinks["rel_e1"]["correlation_type"] == "Entity"  # entity_correlation -> Entity


def test_ingest_projects_producer_collections(tmp_path, monkeypatch):
    """canonical entities -> best-effort per-domain page collections.

    Covers the per-producer split, the (producer, entity_type) -> collection
    mapping, lat/lon flatten, synthetic skip, the PatternObservations alias, and
    the per-collection cap. GraphNodes/GraphEdges/UnifiedSources are the generic
    _UI_PROJECTIONS pass's job (test_ingest_projects_ui_collections) — out of
    scope here.
    """
    import hub.ingest as ingest_mod
    monkeypatch.setattr(ingest_mod, "_LEDGER_CAP", 2)

    agg = tmp_path / "agg"
    agg.mkdir()
    ents = [
        # aguayluz -> InfrastructureAssets: 3 rows to exercise cap=2 (ungeocoded/low-conf drops)
        {"entity_id": "ent_ag1", "name": "Ceiba WTP", "entity_type": "utility_asset", "confidence": 0.9,
         "location": {"lat": 18.0, "lon": -66.0}, "_producers": ["aguayluz-pr"]},
        {"entity_id": "ent_ag2", "entity_type": "utility_asset", "confidence": 0.8,
         "location": {"lat": 18.1, "lon": -66.1}, "_producers": ["aguayluz-pr"]},
        {"entity_id": "ent_ag3", "entity_type": "utility_asset", "confidence": 0.1,
         "_producers": ["aguayluz-pr"]},
        # ovnis -> UnifiedCases (+ PatternObservations alias)
        {"entity_id": "ent_ov1", "name": "Lajas 1977", "entity_type": "uap_case",
         "confidence": 0.7, "_producers": ["ovnis-pr"]},
        # moneysweep -> Vendors + Contracts
        {"entity_id": "ent_mv1", "name": "ACME Corp", "entity_type": "recipient",
         "_producers": ["moneysweep-pr"]},
        {"entity_id": "ent_mc1", "name": "Contract 9", "entity_type": "contract",
         "_producers": ["moneysweep-pr"]},
        # synthetic -> skipped; unmapped entity_type -> not projected
        {"entity_id": "ent_syn", "entity_type": "utility_asset", "synthetic": True,
         "_producers": ["aguayluz-pr"]},
        {"entity_id": "ent_x", "entity_type": "municipality", "_producers": ["aguayluz-pr"]},
    ]
    (agg / "entities.jsonl").write_text("\n".join(json.dumps(e) for e in ents) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    # mapping + curation counts
    assert summary["collections"]["InfrastructureAssets"] == 2  # capped from 3
    assert summary["collections"]["UnifiedCases"] == 1
    assert summary["collections"]["PatternObservations"] == 1   # alias mirrors UnifiedCases
    assert summary["collections"]["Vendors"] == 1
    assert summary["collections"]["Contracts"] == 1

    # synthetic never projected; cap drops the ungeocoded low-confidence asset.
    ia = _rows(db, "InfrastructureAssets")
    assert set(ia) == {"ent_ag1", "ent_ag2"}

    # field projection: lat/lon flattened from location, id/type aliases, rich fields null.
    asset = ia["ent_ag1"]
    assert asset["latitude"] == 18.0 and asset["longitude"] == -66.0
    assert asset["id"] == "ent_ag1" and asset["asset_id"] == "ent_ag1"
    assert asset["asset_type"] == "utility_asset"
    assert asset["label"] == "Ceiba WTP"
    assert asset["municipality"] is None and asset["award_amount"] is None
    # confidence is banded with the same _conf01_band the generic UI projections use
    # (0.9 -> High); raw score kept alongside.
    assert asset["confidence"] == "High" and asset["confidence_score"] == 0.9
    # a row with no canonical confidence bands to None (blank chip, not a misleading value).
    assert _rows(db, "Vendors")["ent_mv1"]["confidence"] is None

    # Contracts row carries the contract_id alias.
    assert _rows(db, "Contracts")["ent_mc1"]["contract_id"] == "ent_mc1"


def test_ingest_empty_dir_returns_zero(tmp_path):
    agg = tmp_path / "empty"
    agg.mkdir()
    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)
    assert summary["total"] == 0
    assert summary["collections"] == {}


def test_ingest_cli_reports_and_errors(valid_package, tmp_path):
    from hub.cli import main

    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    db = tmp_path / "hub.db"

    assert main(["ingest", "--in", str(agg), "--db", str(db)]) == 0
    # Empty aggregate dir -> non-zero exit.
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["ingest", "--in", str(empty), "--db", str(db)]) == 1

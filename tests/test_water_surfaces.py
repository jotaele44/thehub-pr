"""Hub-side water-monitoring surfaces: rich assets, Continuity Risks, live feed.

Verifies that the aguayluz-pr canonical export (rich entity `attributes`,
`energized_by` relationships, water alerts) renders end-to-end into the Hub's
per-domain collections.
"""
import json
import sqlite3

from hub.ingest import ingest_aggregate


def _rows(db, collection):
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT entity_id, data FROM entities WHERE entity_type=?", (collection,)
        )
        return {r[0]: json.loads(r[1]) for r in cur.fetchall()}
    finally:
        conn.close()


def _write(agg, name, rows):
    (agg / name).write_text("".join(json.dumps(r) + "\n" for r in rows))


def _build_aggregate(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    water = {
        "entity_id": "ent_water1", "entity_type": "utility_asset", "name": "Bomba Río",
        "confidence": 0.6, "synthetic": False, "_producers": ["aguayluz-pr"],
        "location": {"lat": 18.2, "lon": -66.2, "municipality": "Utuado"},
        "attributes": {
            "municipality": "Utuado", "operator": "AAA/PRASA", "owner_agency": "AAA/PRASA",
            "status": "active", "review_status": "needs_review", "evidence_tier": "T3",
            "asset_subtype": "pumping_station", "sensitivity": "power_dependent",
        },
    }
    power = {
        "entity_id": "ent_power1", "entity_type": "utility_asset", "name": "Substation X",
        "confidence": 0.95, "synthetic": False, "_producers": ["aguayluz-pr"],
        "location": {"lat": 18.21, "lon": -66.21, "municipality": "Utuado"},
    }
    _write(agg, "entities.jsonl", [water, power])
    _write(agg, "relationships.jsonl", [{
        "relationship_id": "rel_e1", "relationship_type": "energized_by",
        "source_entity_id": "ent_water1", "target_entity_id": "ent_power1",
        "confidence": 0.5, "synthetic": False,
    }])
    _write(agg, "alerts.jsonl", [{
        "alert_id": "alrt_c1", "module": "CONTAMINATION", "alert_type": "quality",
        "severity": 4, "status": "active", "confidence": 0.8, "synthetic": False,
        "observed_at": "2026-07-01T00:00:00Z", "source_id": "src_1",
        "_producers": ["aguayluz-pr"],
        "attributes": {"asset_name": "Utuado PWS", "municipalities": ["Utuado"],
                       "review_status": "needs_review"},
        "location": {"lat": 18.2, "lon": -66.2, "municipality": "Utuado"},
    }])
    return agg


def test_infrastructure_assets_carry_rich_fields(tmp_path):
    agg = _build_aggregate(tmp_path)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    assets = _rows(db, "InfrastructureAssets")
    row = assets["ent_water1"]
    assert row["municipality"] == "Utuado"
    assert row["operator"] == "AAA/PRASA"
    assert row["owner_agency"] == "AAA/PRASA"
    assert row["status"] == "active"
    assert row["sensitivity"] == "power_dependent"


def test_continuity_risks_from_dependency_and_alert(tmp_path):
    agg = _build_aggregate(tmp_path)
    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)
    assert summary["collections"].get("ContinuityRisks", 0) >= 1
    risks = _rows(db, "ContinuityRisks")
    # power-dependency risk from the energized_by relationship
    dep = risks.get("risk_dep_ent_water1")
    assert dep is not None
    assert dep["risk_type"] == "Dependency"
    assert dep["dependency_type"] == "WaterToPower"
    assert dep["asset_id"] == "ent_water1"
    assert dep["related_asset_id"] == "ent_power1"
    # asset-anchored alert risk (the CONTAMINATION alert names ent... via entity_id?)
    # this alert has no entity_id, so only the dependency risk is expected here.
    assert dep["severity"] == "High"


def test_alert_anchored_continuity_risk(tmp_path):
    agg = _build_aggregate(tmp_path)
    # add an asset-anchored alert (entity_id set) -> its own continuity risk
    alerts = [json.loads(line) for line in (agg / "alerts.jsonl").read_text().splitlines()]
    alerts.append({
        "alert_id": "alrt_h1", "module": "HYDRO_OPS", "alert_type": "hazard",
        "severity": 2, "status": "active", "confidence": 0.6, "synthetic": False,
        "entity_id": "ent_water1", "observed_at": "2026-07-02T00:00:00Z",
        "_producers": ["aguayluz-pr"],
    })
    _write(agg, "alerts.jsonl", alerts)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    risks = _rows(db, "ContinuityRisks")
    assert "risk_alert_alrt_h1" in risks
    assert risks["risk_alert_alrt_h1"]["asset_id"] == "ent_water1"


def test_livefeed_items_from_water_alerts(tmp_path):
    agg = _build_aggregate(tmp_path)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    feed = _rows(db, "LiveFeedItems")
    item = feed["alrt_c1"]
    assert item["module"] == "AguaYLuz-PR"
    # must be one of the feed's recognized DOMAINS so the Water Events KPI counts it
    assert item["utility_domain"] == "Water"
    assert item["municipality"] == "Utuado"
    assert item["sync_status"] == "NeedsReview"  # from review_status


def test_closed_alerts_excluded_from_continuity_risks(tmp_path):
    agg = _build_aggregate(tmp_path)
    alerts = [json.loads(line) for line in (agg / "alerts.jsonl").read_text().splitlines()]
    alerts.append({
        "alert_id": "alrt_closed", "module": "HYDRO_OPS", "alert_type": "hazard",
        "severity": 3, "status": "closed", "confidence": 0.6, "synthetic": False,
        "entity_id": "ent_water1", "observed_at": "2026-07-03T00:00:00Z",
        "_producers": ["aguayluz-pr"],
    })
    _write(agg, "alerts.jsonl", alerts)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    # a closed alert must not surface as a current continuity risk
    assert "risk_alert_alrt_closed" not in _rows(db, "ContinuityRisks")


def test_foreign_producer_alert_not_in_aguayluz_feed(tmp_path):
    agg = _build_aggregate(tmp_path)
    alerts = [json.loads(line) for line in (agg / "alerts.jsonl").read_text().splitlines()]
    # another producer emits a like-named module — must NOT leak into the AguaYLuz feed
    alerts.append({
        "alert_id": "alrt_foreign", "module": "POWER_OPS", "alert_type": "outage",
        "severity": 2, "status": "active", "confidence": 0.6, "synthetic": False,
        "observed_at": "2026-07-04T00:00:00Z", "_producers": ["spiderweb-pr"],
    })
    _write(agg, "alerts.jsonl", alerts)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    assert "alrt_foreign" not in _rows(db, "LiveFeedItems")

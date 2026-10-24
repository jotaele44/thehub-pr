"""Hub-side outdoor-conditions surface: aguayluz `outdoor_condition` -> OutdoorConditions.

aguayluz-pr exports one `outdoor_condition` entity per municipio with the composed
snapshot in `attributes.components`. The Hub flattens the headline value of each
component into a ledger column and keeps every component's state beside it, so a
component that is not covered, stale or failed reads as that state — never as a
value that looks safe.
"""
import json
import sqlite3

from hub.ingest import ingest_aggregate, project_outdoor_conditions


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


def _component(state, sid, **fields):
    return {"state": state, "source_ids": [sid], **fields}


def _coastal_components():
    return {
        "rip_current": _component(
            "REPORTED", "nws_surf_zone", zone="PRZ001", zone_name="San Juan and Vicinity",
            today={"date": "2026-10-19", "label": "Today", "rip_current_risk": "HIGH",
                   "surf_min_ft": 5, "surf_max_ft": 7, "surf_height_text": "5 to 7 feet"},
            evidence_class="AUTHORITATIVE_BINDING", source_status="FRESH"),
        "marine_alerts": _component(
            "REPORTED", "nws_marine_alerts",
            alerts=[{"event": "Small Craft Advisory", "zones": ["AMZ712"], "record_id": "r1"},
                    {"event": "Small Craft Advisory", "zones": ["AMZ715"], "record_id": "r2"}],
            evidence_class="PROXIMITY"),
        "sea_state": _component(
            "REPORTED", "ndbc_buoys", station="41053", station_name="San Juan", distance_km=4.2,
            wave_height_ft=6.2, dominant_period_s=9, water_temp_f=84.4, wind_speed_kt=14.0,
            evidence_class="PROXIMITY"),
        "beach_water_quality": _component(
            "REPORTED", "drna_beach_monitoring",
            advisories=[{"beach": "Escambrón", "record_id": "b1"}, {"beach": "Ocean Park", "record_id": "b2"}]),
        "uv": _component("REPORTED", "epa_uv", uv_index=11, uv_category="EXTREME", evidence_class="PROXIMITY"),
        "heat": _component("REPORTED", "nws_gridpoint_heat", heat_band_24h="DANGER", heat_index_max_f_24h=106),
        "air_quality": _component("NOT_CONFIGURED", "airnow", note="AirNow needs the AIRNOW_API_KEY secret."),
        "rainfall_24h": _component("REPORTED", "stage_iv_pr", data_date="2026-10-18",
                                   obs_mean_in=0.4, obs_max_in=1.1),
        "river_flood": _component("REPORTED", "nwps_gauges", gauges_total=2, gauges_current=2,
                                  gauges_in_flood=[], worst_category=None),
        "nws_alerts": _component("REPORTED", "nws_alerts",
                                 alerts=[{"event": "Heat Advisory", "event_id": "e1"}]),
        "tropical_cyclone": _component("NONE_ACTIVE", "nhc_storms", storms=[]),
        "earthquakes": _component("REPORTED", "usgs_quakes",
                                  recent=[{"magnitude": 3.1, "event_id": "q1"}, {"magnitude": 4.0, "event_id": "q2"}]),
        "access_closures": _component("NOT_COVERED", "usfs_el_yunque_access",
                                      note="No certified El Yunque access asset in this municipio."),
    }


def _inland_components():
    comps = {name: _component("NOT_COVERED", "x", note="Inland municipio.")
             for name in ("rip_current", "marine_alerts", "sea_state", "beach_water_quality")}
    comps.update({
        "uv": _component("SOURCE_FAILED", "epa_uv"),
        "heat": _component("STALE", "nws_gridpoint_heat", heat_band_24h="CAUTION",
                           heat_index_max_f_24h=88, carried_forward=True),
        "air_quality": _component("NOT_INGESTED", "airnow"),
        "rainfall_24h": _component("NOT_COVERED", "stage_iv_pr"),
        "river_flood": _component("REPORTED", "nwps_gauges", gauges_total=1, gauges_current=1,
                                  gauges_in_flood=[{"lid": "UTUP4", "flood_category": "minor"}],
                                  worst_category="minor"),
        "nws_alerts": _component("NONE_ACTIVE", "nws_alerts", alerts=[]),
        "tropical_cyclone": _component("NONE_ACTIVE", "nhc_storms", storms=[]),
        "earthquakes": _component("NONE_ACTIVE", "usgs_quakes", recent=[]),
        "access_closures": _component("REPORTED", "usfs_el_yunque_access",
                                      closures=[{"asset": "El Portal", "status": "closed", "condition_id": "c1"}]),
    })
    return comps


def _outdoor(eid, muni, geoid, components, level, drivers, producers=("aguayluz-pr",)):
    return {
        "entity_id": eid, "entity_type": "outdoor_condition",
        "name": f"Outdoor conditions — {muni}", "confidence": 0.8, "synthetic": False,
        "_producers": list(producers),
        "location": {"lat": 18.4, "lon": -66.06, "municipality": muni},
        "evidence_state": {"epistemic_class": "COMPUTED", "geometry_precision": "REPRESENTATIVE_POINT"},
        "attributes": {
            "municipality": muni, "geoid": geoid, "coastal": geoid == "72127",
            "status": level, "level": level, "drivers": drivers,
            "stale_components": [], "unavailable_components": [],
            "as_of": "2026-10-19T12:00:00Z", "composed_at": "2026-10-19T12:05:00Z",
            "components": components,
            "scope_note": "Conditions context, not safety advice.",
            "schema_version": "aguayluz.outdoor-condition/v1",
        },
    }


def _build_aggregate(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    _write(agg, "entities.jsonl", [
        _outdoor("ent_out_sj", "San Juan", "72127", _coastal_components(), "ELEVATED",
                 [{"component": "rip_current", "level": "ELEVATED", "reason": "High rip current risk today"},
                  {"component": "heat", "level": "ELEVATED", "reason": "Heat index in the Danger band"}]),
        _outdoor("ent_out_ut", "Utuado", "72141", _inland_components(), "CAUTION",
                 [{"component": "river_flood", "level": "ELEVATED", "reason": "River gauge at minor flood stage"}]),
        # an aguayluz asset that is not an outdoor condition
        {"entity_id": "ent_water1", "entity_type": "utility_asset", "name": "Bomba Río",
         "_producers": ["aguayluz-pr"], "location": {"lat": 18.2, "lon": -66.2, "municipality": "Utuado"}},
    ])
    return agg


def test_outdoor_conditions_flatten_headline_values(tmp_path):
    agg = _build_aggregate(tmp_path)
    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)
    assert summary["collections"]["OutdoorConditions"] == 2
    row = _rows(db, "OutdoorConditions")["ent_out_sj"]
    assert row["municipality"] == "San Juan"
    assert row["level"] == "ELEVATED"
    assert row["driver_summary"] == "High rip current risk today; Heat index in the Danger band"
    assert row["rip_current_risk"] == "HIGH"
    assert row["surf_ft"] == "5–7"
    assert row["marine_alerts"] == "Small Craft Advisory"  # deduplicated across zones
    assert (row["buoy_station"], row["buoy_distance_km"]) == ("41053", 4.2)
    assert (row["wave_height_ft"], row["water_temp_f"], row["wind_speed_kt"]) == (6.2, 84.4, 14.0)
    assert (row["uv_index"], row["uv_category"]) == (11, "EXTREME")
    assert (row["heat_band"], row["heat_index_max_f"]) == ("DANGER", 106)
    assert row["beach_advisories"] == 2
    assert row["beach_advisory_names"] == "Escambrón; Ocean Park"
    assert row["rain_24h_max_in"] == 1.1
    assert row["nws_alerts"] == "Heat Advisory"
    assert row["quake_max_magnitude"] == 4.0
    assert row["latitude"] == 18.4
    # raw components and the producer's evidence state ride along for detail views
    assert row["components"]["sea_state"]["evidence_class"] == "PROXIMITY"
    assert row["evidence_state"]["epistemic_class"] == "COMPUTED"


def test_every_component_state_is_projected(tmp_path):
    rows = dict(project_outdoor_conditions(_build_aggregate(tmp_path)))
    for row in rows.values():
        for name in ("rip_current", "marine_alerts", "sea_state", "beach_water_quality", "uv", "heat",
                     "air_quality", "rainfall_24h", "river_flood", "nws_alerts", "tropical_cyclone",
                     "earthquakes", "access_closures"):
            assert row[f"{name}_state"], name


def test_missing_data_is_a_state_not_a_safe_value(tmp_path):
    rows = dict(project_outdoor_conditions(_build_aggregate(tmp_path)))
    sj, ut = rows["ent_out_sj"], rows["ent_out_ut"]
    # AirNow without its key: the state says so and no AQI value is invented
    assert sj["air_quality_state"] == "NOT_CONFIGURED"
    assert "aqi" not in sj and "aqi_category" not in sj
    # inland: no rip/surf/buoy values, only NOT_COVERED states
    assert ut["rip_current_state"] == "NOT_COVERED"
    assert not {"rip_current_risk", "surf_ft", "wave_height_ft", "water_temp_f"} & set(ut)
    # a failed source is FAILED, not "low UV"
    assert ut["uv_state"] == "SOURCE_FAILED"
    assert "uv_index" not in ut
    # a carried-forward value stays visible but its state is STALE
    assert (ut["heat_band"], ut["heat_state"]) == ("CAUTION", "STALE")
    assert ut["river_flood_category"] == "minor"
    assert ut["river_gauges_in_flood"] == 1
    assert (ut["closures"], ut["closure_assets"]) == (1, "El Portal")


def test_only_aguayluz_outdoor_conditions_are_projected(tmp_path):
    agg = _build_aggregate(tmp_path)
    entities = [json.loads(line) for line in (agg / "entities.jsonl").read_text().splitlines()]
    # another producer's like-typed entity must not appear in the AguaYLuz tab
    entities.append(_outdoor("ent_out_foreign", "Ponce", "72113", _coastal_components(), "CAUTION", [],
                             producers=("skywatcher-pr",)))
    _write(agg, "entities.jsonl", entities)
    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)
    rows = _rows(db, "OutdoorConditions")
    assert set(rows) == {"ent_out_sj", "ent_out_ut"}  # no foreign row, no utility asset


def test_no_entities_stream_projects_nothing(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    assert project_outdoor_conditions(agg) == []
    db = tmp_path / "hub.db"
    assert "OutdoorConditions" not in ingest_aggregate(agg, db)["collections"]

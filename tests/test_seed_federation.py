"""Contract tests for the federation control-plane seeding.

Two things are pinned here.

First, the *vocabularies*. Gates, Integrations and Manifest are backed by closed
`<select>` option lists in the frontend, so a seeded row carrying a value outside
them renders an unselectable record that an operator cannot edit without silently
changing it. The enums below are copied from the pages deliberately — if someone
widens a UI vocabulary, these tests should be what reminds them the seeder feeds it.

Second, the *lifespan*. `_seed_programs` and `_seed_federation` both run from the
FastAPI lifespan, and `TestClient(app)` without a context manager never runs it.
That is not hypothetical: an audit probe made exactly that mistake and recorded
zero rows for a collection that seeds correctly. `test_lifespan_is_what_seeds`
pins the difference so the trap is documented in executable form.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from server.backend.seed_federation import seed_federation_collections  # noqa: E402

# server/frontend/src/pages/Manifest.jsx:14-15
MODULE_ROLES = {"ParentControlPlane", "ChildModule", "SharedService"}
MANIFEST_STATUS = {"Draft", "Reviewing", "Stable", "Deprecated"}
# server/frontend/src/pages/Integrations.jsx:13-14
INTEGRATION_NAMES = {"Federation", "GitHub", "CSVExport", "GeoJSONExport",
                     "GoogleDrive", "ManualImport"}
INTEGRATION_STATUS = {"NotConnected", "Blocked", "Ready", "Connected", "Error"}
# server/frontend/src/pages/Gates.jsx:14 + src/lib/federation.js:81-92
GATE_STATUS = {"NotStarted", "InProgress", "Passed", "Failed", "Blocked"}
GATE_NAMES = {"SchemaValidation", "ManifestValidation", "ExportPackageValidation",
              "EvidenceStandards", "ProvenancePreservation", "SensitivityReview",
              "SyntheticDataSweep", "GitHubSyncApproval", "LiveExecutionReadiness",
              "ParityAudit"}

TS = "2026-01-01T00:00:00+00:00"


def _producer(program_id, **overrides):
    row = {
        "program_id": program_id,
        "declared_status": "ready_for_live",
        "checkout_present": True,
        "manifest_present": True, "manifest_valid": True,
        "package_present": True, "package_valid": True,
        "live_execution_ready": True,
        "blocker_class": "ready",
        "errors": [],
        "last_package_timestamp": None,
    }
    row.update(overrides)
    return row


def _snapshot(*producers):
    return {
        "hub": "thehub-pr",
        "schema_version": "hub_registry_v1",
        "generated_at": "2026-07-28T12:00:00+00:00",
        "producers": list(producers),
    }


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE entities (
            entity_type TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            data        TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (entity_type, entity_id)
        )
    """)
    yield c
    c.close()


def _seed(conn, tmp_path, snapshot=None, registry=None):
    status_path = tmp_path / "federation_status.json"
    registry_path = tmp_path / "producers.yaml"
    if snapshot is not None:
        status_path.write_text(json.dumps(snapshot))
    if registry is not None:
        registry_path.write_text(registry)
    return seed_federation_collections(
        conn, TS, status_path=status_path, registry_path=registry_path
    )


def _rows(conn, entity_type):
    return [json.loads(r["data"]) for r in conn.execute(
        "SELECT data FROM entities WHERE entity_type=? ORDER BY entity_id", (entity_type,)
    )]


# ── Shape and vocabulary ──────────────────────────────────────────────────────

def test_seeds_all_three_collections(conn, tmp_path):
    written = _seed(conn, tmp_path, _snapshot(_producer("a-pr"), _producer("b-pr")))

    # One manifest per producer plus the hub's own ParentControlPlane row.
    assert written["FederationManifest"] == 3
    # 2 producers x "Federation" row, plus the hub's own "GitHub" rollup row.
    assert written["IntegrationStatus"] == 3
    # 2 producers x 3 evidenced gates, plus the hub's GitHubSyncApproval rollup.
    assert written["ValidationGates"] == 7
    # The hub's own Programs row.
    assert written["Programs"] == 1


def test_rows_stay_inside_the_ui_vocabularies(conn, tmp_path):
    _seed(conn, tmp_path, _snapshot(
        _producer("ready-pr"),
        _producer("nopkg-pr", package_present=False, package_valid=False,
                  blocker_class="missing_export_package"),
        _producer("bad-pr", manifest_valid=False, blocker_class="invalid_manifest",
                  errors=["manifest fails schema"]),
        _producer("gone-pr", checkout_present=False, manifest_present=False,
                  manifest_valid=False, package_present=False, package_valid=False,
                  live_execution_ready=False, blocker_class="missing_checkout"),
    ))

    for row in _rows(conn, "FederationManifest"):
        assert row["module_role"] in MODULE_ROLES
        assert row["status"] in MANIFEST_STATUS
        assert row["schema_version"]

    for row in _rows(conn, "IntegrationStatus"):
        assert row["integration_name"] in INTEGRATION_NAMES
        assert row["status"] in INTEGRATION_STATUS

    for row in _rows(conn, "ValidationGates"):
        assert row["gate_name"] in GATE_NAMES
        assert row["status"] in GATE_STATUS
        assert row["requirement"].strip()


def test_blocking_is_a_real_boolean(conn, tmp_path):
    """Gates.jsx coerces the form's string back to a bool; Dashboard tests truthiness."""
    _seed(conn, tmp_path, _snapshot(_producer("a-pr")))
    for row in _rows(conn, "ValidationGates"):
        assert row["blocking"] is True


def test_child_rows_report_the_producer_manifest_contract(conn, tmp_path):
    """A child row describes federation.json, not the registry.

    The rollup's top-level schema_version is `hub_registry_v1`; copying it onto a
    child row would have that row claim its federation.json validated while
    reporting a version that file cannot legally carry.
    """
    _seed(conn, tmp_path, _snapshot(
        _producer("declared-pr", manifest_schema_version="repo_federation_manifest_v1"),
        _producer("legacy-pr"),   # snapshot predating the field
    ))
    by_program = {r["program_id"]: r for r in _rows(conn, "FederationManifest")}

    assert by_program["declared-pr"]["schema_version"] == "repo_federation_manifest_v1"
    assert by_program["legacy-pr"]["schema_version"] == "repo_federation_manifest_v1"
    # The hub is the one thing the registry does describe.
    assert by_program["thehub-pr"]["schema_version"] == "hub_registry_v1"


def test_child_schema_version_matches_the_repo_manifest_schema():
    """Pin the fallback to the schema's own `const`, so a bump cannot drift."""
    import json as _json
    from pathlib import Path as _Path

    from server.backend.seed_federation import _REPO_MANIFEST_SCHEMA

    schema = _json.loads(
        (_Path(__file__).resolve().parents[1]
         / "schemas" / "repo_federation_manifest.schema.json").read_text()
    )
    assert schema["properties"]["schema_version"]["const"] == _REPO_MANIFEST_SCHEMA


def test_exactly_one_parent_control_plane(conn, tmp_path):
    _seed(conn, tmp_path, _snapshot(_producer("a-pr"), _producer("b-pr")))
    roles = [r["module_role"] for r in _rows(conn, "FederationManifest")]
    assert roles.count("ParentControlPlane") == 1
    assert roles.count("ChildModule") == 2


# ── Gate status mapping ───────────────────────────────────────────────────────

@pytest.mark.parametrize("overrides,gate,expected", [
    ({}, "ManifestValidation", "Passed"),
    ({"manifest_valid": False}, "ManifestValidation", "Failed"),
    ({"manifest_present": False, "manifest_valid": False}, "ManifestValidation", "Blocked"),
    ({}, "ExportPackageValidation", "Passed"),
    ({"package_valid": False}, "ExportPackageValidation", "Failed"),
    ({"package_present": False, "package_valid": False}, "ExportPackageValidation", "Blocked"),
    ({}, "LiveExecutionReadiness", "Passed"),
    ({"live_execution_ready": False}, "LiveExecutionReadiness", "Blocked"),
])
def test_gate_status_mapping(conn, tmp_path, overrides, gate, expected):
    _seed(conn, tmp_path, _snapshot(_producer("a-pr", **overrides)))
    row = next(r for r in _rows(conn, "ValidationGates") if r["gate_name"] == gate)
    assert row["status"] == expected


def test_absent_checkout_is_not_started_rather_than_failed(conn, tmp_path):
    """Nothing was measured, so nothing failed — 'Failed' would be a false claim."""
    _seed(conn, tmp_path, _snapshot(_producer(
        "gone-pr", checkout_present=False, manifest_present=False, manifest_valid=False,
        package_present=False, package_valid=False, live_execution_ready=False,
        blocker_class="missing_checkout",
    )))
    assert {r["status"] for r in _rows(conn, "ValidationGates")} == {"NotStarted"}


# ── Hub-level GitHubSyncApproval rollup ──────────────────────────────────────

def _hub_gate(conn):
    return next(
        r for r in _rows(conn, "ValidationGates")
        if r["gate_name"] == "GitHubSyncApproval"
    )


def _hub_integration(conn):
    return next(
        r for r in _rows(conn, "IntegrationStatus")
        if r["integration_name"] == "GitHub"
    )


def _hub_program(conn):
    return next(r for r in _rows(conn, "Programs") if r["program_id"] == "prog-control")


def test_sync_approval_passes_when_every_producer_passes(conn, tmp_path):
    _seed(conn, tmp_path, _snapshot(_producer("a-pr"), _producer("b-pr")))

    gate = _hub_gate(conn)
    assert gate["program_id"] == "prog-control"
    assert gate["status"] == "Passed"
    assert gate["blocking"] is True

    integration = _hub_integration(conn)
    assert integration["program_id"] == "prog-control"
    assert integration["status"] == "Connected"
    assert integration["blocking_reason"] == ""

    program = _hub_program(conn)
    assert program["parity_status"] == "Ready"
    assert program["transition_status"] == "Complete"
    assert program["github_sync_status"] == "Connected"
    assert program["source_repo"] == "thehub-pr"


def test_sync_approval_blocks_on_any_producer_gap(conn, tmp_path):
    _seed(conn, tmp_path, _snapshot(
        _producer("a-pr"),
        _producer("b-pr", package_present=False, package_valid=False,
                   blocker_class="missing_export_package"),
    ))

    gate = _hub_gate(conn)
    assert gate["status"] == "Blocked"
    assert "b-pr" in gate["review_notes"]
    assert "a-pr" not in gate["review_notes"]

    integration = _hub_integration(conn)
    assert integration["status"] == "Blocked"
    assert integration["blocking_reason"] == gate["review_notes"]

    program = _hub_program(conn)
    assert program["parity_status"] == "Blocked"
    assert program["transition_status"] == "InProgress"


def test_sync_approval_fails_on_any_producer_failure(conn, tmp_path):
    """A measured failure (invalid manifest) outranks a mere block."""
    _seed(conn, tmp_path, _snapshot(
        _producer("a-pr", package_present=False, package_valid=False,
                   blocker_class="missing_export_package"),
        _producer("b-pr", manifest_valid=False, blocker_class="invalid_manifest"),
    ))

    assert _hub_gate(conn)["status"] == "Failed"
    assert _hub_integration(conn)["status"] == "Error"
    assert _hub_program(conn)["github_sync_status"] == "Error"


def test_sync_approval_not_started_when_nothing_measured(conn, tmp_path):
    """All producers unmeasured (no checkout) rolls up to NotStarted, not Blocked."""
    _seed(conn, tmp_path, _snapshot(_producer(
        "gone-pr", checkout_present=False, manifest_present=False, manifest_valid=False,
        package_present=False, package_valid=False, live_execution_ready=False,
        blocker_class="missing_checkout",
    )))
    assert _hub_gate(conn)["status"] == "NotStarted"


def test_hub_program_seeds_once_and_survives_a_restart(conn, tmp_path):
    snapshot = _snapshot(_producer("a-pr"))
    first = _seed(conn, tmp_path, snapshot)
    assert first["Programs"] == 1

    edited = _hub_program(conn)
    edited["description"] = "reviewed by hand"
    conn.execute("UPDATE entities SET data=? WHERE entity_type='Programs' AND entity_id='prog-control'",
                 (json.dumps(edited), ))
    conn.commit()

    second = _seed(conn, tmp_path, snapshot)     # a second boot
    assert "Programs" not in second
    assert _hub_program(conn)["description"] == "reviewed by hand"


def test_no_hub_rollup_rows_in_registry_only_mode(conn, tmp_path):
    """No snapshot means no evidence — the rollup gate/integration stay absent
    entirely rather than asserting a status nothing measured."""
    _seed(conn, tmp_path, snapshot=None, registry=REGISTRY)

    assert _rows(conn, "ValidationGates") == []
    assert all(r["integration_name"] != "GitHub" for r in _rows(conn, "IntegrationStatus"))

    program = _hub_program(conn)
    assert program["parity_status"] == "Unmeasured"
    assert program["transition_status"] == "Unmeasured"


# ── Registry-only fallback ────────────────────────────────────────────────────

REGISTRY = """
schema_version: hub_registry_v1
hub: thehub-pr
producers:
  - program_id: live-pr
    repo: o/live-pr
    role: r
    status: ready_for_live
  - program_id: disco-pr
    repo: o/disco-pr
    role: r
    status: ready_for_discovery
"""


def test_registry_fallback_seeds_topology_but_no_gates(conn, tmp_path):
    written = _seed(conn, tmp_path, snapshot=None, registry=REGISTRY)

    assert written["FederationManifest"] == 3       # 2 producers + hub
    assert written["IntegrationStatus"] == 2
    # No snapshot means no evidence about manifests or packages. An empty
    # ValidationGates is the honest answer, not a gap to fill with NotStarted.
    assert "ValidationGates" not in written
    assert _rows(conn, "ValidationGates") == []


def test_registry_fallback_says_ready_not_connected(conn, tmp_path):
    """The registry records a producer's *declaration*, not an observed connection."""
    _seed(conn, tmp_path, snapshot=None, registry=REGISTRY)
    by_program = {r["program_id"]: r for r in _rows(conn, "IntegrationStatus")}
    assert by_program["live-pr"]["status"] == "Ready"
    assert by_program["disco-pr"]["status"] == "Blocked"


def test_no_snapshot_and_no_registry_seeds_nothing(conn, tmp_path):
    assert _seed(conn, tmp_path, snapshot=None, registry=None) == {}
    assert _rows(conn, "FederationManifest") == []


def test_unreadable_snapshot_falls_back_to_registry(conn, tmp_path):
    (tmp_path / "federation_status.json").write_text("{not json")
    (tmp_path / "producers.yaml").write_text(REGISTRY)
    written = seed_federation_collections(
        conn, TS,
        status_path=tmp_path / "federation_status.json",
        registry_path=tmp_path / "producers.yaml",
    )
    assert written["FederationManifest"] == 3
    assert "ValidationGates" not in written


# ── Seed-once semantics ───────────────────────────────────────────────────────

def test_seeding_twice_does_not_duplicate(conn, tmp_path):
    snapshot = _snapshot(_producer("a-pr"))
    _seed(conn, tmp_path, snapshot)
    before = len(_rows(conn, "ValidationGates"))
    assert _seed(conn, tmp_path, snapshot) == {}
    assert len(_rows(conn, "ValidationGates")) == before


def test_operator_edits_survive_a_restart(conn, tmp_path):
    """These collections are operator-editable; re-seeding must not clobber them."""
    snapshot = _snapshot(_producer("a-pr"))
    _seed(conn, tmp_path, snapshot)

    edited = _rows(conn, "ValidationGates")[0]
    edited["review_notes"] = "checked by hand"
    conn.execute("UPDATE entities SET data=? WHERE entity_type='ValidationGates' AND entity_id=?",
                 (json.dumps(edited), edited["id"]))
    conn.commit()

    _seed(conn, tmp_path, snapshot)     # a second boot

    kept = next(r for r in _rows(conn, "ValidationGates") if r["id"] == edited["id"])
    assert kept["review_notes"] == "checked by hand"


# ── The lifespan trap ─────────────────────────────────────────────────────────

def test_lifespan_is_what_seeds(tmp_path, monkeypatch):
    """Seeding happens in the FastAPI lifespan, which only a context manager runs.

    A probe that builds `TestClient(app)` bare sees empty collections and can
    mistake that for "the seed path is broken". It isn't — the lifespan simply
    never ran.
    """
    from fastapi.testclient import TestClient

    from server.backend import main

    monkeypatch.setattr(main, "DB_PATH", tmp_path / "hub.db")

    with TestClient(main.app) as client:
        # 6 producers plus the hub's own "prog-control" row.
        assert len(client.get("/api/entities/Programs").json()) == 7
        assert len(client.get("/api/entities/FederationManifest").json()) == 7

    bare = TestClient(main.app)          # never enters the lifespan
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "unseeded.db")
    main._init_db()
    assert bare.get("/api/entities/Programs").json() == []

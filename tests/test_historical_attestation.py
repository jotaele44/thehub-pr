import pytest

from src.hub.historical_attestation import (
    LineageError,
    adjudicate_lineage,
    ingest_observation,
)


def row(mid, **kw):
    base = {
        "schema_version": "federation_temporal_ci_attestation_v1",
        "program_id": "aguayluz",
        "manifestation_id": mid,
        "environment": "CI",
        "valid_at": "2026-09-06T00:00:00Z",
        "execution_state": "EXECUTED",
        "test_state": "PASS",
        "evidence_binding_state": "UNRESOLVED",
    }
    base.update(kw)
    return base


def test_unbound_historical_observation_stays_unresolved():
    assert ingest_observation(row("a"))["evidence_binding_state"] == "UNRESOLVED"


def test_complete_reciprocal_dag_passes():
    a = row("a", superseded_by=["b"])
    b = row("b", supersedes=["a"], valid_at="2026-09-08T00:00:00Z")
    result = adjudicate_lineage([a, b])
    assert result["status"] == "PASS"
    assert result["edge_count"] == 1


def test_orphan_edge_fails_open():
    result = adjudicate_lineage([row("b", supersedes=["missing"])])
    assert result["status"] == "OPEN"
    assert result["orphan_edges"] == [("missing", "b")]


def test_one_sided_supersession_fails_open():
    result = adjudicate_lineage(
        [row("a"), row("b", supersedes=["a"], valid_at="2026-09-08T00:00:00Z")]
    )
    assert result["status"] == "OPEN"
    assert result["reciprocal_mismatches"] == [("a", "b")]


def test_cycle_fails_open():
    a = row("a", supersedes=["b"], superseded_by=["b"])
    b = row("b", supersedes=["a"], superseded_by=["a"])
    result = adjudicate_lineage([a, b])
    assert result["status"] == "OPEN"
    assert result["cycle_nodes"] == ["a", "b"]


def test_same_dimension_conflicting_states_collide():
    a = row("a")
    b = row("b", execution_state="NONEXECUTED", test_state="NOT_RUN")
    result = adjudicate_lineage([a, b])
    assert result["status"] == "OPEN"
    assert len(result["state_collisions"]) == 1


def test_different_environment_does_not_collide():
    a = row("a", environment="DEVELOPMENT", deployment_state="BLOCKED")
    b = row("b", environment="PRODUCTION", deployment_state="OPEN")
    assert adjudicate_lineage([a, b])["state_collisions"] == []


def test_duplicate_manifestation_fails_closed():
    with pytest.raises(LineageError, match="duplicate_manifestation_id"):
        adjudicate_lineage([row("a"), row("a")])

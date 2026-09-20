import json
from pathlib import Path
from src.hub.historical_attestation import adjudicate_lineage

PATH = Path("registry/historical_certification_observations.v1.json")

def test_historical_certification_observation_corpus_is_bounded_and_adjudicable():
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    rows = payload["observations"]
    assert len(rows) == 18
    assert all(row["evidence_binding_state"] == "UNRESOLVED" for row in rows)
    result = adjudicate_lineage(rows)
    assert result["record_count"] == 18
    assert result["cycle_nodes"] == []
    assert result["state_collisions"] == []
    assert result["status"] == "OPEN"
    assert result["orphan_edges"]

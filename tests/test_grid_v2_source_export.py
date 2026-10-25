"""Hub-side certification of the shared exact-observation V2 source exporter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "federation-templates/spatial/export_pr_grid_v2_exact_observations.py"
SPEC = importlib.util.spec_from_file_location("grid_v2_source_export", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _row(observation_id: str, *, exact: bool = True, synthetic: bool = False):
    attributes = {}
    if exact:
        attributes["grid_v2_coordinate_evidence_state"] = mod.EVIDENCE_STATE
    return {
        "observation_id": observation_id,
        "source_id": "src_" + "1" * 32,
        "observation_type": "aircraft_transit",
        "observed_at": "2026-10-20T12:00:00Z",
        "location": {"lat": 18.35, "lon": -66.0},
        "attributes": attributes,
        "confidence": 1.0,
        "lineage": {
            "producer_script": "fixture",
            "producer_phase": "test",
            "source_inputs": ["fixture"],
        },
        "synthetic": synthetic,
        "created_at": "2026-10-20T12:00:00Z",
        "extracted_at": "2026-10-20T12:00:00Z",
    }


def test_exporter_never_infers_exactness_from_lat_lon():
    rows = [
        _row("obs_" + "a" * 32),
        _row("obs_" + "b" * 32, exact=False),
        _row("obs_" + "c" * 32, synthetic=True),
    ]
    sources, records, excluded = mod.project_observations(
        rows,
        repository="skywatcher-pr",
    )
    assert len(sources) == len(records) == 1
    assert sources[0]["Source_CRS"] == "EPSG:4326"
    assert sources[0]["Coordinate_Evidence_State"] == "VERIFIED_SOURCE_COORDINATE"
    assert sources[0]["Uncertainty_Class"] == "EXACT"
    assert excluded == {"NO_EXACT_EVIDENCE": 1, "SYNTHETIC": 1}


def test_exporter_rejects_invalid_wgs84():
    row = _row("obs_" + "d" * 32)
    row["location"]["lat"] = 100.0
    with pytest.raises(mod.SourceExportError, match="out-of-range"):
        mod.project_observations([row], repository="ovnis-pr")

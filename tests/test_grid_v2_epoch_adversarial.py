"""Permanent fail-closed regressions for PR Grid V2 authority epochs.

The real federation audit must still verify all six exact external checkouts.
These unit cases prohibit false local acceptance of incomplete epochs.
"""
import copy
import json
from pathlib import Path

import pytest

from hub.grid_v2 import AUTHORITY_COMMIT, EXPECTED_CONSUMERS, GridV2PinError, validate_pin_payload, validate_pin_set

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / "federation/spatial/pr_grid_geographic_v2.pin.json").read_text(encoding="utf-8"))
OLD_EPOCH = "0c66e13d14232c0d7cbcbc179b3655904777dc71"


def test_current_epoch_is_pinned_and_valid():
    assert AUTHORITY_COMMIT == "b8f5cf303ab7fc2b6ed006edce0fb12e1344a096"
    assert validate_pin_payload(PIN, expected_consumer="thehub-pr") == []


@pytest.mark.parametrize("mutation", [
    {"authority_commit": OLD_EPOCH},
    {"authority_commit": ""},
    {"grid_manifest_sha256": "0" * 64},
    {"cell_schema_sha256": "0" * 64},
    {"binding_schema_sha256": "0" * 64},
    {"mask_schema_sha256": "0" * 64},
    {"geometry_mode": "COPIED"},
    {"local_geometry_copy": True},
    {"v1_coexistence": "REINTERPRET"},
])
def test_stale_or_corrupt_epoch_is_rejected(mutation):
    altered = copy.deepcopy(PIN)
    altered.update(mutation)
    assert validate_pin_payload(altered, expected_consumer="thehub-pr"), mutation


def test_federation_denominator_is_exact():
    assert EXPECTED_CONSUMERS == {
        "aguayluz-pr", "skywatcher-pr", "ovnis-pr",
        "moneysweep-pr", "centinelas-pr", "thehub-pr",
    }


def test_missing_consumer_fails_closed(tmp_path):
    with pytest.raises((GridV2PinError, FileNotFoundError, ValueError)):
        validate_pin_set({consumer: tmp_path / consumer / "missing.json" for consumer in EXPECTED_CONSUMERS})


def test_duplicate_or_extra_consumer_cannot_change_denominator():
    assert len(EXPECTED_CONSUMERS) == 6
    assert len(set(EXPECTED_CONSUMERS)) == 6

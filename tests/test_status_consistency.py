"""Status-consistency gate.

The producer registry (`registry/producers.yaml`), the `docs/FEDERATION_STATUS.md`
node table, and — when producer checkouts are available — each producer's
`federation.json` must agree on live-execution readiness.

This catches the drift class where the status doc still shows a producer as
live-exec ⛔ / "placeholder" while its manifest already declares
`ready_for_hub_live_execution=true` (as happened for OVNIS on 2026-07-02, when
the registry + status doc lagged the producer manifest and its 470-case ledger).

Invariant: a registry entry has `status: ready_for_live` **iff** that producer's
`federation.json` declares `ready_for_hub_live_execution: true`, and the status
doc's "Live exec" column agrees.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from hub.registry import load_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "registry" / "producers.yaml"
STATUS_DOC = REPO_ROOT / "docs" / "FEDERATION_STATUS.md"

LIVE_STATUS = "ready_for_live"


def _registry_expected_live() -> dict[str, bool]:
    """Map each registered producer to its registry-declared live-exec state."""
    reg = load_registry(REGISTRY)
    return {p.program_id: (p.status == LIVE_STATUS) for p in reg.producers}


def _parse_status_doc_live() -> dict[str, bool]:
    """Return {program_id: live_exec_bool} from the FEDERATION_STATUS node table.

    Columns are: Node | Role | Discovery | Live exec | location | Notes, so the
    Live-exec cell is index 3 once the leading/trailing pipes are stripped.
    """
    live: dict[str, bool] = {}
    for raw in STATUS_DOC.read_text().splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        match = re.search(r"`([a-z0-9-]+)`", cells[0])
        if not match:
            continue
        pid = match.group(1)
        live_cell = cells[3]
        if "✅" in live_cell:
            live[pid] = True
        elif "⛔" in live_cell:
            live[pid] = False
    return live


def test_registry_and_status_doc_agree_on_live_exec():
    expected = _registry_expected_live()
    doc_live = _parse_status_doc_live()
    for pid, exp in expected.items():
        assert pid in doc_live, f"{pid} missing from FEDERATION_STATUS.md node table"
        assert doc_live[pid] == exp, (
            f"{pid}: registry status implies live_exec={exp} but "
            f"FEDERATION_STATUS.md shows live_exec={doc_live[pid]}"
        )


def test_every_registry_producer_is_documented():
    expected = _registry_expected_live()
    documented = set(_parse_status_doc_live())
    for pid in expected:
        assert pid in documented, f"{pid} not present in FEDERATION_STATUS.md node table"


def test_manifest_live_flag_matches_registry():
    """Cross-check registry status against each producer's own federation.json.

    Producer checkouts are expected under a shared parent directory (or
    HUB_WORKSPACE_ROOT). In CI, where only thehub-pr is checked out, no sibling
    manifests exist and the check is skipped.
    """
    expected = _registry_expected_live()
    reg = load_registry(REGISTRY)
    root = Path(os.environ.get("HUB_WORKSPACE_ROOT", REPO_ROOT.parent))

    checked = 0
    for producer in reg.producers:
        manifest_path = root / producer.repo_name / producer.federation_manifest
        if not manifest_path.exists():
            continue
        data = json.loads(manifest_path.read_text())
        gate = data.get("federation_readiness_gate", {})
        live = bool(gate.get("ready_for_hub_live_execution", False))
        assert live == expected[producer.program_id], (
            f"{producer.program_id}: manifest ready_for_hub_live_execution={live} "
            f"but registry status={'ready_for_live' if expected[producer.program_id] else 'not-live'}"
        )
        checked += 1

    if checked == 0:
        pytest.skip("no producer checkouts available for manifest cross-check")

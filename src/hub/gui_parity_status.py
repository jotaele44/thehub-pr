"""GUI-capability-parity rollup for producer workspaces.

Companion to federation_status.py, and built for the same reason: the
federation's road-to-100 scorecard carries a self-scored ``gui_completeness``
dimension per repo, and a 2026-08-20 reassessment found three of six
producers have no automated GUI-capability-parity gate on ``main`` at all —
a fact the self-scored numbers never surfaced. This module turns "does this
producer actually enforce GUI reachability, and what does it currently find"
into a real, derived rollup instead of a subjective score.

Like federation_status.py, this module is intentionally filesystem-*and*
subprocess-local in spirit — it does not itself spawn a producer's checker.
The caller (scripts/build_gui_parity_status.py) runs each producer's own
``scripts/check_gui_parity.py`` and hands the resulting report dict in here;
this module only classifies and aggregates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProducerGuiParity:
    program_id: str
    repo: str
    local_path: str
    checkout_present: bool
    gui_manifest_present: bool
    gui_checker_present: bool
    staged_capability_count: int
    mode: Optional[str]
    current: Optional[int]
    mapped: Optional[int]
    legacy: Optional[int]
    new: Optional[int]
    manifest_issues: Optional[int]
    passed: Optional[bool]
    run_error: Optional[str]
    blocker_class: str


def classify(
    *,
    checkout_present: bool,
    gui_manifest_present: bool,
    gui_checker_present: bool,
    run_error: Optional[str],
    passed: Optional[bool],
    new: Optional[int],
    manifest_issues: Optional[int],
    staged_capability_count: int,
) -> str:
    """Bucket one producer's GUI-parity state.

    Mirrors federation_status._blocker_class's shape (most-specific blocker
    wins), but the vocabulary is different: "gate present but never run" and
    "gate absent" are distinct failure modes here, and a passing gate that is
    still leaning on a staged exemption is called out rather than folded into
    a bare "clean".
    """
    if not checkout_present:
        return "missing_checkout"
    if not gui_manifest_present and not gui_checker_present:
        return "no_gui_parity_gate"
    if gui_manifest_present != gui_checker_present:
        return "partial_gui_parity_gate"
    if run_error:
        return "gate_run_failed"
    if passed is False or (new or 0) > 0 or (manifest_issues or 0) > 0:
        return "gui_parity_gaps"
    if staged_capability_count > 0:
        return "clean_with_staged_debt"
    return "clean"


def summarize(producers: List[ProducerGuiParity]) -> Dict[str, Any]:
    by_blocker: Dict[str, int] = {}
    for producer in producers:
        by_blocker[producer.blocker_class] = (
            by_blocker.get(producer.blocker_class, 0) + 1
        )
    return {
        "producer_count": len(producers),
        "clean_count": by_blocker.get("clean", 0),
        "by_blocker": by_blocker,
        "producers": [asdict(producer) for producer in producers],
    }

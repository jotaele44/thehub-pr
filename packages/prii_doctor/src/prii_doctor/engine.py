"""Runs every check declared in a repo's ``.federation/doctor-checks.json``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .manifest import load as load_manifest
from .runners import RUNNERS
from .types import CheckReport, CheckResult, DiagnosabilityClass

logger = logging.getLogger(__name__)

# Used only when a runner crashes (raises) instead of returning a result --
# never for a normal outcome. Chosen so the fallback result is always legal
# for its class (see types.status_allowed): FAIL for a class that can speak
# authoritatively, WARN for a class whose signal is inherently ambiguous,
# INFO for a class that never computes anything.
_CRASH_FALLBACK_STATUS: dict[DiagnosabilityClass, str] = {
    DiagnosabilityClass.LOCAL_DETERMINISTIC: "FAIL",
    DiagnosabilityClass.PRESENCE_ONLY: "WARN",
    DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT: "WARN",
    DiagnosabilityClass.NOT_AUTOMATABLE: "INFO",
}


def run(
    repo_root: Path,
    federation_json_path: Path | None = None,
    manifest_path: Path | None = None,
) -> CheckReport:
    """Run every check in ``repo_root/.federation/doctor-checks.json``.

    Never raises for the ordinary "nothing declared yet" state -- a missing
    manifest returns an empty report, matching the federation's established
    "WARN/SKIP, never fake-PASS" posture for a check that cannot run (see
    spiderweb-pr's ``tools/pr_geodata_integrity_audit.py``). A malformed
    manifest raises ``ManifestError`` so the caller decides how loudly to
    surface it -- the CLI turns this into a table row; the desktop GUI
    integration in ``prii_desktop.setup_center`` swallows it into a single
    logged warning so an unrelated producer without a doctor manifest yet
    never regresses its existing diagnostics screen.
    """
    repo_root = Path(repo_root)
    manifest_path = manifest_path or (repo_root / ".federation" / "doctor-checks.json")
    federation_json_path = federation_json_path or (repo_root / "federation.json")

    if not manifest_path.exists():
        return CheckReport(results=[])

    manifest = load_manifest(manifest_path)

    try:
        federation_json = json.loads(federation_json_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("doctor: could not read %s: %s", federation_json_path, exc)
        federation_json = {}

    # A delegate_subprocess check may omit its own entrypoint_key and fall
    # back to the manifest's top-level validation_entrypoint.
    if manifest.validation_entrypoint:
        for spec in manifest.checks:
            if spec.check.get("type") == "delegate_subprocess" and "entrypoint_key" not in spec.check:
                spec.check = {**spec.check, "entrypoint_key": manifest.validation_entrypoint}

    results: list[CheckResult] = []
    for spec in manifest.checks:
        check_type = spec.check.get("type", "manual")
        runner = RUNNERS.get(check_type)
        if runner is None:
            results.append(
                CheckResult(
                    spec.id,
                    DiagnosabilityClass.NOT_AUTOMATABLE,
                    "INFO",
                    f"Unknown check type {check_type!r} -- not automatable from here.",
                    spec.operator_action,
                )
            )
            continue
        try:
            result = runner(spec, repo_root, federation_json)
        except Exception as exc:  # noqa: BLE001 - a runner crash must never look like a silent PASS
            logger.exception("doctor: check %s (%s) raised", spec.id, check_type)
            fallback_class = spec.diagnosability_class
            fallback_status = _CRASH_FALLBACK_STATUS[fallback_class]
            result = CheckResult(
                spec.id,
                fallback_class,
                fallback_status,
                f"Check crashed: {exc.__class__.__name__}: {exc}",
                spec.operator_action,
            )
        else:
            if result.diagnosability_class != spec.diagnosability_class:
                logger.warning(
                    "doctor: check %s declared diagnosability_class=%s but its runner "
                    "produced %s; using the runner's class (defense-in-depth) -- fix the "
                    "manifest to match.",
                    spec.id,
                    spec.diagnosability_class.value,
                    result.diagnosability_class.value,
                )
        results.append(result)
    return CheckReport(results=results)

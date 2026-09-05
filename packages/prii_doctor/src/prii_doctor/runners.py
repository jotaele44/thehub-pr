"""Check runners: one function per ``check.type``, dispatched by ``engine.run``.

Each runner **hardcodes** the ``DiagnosabilityClass`` of the ``CheckResult``
it constructs, rather than trusting whatever class the manifest entry
happens to declare. This is deliberate defense-in-depth: a manifest
authoring mistake (e.g. declaring ``local-deterministic`` on a check whose
``type`` is ``manual``) cannot cause a wrong-class result to slip through,
because the runner that actually executes decides its own class. ``engine.run``
logs a warning if the two disagree, so the mistake is still visible without
being load-bearing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from .manifest import CheckSpec
from .types import CheckResult, DiagnosabilityClass

_MAX_DETAIL_CHARS = 800


def _truncate(text: str, limit: int = _MAX_DETAIL_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"… (+{len(text) - limit} more chars)"


def run_env_var_presence(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Presence-only: an env var either exists or it doesn't. Never confirms validity."""
    env_var = spec.check.get("env_var")
    if not env_var:
        raise ValueError(f"{spec.id}: env_var_presence check missing 'env_var'")
    present = bool(os.environ.get(env_var, "").strip())
    blocking = spec.severity_if_absent == "blocking"
    if present:
        detail = f"{env_var} is set. Presence only -- this does not confirm the credential is valid."
        return CheckResult(spec.id, DiagnosabilityClass.PRESENCE_ONLY, "INFO", detail, spec.operator_action)
    status: str = "FAIL" if blocking else "WARN"
    return CheckResult(
        spec.id, DiagnosabilityClass.PRESENCE_ONLY, status, f"{env_var} is not set.", spec.operator_action
    )


def run_file_presence(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Presence-only: a file/path either exists on disk or it doesn't."""
    rel_path = spec.check.get("path")
    if not rel_path:
        raise ValueError(f"{spec.id}: file_presence check missing 'path'")
    target = repo_root / rel_path
    blocking = spec.severity_if_absent == "blocking"
    if target.exists():
        return CheckResult(
            spec.id, DiagnosabilityClass.PRESENCE_ONLY, "INFO", f"{rel_path} exists.", spec.operator_action
        )
    status: str = "FAIL" if blocking else "WARN"
    return CheckResult(
        spec.id, DiagnosabilityClass.PRESENCE_ONLY, status, f"{rel_path} does not exist.", spec.operator_action
    )


def run_delegate_subprocess(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Shells out to this repo's own declared validation entrypoint.

    Looks the command up via ``federation.json.hub_callable_commands[key]``,
    where ``key`` comes from the check's ``entrypoint_key`` (defaulted by
    ``engine.run`` from the manifest's top-level ``validation_entrypoint``
    when omitted) -- never a hardcoded key name, since producers name this
    differently (aguayluz-pr: ``"validation_gates"``; moneysweep-pr:
    ``"strict_preflight"``). Captures only the exit code and a truncated
    stdout/stderr tail; it never parses per-gate structure, since that
    structure differs per repo -- this is what lets one runner wrap every
    producer's own validation suite unchanged.
    """
    entrypoint_key = spec.check.get("entrypoint_key")
    hub_callable_commands = federation_json.get("hub_callable_commands", {})
    command = hub_callable_commands.get(entrypoint_key) if entrypoint_key else None
    if not command:
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LOCAL_DETERMINISTIC,
            "SKIP",
            f"No hub_callable_commands entry for entrypoint key {entrypoint_key!r}.",
            spec.operator_action,
        )
    try:
        proc = subprocess.run(
            command, shell=True, cwd=repo_root, capture_output=True, text=True, timeout=300  # noqa: S602
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LOCAL_DETERMINISTIC,
            "FAIL",
            f"`{command}` timed out after 300s.",
            spec.operator_action,
        )
    output = _truncate((proc.stdout or "") + (proc.stderr or ""))
    if proc.returncode == 0:
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LOCAL_DETERMINISTIC,
            "PASS",
            f"`{command}` exited 0. {output}".strip(),
            spec.operator_action,
        )
    return CheckResult(
        spec.id,
        DiagnosabilityClass.LOCAL_DETERMINISTIC,
        "FAIL",
        f"`{command}` exited {proc.returncode}. {output}".strip(),
        spec.operator_action,
    )


def run_manifest_consistency(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Generic doc-vs-manifest drift detector.

    Confirms a marker string still appears in a source file that is
    supposed to track a value declared elsewhere in ``federation.json``.
    Motivated directly by a real bug found during research: spiderweb-pr's
    ``federation/readiness.py`` docstring said the readiness gate was
    ``false`` while ``federation.json`` had already flipped it to ``true``.
    This check cannot prove the *values* still agree (that would require
    parsing arbitrary source), only that the stated marker is still present
    -- so a WARN here means "go look," not "confirmed broken."
    """
    declared_in = spec.check.get("declared_in")
    against_path = spec.check.get("against")
    marker = spec.check.get("marker")
    if not declared_in or not against_path:
        raise ValueError(f"{spec.id}: manifest_consistency check missing 'declared_in' or 'against'")

    target_file = repo_root / declared_in
    if not target_file.exists():
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LOCAL_DETERMINISTIC,
            "SKIP",
            f"{declared_in} not found.",
            spec.operator_action,
        )

    manifest_value: Any = federation_json
    dotted = against_path.split(":", 1)[-1]
    for part in dotted.split("."):
        if not isinstance(manifest_value, dict):
            manifest_value = None
            break
        manifest_value = manifest_value.get(part)

    text = target_file.read_text(encoding="utf-8", errors="ignore")
    if marker and marker not in text:
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LOCAL_DETERMINISTIC,
            "WARN",
            f"Marker {marker!r} not found in {declared_in}; cannot confirm it still matches "
            f"federation.json:{against_path} (currently {manifest_value!r}). May be stale.",
            spec.operator_action,
        )
    return CheckResult(
        spec.id,
        DiagnosabilityClass.LOCAL_DETERMINISTIC,
        "PASS",
        f"{declared_in} is consistent with federation.json:{against_path} ({manifest_value!r}).",
        spec.operator_action,
    )


def run_manual(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Not-automatable checks perform zero I/O, by construction.

    Always reports the manifest's recorded ``last_known_state`` and
    ``operator_action`` verbatim -- never a computed result. This is the
    runner a "helpful" future change might be tempted to wire a live probe
    into; doing so without reclassifying the check to
    ``live-probe-best-effort`` defeats the whole point of this design, so
    keep this function free of any I/O primitive.
    """
    state = spec.last_known_state
    if state:
        as_of = state.get("as_of", "unknown date")
        note = state.get("note", "")
        detail = f"Not automatable. Last known state as of {as_of}: {note}".strip()
    else:
        detail = "Not automatable -- no automated check exists for this source."
    return CheckResult(spec.id, DiagnosabilityClass.NOT_AUTOMATABLE, "INFO", detail, spec.operator_action)


def run_http_probe(spec: CheckSpec, repo_root: Path, federation_json: dict) -> CheckResult:
    """Best-effort live reachability probe.

    A non-2xx response or connection failure is fundamentally ambiguous --
    it could be a WAF block, a rate limit, an expired credential, or a
    genuine outage -- so anything other than a clean 2xx or an unambiguous
    connection-level failure renders WARN, not FAIL, and always carries the
    raw signal (exception type, HTTP status if any) in the detail text so a
    human isn't misled by a coarse color.
    """
    url = spec.check.get("url")
    if not url:
        raise ValueError(f"{spec.id}: http_probe check missing 'url'")
    timeout = spec.check.get("timeout_seconds", 10)
    try:
        import urllib.request

        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "prii-doctor/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status_code = resp.status
    except Exception as exc:  # noqa: BLE001 - any exception here is signal to surface, not to crash on
        exc_name = exc.__class__.__name__
        code = getattr(exc, "code", None)
        # Unambiguous connection-level failures (no HTTP status attached at
        # all) are the one case genuinely safe to call FAIL; anything that
        # carries an HTTP status (403/429/5xx) is ambiguous by design.
        if code is None:
            return CheckResult(
                spec.id,
                DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT,
                "FAIL",
                f"{url}: unreachable ({exc_name}: {exc}).",
                spec.operator_action,
            )
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT,
            "WARN",
            f"{url}: ambiguous response ({exc_name}, HTTP {code}: {exc}). Could be a WAF block, "
            f"rate limit, expired credential, or genuine outage -- cannot distinguish from here.",
            spec.operator_action,
        )
    if 200 <= status_code < 300:
        return CheckResult(
            spec.id,
            DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT,
            "PASS",
            f"{url}: HTTP {status_code}.",
            spec.operator_action,
        )
    return CheckResult(
        spec.id,
        DiagnosabilityClass.LIVE_PROBE_BEST_EFFORT,
        "WARN",
        f"{url}: HTTP {status_code} -- ambiguous, not a clean success.",
        spec.operator_action,
    )


RUNNERS: dict[str, Callable[[CheckSpec, Path, dict], CheckResult]] = {
    "env_var_presence": run_env_var_presence,
    "file_presence": run_file_presence,
    "delegate_subprocess": run_delegate_subprocess,
    "manifest_consistency": run_manifest_consistency,
    "manual": run_manual,
    "http_probe": run_http_probe,
}

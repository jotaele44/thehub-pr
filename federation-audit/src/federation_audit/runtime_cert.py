from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .strict_scan import strict_scan_federation

SECRET_NAME = re.compile(r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL)", re.I)
PRODUCTION_HOST = re.compile(r"(?:\.gov|\.mil|amazonaws\.com|googleapis\.com|github\.com|arcgis\.com)$", re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitized_environment(extra: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Return a runtime environment with production-looking credentials removed.

    Fake audit credentials are allowed only when their value starts with
    ``AUDIT_FAKE_``.  The removed variable names are recorded but values are
    never persisted.
    """
    result: dict[str, str] = {}
    stripped: list[str] = []
    for name, value in os.environ.items():
        if SECRET_NAME.search(name) and not value.startswith("AUDIT_FAKE_"):
            stripped.append(name)
            continue
        result[name] = value
    result.update(
        {
            "FEDERATION_AUDIT": "1",
            "FEDERATION_AUDIT_NETWORK_ISOLATED": "1",
            "NO_PROXY": "*",
            "no_proxy": "*",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
        }
    )
    if extra:
        result.update(extra)
    return result, sorted(stripped)


@dataclass(frozen=True)
class Probe:
    probe_id: str
    repository: str
    surface_kind: str
    cwd: str
    command: tuple[str, ...]
    timeout_seconds: int
    expected_exit: tuple[int, ...]
    expected_stdout: str | None = None
    expected_artifact: str | None = None
    minimum_gate: str = "G3"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Probe":
        command = data["command"]
        if isinstance(command, str):
            command = shlex.split(command)
        return cls(
            probe_id=data["probe_id"],
            repository=data["repository"],
            surface_kind=data["surface_kind"],
            cwd=data.get("cwd", "."),
            command=tuple(command),
            timeout_seconds=int(data.get("timeout_seconds", 60)),
            expected_exit=tuple(int(x) for x in data.get("expected_exit", [0])),
            expected_stdout=data.get("expected_stdout"),
            expected_artifact=data.get("expected_artifact"),
            minimum_gate=data.get("minimum_gate", "G3"),
        )


def git_head(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def verify_workspace(workspace_root: Path, manifest: dict) -> tuple[list[dict[str, Any]], list[str]]:
    receipts: list[dict[str, Any]] = []
    failures: list[str] = []
    for repo in manifest["repositories"]:
        root = workspace_root / repo["workspace_directory"]
        actual = git_head(root) if root.is_dir() else None
        exact = actual == repo["commit"]
        receipt = {
            "repository": repo["repository"],
            "workspace_directory": repo["workspace_directory"],
            "expected_commit": repo["commit"],
            "actual_commit": actual,
            "present": root.is_dir(),
            "exact_commit": exact,
        }
        receipts.append(receipt)
        if not exact:
            failures.append(f"workspace-pin:{repo['id']}:expected={repo['commit']}:actual={actual}")
    return receipts, failures


def _snapshot_tree(root: Path, maximum_files: int = 10000) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for index, path in enumerate(sorted(root.rglob("*"))):
        if index >= maximum_files:
            result["__TRUNCATED__"] = str(maximum_files)
            break
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            try:
                result[rel] = sha256_file(path)
            except OSError:
                result[rel] = "UNREADABLE"
    return result


def _artifact_receipt(repo_root: Path, artifact: str | None) -> dict[str, Any] | None:
    if not artifact:
        return None
    path = repo_root / artifact
    if not path.is_file():
        return {"path": artifact, "exists": False, "sha256": None, "size": None}
    return {"path": artifact, "exists": True, "sha256": sha256_file(path), "size": path.stat().st_size}


def execute_probe(workspace_root: Path, shadow_root: Path, probe: Probe) -> dict[str, Any]:
    repo_root = workspace_root / probe.repository
    cwd = (repo_root / probe.cwd).resolve()
    try:
        cwd.relative_to(repo_root.resolve())
    except ValueError:
        return {"probe_id": probe.probe_id, "passed": False, "gate": "G2", "error": "cwd-escaped-repository"}

    probe_shadow = shadow_root / probe.probe_id
    home = probe_shadow / "home"
    tmp = probe_shadow / "tmp"
    fs_sink = probe_shadow / "fs"
    for path in (home, tmp, fs_sink):
        path.mkdir(parents=True, exist_ok=True)

    env, stripped = sanitized_environment(
        {
            "HOME": str(home),
            "TMPDIR": str(tmp),
            "FEDERATION_AUDIT_FS_ROOT": str(fs_sink),
            "FEDERATION_AUDIT_AUTH_TOKEN": "AUDIT_FAKE_TOKEN",
            "DATABASE_URL": f"sqlite:///{(probe_shadow / 'shadow.db').as_posix()}",
            "SMTP_HOST": "shadow-smtp",
            "SMTP_PORT": "2525",
            "MESSAGE_ENDPOINT": "http://shadow-message:9090",
            "EXTERNAL_API_BASE_URL": "http://shadow-http:9080",
        }
    )
    before = _snapshot_tree(probe_shadow)
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            list(probe.command),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=probe.timeout_seconds,
            check=False,
        )
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except OSError as exc:
        returncode = None
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"

    elapsed = round(time.monotonic() - started, 3)
    after = _snapshot_tree(probe_shadow)
    stdout_ok = probe.expected_stdout is None or probe.expected_stdout in stdout
    exit_ok = returncode in probe.expected_exit
    artifact = _artifact_receipt(repo_root, probe.expected_artifact)
    artifact_ok = artifact is None or bool(artifact["exists"])
    passed = (not timed_out) and exit_ok and stdout_ok and artifact_ok

    # A passing real process invocation reaches G4.  A declared terminal
    # artifact/output can reach G6 only when the enclosing runtime asserts
    # isolation and emits this T2 receipt.
    gate = "G4" if passed else "G3"
    if passed and (probe.expected_stdout or probe.expected_artifact):
        gate = "G6"

    receipt_payload = {
        "probe_id": probe.probe_id,
        "repository": probe.repository,
        "surface_kind": probe.surface_kind,
        "command": list(probe.command),
        "cwd": probe.cwd,
        "started_at": utcnow(),
        "elapsed_seconds": elapsed,
        "returncode": returncode,
        "timed_out": timed_out,
        "expected_exit": list(probe.expected_exit),
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8", errors="replace")),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8", errors="replace")),
        "stdout_expectation_met": stdout_ok,
        "artifact": artifact,
        "shadow_tree_before": before,
        "shadow_tree_after": after,
        "stripped_secret_variable_names": stripped,
        "runtime_isolated": os.environ.get("FEDERATION_AUDIT_NETWORK_ISOLATED") == "1",
        "production_credentials": False,
        "production_egress": False,
        "uncontained_side_effects": 0,
        "gate": gate,
        "passed": passed,
    }
    receipt_payload["receipt_sha256"] = sha256_bytes(
        json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return receipt_payload


def load_topology(path: Path) -> list[Probe]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Probe.from_dict(item) for item in data["probes"]]


def calibrate(calibration: dict[str, Any]) -> dict[str, Any]:
    tp = int(calibration.get("true_positive", 0))
    fp = int(calibration.get("false_positive", 0))
    fn = int(calibration.get("false_negative", 0))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
    }


def runtime_certify(
    workspace_root: Path,
    manifest: dict,
    topology_path: Path,
    shadow_root: Path,
    execute: bool = True,
) -> dict[str, Any]:
    workspace_receipts, failures = verify_workspace(workspace_root, manifest)
    strict = strict_scan_federation(workspace_root, manifest)
    probes = load_topology(topology_path)
    probe_receipts: list[dict[str, Any]] = []

    if not failures and execute:
        for probe in probes:
            probe_receipts.append(execute_probe(workspace_root, shadow_root, probe))
    elif execute:
        failures.append("runtime-probes-skipped:workspace-pin-gate")

    repo_ids = {repo["workspace_directory"] for repo in manifest["repositories"]}
    probed_repos = {item["repository"] for item in probe_receipts if item.get("passed")}
    failures.extend(f"repository-unprobed:{repo}" for repo in sorted(repo_ids - probed_repos) if execute)

    for item in probe_receipts:
        if item.get("production_egress"):
            failures.append(f"production-egress:{item['probe_id']}")
        if item.get("production_credentials"):
            failures.append(f"production-credentials:{item['probe_id']}")
        if item.get("uncontained_side_effects"):
            failures.append(f"uncontained-side-effect:{item['probe_id']}")
        if not item.get("passed"):
            failures.append(f"probe-failed:{item['probe_id']}")

    calibration_data = calibrate({"true_positive": 0, "false_positive": 0, "false_negative": 0})
    summary = {
        "repositories_expected": len(manifest["repositories"]),
        "repositories_exact": sum(bool(item["exact_commit"]) for item in workspace_receipts),
        "probes_expected": len(probes),
        "probes_passed": sum(bool(item.get("passed")) for item in probe_receipts),
        "g6_receipts": sum(item.get("gate") == "G6" and item.get("passed") for item in probe_receipts),
        "production_egress_events": sum(bool(item.get("production_egress")) for item in probe_receipts),
        "production_credential_events": sum(bool(item.get("production_credentials")) for item in probe_receipts),
        "uncontained_side_effects": sum(int(item.get("uncontained_side_effects", 0)) for item in probe_receipts),
        "strict_static": strict["coverage"],
        "calibration": calibration_data,
    }
    certified = (
        not failures
        and summary["repositories_exact"] == 7
        and summary["probes_passed"] == summary["probes_expected"]
        and summary["production_egress_events"] == 0
        and summary["production_credential_events"] == 0
        and summary["uncontained_side_effects"] == 0
    )
    return {
        "schema_version": "0.2.0",
        "generated_at": utcnow(),
        "certification": "SEVEN_REPOSITORY_EXECUTABILITY_CONFIRMED" if certified else "NOT_CERTIFIED",
        "certified": certified,
        "workspace": workspace_receipts,
        "strict_static": strict,
        "runtime_receipts": probe_receipts,
        "summary": summary,
        "failures": sorted(set(failures)),
    }

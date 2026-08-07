from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .calibration import run_calibration
from .strict_scan import strict_scan_federation

SECRET_NAME = re.compile(r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL)", re.I)
GATE_ORDER = {f"G{index}": index for index in range(7)}
RISKY_COMMANDS = ("curl", "wget", "ssh", "scp", "nc", "ncat", "socat", "aws", "gcloud", "gsutil", "kubectl", "mail", "sendmail")
ATTESTATIONS = (
    "FEDERATION_AUDIT_NETWORK_ISOLATED",
    "FEDERATION_AUDIT_PRIVATE_NETWORK",
    "FEDERATION_AUDIT_CONTAINER_READ_ONLY",
)


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
    result: dict[str, str] = {}
    stripped: list[str] = []
    for name, value in os.environ.items():
        if SECRET_NAME.search(name) and not value.startswith("AUDIT_FAKE_"):
            stripped.append(name)
            continue
        result[name] = value
    result.update({"FEDERATION_AUDIT": "1", "NO_PROXY": "*", "no_proxy": "*", "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": ""})
    if extra:
        result.update(extra)
    return result, sorted(stripped)


@dataclass(frozen=True)
class Probe:
    probe_id: str
    repository: str
    surface_kind: str
    entry_point: str
    cwd: str
    command: tuple[str, ...]
    mode: str
    timeout_seconds: int
    startup_seconds: int
    expected_exit: tuple[int, ...]
    expected_stdout: str | None = None
    expected_artifact: str | None = None
    minimum_gate: str = "G3"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Probe":
        command = data["command"]
        if isinstance(command, str):
            command = shlex.split(command)
        minimum_gate = str(data.get("minimum_gate", "G3"))
        if minimum_gate not in GATE_ORDER:
            raise ValueError(f"invalid minimum gate: {minimum_gate}")
        mode = str(data.get("mode", "command"))
        if mode not in {"command", "boot"}:
            raise ValueError(f"invalid probe mode: {mode}")
        return cls(
            probe_id=data["probe_id"], repository=data["repository"], surface_kind=data["surface_kind"],
            entry_point=data["entry_point"], cwd=data.get("cwd", "."), command=tuple(command), mode=mode,
            timeout_seconds=int(data.get("timeout_seconds", 60)), startup_seconds=int(data.get("startup_seconds", 5)),
            expected_exit=tuple(int(x) for x in data.get("expected_exit", [0])),
            expected_stdout=data.get("expected_stdout"), expected_artifact=data.get("expected_artifact"),
            minimum_gate=minimum_gate,
        )


def git_head(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=False, capture_output=True, text=True, timeout=10)
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
        entry_points = []
        for entry in repo.get("entry_points", []):
            exists = (root / entry["path"]).exists()
            entry_points.append({"kind": entry["kind"], "path": entry["path"], "command": entry.get("command"), "exists": exists})
            if root.is_dir() and not exists:
                failures.append(f"entrypoint-missing:{repo['id']}:{entry['path']}")
        receipts.append({"repository": repo["repository"], "workspace_directory": repo["workspace_directory"], "expected_commit": repo["commit"], "actual_commit": actual, "present": root.is_dir(), "exact_commit": exact, "entry_points": entry_points})
        if not exact:
            failures.append(f"workspace-pin:{repo['id']}:expected={repo['commit']}:actual={actual}")
    return receipts, failures


def validate_topology(manifest: dict, probes: list[Probe]) -> list[str]:
    failures: list[str] = []
    repositories = {repo["workspace_directory"]: repo for repo in manifest["repositories"]}
    seen_ids: set[str] = set()
    for probe in probes:
        if probe.probe_id in seen_ids:
            failures.append(f"duplicate-probe-id:{probe.probe_id}")
        seen_ids.add(probe.probe_id)
        repo = repositories.get(probe.repository)
        if repo is None:
            failures.append(f"probe-unknown-repository:{probe.probe_id}:{probe.repository}")
            continue
        matches = [entry for entry in repo.get("entry_points", []) if entry["path"] == probe.entry_point]
        if len(matches) != 1:
            failures.append(f"probe-unbound-entrypoint:{probe.probe_id}:{probe.entry_point}")
            continue
        declared = matches[0].get("command")
        if not declared:
            failures.append(f"probe-entrypoint-has-no-declared-command:{probe.probe_id}:{probe.entry_point}")
            continue
        declared_argv = tuple(shlex.split(declared))
        if probe.command[: len(declared_argv)] != declared_argv:
            failures.append(f"probe-command-not-declared-prefix:{probe.probe_id}")
    covered = {probe.repository for probe in probes}
    failures.extend(f"topology-repository-uncovered:{repo}" for repo in sorted(set(repositories) - covered))
    return failures


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


def _artifact_receipt(shadow_root: Path, artifact: str | None) -> dict[str, Any] | None:
    if not artifact:
        return None
    path = shadow_root / artifact
    if not path.is_file():
        return {"path": artifact, "exists": False, "sha256": None, "size": None}
    return {"path": artifact, "exists": True, "sha256": sha256_file(path), "size": path.stat().st_size}


def _install_block_wrappers(root: Path) -> tuple[Path, Path]:
    bin_dir, log_path = root / "blocked-bin", root / "blocked-subprocess.jsonl"
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = "#!/bin/sh\nname=$(basename \"$0\")\nargc=$#\nprintf '{\"command\":\"%s\",\"argc\":%s}\\n' \"$name\" \"$argc\" >> \"$FEDERATION_AUDIT_BLOCK_LOG\"\nexit 126\n"
    for name in RISKY_COMMANDS:
        path = bin_dir / name
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir, log_path


def _attestation() -> dict[str, bool]:
    return {name: os.environ.get(name) == "1" for name in ATTESTATIONS}


def _run_boot(command: list[str], cwd: Path, env: dict[str, str], startup_seconds: int) -> tuple[int | None, str, str, bool]:
    try:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        return None, "", f"{type(exc).__name__}: {exc}", False
    time.sleep(max(1, startup_seconds))
    alive = proc.poll() is None
    if alive:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
        return proc.returncode, stdout, stderr, True
    stdout, stderr = proc.communicate(timeout=5)
    return proc.returncode, stdout, stderr, False


def execute_probe(workspace_root: Path, shadow_root: Path, probe: Probe) -> dict[str, Any]:
    repo_root = workspace_root / probe.repository
    cwd = (repo_root / probe.cwd).resolve()
    try:
        cwd.relative_to(repo_root.resolve())
    except ValueError:
        return {"probe_id": probe.probe_id, "passed": False, "gate": "G2", "error": "cwd-escaped-repository"}
    probe_shadow, home, tmp, fs_sink = shadow_root / probe.probe_id, shadow_root / probe.probe_id / "home", shadow_root / probe.probe_id / "tmp", shadow_root / probe.probe_id / "fs"
    for path in (home, tmp, fs_sink):
        path.mkdir(parents=True, exist_ok=True)
    blocked_bin, blocked_log = _install_block_wrappers(probe_shadow)
    attestation, isolation_ok = _attestation(), all(_attestation().values())
    env, stripped = sanitized_environment({"HOME": str(home), "TMPDIR": str(tmp), "FEDERATION_AUDIT_FS_ROOT": str(fs_sink), "FEDERATION_AUDIT_AUTH_TOKEN": "AUDIT_FAKE_TOKEN", "FEDERATION_AUDIT_BLOCK_LOG": str(blocked_log), "PATH": f"{blocked_bin}:{os.environ.get('PATH', '')}", "DATABASE_URL": f"sqlite:///{(probe_shadow / 'shadow.db').as_posix()}", "SMTP_HOST": "shadow-smtp", "SMTP_PORT": "2525", "MESSAGE_ENDPOINT": "http://shadow-message:9090", "EXTERNAL_API_BASE_URL": "http://shadow-http:9080"})
    before, started_at, started = _snapshot_tree(probe_shadow), utcnow(), time.monotonic()
    timed_out = False
    if probe.mode == "boot":
        returncode, stdout, stderr, alive_after_startup = _run_boot(list(probe.command), cwd, env, probe.startup_seconds)
        execution_ok = alive_after_startup and isolation_ok
    else:
        try:
            proc = subprocess.run(list(probe.command), cwd=cwd, env=env, capture_output=True, text=True, timeout=probe.timeout_seconds, check=False)
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out, returncode = True, None
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        except OSError as exc:
            returncode, stdout, stderr = None, "", f"{type(exc).__name__}: {exc}"
        stdout_ok = probe.expected_stdout is None or probe.expected_stdout in stdout
        execution_ok = not timed_out and returncode in probe.expected_exit and stdout_ok and isolation_ok
        alive_after_startup = False
    elapsed, after = round(time.monotonic() - started, 3), _snapshot_tree(probe_shadow)
    artifact = _artifact_receipt(probe_shadow, probe.expected_artifact)
    if artifact is not None:
        execution_ok = execution_ok and bool(artifact["exists"])
    stdout_ok = probe.expected_stdout is None or probe.expected_stdout in stdout
    gate = "G3" if execution_ok and probe.mode == "boot" else "G4" if execution_ok else "G2"
    if execution_ok and probe.mode == "command" and (probe.expected_stdout or probe.expected_artifact):
        gate = "G6"
    minimum_met, passed = GATE_ORDER[gate] >= GATE_ORDER[probe.minimum_gate], execution_ok and GATE_ORDER[gate] >= GATE_ORDER[probe.minimum_gate]
    blocked_attempts = len(blocked_log.read_text(encoding="utf-8").splitlines()) if blocked_log.is_file() else 0
    receipt = {"probe_id": probe.probe_id, "repository": probe.repository, "surface_kind": probe.surface_kind, "entry_point": probe.entry_point, "mode": probe.mode, "command_name": probe.command[0] if probe.command else None, "command_argc": max(0, len(probe.command)-1), "cwd": probe.cwd, "started_at": started_at, "elapsed_seconds": elapsed, "returncode": returncode, "timed_out": timed_out, "alive_after_startup": alive_after_startup, "stdout_sha256": sha256_bytes(stdout.encode(errors="replace")), "stderr_sha256": sha256_bytes(stderr.encode(errors="replace")), "stdout_expectation_met": stdout_ok, "artifact": artifact, "shadow_tree_before": before, "shadow_tree_after": after, "stripped_secret_variable_names": stripped, "isolation_attestation": attestation, "runtime_isolated": isolation_ok, "blocked_subprocess_attempts": blocked_attempts, "production_credentials": False if isolation_ok else None, "production_egress": False if isolation_ok else None, "uncontained_side_effects": 0 if isolation_ok else None, "minimum_gate": probe.minimum_gate, "minimum_gate_met": minimum_met, "gate": gate, "t2_receipt": True, "passed": passed}
    receipt["receipt_sha256"] = sha256_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    return receipt


def load_topology(path: Path) -> list[Probe]:
    return [Probe.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))["probes"]]


def runtime_certify(workspace_root: Path, manifest: dict, topology_path: Path, shadow_root: Path, execute: bool = True) -> dict[str, Any]:
    workspace_receipts, failures = verify_workspace(workspace_root, manifest)
    strict, calibration, probes = strict_scan_federation(workspace_root, manifest), run_calibration(), load_topology(topology_path)
    failures.extend(validate_topology(manifest, probes))
    if not calibration["passed"]:
        failures.append("scanner-calibration-failed")
    probe_receipts: list[dict[str, Any]] = []
    if not failures and execute:
        probe_receipts = [execute_probe(workspace_root, shadow_root, probe) for probe in probes]
    elif execute:
        failures.append("runtime-probes-skipped:preflight-gate")
    repo_ids = {repo["workspace_directory"] for repo in manifest["repositories"]}
    probed_repos = {item["repository"] for item in probe_receipts if item.get("passed")}
    failures.extend(f"repository-unprobed:{repo}" for repo in sorted(repo_ids - probed_repos) if execute)
    for item in probe_receipts:
        if item.get("production_egress") is not False: failures.append(f"production-egress-unproven:{item['probe_id']}")
        if item.get("production_credentials") is not False: failures.append(f"production-credentials-unproven:{item['probe_id']}")
        if item.get("uncontained_side_effects") != 0: failures.append(f"containment-unproven:{item['probe_id']}")
        if not item.get("passed"): failures.append(f"probe-failed:{item['probe_id']}")
    summary = {"repositories_expected": len(manifest["repositories"]), "repositories_exact": sum(bool(item["exact_commit"]) for item in workspace_receipts), "entry_points_expected": sum(len(item["entry_points"]) for item in workspace_receipts), "entry_points_present": sum(sum(bool(ep["exists"]) for ep in item["entry_points"]) for item in workspace_receipts), "probes_expected": len(probes), "probes_passed": sum(bool(item.get("passed")) for item in probe_receipts), "g6_receipts": sum(item.get("gate") == "G6" and item.get("passed") for item in probe_receipts), "production_egress_events": sum(item.get("production_egress") is True for item in probe_receipts), "production_credential_events": sum(item.get("production_credentials") is True for item in probe_receipts), "uncontained_side_effects": sum(int(item.get("uncontained_side_effects") or 0) for item in probe_receipts), "strict_static": strict["coverage"], "calibration": calibration}
    certified = execute and not failures and summary["repositories_exact"] == 7 and summary["entry_points_present"] == summary["entry_points_expected"] and summary["probes_passed"] == summary["probes_expected"] and len(probed_repos) == 7 and calibration["precision"] == 1.0 and calibration["recall"] == 1.0
    return {"schema_version": "0.2.0", "generated_at": utcnow(), "certification": "SEVEN_REPOSITORY_EXECUTABILITY_CONFIRMED" if certified else "NOT_CERTIFIED", "certified": certified, "workspace": workspace_receipts, "strict_static": strict, "runtime_receipts": probe_receipts, "summary": summary, "failures": sorted(set(failures))}

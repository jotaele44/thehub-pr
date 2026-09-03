"""Federation development-vector pickup and bounded execution control plane.

The engine treats GitHub/repository state as evidence and the canonical ledger as
intent. Discovery never proves identity; execution is fail-closed.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

ALLOWED_STATUSES = {"READY", "BLOCKED", "OPEN", "PASS", "FAIL", "UNRESOLVED"}
ALLOWED_CERTIFICATIONS = {
    "PASS", "FAIL", "OPEN", "BLOCKED", "PROVISIONAL", "AUDIT_ONLY",
    "NONCANONICAL", "CANDIDATE_NOT_IDENTITY", "UNRESOLVED", "SUPERSEDED",
}
REPO_STATUS_PRECEDENCE = ("FAIL", "UNRESOLVED", "BLOCKED", "READY", "OPEN", "PASS")
DEFAULT_LEDGER = Path("registry/development_vectors.yaml")
DEFAULT_RECEIPT_ROOT = Path(".fed/runs")


class FedError(RuntimeError):
    """Fail-closed federation error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_ledger(path: Path = DEFAULT_LEDGER) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FedError("ledger_unreadable:%s:%s" % (path, exc)) from exc
    except yaml.YAMLError as exc:
        raise FedError("ledger_invalid_yaml:%s:%s" % (path, exc)) from exc
    if not isinstance(data, dict):
        raise FedError("ledger_root_must_be_mapping")
    return data


def repository_index(ledger: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    repos = ledger.get("snapshot", {}).get("repositories", [])
    if not isinstance(repos, list):
        raise FedError("snapshot.repositories_must_be_list")
    result: Dict[str, Dict[str, Any]] = {}
    ids: Dict[int, str] = {}
    for row in repos:
        if not isinstance(row, dict):
            raise FedError("repository_row_must_be_mapping")
        repo = str(row.get("repo", ""))
        repo_id = row.get("repo_id")
        sha = str(row.get("expected_sha", ""))
        if not repo or not isinstance(repo_id, int):
            raise FedError("repository_requires_repo_and_stable_integer_repo_id")
        if repo in result:
            raise FedError("duplicate_repository:%s" % repo)
        if repo_id in ids:
            raise FedError("duplicate_repository_id:%s:%s:%s" % (repo_id, ids[repo_id], repo))
        if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
            raise FedError("invalid_expected_sha:%s:%s" % (repo, sha))
        result[repo] = dict(row)
        ids[repo_id] = repo
    return result


def vector_index(ledger: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    vectors = ledger.get("vectors", [])
    if not isinstance(vectors, list):
        raise FedError("vectors_must_be_list")
    result: Dict[str, Dict[str, Any]] = {}
    issue_bindings: Dict[str, str] = {}
    for row in vectors:
        if not isinstance(row, dict):
            raise FedError("vector_row_must_be_mapping")
        vector_id = str(row.get("vector_id", ""))
        if not vector_id:
            raise FedError("missing_vector_id")
        if vector_id in result:
            raise FedError("duplicate_vector_id:%s" % vector_id)
        status = str(row.get("declared_status", ""))
        certification = str(row.get("certification", ""))
        if status not in ALLOWED_STATUSES:
            raise FedError("invalid_vector_status:%s:%s" % (vector_id, status))
        if certification not in ALLOWED_CERTIFICATIONS:
            raise FedError("invalid_certification:%s:%s" % (vector_id, certification))
        bindings = row.get("source_bindings", [])
        if not isinstance(bindings, list) or not bindings:
            raise FedError("vector_requires_source_binding:%s" % vector_id)
        for binding in bindings:
            if not isinstance(binding, dict):
                raise FedError("binding_must_be_mapping:%s" % vector_id)
            ref = str(binding.get("ref", ""))
            basis = str(binding.get("binding_basis", ""))
            if not ref or not basis:
                raise FedError("binding_requires_ref_and_basis:%s" % vector_id)
            if binding.get("kind") == "github_issue":
                prior = issue_bindings.get(ref)
                if prior and prior != vector_id:
                    raise FedError("github_issue_bound_to_multiple_vectors:%s:%s:%s" % (ref, prior, vector_id))
                issue_bindings[ref] = vector_id
        result[vector_id] = dict(row)
    return result


def validate_ledger(ledger: Mapping[str, Any]) -> Dict[str, Any]:
    repos = repository_index(ledger)
    vectors = vector_index(ledger)
    if ledger.get("control_plane") != "jotaele44/thehub-pr":
        raise FedError("unexpected_control_plane:%s" % ledger.get("control_plane"))
    expected_repos = {
        "jotaele44/skywatcher-pr", "jotaele44/aguayluz-pr", "jotaele44/spiderweb-pr",
        "jotaele44/moneysweep-pr", "jotaele44/centinelas-pr", "jotaele44/ovnis-pr",
        "jotaele44/thehub-pr",
    }
    actual_repos = set(repos)
    if actual_repos != expected_repos:
        raise FedError("repository_universe_mismatch:missing=%s:extra=%s" % (
            sorted(expected_repos - actual_repos), sorted(actual_repos - expected_repos)
        ))
    for vector_id, vector in vectors.items():
        repo = vector.get("repo")
        if repo not in repos:
            raise FedError("vector_repo_not_in_snapshot:%s:%s" % (vector_id, repo))
        deps = vector.get("dependencies", [])
        if not isinstance(deps, list):
            raise FedError("dependencies_must_be_list:%s" % vector_id)
        for dep in deps:
            if dep not in vectors:
                raise FedError("missing_dependency:%s:%s" % (vector_id, dep))
        execution = vector.get("execution", {})
        if not isinstance(execution, dict):
            raise FedError("execution_must_be_mapping:%s" % vector_id)
        commands = execution.get("commands", [])
        if not isinstance(commands, list) or any(not isinstance(cmd, str) or not cmd.strip() for cmd in commands):
            raise FedError("execution_commands_must_be_nonempty_strings:%s" % vector_id)
        if commands and execution.get("mutation") == "prohibited_by_fed_max":
            raise FedError("prohibited_vector_may_not_define_commands:%s" % vector_id)
    topological_order(vectors)
    source_count = sum(len(v.get("source_bindings", [])) for v in vectors.values())
    return {
        "repository_count": len(repos),
        "vector_count": len(vectors),
        "source_binding_count": source_count,
        "ledger_sha256": digest(ledger),
        "status": "PASS",
    }


def topological_order(vectors: Mapping[str, Mapping[str, Any]]) -> List[str]:
    indegree: Dict[str, int] = {key: 0 for key in vectors}
    children: Dict[str, List[str]] = {key: [] for key in vectors}
    for key, vector in vectors.items():
        for dep in vector.get("dependencies", []):
            if dep not in vectors:
                raise FedError("missing_dependency:%s:%s" % (key, dep))
            indegree[key] += 1
            children[dep].append(key)
    ready = sorted(key for key, degree in indegree.items() if degree == 0)
    order: List[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(vectors):
        residue = sorted(key for key, degree in indegree.items() if degree)
        raise FedError("dependency_cycle:%s" % ",".join(residue))
    return order


def _run_git(repo_path: Path, args: Sequence[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_path)] + list(args),
        text=True, capture_output=True, check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def discover_checkout(root: Path, repo: str) -> Dict[str, Any]:
    path = root / repo.split("/")[-1]
    if not path.exists():
        return {"present": False, "path": str(path)}
    code, head, err = _run_git(path, ["rev-parse", "HEAD"])
    if code:
        return {"present": True, "path": str(path), "git_valid": False, "error": err}
    code, branch, _ = _run_git(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    code2, porcelain, err2 = _run_git(path, ["status", "--porcelain=v1"])
    remote_code, remote, _ = _run_git(path, ["remote", "get-url", "origin"])
    return {
        "present": True,
        "path": str(path),
        "git_valid": True,
        "head_sha": head,
        "branch": branch if code == 0 else None,
        "dirty": bool(porcelain) if code2 == 0 else None,
        "status_error": err2 if code2 else None,
        "origin": remote if remote_code == 0 else None,
    }


def snapshot_local(ledger: Mapping[str, Any], root: Path) -> Dict[str, Any]:
    repos = repository_index(ledger)
    observed = []
    for repo in sorted(repos):
        expected = repos[repo]
        state = discover_checkout(root, repo)
        state.update({
            "repo": repo,
            "repo_id": expected["repo_id"],
            "expected_sha": expected["expected_sha"],
            "default_branch": expected.get("default_branch", "main"),
        })
        state["sha_match"] = bool(state.get("git_valid") and state.get("head_sha") == expected["expected_sha"])
        observed.append(state)
    return {
        "captured_at_utc": utc_now(),
        "root": str(root),
        "repositories": observed,
        "sha256": digest(observed),
    }


def _gh_head(repo: str, branch: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        proc = subprocess.run(
            ["gh", "api", "repos/%s/commits/%s" % (repo, branch), "--jq", ".sha"],
            text=True, capture_output=True, check=False,
        )
    except FileNotFoundError:
        return None, "gh_missing"
    if proc.returncode:
        return None, "gh_api_failed:%s" % proc.stderr.strip()
    sha = proc.stdout.strip()
    if len(sha) != 40:
        return None, "gh_api_invalid_sha:%s" % sha
    return sha, None


def _gh_parent_shas(repo: str, sha: str) -> Tuple[List[str], Optional[str]]:
    proc = subprocess.run(
        ["gh", "api", "repos/%s/commits/%s" % (repo, sha), "--jq", "[.parents[].sha] | @tsv"],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode:
        return [], "gh_api_failed:%s" % proc.stderr.strip()
    parents = [part for part in proc.stdout.strip().split("\t") if part]
    return parents, None


def snapshot_remote(ledger: Mapping[str, Any]) -> Dict[str, Any]:
    repos = repository_index(ledger)
    control_plane = str(ledger.get("control_plane", ""))
    observed = []
    for repo in sorted(repos):
        expected = repos[repo]
        branch = str(expected.get("default_branch", "main"))
        head, error = _gh_head(repo, branch)
        sha_match = head == expected["expected_sha"] if head else False
        parent_shas: List[str] = []
        if (
            not sha_match
            and head
            and repo == control_plane
            and expected.get("self_snapshot_finalizer_parent") is True
        ):
            parent_shas, parent_error = _gh_parent_shas(repo, head)
            if parent_error:
                error = parent_error
            else:
                sha_match = expected["expected_sha"] in parent_shas
        observed.append({
            "repo": repo,
            "repo_id": expected["repo_id"],
            "default_branch": branch,
            "expected_sha": expected["expected_sha"],
            "observed_sha": head,
            "sha_match": sha_match,
            "self_snapshot_finalizer_parent": bool(expected.get("self_snapshot_finalizer_parent")),
            "observed_parent_shas": parent_shas,
            "error": error,
        })
    return {
        "captured_at_utc": utc_now(),
        "transport": "gh_api",
        "repositories": observed,
        "sha256": digest(observed),
    }


def reconcile(ledger: Mapping[str, Any], snapshot: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    validation = validate_ledger(ledger)
    vectors = vector_index(ledger)
    repo_observed: Dict[str, Mapping[str, Any]] = {}
    if snapshot:
        repo_observed = {str(row["repo"]): row for row in snapshot.get("repositories", [])}
    rows = []
    for vector_id in topological_order(vectors):
        vector = vectors[vector_id]
        declared = str(vector["declared_status"])
        effective = declared
        blockers = list(vector.get("blockers", []))
        observed = repo_observed.get(str(vector["repo"]))
        if observed is not None:
            if observed.get("error"):
                effective = "BLOCKED" if declared not in {"FAIL", "UNRESOLVED"} else declared
                blockers.append("snapshot_error:%s" % observed["error"])
            elif observed.get("sha_match") is False:
                effective = "BLOCKED" if declared not in {"FAIL", "UNRESOLVED"} else declared
                blockers.append("stale_or_unverified_sha")
        rows.append({
            "vector_id": vector_id,
            "repo": vector["repo"],
            "declared_status": declared,
            "effective_status": effective,
            "certification": vector["certification"],
            "dependencies": list(vector.get("dependencies", [])),
            "blockers": sorted(set(blockers)),
        })
    by_vector = {row["vector_id"]: row for row in rows}
    for row in rows:
        if row["effective_status"] != "READY":
            continue
        bad_deps = [
            dep for dep in row["dependencies"]
            if by_vector[dep]["effective_status"] != "PASS"
        ]
        if bad_deps:
            row["effective_status"] = "BLOCKED"
            row["blockers"].append("dependency_not_pass:%s" % ",".join(sorted(bad_deps)))
    return {
        "created_at_utc": utc_now(),
        "validation": validation,
        "vectors": rows,
        "sha256": digest(rows),
    }


def repository_statuses(ledger: Mapping[str, Any], reconciliation: Mapping[str, Any]) -> Dict[str, Any]:
    repos = repository_index(ledger)
    grouped: Dict[str, List[str]] = {repo: [] for repo in repos}
    for row in reconciliation["vectors"]:
        grouped[row["repo"]].append(row["effective_status"])
    result = []
    counts = {status: 0 for status in ALLOWED_STATUSES}
    for repo in sorted(repos):
        statuses = grouped[repo]
        if not statuses:
            final = "UNRESOLVED"
        else:
            final = next((status for status in REPO_STATUS_PRECEDENCE if status in statuses), "UNRESOLVED")
        counts[final] += 1
        result.append({"repo": repo, "status": final, "vector_statuses": sorted(statuses)})
    classified = sum(counts.values())
    arithmetic_ok = classified == len(repos) == 7
    if not arithmetic_ok:
        raise FedError("status_arithmetic_failed:classified=%s:repos=%s" % (classified, len(repos)))
    return {
        "repository_count": len(repos),
        "classified_count": classified,
        "counts": {key: counts[key] for key in sorted(counts)},
        "arithmetic": "%s=%s" % (classified, len(repos)),
        "arithmetic_ok": arithmetic_ok,
        "repositories": result,
    }


def build_plan(ledger: Mapping[str, Any], reconciliation: Mapping[str, Any]) -> Dict[str, Any]:
    vectors = vector_index(ledger)
    rec = {row["vector_id"]: row for row in reconciliation["vectors"]}
    order = topological_order(vectors)
    steps = []
    for ordinal, vector_id in enumerate(order, 1):
        vector = vectors[vector_id]
        row = rec[vector_id]
        steps.append({
            "ordinal": ordinal,
            "vector_id": vector_id,
            "repo": vector["repo"],
            "status": row["effective_status"],
            "dependencies": row["dependencies"],
            "execution_kind": vector.get("execution", {}).get("kind"),
            "mutation": vector.get("execution", {}).get("mutation"),
            "command_count": len(vector.get("execution", {}).get("commands", [])),
            "blockers": row["blockers"],
        })
    return {"created_at_utc": utc_now(), "steps": steps, "sha256": digest(steps)}


def doctor(ledger: Mapping[str, Any]) -> Dict[str, Any]:
    validation = validate_ledger(ledger)
    checks = {
        "python_version": sys.version.split()[0],
        "python_supported": sys.version_info >= (3, 9),
        "git_present": shutil.which("git") is not None,
        "gh_present": shutil.which("gh") is not None,
    }
    if checks["gh_present"]:
        proc = subprocess.run(["gh", "auth", "status"], text=True, capture_output=True, check=False)
        checks["gh_auth_ok"] = proc.returncode == 0
    else:
        checks["gh_auth_ok"] = False
    checks["ledger_valid"] = validation["status"] == "PASS"
    checks["local_core_ready"] = bool(checks["python_supported"] and checks["git_present"] and checks["ledger_valid"])
    checks["remote_snapshot_ready"] = bool(checks["local_core_ready"] and checks["gh_present"] and checks["gh_auth_ok"])
    return {"created_at_utc": utc_now(), "checks": checks, "validation": validation}


def _command_allowed(vector: Mapping[str, Any]) -> None:
    execution = vector.get("execution", {})
    mutation = execution.get("mutation")
    if mutation == "prohibited_by_fed_max":
        raise FedError("mutation_prohibited:%s" % vector["vector_id"])
    commands = execution.get("commands", [])
    if not commands:
        raise FedError("no_executable_command:%s" % vector["vector_id"])
    forbidden = ("git push --force", "git push -f", "git branch -D", "git push origin --delete", "gh pr merge")
    for command in commands:
        lower = command.lower()
        if any(token.lower() in lower for token in forbidden):
            raise FedError("forbidden_command:%s:%s" % (vector["vector_id"], command))


def _execute_vector(vector: Mapping[str, Any], root: Path, apply: bool) -> Dict[str, Any]:
    vector_id = str(vector["vector_id"])
    execution = vector.get("execution", {})
    commands = list(execution.get("commands", []))
    if not commands:
        return {
            "vector_id": vector_id,
            "status": "PASS" if execution.get("kind") == "implementation_self" else "OPEN",
            "executed": False,
            "reason": "self_implementation_receipt" if execution.get("kind") == "implementation_self" else "no_command",
            "commands": [],
        }
    _command_allowed(vector)
    if not apply:
        return {"vector_id": vector_id, "status": "READY", "executed": False, "reason": "dry_run", "commands": commands}
    repo_path = root / str(vector["repo"]).split("/")[-1]
    if not repo_path.exists():
        raise FedError("missing_checkout_for_execution:%s:%s" % (vector_id, repo_path))
    command_rows = []
    for command in commands:
        started = utc_now()
        proc = subprocess.run(command, cwd=str(repo_path), shell=True, text=True, capture_output=True, check=False)
        row = {
            "command": command,
            "started_at_utc": started,
            "ended_at_utc": utc_now(),
            "exit_code": proc.returncode,
            "stdout_sha256": hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(proc.stderr.encode("utf-8")).hexdigest(),
        }
        command_rows.append(row)
        if proc.returncode:
            return {"vector_id": vector_id, "status": "FAIL", "executed": True, "commands": command_rows}
    return {"vector_id": vector_id, "status": "PASS", "executed": True, "commands": command_rows}


def run_ready(
    ledger: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    root: Path,
    apply: bool,
    completed: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    vectors = vector_index(ledger)
    completed_set = set(completed or [])
    rec = {row["vector_id"]: row for row in reconciliation["vectors"]}
    results = []
    dynamic_status = {key: rec[key]["effective_status"] for key in vectors}
    for vector_id in topological_order(vectors):
        if vector_id in completed_set:
            dynamic_status[vector_id] = "PASS"
            continue
        status = dynamic_status[vector_id]
        vector = vectors[vector_id]
        if status != "READY":
            continue
        bad_deps = [dep for dep in vector.get("dependencies", []) if dynamic_status.get(dep) != "PASS"]
        if bad_deps:
            results.append({
                "vector_id": vector_id,
                "status": "BLOCKED",
                "executed": False,
                "reason": "dependency_not_pass:%s" % ",".join(sorted(bad_deps)),
            })
            dynamic_status[vector_id] = "BLOCKED"
            continue
        result = _execute_vector(vector, root, apply)
        results.append(result)
        dynamic_status[vector_id] = result["status"]
        if result["status"] == "FAIL":
            break
    return {
        "created_at_utc": utc_now(),
        "apply": apply,
        "results": results,
        "effective_status": dynamic_status,
        "sha256": digest({"apply": apply, "results": results, "effective_status": dynamic_status}),
    }


def run_max(
    ledger: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    root: Path,
    apply: bool,
    completed: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    vectors = vector_index(ledger)
    rec = copy.deepcopy(reconciliation)
    completed_set = set(completed or [])
    passes: List[Dict[str, Any]] = []
    seen: set = set()
    for _ in range(len(vectors) + 1):
        run = run_ready(ledger, rec, root, apply, completed=completed_set)
        passes.append(run)
        progress = False
        for result in run["results"]:
            vector_id = result["vector_id"]
            signature = (vector_id, result["status"], result.get("executed"), result.get("reason"))
            if signature in seen:
                continue
            seen.add(signature)
            if result["status"] == "PASS":
                completed_set.add(vector_id)
                progress = True
        if not progress:
            break
        for row in rec["vectors"]:
            if row["vector_id"] in completed_set:
                row["effective_status"] = "PASS"
        by_id = {row["vector_id"]: row for row in rec["vectors"]}
        for row in rec["vectors"]:
            if row["effective_status"] != "BLOCKED":
                continue
            blocker = "dependency_not_pass:"
            dep_blockers = [b for b in row.get("blockers", []) if b.startswith(blocker)]
            if dep_blockers and all(by_id[d]["effective_status"] == "PASS" for d in row["dependencies"]):
                row["blockers"] = [b for b in row["blockers"] if not b.startswith(blocker)]
                declared = vectors[row["vector_id"]]["declared_status"]
                row["effective_status"] = declared
    final_status = {
        row["vector_id"]: ("PASS" if row["vector_id"] in completed_set else row["effective_status"])
        for row in rec["vectors"]
    }
    ready_residue = sorted(key for key, status in final_status.items() if status == "READY")
    bounded_exhausted = not ready_residue
    return {
        "created_at_utc": utc_now(),
        "apply": apply,
        "passes": passes,
        "completed": sorted(completed_set),
        "final_status": final_status,
        "ready_residue": ready_residue,
        "bounded_exhausted": bounded_exhausted,
        "sha256": digest({"completed": sorted(completed_set), "final_status": final_status, "ready_residue": ready_residue}),
    }


def certification(
    ledger: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    execution: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    statuses = repository_statuses(ledger, reconciliation)
    vector_statuses = [row["effective_status"] for row in reconciliation["vectors"]]
    execution_ready_residue = list((execution or {}).get("ready_residue", []))
    if "FAIL" in vector_statuses:
        state = "FAIL"
    elif execution_ready_residue:
        state = "OPEN"
    elif any(status in {"UNRESOLVED", "BLOCKED", "OPEN"} for status in vector_statuses):
        state = "PROVISIONAL"
    else:
        state = "PASS"
    return {
        "created_at_utc": utc_now(),
        "certification": state,
        "scope": "frozen_snapshot_and_declared_vector_universe_only",
        "bounded_exhaustion": not execution_ready_residue,
        "universal_exhaustion_claimed": False,
        "repository_status": statuses,
        "vector_count": len(vector_statuses),
        "ready_residue": execution_ready_residue,
        "ledger_sha256": validate_ledger(ledger)["ledger_sha256"],
    }


def write_receipt(receipt: Mapping[str, Any], root: Path = DEFAULT_RECEIPT_ROOT) -> Path:
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root.mkdir(parents=True, exist_ok=True)
    target = root / ("%s_%s.json" % (run_id, digest(receipt)[:12]))
    fd, tmp_name = tempfile.mkstemp(prefix=".fed-receipt-", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def _load_receipt(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FedError("invalid_receipt:%s:%s" % (path, exc)) from exc


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fed", description="Fail-closed federation development-vector controller")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--root", type=Path, default=Path(".."), help="parent directory containing federation repo checkouts")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    snap = sub.add_parser("snapshot")
    snap.add_argument("--remote", action="store_true", help="verify expected main SHAs via authenticated gh api")
    sub.add_parser("ingest-vectors")
    sub.add_parser("reconcile")
    sub.add_parser("plan")
    sub.add_parser("status")
    sub.add_parser("verify")
    run = sub.add_parser("run")
    run.add_argument("vector_id", nargs="?")
    run.add_argument("--ready", action="store_true")
    run.add_argument("--apply", action="store_true")
    resume = sub.add_parser("resume")
    resume.add_argument("receipt", type=Path)
    resume.add_argument("--apply", action="store_true")
    sub.add_parser("certify")
    pickup = sub.add_parser("pickup")
    pickup.add_argument("--remote", action="store_true")
    maxp = sub.add_parser("max")
    maxp.add_argument("--apply", action="store_true")
    maxp.add_argument("--remote", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ledger = load_ledger(args.ledger)
        if args.command == "doctor":
            _print(doctor(ledger))
            return 0
        if args.command == "ingest-vectors":
            _print(validate_ledger(ledger))
            return 0

        if args.command == "snapshot":
            snap = snapshot_remote(ledger) if args.remote else snapshot_local(ledger, args.root)
            _print(snap)
            return 0

        snap = snapshot_local(ledger, args.root)
        reconciliation = reconcile(ledger, snap)

        if args.command == "reconcile":
            _print(reconciliation)
            return 0
        if args.command == "plan":
            _print(build_plan(ledger, reconciliation))
            return 0
        if args.command == "status":
            _print(repository_statuses(ledger, reconciliation))
            return 0
        if args.command == "verify":
            result = {
                "doctor": doctor(ledger),
                "snapshot": snap,
                "reconciliation": reconciliation,
                "plan": build_plan(ledger, reconciliation),
                "status": repository_statuses(ledger, reconciliation),
            }
            _print(result)
            return 0

        if args.command == "run":
            if args.vector_id and args.ready:
                raise FedError("choose_vector_id_or_ready_not_both")
            if args.vector_id:
                vectors = vector_index(ledger)
                if args.vector_id not in vectors:
                    raise FedError("unknown_vector:%s" % args.vector_id)
                rec_map = {row["vector_id"]: row for row in reconciliation["vectors"]}
                row = rec_map[args.vector_id]
                if row["effective_status"] != "READY":
                    raise FedError("vector_not_ready:%s:%s" % (args.vector_id, row["effective_status"]))
                result = _execute_vector(vectors[args.vector_id], args.root, args.apply)
            elif args.ready:
                result = run_ready(ledger, reconciliation, args.root, args.apply)
            else:
                raise FedError("run_requires_vector_id_or_--ready")
            _print(result)
            return 1 if result.get("status") == "FAIL" else 0

        if args.command == "resume":
            prior = _load_receipt(args.receipt)
            completed = prior.get("execution", {}).get("completed", [])
            execution = run_max(ledger, reconciliation, args.root, args.apply, completed=completed)
            cert = certification(ledger, reconciliation, execution)
            receipt = {
                "schema_version": "fed_resume_receipt_v1",
                "resumed_from": str(args.receipt),
                "ledger_sha256": validate_ledger(ledger)["ledger_sha256"],
                "snapshot": snap,
                "reconciliation": reconciliation,
                "execution": execution,
                "certification": cert,
            }
            path = write_receipt(receipt)
            receipt["receipt_path"] = str(path)
            _print(receipt)
            return 1 if cert["certification"] == "FAIL" else 0

        if args.command == "certify":
            cert = certification(ledger, reconciliation)
            _print(cert)
            return 1 if cert["certification"] == "FAIL" else 0

        if args.command in {"pickup", "max"}:
            if getattr(args, "remote", False):
                snap = snapshot_remote(ledger)
                reconciliation = reconcile(ledger, snap)
            plan = build_plan(ledger, reconciliation)
            statuses = repository_statuses(ledger, reconciliation)
            execution = None
            if args.command == "max":
                execution = run_max(ledger, reconciliation, args.root, args.apply)
            cert = certification(ledger, reconciliation, execution)
            receipt = {
                "schema_version": "fed_pickup_receipt_v1",
                "command": args.command,
                "ledger_sha256": validate_ledger(ledger)["ledger_sha256"],
                "snapshot": snap,
                "reconciliation": reconciliation,
                "plan": plan,
                "repository_status": statuses,
                "execution": execution,
                "certification": cert,
            }
            path = write_receipt(receipt)
            receipt["receipt_path"] = str(path)
            _print(receipt)
            return 1 if cert["certification"] == "FAIL" else 0
        raise FedError("unsupported_command:%s" % args.command)
    except FedError as exc:
        _print({"status": "FAIL", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Safety wrapper for the installed ``fed`` command.

Remote or mutating execution must bind every configured owner/repo name back to
its frozen stable GitHub repository ID before the core controller is entered.
For MAX/resume, this wrapper also normalizes the repository rollup to the
post-execution vector states before exposing or freezing the receipt.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

from fed_control import main as core_main


class RemoteIdentityError(RuntimeError):
    pass


_REPO_STATUS_PRECEDENCE = ("FAIL", "UNRESOLVED", "BLOCKED", "READY", "OPEN", "PASS")
_REPO_STATUSES = {"READY", "BLOCKED", "OPEN", "PASS", "FAIL", "UNRESOLVED"}


def _ledger_path(argv: Sequence[str]) -> Path:
    for index, token in enumerate(argv):
        if token == "--ledger":
            try:
                return Path(argv[index + 1])
            except IndexError as exc:
                raise RemoteIdentityError("--ledger_requires_path") from exc
        if token.startswith("--ledger="):
            return Path(token.split("=", 1)[1])
    return Path("registry/development_vectors.yaml")


def _requires_remote_identity(argv: Sequence[str]) -> bool:
    return "--remote" in argv or "--apply" in argv


def _command_name(argv: Sequence[str]) -> Optional[str]:
    skip_next = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token in {"--ledger", "--root"}:
            skip_next = True
            continue
        if token.startswith("--ledger=") or token.startswith("--root="):
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def validate_remote_identity_rows(
    repositories: Sequence[Mapping[str, Any]],
    observed_ids: Mapping[str, int],
) -> None:
    expected_names = {str(row["repo"]) for row in repositories}
    observed_names = set(observed_ids)
    if observed_names != expected_names:
        raise RemoteIdentityError(
            "remote_identity_universe_mismatch:missing=%s:extra=%s"
            % (sorted(expected_names - observed_names), sorted(observed_names - expected_names))
        )
    for row in repositories:
        repo = str(row["repo"])
        expected_id = int(row["repo_id"])
        observed_id = int(observed_ids[repo])
        if observed_id != expected_id:
            raise RemoteIdentityError(
                "remote_repository_id_mismatch:%s:expected=%s:observed=%s"
                % (repo, expected_id, observed_id)
            )


def fetch_remote_repository_ids(repositories: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    observed: dict[str, int] = {}
    for row in repositories:
        repo = str(row["repo"])
        proc = subprocess.run(
            ["gh", "api", "repos/%s" % repo, "--jq", ".id"],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode:
            raise RemoteIdentityError("remote_repository_lookup_failed:%s:%s" % (repo, proc.stderr.strip()))
        try:
            observed[repo] = int(proc.stdout.strip())
        except ValueError as exc:
            raise RemoteIdentityError("remote_repository_id_invalid:%s:%s" % (repo, proc.stdout.strip())) from exc
    return observed


def _load_ledger_for_wrapper(ledger_path: Path) -> dict[str, Any]:
    try:
        ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RemoteIdentityError("remote_identity_ledger_unreadable:%s:%s" % (ledger_path, exc)) from exc
    if not isinstance(ledger, dict):
        raise RemoteIdentityError("remote_identity_ledger_root_invalid:%s" % ledger_path)
    return ledger


def validate_remote_identities(ledger_path: Path) -> None:
    try:
        ledger = _load_ledger_for_wrapper(ledger_path)
        repositories = ledger["snapshot"]["repositories"]
    except (KeyError, TypeError) as exc:
        raise RemoteIdentityError("remote_identity_ledger_unreadable:%s:%s" % (ledger_path, exc)) from exc
    observed = fetch_remote_repository_ids(repositories)
    validate_remote_identity_rows(repositories, observed)


def _post_execution_repository_status(
    ledger: Mapping[str, Any],
    final_status: Mapping[str, str],
) -> dict[str, Any]:
    repositories = ledger.get("snapshot", {}).get("repositories", [])
    vectors = ledger.get("vectors", [])
    repo_names = [str(row["repo"]) for row in repositories]
    grouped: dict[str, list[str]] = {repo: [] for repo in repo_names}
    vector_repo: dict[str, str] = {}
    for vector in vectors:
        vector_id = str(vector["vector_id"])
        repo = str(vector["repo"])
        if repo not in grouped:
            raise RemoteIdentityError("post_execution_vector_repo_outside_snapshot:%s:%s" % (vector_id, repo))
        if vector_id in vector_repo:
            raise RemoteIdentityError("post_execution_duplicate_vector_id:%s" % vector_id)
        vector_repo[vector_id] = repo

    if set(final_status) != set(vector_repo):
        raise RemoteIdentityError(
            "post_execution_vector_universe_mismatch:missing=%s:extra=%s"
            % (sorted(set(vector_repo) - set(final_status)), sorted(set(final_status) - set(vector_repo)))
        )

    for vector_id, status in final_status.items():
        if status not in _REPO_STATUSES:
            raise RemoteIdentityError("post_execution_invalid_status:%s:%s" % (vector_id, status))
        grouped[vector_repo[vector_id]].append(status)

    counts = {status: 0 for status in _REPO_STATUSES}
    rows = []
    for repo in sorted(grouped):
        statuses = grouped[repo]
        if not statuses:
            final = "UNRESOLVED"
        else:
            final = next(
                (status for status in _REPO_STATUS_PRECEDENCE if status in statuses),
                "UNRESOLVED",
            )
        counts[final] += 1
        rows.append({"repo": repo, "status": final, "vector_statuses": sorted(statuses)})

    classified = sum(counts.values())
    expected = len(repo_names)
    if classified != expected:
        raise RemoteIdentityError(
            "post_execution_repository_arithmetic_failed:classified=%s:repos=%s"
            % (classified, expected)
        )
    return {
        "phase": "post_execution",
        "repository_count": expected,
        "classified_count": classified,
        "counts": {key: counts[key] for key in sorted(counts)},
        "arithmetic": "%s=%s" % (classified, expected),
        "arithmetic_ok": True,
        "repositories": rows,
    }


def _atomic_rewrite_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fed-receipt-rewrite-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _normalize_execution_receipt(payload: dict[str, Any], ledger_path: Path) -> dict[str, Any]:
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return payload
    final_status = execution.get("final_status")
    if not isinstance(final_status, dict):
        return payload

    ledger = _load_ledger_for_wrapper(ledger_path)
    post = _post_execution_repository_status(ledger, final_status)
    payload["repository_status"] = post
    certification = payload.get("certification")
    if isinstance(certification, dict):
        certification["repository_status"] = post
        certification["repository_status_phase"] = "post_execution"

    receipt_path = payload.get("receipt_path")
    if isinstance(receipt_path, str) and receipt_path:
        path = Path(receipt_path)
        try:
            frozen = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RemoteIdentityError("post_execution_receipt_unreadable:%s:%s" % (path, exc)) from exc
        frozen["repository_status"] = post
        frozen_certification = frozen.get("certification")
        if isinstance(frozen_certification, dict):
            frozen_certification["repository_status"] = post
            frozen_certification["repository_status_phase"] = "post_execution"
        _atomic_rewrite_json(path, frozen)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    ledger_path = _ledger_path(args)
    if _requires_remote_identity(args):
        try:
            validate_remote_identities(ledger_path)
        except RemoteIdentityError as exc:
            print('{"status":"FAIL","error":"%s"}' % str(exc).replace('"', "'"))
            return 2

    command = _command_name(args)
    if command not in {"max", "resume"}:
        return core_main(args)

    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        result_code = core_main(args)
    raw = capture.getvalue().strip()
    if not raw:
        return result_code
    try:
        payload = json.loads(raw)
        payload = _normalize_execution_receipt(payload, ledger_path)
    except (json.JSONDecodeError, RemoteIdentityError) as exc:
        print(json.dumps({"status": "FAIL", "error": "post_execution_normalization_failed:%s" % exc}))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())

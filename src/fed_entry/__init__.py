"""Safety wrapper for the installed ``fed`` command.

Remote or mutating execution must bind every configured owner/repo name back to
its frozen stable GitHub repository ID before the core controller is entered.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

from fed_control import main as core_main


class RemoteIdentityError(RuntimeError):
    pass


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


def validate_remote_identities(ledger_path: Path) -> None:
    try:
        ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
        repositories = ledger["snapshot"]["repositories"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise RemoteIdentityError("remote_identity_ledger_unreadable:%s:%s" % (ledger_path, exc)) from exc
    observed = fetch_remote_repository_ids(repositories)
    validate_remote_identity_rows(repositories, observed)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _requires_remote_identity(args):
        try:
            validate_remote_identities(_ledger_path(args))
        except RemoteIdentityError as exc:
            print('{"status":"FAIL","error":"%s"}' % str(exc).replace('"', "'"))
            return 2
    return core_main(args)


if __name__ == "__main__":
    raise SystemExit(main())

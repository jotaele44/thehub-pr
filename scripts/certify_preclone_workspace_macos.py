#!/usr/bin/env python3
"""Certify a clean seven-repository PRII workspace on macOS.

The script performs real network clones and local dependency installation into
one private ``.venv`` per repository. It never deletes an existing directory,
never installs into system Python, and can pin every checkout to an exact
certification commit without moving any pull-request branch.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hub.fetch import GIT_URL  # noqa: E402
from hub.registry import load_registry  # noqa: E402
from hub.workspace import (  # noqa: E402
    CANONICAL_PYTHON,
    WorkspaceError,
    bootstrap_local,
    clone_workspace,
    repository_specs,
    validate_workspace,
)


def _run_stdout(command, cwd=None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _run(command, cwd=None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _require_clean_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise WorkspaceError(f"certification root must be absent or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)


def _python_version(executable: str) -> str:
    return _run_stdout(
        [
            executable,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ]
    )


def _heads(registry, root: Path) -> Dict[str, str]:
    return {
        spec.program_id: _run_stdout(
            ["git", "rev-parse", "HEAD"], cwd=str(root / spec.name)
        )
        for spec in repository_specs(registry)
    }


def _expected_heads(path: Path | None) -> Dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: Dict[str, str] = {}
    for item in payload.get("repositories", []):
        program_id = item.get("program_id")
        revision = (
            item.get("certification_head")
            or item.get("target_head")
            or item.get("main_head")
        )
        if not program_id or not revision:
            raise WorkspaceError(
                "each expected-head entry requires program_id and a certification revision"
            )
        result[str(program_id)] = str(revision)
    return result


def _clone_exact_workspace(
    registry,
    root: Path,
    revisions: Mapping[str, str],
    *,
    depth: int,
) -> list[dict]:
    """Clone every repository at an exact detached commit, Hub first."""
    specs = repository_specs(registry)
    expected_ids = {spec.program_id for spec in specs}
    missing = sorted(expected_ids - set(revisions))
    extra = sorted(set(revisions) - expected_ids)
    if missing or extra:
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if extra:
            detail.append("unknown=" + ",".join(extra))
        raise WorkspaceError("invalid exact-head ledger: " + "; ".join(detail))

    receipts = []
    for spec in specs:
        destination = root / spec.name
        if destination.exists():
            raise WorkspaceError(
                f"exact certification destination already exists: {destination}"
            )
        destination.mkdir(parents=False)
        revision = revisions[spec.program_id]
        _run(["git", "init", "--quiet"], cwd=str(destination))
        _run(
            [
                "git",
                "remote",
                "add",
                "origin",
                GIT_URL.format(repo=spec.repository),
            ],
            cwd=str(destination),
        )
        _run(
            [
                "git",
                "fetch",
                "--depth",
                str(depth),
                "--quiet",
                "origin",
                revision,
            ],
            cwd=str(destination),
        )
        _run(
            ["git", "checkout", "--detach", "--quiet", "FETCH_HEAD"],
            cwd=str(destination),
        )
        observed = _run_stdout(["git", "rev-parse", "HEAD"], cwd=str(destination))
        if observed != revision:
            raise WorkspaceError(
                f"exact checkout mismatch for {spec.program_id}: "
                f"expected {revision}, observed {observed}"
            )
        receipts.append(
            {
                "program_id": spec.program_id,
                "repository": spec.repository,
                "revision": revision,
                "path": str(destination),
                "status": "passed",
            }
        )
    return receipts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", required=True, help="new or empty neutral workspace directory"
    )
    parser.add_argument("--registry", default=str(ROOT / "registry/producers.yaml"))
    parser.add_argument("--python", default="python3.11")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--expected-heads", type=Path)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("reports/preclone_workspace/macos_certification.json"),
    )
    args = parser.parse_args(argv)

    receipt = {
        "schema_version": "prii_macos_preclone_certification_v2",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "root": str(Path(args.root).expanduser().resolve()),
        "canonical_python": CANONICAL_PYTHON,
        "status": "failed",
        "steps": [],
    }

    try:
        if platform.system() != "Darwin":
            raise WorkspaceError("macOS certification must run on Darwin")
        selected = _python_version(args.python)
        if selected != CANONICAL_PYTHON:
            raise WorkspaceError(
                f"expected Python {CANONICAL_PYTHON}, found {selected} via {args.python}"
            )
        receipt["python_executable"] = args.python
        receipt["python_version"] = selected

        root = Path(args.root).expanduser().resolve()
        _require_clean_root(root)
        registry = load_registry(args.registry)
        expected = _expected_heads(args.expected_heads)

        if expected:
            clone_receipts = _clone_exact_workspace(
                registry, root, expected, depth=args.depth
            )
            receipt["clone_mode"] = "exact_detached_commits"
            receipt["exact_clone_receipts"] = clone_receipts
        else:
            clone_receipts = clone_workspace(registry, root, depth=args.depth)
            receipt["clone_mode"] = "default_branches"
        receipt["steps"].append(
            {"name": "clone", "status": "passed", "count": len(clone_receipts)}
        )

        initial = validate_workspace(registry, root)
        if not initial["valid"]:
            raise WorkspaceError(
                "post-clone validation failed: " + "; ".join(initial["errors"])
            )
        receipt["steps"].append(
            {"name": "post_clone_validate", "status": "passed"}
        )

        observed_heads = _heads(registry, root)
        receipt["observed_heads"] = observed_heads
        if expected:
            mismatches = {
                key: {"expected": value, "observed": observed_heads.get(key)}
                for key, value in expected.items()
                if observed_heads.get(key) != value
            }
            if mismatches:
                receipt["head_mismatches"] = mismatches
                raise WorkspaceError(
                    f"head pin mismatch in {len(mismatches)} repository(s)"
                )
            receipt["steps"].append({"name": "head_pins", "status": "passed"})

        bootstrap_receipts = bootstrap_local(
            registry,
            root,
            python_executable=args.python,
        )
        receipt["steps"].append(
            {
                "name": "bootstrap_local",
                "status": "passed",
                "count": len(bootstrap_receipts),
            }
        )

        final = validate_workspace(registry, root)
        if not final["valid"]:
            raise WorkspaceError(
                "post-bootstrap validation failed: " + "; ".join(final["errors"])
            )
        receipt["workspace_validation"] = final
        receipt["steps"].append(
            {"name": "post_bootstrap_validate", "status": "passed"}
        )
        receipt["status"] = "passed"
        return_code = 0
    except (
        WorkspaceError,
        subprocess.CalledProcessError,
        OSError,
        ValueError,
    ) as exc:
        receipt["error"] = str(exc)
        return_code = 1
    finally:
        receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
        output = args.receipt
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

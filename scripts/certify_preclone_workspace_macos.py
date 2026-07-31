#!/usr/bin/env python3
"""Certify a clean seven-repository PRII workspace on macOS.

The script is intentionally operator-run: it performs real network clones and
local dependency installation into one private ``.venv`` per repository. It
never deletes an existing directory and never installs into system Python.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
    return {
        item["program_id"]: item["main_head"]
        for item in payload.get("repositories", [])
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="new or empty neutral workspace directory")
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
        "schema_version": "prii_macos_preclone_certification_v1",
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

        clone_receipts = clone_workspace(registry, root, depth=args.depth)
        receipt["steps"].append(
            {"name": "clone", "status": "passed", "count": len(clone_receipts)}
        )

        initial = validate_workspace(registry, root)
        if not initial["valid"]:
            raise WorkspaceError("post-clone validation failed: " + "; ".join(initial["errors"]))
        receipt["steps"].append({"name": "post_clone_validate", "status": "passed"})

        observed_heads = _heads(registry, root)
        receipt["observed_heads"] = observed_heads
        expected = _expected_heads(args.expected_heads)
        if expected:
            mismatches = {
                key: {"expected": value, "observed": observed_heads.get(key)}
                for key, value in expected.items()
                if observed_heads.get(key) != value
            }
            if mismatches:
                receipt["head_mismatches"] = mismatches
                raise WorkspaceError(f"head pin mismatch in {len(mismatches)} repository(s)")
            receipt["steps"].append({"name": "head_pins", "status": "passed"})

        bootstrap_receipts = bootstrap_local(
            registry,
            root,
            python_executable=args.python,
        )
        receipt["steps"].append(
            {"name": "bootstrap_local", "status": "passed", "count": len(bootstrap_receipts)}
        )

        final = validate_workspace(registry, root)
        if not final["valid"]:
            raise WorkspaceError("post-bootstrap validation failed: " + "; ".join(final["errors"]))
        receipt["workspace_validation"] = final
        receipt["steps"].append({"name": "post_bootstrap_validate", "status": "passed"})
        receipt["status"] = "passed"
        return_code = 0
    except (WorkspaceError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        receipt["error"] = str(exc)
        return_code = 1
    finally:
        receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
        output = args.receipt
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

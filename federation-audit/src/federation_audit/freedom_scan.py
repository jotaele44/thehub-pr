from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

AXES = (
    "COST_FREE",
    "SERVICE_INDEPENDENT",
    "SELF_CONTAINED_RELEASE",
    "OFFLINE_REPRODUCIBLE_BUILD",
)
ACTION = re.compile(r"^\s*uses:\s*([^\s#]+)")
SHA40 = re.compile(r"^[0-9a-f]{40}$", re.I)
REMOTE = re.compile(r"(?:git\+)?https?://|github\.com", re.I)
MANIFESTS = {"package.json", "pyproject.toml", "requirements.txt", "requirements.in"}


def _glob(path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern)
        or (pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]))
        for pattern in patterns
    )


def _id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def _finding(
    repo: dict[str, Any],
    rule: str,
    axes: list[str] | tuple[str, ...],
    severity: str,
    classification: str,
    path: str,
    line: int,
    raw: str,
    rationale: str,
) -> dict[str, Any]:
    evidence = raw.rstrip("\r\n")
    return {
        "finding_id": _id(
            repo["repository"], repo["commit"], rule, path, str(line), evidence
        ),
        "repository": repo["repository"],
        "commit": repo["commit"],
        "rule_id": rule,
        "axes": list(axes),
        "severity": severity,
        "classification": classification,
        "status": "OPEN",
        "path": path,
        "line": line,
        "raw_evidence": evidence,
        "rationale": rationale,
    }


def _text_files(root: Path, policy: dict[str, Any]):
    scan = policy["scan"]
    ignored = set(scan["ignored_directories"])
    suffixes = set(scan["authored_suffixes"])
    names = set(scan["exact_names"])
    for path in sorted(root.rglob("*")):
        rel_path = path.relative_to(root)
        if not path.is_file() or any(part in ignored for part in rel_path.parts):
            continue
        if path.name in names or path.suffix.lower() in suffixes:
            yield path


def _regex_findings(
    root: Path, repo: dict[str, Any], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    findings: list[dict[str, Any]] = []
    scanned = raw_preserved = 0
    errors: list[str] = []
    rules = [(rule, re.compile(rule["pattern"], re.I)) for rule in policy["rules"]]
    raw_globs = policy["scan"]["raw_evidence_globs"]
    for path in _text_files(root, policy):
        rel = path.relative_to(root).as_posix()
        if _glob(rel, raw_globs):
            raw_preserved += 1
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        scanned += 1
        for number, text in enumerate(lines, 1):
            for rule, pattern in rules:
                if not _glob(rel, rule["include_globs"]):
                    continue
                if _glob(rel, rule.get("exclude_globs", [])):
                    continue
                if pattern.search(text):
                    findings.append(
                        _finding(
                            repo,
                            rule["id"],
                            rule["axes"],
                            rule["severity"],
                            rule["classification"],
                            rel,
                            number,
                            text,
                            rule["rationale"],
                        )
                    )
    return findings, scanned, raw_preserved, errors


def _package_findings(
    root: Path, repo: dict[str, Any], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    ignored = set(policy["scan"]["ignored_directories"])
    for path in sorted(root.rglob("package.json")):
        relative = path.relative_to(root)
        rel = relative.as_posix()
        if any(part in ignored for part in relative.parts):
            continue
        if _glob(rel, policy["scan"]["raw_evidence_globs"]):
            continue
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                _finding(
                    repo,
                    "FF-SCAN-INVALID-PACKAGE-JSON",
                    AXES,
                    "BLOCKER",
                    "UNRESOLVED",
                    rel,
                    1,
                    str(exc),
                    "An unreadable package manifest blocks classification.",
                )
            )
            continue
        for section in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        ):
            values = package.get(section) or {}
            if not isinstance(values, dict):
                continue
            for name, value in sorted(values.items()):
                spec = str(value).strip()
                if spec.lower() in {"latest", "*", "x"}:
                    findings.append(
                        _finding(
                            repo,
                            "FF-BUILD-FLOATING-SPEC",
                            ("OFFLINE_REPRODUCIBLE_BUILD",),
                            "BLOCKER",
                            "PIN_AND_LOCK",
                            rel,
                            1,
                            f"{section}.{name}={spec}",
                            "Floating dependency specifications are nondeterministic.",
                        )
                    )
                if REMOTE.search(spec) and not spec.startswith("file:"):
                    findings.append(
                        _finding(
                            repo,
                            "FF-BUILD-REMOTE-PACKAGE-SOURCE",
                            ("OFFLINE_REPRODUCIBLE_BUILD",),
                            "BLOCKER",
                            "VENDOR_AND_HASH",
                            rel,
                            1,
                            f"{section}.{name}={spec}",
                            "A remote pin does not preserve bytes for an offline rebuild.",
                        )
                    )
    return findings


def _python_manifest_findings(
    root: Path, repo: dict[str, Any], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name not in {
            "pyproject.toml",
            "requirements.txt",
            "requirements.in",
        }:
            continue
        rel = path.relative_to(root).as_posix()
        if _glob(rel, policy["scan"]["raw_evidence_globs"]):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, text in enumerate(lines, 1):
            stripped = text.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if REMOTE.search(stripped):
                findings.append(
                    _finding(
                        repo,
                        "FF-BUILD-REMOTE-PYTHON-SOURCE",
                        ("OFFLINE_REPRODUCIBLE_BUILD",),
                        "BLOCKER",
                        "VENDOR_AND_HASH",
                        rel,
                        number,
                        text,
                        "A remote Python source pin does not preserve dependency bytes.",
                    )
                )
            if path.name in {"requirements.txt", "requirements.in"} and re.match(
                r"pytest(?:-cov)?(?:\b|[<>=!~])", stripped, re.I
            ):
                findings.append(
                    _finding(
                        repo,
                        "FF-DEPENDENCY-PLANE-MIX",
                        ("SELF_CONTAINED_RELEASE", "OFFLINE_REPRODUCIBLE_BUILD"),
                        "BLOCKER",
                        "MOVE_TO_DEV_EXTRA",
                        rel,
                        number,
                        text,
                        "Test tooling is declared in the runtime dependency plane.",
                    )
                )
        if path.name != "pyproject.toml":
            continue
        in_project = in_dependencies = False
        for number, text in enumerate(lines, 1):
            stripped = text.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_project = stripped == "[project]"
                in_dependencies = False
                continue
            if in_project and stripped.startswith("dependencies") and "[" in stripped:
                in_dependencies = True
            test_dep = re.search(
                r'["\']pytest(?:-cov)?(?:[<>=!~][^"\']*)?["\']', stripped, re.I
            )
            if in_dependencies and test_dep:
                findings.append(
                    _finding(
                        repo,
                        "FF-DEPENDENCY-PLANE-MIX",
                        ("SELF_CONTAINED_RELEASE", "OFFLINE_REPRODUCIBLE_BUILD"),
                        "BLOCKER",
                        "MOVE_TO_DEV_EXTRA",
                        rel,
                        number,
                        text,
                        "Test tooling is declared in core project dependencies.",
                    )
                )
            if in_dependencies and "]" in stripped:
                in_dependencies = False
    return findings


def _action_findings(root: Path, repo: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return findings
    for path in sorted(workflows.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        rel = path.relative_to(root).as_posix()
        for number, text in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            match = ACTION.match(text)
            if not match:
                continue
            spec = match.group(1)
            if spec.startswith("./") or spec.startswith("docker://"):
                continue
            ref = spec.rsplit("@", 1)[1] if "@" in spec else ""
            if not SHA40.fullmatch(ref):
                findings.append(
                    _finding(
                        repo,
                        "FF-BUILD-UNPINNED-ACTION",
                        ("OFFLINE_REPRODUCIBLE_BUILD",),
                        "BLOCKER",
                        "PIN_AND_LOCK",
                        rel,
                        number,
                        text,
                        "Marketplace actions must use an immutable full commit SHA.",
                    )
                )
    return findings


def _identity(
    root: Path, expected_commit: str, expected_tree: str | None
) -> tuple[bool | None, str | None, bool | None, str | None]:
    if not (root / ".git").exists():
        return None, None, None, None
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, str(exc), False, str(exc)
    return commit == expected_commit, commit, tree == expected_tree, tree


def _states(findings: list[dict[str, Any]]) -> dict[str, str]:
    states = {}
    for axis in AXES:
        relevant = [finding for finding in findings if axis in finding["axes"]]
        if any(finding["severity"] == "BLOCKER" for finding in relevant):
            states[axis] = "FAIL"
        elif relevant:
            states[axis] = "OPEN"
        else:
            states[axis] = "PROVISIONAL"
    return states


def scan_freedom(
    workspace_root: Path, snapshot: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    repositories = []
    all_findings: list[dict[str, Any]] = []
    missing: list[str] = []
    mismatches: list[dict[str, Any]] = []
    for repo in snapshot["repositories"]:
        root = workspace_root / repo["workspace_directory"]
        if not root.is_dir():
            missing.append(repo["workspace_directory"])
            continue
        commit_ok, commit, tree_ok, tree = _identity(
            root, repo["commit"], repo.get("tree")
        )
        if commit_ok is False or tree_ok is False:
            mismatches.append(
                {
                    "repository": repo["repository"],
                    "expected": repo["commit"],
                    "actual": commit,
                    "expected_tree": repo.get("tree"),
                    "actual_tree": tree,
                }
            )
        findings, scanned, raw_count, errors = _regex_findings(root, repo, policy)
        findings += _package_findings(root, repo, policy)
        findings += _python_manifest_findings(root, repo, policy)
        findings += _action_findings(root, repo)
        has_manifest = any(
            path.is_file() and path.name in MANIFESTS for path in root.rglob("*")
        )
        offline_manifest = any(
            (root / path).is_file()
            for path in policy["offline_bundle_manifest_candidates"]
        )
        if has_manifest and not offline_manifest:
            findings.append(
                _finding(
                    repo,
                    "FF-BUILD-NO-OFFLINE-BUNDLE-MANIFEST",
                    ("OFFLINE_REPRODUCIBLE_BUILD",),
                    "BLOCKER",
                    "CREATE_OFFLINE_BUNDLE",
                    ".",
                    0,
                    "no approved offline dependency manifest found",
                    "Lockfiles do not preserve every package, extension, and binary byte.",
                )
            )
        findings = sorted(
            {item["finding_id"]: item for item in findings}.values(),
            key=lambda item: (
                item["rule_id"],
                item["path"],
                item["line"],
                item["finding_id"],
            ),
        )
        all_findings += findings
        repositories.append(
            {
                "id": repo["id"],
                "repository": repo["repository"],
                "expected_commit": repo["commit"],
                "expected_tree": repo.get("tree"),
                "commit_verified": commit_ok,
                "actual_commit": commit,
                "tree_verified": tree_ok,
                "actual_tree": tree,
                "files_scanned": scanned,
                "raw_evidence_files_preserved": raw_count,
                "scan_errors": errors,
                "finding_count": len(findings),
                "axis_states": _states(findings),
                "findings": findings,
            }
        )
    blocking = sum(item["severity"] == "BLOCKER" for item in all_findings)
    total = len(all_findings)
    summary = {
        "repositories_declared": len(snapshot["repositories"]),
        "repositories_present": len(repositories),
        "repositories_missing": len(missing),
        "commits_verified": sum(
            repo["commit_verified"] is True for repo in repositories
        ),
        "trees_verified": sum(repo["tree_verified"] is True for repo in repositories),
        "commit_verification_unavailable": sum(
            repo["commit_verified"] is None for repo in repositories
        ),
        "tree_verification_unavailable": sum(
            repo["tree_verified"] is None for repo in repositories
        ),
        "commit_mismatches": len(mismatches),
        "findings_discovered": total,
        "findings_classified": total,
        "blocking_findings": blocking,
        "raw_evidence_files_preserved": sum(
            repo["raw_evidence_files_preserved"] for repo in repositories
        ),
        "scan_errors": sum(len(repo["scan_errors"]) for repo in repositories),
        "arithmetic_closed": total
        == sum(repo["finding_count"] for repo in repositories),
        "dynamic_gates_executed": 0,
        "dynamic_gates_required": len(policy["dynamic_gates"]),
    }
    return {
        "schema_version": "1.0.0",
        "mode": "STATIC_PRIORITY_DENOMINATOR",
        "snapshot_id": snapshot["snapshot_id"],
        "policy_id": policy["policy_id"],
        "certified": False,
        "certification_state": (
            "FAIL" if blocking or missing or mismatches else "PROVISIONAL"
        ),
        "repositories": repositories,
        "summary": summary,
        "workspace_gaps": missing,
        "commit_mismatches": mismatches,
        "dynamic_gates": [
            {
                "id": gate,
                "status": "BLOCKED",
                "reason": "not executed by static scanner",
            }
            for gate in policy["dynamic_gates"]
        ],
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="federation-freedom-scan")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args(argv)
    result = scan_freedom(
        args.workspace_root.resolve(), _load_json(args.snapshot), _load_json(args.policy)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], sort_keys=True))
    return (
        5
        if args.require_pass
        and result["certification_state"] != "PROVISIONAL"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())

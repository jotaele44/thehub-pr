#!/usr/bin/env python3
"""Compatibility matrix for the federation applications (RC9).

Reads, for each application, one export of a commit and writes what that tree
declares and what its build relies on: toolchain versions, shared-package and
desktop-runtime pins, the browser features that set a browser floor, and the
platforms its own CI names. It reports; it sets no state.

Two things it does not establish:

* A platform named in a workflow file is a platform CI is configured for. The
  script does not know whether those jobs ran or passed.
* The browser versions in FEATURES were written from memory and have not been
  checked against a compatibility source. The floor computed from them is an
  ASSUMPTION until they are.

Usage:
  rc9_matrix.py --targets <targets.json> --observed <observed.json> --out <compatibility_matrix.json>

targets.json:  [{"repository", "commit", "snapshots", "frontend"}], one export per application.
observed.json: {"<repository>": [{"engine", "os", "what", "by"}]}, the runs someone actually made.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Feature -> (pattern over built CSS or JS, first version per engine).
# Versions from memory; see the module docstring.
FEATURES = {
    "css color-mix()": (r"color-mix\(", {"chromium": 111, "firefox": 113, "safari": 16.2}),
    "css oklch()/oklab()": (r"okl(?:ch|ab)\(", {"chromium": 111, "firefox": 113, "safari": 15.4}),
    "css @layer": (r"@layer\b", {"chromium": 99, "firefox": 97, "safari": 15.4}),
    "css :has()": (r":has\(", {"chromium": 105, "firefox": 121, "safari": 15.4}),
    "css @container": (r"@container\b", {"chromium": 105, "firefox": 110, "safari": 16.0}),
    "css @property": (r"@property\b", {"chromium": 85, "firefox": 128, "safari": 16.4}),
    "css dynamic viewport units": (
        r"\d(?:dvh|dvw|svh|lvh)\b",
        {"chromium": 108, "firefox": 101, "safari": 15.4},
    ),
    "css :modal": (r":modal\b", {"chromium": 105, "firefox": 103, "safari": 15.6}),
    "dialog.showModal()": (r"\.showModal\(", {"chromium": 37, "firefox": 98, "safari": 15.4}),
}
PACKAGES = (
    "react",
    "react-dom",
    "react-router-dom",
    "tailwindcss",
    "vite",
    "typescript",
    "@pr-federation/react",
)
# A runner label, taken only from a `runs-on:` value or an `os:` matrix list,
# so file names that merely contain "macos-" are not counted as platforms.
RUNNER_LINE = re.compile(r"^\s*(?:-\s*)?(?:runs-on|os):\s*(.+)$", re.M)
PLATFORM = re.compile(r"\b(ubuntu-[\w.]+|macos-[\w.]+|windows-[\w.-]+)")
ENGINE = re.compile(r"\b(chromium|firefox|webkit)\b")
VERSION = re.compile(r"""(python|node)-version:\s*(\[[^\]]*\]|["']?[\w.]+["']?)""")
PIN = re.compile(r"^(prii[-_][\w-]+)\s*@\s*(\S+)|^-e\s+(packages/prii_\w+)", re.M)


def toolchain(root: Path, frontend: str) -> dict:
    package = json.loads((root / frontend / "package.json").read_text())
    declared = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    pyproject = root / "pyproject.toml"
    requires = (
        re.search(r'requires-python\s*=\s*"([^"]+)"', pyproject.read_text()) if pyproject.exists() else None
    )
    pinned = root / ".python-version"
    return {
        "frontend_packages": {name: declared[name] for name in PACKAGES if name in declared},
        "node_engines": package.get("engines", {}).get("node"),
        "python_requires": requires.group(1) if requires else None,
        "python_version_file": pinned.read_text().strip() if pinned.exists() else None,
    }


def ci(root: Path) -> dict:
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    platforms: dict[str, set] = {}
    engines: dict[str, set] = {}
    versions: dict[str, set] = {"python": set(), "node": set()}
    for workflow in workflows:
        text = workflow.read_text()
        for value in RUNNER_LINE.findall(text):
            for platform in PLATFORM.findall(value):
                platforms.setdefault(platform.rstrip(".,"), set()).add(workflow.name)
        # Only a workflow that installs or selects a browser counts.
        if re.search(r"playwright|GUI_ENGINES|browser", text, re.I):
            for engine in ENGINE.findall(text):
                engines.setdefault(engine, set()).add(workflow.name)
        for tool, value in VERSION.findall(text):
            versions[tool].update(re.findall(r"\d+(?:\.\d+)*", value))

    def order(values: set) -> list:
        return sorted(values, key=lambda version: [int(part) for part in version.split(".")])

    return {
        "workflows": len(workflows),
        "platforms_named": {name: len(files) for name, files in sorted(platforms.items())},
        "browser_engines_named": {name: sorted(files) for name, files in sorted(engines.items())},
        "python_versions_named": order(versions["python"]),
        "node_versions_named": order(versions["node"]),
    }


def pins(root: Path) -> dict:
    path = root / "requirements-desktop.txt"
    if not path.exists():
        return {"file": None, "pins": []}
    found = []
    for name, target, editable in PIN.findall(path.read_text()):
        if editable:
            found.append({"name": Path(editable).name, "source": "this repository", "ref": "editable"})
        else:
            commit = re.search(r"[0-9a-f]{40}", target)
            found.append({"name": name, "source": "thehub-pr", "ref": commit.group(0) if commit else target})
    return {"file": "requirements-desktop.txt", "pins": found}


def browser_floor(dist: Path) -> dict:
    if not dist.is_dir():
        return {"build": "not built", "features": [], "floor": None}
    text = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(dist.rglob("*"))
        if path.suffix in (".css", ".js", ".mjs")
    )
    used = [name for name, (pattern, _) in FEATURES.items() if re.search(pattern, text)]
    floor = {
        engine: max((FEATURES[name][1][engine] for name in used), default=None)
        for engine in ("chromium", "firefox", "safari")
    }
    return {"build": "scanned", "features": used, "floor": floor}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("targets", "observed", "out"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    observed = json.loads(Path(args.observed).read_text())
    rows = []
    for target in json.loads(Path(args.targets).read_text()):
        root = Path(target["snapshots"]) / target["repository"]
        tools = toolchain(root, target["frontend"])
        design = tools["frontend_packages"].get("@pr-federation/react")
        release = re.search(r"federation-design-v([\w.-]+?)/", design or "")
        rows.append(
            {
                "repository": target["repository"],
                "commit": target["commit"],
                "toolchain": tools,
                "design_system": {
                    "pin": "none"
                    if design is None
                    else "source"
                    if design.startswith("file:")
                    else "release",
                    "version": release.group(1) if release else None,
                    "spec": design,
                },
                "desktop_runtime": pins(root),
                "experience_contract": {
                    "adopted": (root / ".federation" / "experience-contract.json").exists(),
                    "note": "No application has declared a contract; the RC2 schemas are unadopted.",
                },
                "browser_floor_from_build": browser_floor(root / target["frontend"] / "dist"),
                "ci_configuration": ci(root),
                "observed_runs": observed.get(target["repository"], []),
            }
        )
    document = {
        "schema": "federation.experience-program.compatibility-matrix/1",
        "claim_classes": {
            "toolchain, design_system, desktop_runtime, ci_configuration": "FACT (read from the tree)",
            "browser_floor_from_build.features": "COMPUTED (pattern scan of the built CSS and JS)",
            "browser_floor_from_build.floor": "ASSUMPTION (browser versions written from memory, unchecked)",
            "observed_runs": "FACT (each names who ran it and what)",
        },
        "reading": [
            "ci_configuration lists platforms and engines that workflow files name. It does not say those "
            "jobs ran or passed.",
            "observed_runs lists runs that were actually made. An engine or operating system absent from it "
            "was not run against that application.",
            "The RC2 compatibility schema describes a declaration an application makes when it adopts the "
            "contract. None has, so no row here is, or can be validated as, such a declaration.",
        ],
        "feature_first_versions_assumed": {name: versions for name, (_, versions) in FEATURES.items()},
        "applications": rows,
    }
    Path(args.out).write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    for row in rows:
        packages = row["toolchain"]["frontend_packages"]
        print(
            row["repository"],
            packages.get("react"),
            packages.get("tailwindcss"),
            row["design_system"]["pin"],
            row["design_system"]["version"],
            row["browser_floor_from_build"]["floor"],
            sorted(row["ci_configuration"]["browser_engines_named"]),
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""How far each producer lags the hub's shared templates and desktop runtime.

Every producer's template-drift gate compares it with the hub commit *that
producer* pinned (``PRII_TEMPLATE_REF``), and its desktop app installs
``prii-desktop`` from the hub commit named in its ``requirements-desktop.txt``.
Both stay green however old the pins are, so a hub change that producers never
picked up is invisible from either side. This report makes it visible:

* ``prii-desktop`` pin in the producer against the pin in
  ``federation-templates/requirements-desktop.txt``;
* ``PRII_TEMPLATE_REF`` and how many hub commits it is behind ``HEAD`` (needs
  full history; ``unknown`` in a shallow clone);
* whether the producer declares a Launch Pad (``LAUNCHPAD`` in
  ``desktop/config.py``).

Producer files are read from sibling checkouts with ``--root`` (offline), or
from each repository's ``main`` branch on GitHub otherwise. The report is
advisory: it exits 0 unless ``--strict`` is given and a desktop producer runs an
older ``prii-desktop`` than the template pins.

    python tools/federation_pin_report.py              # table, from GitHub
    python tools/federation_pin_report.py --root ..    # table, from checkouts
    python tools/federation_pin_report.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

HUB_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = HUB_ROOT / "federation-templates"
HUB = "thehub-pr"
OWNER = "jotaele44"

_DESKTOP_PIN = re.compile(
    r"^prii-desktop\s*@\s*\S*?(?:archive/|\.git@)(?P<sha>[0-9a-f]{7,40})",
    re.MULTILINE,
)
_TEMPLATE_REF = re.compile(r"PRII_TEMPLATE_REF:\s*['\"]?(?P<sha>[0-9a-f]{7,40})")
_LAUNCHPAD = re.compile(r"^LAUNCHPAD\s*=", re.MULTILINE)

Reader = Callable[[str, str], "str | None"]


def desktop_pin(text: str | None) -> str | None:
    match = _DESKTOP_PIN.search(text or "")
    return match.group("sha") if match else None


def template_ref(text: str | None) -> str | None:
    match = _TEMPLATE_REF.search(text or "")
    return match.group("sha") if match else None


def declares_launchpad(text: str | None) -> bool:
    return bool(_LAUNCHPAD.search(text or ""))


def _same(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    size = min(len(left), len(right))
    return left[:size] == right[:size]


def commits_behind(ref: str | None, repo: Path = HUB_ROOT) -> int | None:
    """Hub commits on HEAD that ``ref`` does not have; None when unknowable."""
    if not ref:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{ref}..HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return int(result.stdout.strip()) if result.returncode == 0 else None


def local_reader(root: Path) -> Reader:
    def read(repo: str, path: str) -> str | None:
        try:
            return (root / repo / path).read_text(encoding="utf-8")
        except OSError:
            return None

    return read


def github_reader(branch: str = "main") -> Reader:
    def read(repo: str, path: str) -> str | None:
        url = f"https://raw.githubusercontent.com/{OWNER}/{repo}/{branch}/{path}"
        try:
            with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    return read


def _targets() -> dict[str, Any]:
    return yaml.safe_load((TEMPLATES / "targets.yaml").read_text(encoding="utf-8"))


def desktop_producers() -> list[str]:
    """Repos that receive the shared requirements-desktop.txt template."""
    for target in _targets()["targets"]:
        if target["template"] == "requirements-desktop.txt":
            return list(target["repos"])
    return []


def producers() -> list[str]:
    data = yaml.safe_load(
        (TEMPLATES / "producers.vars.yaml").read_text(encoding="utf-8")
    )
    return [name for name in data["producers"] if name != HUB]


def build_report(read: Reader) -> dict[str, Any]:
    expected = desktop_pin((TEMPLATES / "requirements-desktop.txt").read_text("utf-8"))
    desktop = set(desktop_producers())
    rows = []
    for repo in producers():
        requirements = read(repo, "requirements-desktop.txt")
        drift = read(repo, ".github/workflows/template-drift.yml")
        config = read(repo, "desktop/config.py")
        pin = desktop_pin(requirements)
        ref = template_ref(drift)
        current = _same(pin, expected)
        rows.append(
            {
                "repo": repo,
                "templated_desktop": repo in desktop,
                "prii_desktop_pin": pin,
                "prii_desktop_current": current,
                "template_ref": ref,
                "template_ref_behind": commits_behind(ref),
                "launchpad": declares_launchpad(config),
                "readable": requirements is not None or drift is not None,
            }
        )
    lagging = [
        row["repo"]
        for row in rows
        if row["templated_desktop"] and not row["prii_desktop_current"]
    ]
    return {
        "schema_version": "prii_federation_pin_report_v1",
        "expected_prii_desktop_pin": expected,
        "producers": rows,
        "lagging_desktop_producers": lagging,
        "launchpad_missing": [
            row["repo"] for row in rows if row["prii_desktop_pin"] and not row["launchpad"]
        ],
    }


def _short(sha: str | None) -> str:
    return sha[:7] if sha else "—"


def render_table(report: dict[str, Any]) -> str:
    lines = [
        f"Template prii-desktop pin: {_short(report['expected_prii_desktop_pin'])}",
        "",
        "| Producer | prii-desktop | Current | PRII_TEMPLATE_REF | Behind | Launch Pad |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["producers"]:
        if not row["readable"]:
            lines.append(f"| {row['repo']} | unreadable | | | | |")
            continue
        behind = row["template_ref_behind"]
        current = "yes" if row["prii_desktop_current"] else "**no**"
        if not row["templated_desktop"]:
            current += " (hand-managed)"
        lines.append(
            f"| {row['repo']} | {_short(row['prii_desktop_pin'])} | {current} | "
            f"{_short(row['template_ref'])} | "
            f"{'unknown' if behind is None else behind} | "
            f"{'yes' if row['launchpad'] else 'no'} |"
        )
    lagging = report["lagging_desktop_producers"]
    lines += [
        "",
        (
            "Lagging desktop producers: " + ", ".join(lagging)
            if lagging
            else "Every templated desktop producer runs the template's prii-desktop."
        ),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, help="read sibling checkouts under ROOT")
    parser.add_argument("--branch", default="main", help="GitHub branch (default main)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--out", type=Path, help="also write the JSON report here")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a templated desktop producer lags the template pin",
    )
    args = parser.parse_args(argv)
    read = local_reader(args.root) if args.root else github_reader(args.branch)
    report = build_report(read)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2) if args.json else render_table(report))
    return 1 if args.strict and report["lagging_desktop_producers"] else 0


if __name__ == "__main__":
    sys.exit(main())

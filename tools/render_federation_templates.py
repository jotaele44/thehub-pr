#!/usr/bin/env python3
"""Render the shared federation boilerplate into each producer repo.

Single-sources the byte-identical / app-slug-parameterized files that used to be
copied per repo: the ``Fix-Gatekeeper.command`` and ``PRII-<APP>.{command,bat,sh}``
launchers, ``requirements-desktop.txt`` (desktop producers), and the shared
``schemas/federation_export_manifest.schema.json`` contract.

Inputs (all under ``thehub-pr/federation-templates/``):
  - the template files (``{{APP_SLUG}}`` is the only placeholder),
  - ``producers.vars.yaml`` — program_id -> {app_slug},
  - ``targets.yaml`` — template -> output path + which repos receive it.

Each producer is a sibling checkout of thehub-pr (federation convention), so the
default target root is ``<thehub-parent>/<program_id>``.

Usage:
  render_federation_templates.py --repo <program_id> [--check] [--repo-root PATH]
  render_federation_templates.py --all               [--check]
    (no --check) writes the rendered files into the target repo(s)
    --check       renders in memory and diffs vs the committed files; exit 1 on drift

Standalone (PyYAML only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]           # thehub-pr/
_TEMPLATES = _REPO_ROOT / "federation-templates"
_PLACEHOLDER = "{{APP_SLUG}}"


def _load(name: str) -> dict:
    return yaml.safe_load((_TEMPLATES / name).read_text(encoding="utf-8")) or {}


def _render_bytes(template: str, slug: str) -> bytes:
    raw = (_TEMPLATES / template).read_bytes()
    if _PLACEHOLDER.encode() in raw:
        raw = raw.replace(_PLACEHOLDER.encode(), slug.encode())
    return raw


def _targets_for(program_id: str, targets: list[dict]) -> list[tuple[str, str]]:
    """Return (template, output_relpath) pairs that apply to this repo."""
    out = []
    for t in targets:
        if program_id in t["repos"]:
            out.append((t["template"], t["output"]))
    return out


def render_repo(program_id: str, slug: str, repo_root: Path, targets: list[dict],
                check: bool) -> list[str]:
    """Write (or --check) every target for one repo. Returns list of drifted paths."""
    drift = []
    for template, output_tmpl in _targets_for(program_id, targets):
        content = _render_bytes(template, slug)
        rel = output_tmpl.replace(_PLACEHOLDER, slug)
        dest = repo_root / rel
        if check:
            current = dest.read_bytes() if dest.exists() else None
            if current != content:
                drift.append(rel)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            # Preserve the executable bit on the shell/command launchers.
            if rel.endswith((".sh", ".command")):
                dest.chmod(0o755)
    return drift


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="program_id of a single producer (e.g. ovnis-pr)")
    g.add_argument("--all", action="store_true", help="render every producer in the vars file")
    ap.add_argument("--check", action="store_true",
                    help="diff rendered output vs committed files; exit 1 on drift")
    ap.add_argument("--repo-root", type=Path, default=None,
                    help="target repo root (default: <thehub-parent>/<program_id>)")
    args = ap.parse_args(argv)

    vars_ = _load("producers.vars.yaml").get("producers", {})
    targets = _load("targets.yaml").get("targets", [])

    repos = list(vars_) if args.all else [args.repo]
    any_drift = False
    for program_id in repos:
        if program_id not in vars_:
            print(f"error: {program_id} not in producers.vars.yaml", file=sys.stderr)
            return 2
        slug = vars_[program_id]["app_slug"]
        root = args.repo_root or (_REPO_ROOT.parent / program_id)
        drift = render_repo(program_id, slug, root, targets, args.check)
        if args.check:
            if drift:
                any_drift = True
                print(f"DRIFT {program_id}: " + ", ".join(drift))
            else:
                print(f"ok    {program_id}: all federation templates match")
        else:
            print(f"rendered {program_id} -> {root}")
    return 1 if any_drift else 0


if __name__ == "__main__":
    raise SystemExit(main())

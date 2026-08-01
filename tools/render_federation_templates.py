#!/usr/bin/env python3
"""Render the shared federation boilerplate into each producer repo.

Single-sources the byte-identical / app-slug-parameterized files that used to be
copied per repo: the ``Fix-Gatekeeper.command`` and ``PRII-<APP>.{command,bat,sh}``
launchers, ``requirements-desktop.txt`` (desktop producers), and the shared
``schemas/federation_export_manifest.schema.json`` contract.

Inputs (all under ``thehub-pr/federation-templates/``):
  - the template files (``{{KEY}}`` placeholders, one per vars key),
  - ``producers.vars.yaml`` — program_id -> {app_slug, npm_dir, ...},
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
import re
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]           # thehub-pr/
_TEMPLATES = _REPO_ROOT / "federation-templates"


def _load(name: str) -> dict:
    return yaml.safe_load((_TEMPLATES / name).read_text(encoding="utf-8")) or {}


def _placeholders(vars_for_repo: dict) -> dict[str, str]:
    """Map ``{{KEY}}`` -> value for one repo's entry in producers.vars.yaml.

    Keys are upper-cased, so ``app_slug`` fills ``{{APP_SLUG}}`` exactly as
    before; any key added to the vars file becomes a placeholder with no code
    change here. Values are stringified so ints (e.g. a Python minor version)
    can be written unquoted in YAML.
    """
    return {f"{{{{{k.upper()}}}}}": str(v) for k, v in vars_for_repo.items()}


def _render_bytes(template: str, subs: dict[str, str]) -> bytes:
    raw = (_TEMPLATES / template).read_bytes()
    for placeholder, value in subs.items():
        if placeholder.encode() in raw:
            raw = raw.replace(placeholder.encode(), value.encode())
    return raw


def _unresolved(raw: bytes) -> list[str]:
    """Any ``{{...}}`` left after substitution — a typo'd or missing var.

    Silently shipping an unsubstituted placeholder into seven repos is the
    failure mode this renderer most needs to catch, so callers treat a non-empty
    result as fatal rather than writing the file.
    """
    return sorted({m.decode() for m in re.findall(rb"\{\{[A-Z0-9_]+\}\}", raw)})


def _mode_for(output_tmpl: str, target: dict) -> int | None:
    """Permission bits the rendered file must carry, or None to leave it alone.

    ``.sh``/``.command`` launchers have always been part of a 0755 contract, so
    that rule stays implicit. An explicit ``mode:`` in targets.yaml extends it to
    outputs the extension rule cannot see — the executable inside a macOS ``.app``
    bundle has no suffix at all, and shipping it non-executable breaks the app
    while its content still matches the template.
    """
    declared = target.get("mode")
    if declared is not None:
        # Both spellings have to work, because both are natural to write here.
        # YAML 1.1 resolves an unquoted ``0755`` to the int 493 — already the
        # mode meant — while a quoted ``"0755"`` arrives as text needing base 8.
        # Round-tripping the int through str() and int(…, 8) instead would raise
        # on the digit 9 and take rendering down with it.
        mode = declared if isinstance(declared, int) else int(declared, 8)
        if not 0 <= mode <= 0o7777:
            raise SystemExit(
                f"error: {output_tmpl}: mode {declared!r} is not a permission "
                "mask — write it as 0755 or \"0755\""
            )
        return mode
    if output_tmpl.endswith((".sh", ".command")):
        return 0o755
    return None


def _targets_for(program_id: str, targets: list[dict]) -> list[tuple[str, str, int | None]]:
    """Return (template, output_relpath, mode) triples that apply to this repo."""
    out = []
    for t in targets:
        if program_id in t["repos"]:
            out.append((t["template"], t["output"], _mode_for(t["output"], t)))
    return out


def render_repo(program_id: str, vars_for_repo: dict, repo_root: Path,
                targets: list[dict], check: bool) -> list[str]:
    """Write (or --check) every target for one repo. Returns list of drifted paths."""
    subs = _placeholders(vars_for_repo)
    drift = []
    for template, output_tmpl, mode in _targets_for(program_id, targets):
        content = _render_bytes(template, subs)
        missing = _unresolved(content)
        if missing:
            raise SystemExit(
                f"error: {program_id}: {template} has unresolved placeholder(s) "
                f"{', '.join(missing)} — add the key to producers.vars.yaml"
            )
        rel = output_tmpl
        for placeholder, value in subs.items():
            rel = rel.replace(placeholder, value)
        dest = repo_root / rel
        if check:
            current = dest.read_bytes() if dest.exists() else None
            drifted = current != content
            # Launchers are part of a 0755 contract (the write path chmods them);
            # a mode-only change that drops the executable bit breaks the
            # double-click launchers on Linux/macOS while content still matches.
            # Only the owner exec bit is compared: git records 100644 vs 100755
            # and nothing finer, and a restrictive umask legitimately checks an
            # executable out as 0700 — so demanding the full mode, or all three
            # exec bits, would flag umask noise. Testing the owner bit rather
            # than "any exec bit" still catches a file left group-executable
            # only (0055), which the owner cannot run.
            if (
                not drifted
                and mode is not None
                and mode & 0o100
                and dest.exists()
                and not (dest.stat().st_mode & 0o100)
            ):
                drifted = True
            if drifted:
                drift.append(rel)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            # write_bytes keeps an existing file's mode, so this also has to run
            # for a first render into a fresh checkout, where the file is created
            # 0644 and would otherwise ship non-executable.
            if mode is not None:
                dest.chmod(mode)
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
        root = args.repo_root or (_REPO_ROOT.parent / program_id)
        drift = render_repo(program_id, vars_[program_id], root, targets, args.check)
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

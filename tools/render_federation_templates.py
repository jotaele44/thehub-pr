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

Two placeholders are derived from targets.yaml instead of read from the vars
file, so the producers' Dependabot config can exclude exactly the files the hub
renders into them (a dependency bumped in a rendered copy breaks that repo's
drift gate, so those bumps happen in the template, never in a copy):

  - ``{{RENDERED_WORKFLOWS}}`` — the ``.github/workflows/`` files rendered into
    the repo, for the github-actions ecosystem;
  - ``{{RENDERED_PIP_MANIFESTS}}`` — the rendered files Dependabot's pip
    ecosystem would read as manifests (``requirements-desktop.txt`` in the
    desktop producers).

Each renders as the inside of a quoted YAML flow sequence. A repo whose list is
empty gets the template line ``<key>: ["{{PLACEHOLDER}}"]`` removed whole rather
than an empty pattern; the placeholder anywhere else is refused.

Each producer is a sibling checkout of thehub-pr (federation convention), so the
default target root is ``<thehub-parent>/<program_id>``.

Usage:
  render_federation_templates.py --repo <program_id> [--check] [--repo-root PATH]
                                  [--template-ref SHA]
  render_federation_templates.py --all               [--check]
                                  [--template-ref SHA]
    (no --check) writes the rendered files into the target repo(s)
    --check       renders in memory and diffs vs the committed files; exit 1 on drift

Standalone (PyYAML only).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]           # thehub-pr/
_TEMPLATES = _REPO_ROOT / "federation-templates"
_TEMPLATE_REF_PATH = Path(".github/workflows/template-drift.yml")
_WORKFLOWS_DIR = ".github/workflows"
# Derived from targets.yaml, not read from producers.vars.yaml (see _subs_for).
_RENDERED_WORKFLOWS = "{{RENDERED_WORKFLOWS}}"
_RENDERED_PIP_MANIFESTS = "{{RENDERED_PIP_MANIFESTS}}"
# What Dependabot's pip ecosystem reads under `directory: "/"`, from
# dependabot-core python/lib/dependabot/python/shared_file_fetcher.rb and
# file_fetcher.rb: *.txt / *.in files at the root and one directory below it
# (req_txt_and_in_files, req_files_for_dir), and these names at the root only.
_PIP_REQUIREMENT_SUFFIXES = (".txt", ".in")
_PIP_ROOT_MANIFESTS = frozenset({
    "Pipfile", "Pipfile.lock", "pdm.lock", "poetry.lock",
    "pyproject.toml", "setup.cfg", "setup.py",
})
_SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]+")
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_TEMPLATE_REF_LINE = re.compile(
    rb"^(?P<prefix>[ \t]*PRII_TEMPLATE_REF:[ \t]*)"
    rb"(?P<sha>[0-9a-f]{40})(?P<suffix>[ \t]*)$",
    re.MULTILINE,
)


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


def _resolve_output(output_tmpl: str, subs: dict[str, str]) -> str:
    """Substitute placeholders (e.g. ``{{APP_SLUG}}``) in a target's output path."""
    rel = output_tmpl
    for placeholder, value in subs.items():
        rel = rel.replace(placeholder, value)
    return rel


def _rendered_paths(program_id: str, targets: list[dict], subs: dict[str, str],
                    kind: str, keep) -> list[str]:
    """Sorted repo-relative outputs rendered into one repo that ``keep`` accepts.

    Shared by the derived Dependabot lists. Each list is spliced into a
    double-quoted YAML string, so a path that needs quoting would corrupt the
    config rather than fail loudly; it is refused instead.
    """
    out = set()
    for _template, output_tmpl, _mode in _targets_for(program_id, targets):
        rel = PurePosixPath(_resolve_output(output_tmpl, subs))
        if not keep(rel):
            continue
        if not _SAFE_PATH.fullmatch(str(rel)):
            raise SystemExit(
                f"error: {program_id}: rendered {kind} path {rel!s} has "
                "characters that cannot be listed in dependabot.yml unescaped"
            )
        out.add(str(rel))
    return sorted(out)


def _rendered_workflows(program_id: str, targets: list[dict],
                        subs: dict[str, str]) -> list[str]:
    """Repo-relative paths of the GitHub workflows rendered into one repo.

    These are the files Dependabot must never edit in a producer: a pin bumped
    in a rendered copy diverges from its template and turns the drift gate red.
    The producers' ``.github/dependabot.yml`` excludes exactly this list, and
    computing it from targets.yaml means a repository that adopts another
    workflow template (``_gui_code``, say) is excluded from bumping it on the
    same render, without anyone having to remember a second list.
    """
    return _rendered_paths(
        program_id, targets, subs, "workflow",
        lambda rel: str(rel.parent) == _WORKFLOWS_DIR and rel.suffix in (".yml", ".yaml"),
    )


def _is_pip_manifest(rel: PurePosixPath) -> bool:
    """Whether Dependabot's pip ecosystem, scanning ``/``, would read ``rel``.

    It reads every ``*.txt`` / ``*.in`` file at the root and one directory
    below it, keeping those named like requirements or whose lines all parse as
    requirements, and a fixed set of manifest names at the root. Excluding a
    rendered ``.txt`` that turns out not to be a manifest costs nothing, so the
    content test is not reproduced here.
    """
    if rel.suffix in _PIP_REQUIREMENT_SUFFIXES and len(rel.parts) <= 2:
        return True
    return len(rel.parts) == 1 and rel.name in _PIP_ROOT_MANIFESTS


def _rendered_pip_manifests(program_id: str, targets: list[dict],
                            subs: dict[str, str]) -> list[str]:
    """Repo-relative paths of the rendered files Dependabot's pip ecosystem reads.

    The same rule as the workflows, for Python dependencies: a requirement
    bumped in a rendered copy (``pywebview`` in ``requirements-desktop.txt``,
    say) diverges from its template and fails that repo's drift gate. The
    producers' pip ecosystem excludes exactly this list.
    """
    return _rendered_paths(program_id, targets, subs, "pip manifest", _is_pip_manifest)


# Each derived placeholder and the function that computes its list for a repo.
_DERIVED = {
    _RENDERED_WORKFLOWS: _rendered_workflows,
    _RENDERED_PIP_MANIFESTS: _rendered_pip_manifests,
}


def _subs_for(program_id: str, vars_for_repo: dict,
              targets: list[dict]) -> tuple[dict[str, str], frozenset[str]]:
    """Every placeholder for one repo, and the derived ones that came out empty.

    The ``_DERIVED`` placeholders are computed from targets.yaml rather than
    read from producers.vars.yaml. Each renders as the inside of a YAML flow
    sequence of double-quoted strings, so a template writes
    ``["{{RENDERED_WORKFLOWS}}"]`` and stays valid YAML before rendering as well
    as after (the hub's Dependabot parses the template files themselves). A vars
    key of the same name would silently win over the derived value, so it is
    rejected instead. An empty list gets no substitution: ``render_repo`` drops
    the line that holds it (see ``_drop_empty_list_lines``).
    """
    subs = _placeholders(vars_for_repo)
    for placeholder in _DERIVED:
        if placeholder in subs:
            raise SystemExit(
                f"error: {program_id}: producers.vars.yaml defines a key that fills "
                f"{placeholder}, which the renderer derives from "
                "targets.yaml — rename the key"
            )
    empty = set()
    for placeholder, derive in _DERIVED.items():
        paths = derive(program_id, targets, subs)
        if paths:
            subs[placeholder] = '", "'.join(paths)
        else:
            empty.add(placeholder)
    return subs, frozenset(empty)


def _drop_empty_list_lines(raw: bytes, empty: frozenset[str]) -> bytes:
    """Remove each ``<key>: ["{{P}}"]`` line whose derived list ``P`` is empty.

    Rendering ``exclude-paths: [""]`` would hand Dependabot a pattern that
    matches nothing while looking deliberate, and whether its config schema
    accepts ``[]`` is unverified. Nothing to exclude means no key at all, so the
    whole line goes. Only that exact line shape is removed: the placeholder anywhere
    else is left in place, and ``render_repo`` refuses it as unresolved.
    """
    for placeholder in sorted(empty):
        line = re.compile(
            rb'^[ \t]*[A-Za-z0-9_-]+:[ \t]*\["' + re.escape(placeholder.encode())
            + rb'"\][ \t]*(?:\r?\n|\Z)',
            re.MULTILINE,
        )
        raw = line.sub(b"", raw)
    return raw


def _manage_template_ref(repo_root: Path, template_ref: str, check: bool) -> bool:
    """Write or check the producer verifier's frozen canonical-template SHA.

    The workflow is intentionally not rendered wholesale because producer action
    pins can differ while their dependency PRs are in flight. Parse the YAML to
    verify the semantic field, then replace exactly one scalar in the original
    bytes so every unrelated byte and file mode stays intact.
    """
    if not _FULL_SHA.fullmatch(template_ref):
        raise SystemExit(
            "error: --template-ref must be a lowercase 40-character Git SHA"
        )

    path = repo_root / _TEMPLATE_REF_PATH
    try:
        raw = path.read_bytes()
        # BaseLoader keeps an all-numeric SHA as text instead of coercing it to
        # an integer, so validation does not depend on the commit's characters.
        doc = yaml.load(raw, Loader=yaml.BaseLoader) or {}
        current = doc["jobs"]["drift"]["env"]["PRII_TEMPLATE_REF"]
    except (OSError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise SystemExit(
            f"error: {_TEMPLATE_REF_PATH}: cannot read "
            "jobs.drift.env.PRII_TEMPLATE_REF"
        ) from exc

    matches = list(_TEMPLATE_REF_LINE.finditer(raw))
    if (
        not isinstance(current, str)
        or not _FULL_SHA.fullmatch(current)
        or len(matches) != 1
        or matches[0].group("sha").decode() != current
    ):
        raise SystemExit(
            f"error: {_TEMPLATE_REF_PATH}: expected exactly one lowercase "
            "40-character PRII_TEMPLATE_REF scalar"
        )

    match = matches[0]
    expected = raw[:match.start("sha")] + template_ref.encode() + raw[match.end("sha"):]
    if raw == expected:
        return False
    if not check:
        path.write_bytes(expected)
    return True


def render_repo(program_id: str, vars_for_repo: dict, repo_root: Path,
                targets: list[dict], check: bool,
                template_ref: str | None = None) -> list[str]:
    """Write (or --check) every target for one repo. Returns list of drifted paths."""
    subs, empty = _subs_for(program_id, vars_for_repo, targets)
    drift = []
    for template, output_tmpl, mode in _targets_for(program_id, targets):
        content = _drop_empty_list_lines(_render_bytes(template, subs), empty)
        missing = _unresolved(content)
        stranded = sorted(empty.intersection(missing))
        if stranded:
            raise SystemExit(
                f"error: {program_id}: {template} uses {', '.join(stranded)}, "
                "which is empty for this repo, outside a whole "
                '`<key>: ["{{...}}"]` line — only such a line can be omitted'
            )
        if missing:
            raise SystemExit(
                f"error: {program_id}: {template} has unresolved placeholder(s) "
                f"{', '.join(missing)} — add the key to producers.vars.yaml"
            )
        rel = _resolve_output(output_tmpl, subs)
        dest = repo_root / rel
        if check:
            # A file this gate cannot read or stat is not in its expected state,
            # which is what drift means — and letting the OSError propagate
            # would abandon the report for every later file and, under --all,
            # every later repo. Scoped to these two calls so the deliberate
            # SystemExit above still escapes.
            try:
                current = dest.read_bytes() if dest.exists() else None
                dest_mode = dest.stat().st_mode if dest.exists() else None
            except OSError:
                drift.append(rel)
                continue
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
                and dest_mode is not None
                and not (dest_mode & 0o100)
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
    if template_ref is not None and _manage_template_ref(repo_root, template_ref, check):
        drift.append(str(_TEMPLATE_REF_PATH))
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
    ap.add_argument(
        "--template-ref",
        help="also bind the producer drift workflow to this exact thehub commit",
    )
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
        drift = render_repo(
            program_id,
            vars_[program_id],
            root,
            targets,
            args.check,
            args.template_ref,
        )
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

#!/usr/bin/env python3
"""Re-derive the mechanical claims in the maturity-audit documents from the code.

The audit documents in `docs/MATURITY_AUDIT.md` (per repo) and
`docs/FEDERATION_MATURITY_AUDIT.md` (this repo) assert a lot of countable facts:
how many routes a backend serves, how many of its mutating routes carry an auth
dependency, how many workflows a repo has, whether a frontend has a `lint`
script and whether CI actually runs it.

Every one of those is derivable from the tree. Prose is not. This gate checks
only the derivable half, and it treats the code as the source of truth: it reads
the number out of the document and fails if the tree disagrees. Two real errors
motivated it, both the same shape — a summary sentence that generalised past the
evidence beneath it:

  * "`_require_key` ... is attached to every mutating route" in `aguayluz-pr`,
    written under a list naming five of the six that exist.
  * "all seven frontends build and lint clean" in the federation rollup, when
    six have a `lint` script and two repos gate it in CI.

Neither was a fabricated number; each was a true observation with a quantifier
bolted on. A human re-read caught them roughly ten thousand words in. This finds
them in about a second.

Scope and honesty about it
--------------------------
The federation lives in seven separate repositories. A CI job for one repo has
only that repo checked out, so most checks cannot run there. Missing repos are
reported as SKIPPED and counted in the summary — never silently passed. Run it
against a directory holding all seven (the layout `hub validate-federation
--root ..` already assumes) to exercise the full set, and pass `--require-all`
to make a missing repo an error rather than a skip.

Deliberately not checked here: test counts and coverage percentages. Those need
the suites actually run, which is the job of each repo's own test workflow, not
of a static gate. A claim this script cannot derive is left to the reader rather
than approximated — an audit gate that guesses is worse than one with a stated
boundary.

Usage
-----
    python3 scripts/verify_audit.py                 # --root .. by default
    python3 scripts/verify_audit.py --root ~/src
    python3 scripts/verify_audit.py --require-all   # missing repo == failure
    python3 scripts/verify_audit.py --list          # show the check registry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")
MUTATING_VERBS = ("post", "put", "patch", "delete")

#: The repository this script ships in. `actions/checkout` refuses to write
#: outside $GITHUB_WORKSPACE, so in CI the siblings land in a subdirectory while
#: this repo sits at the workspace root — meaning `<root>/thehub-pr` does not
#: exist. Resolving this one name to the script's own tree makes the CI layout
#: work and, incidentally, makes `--root` optional when running from inside the
#: repo.
SELF_REPO_NAME = "thehub-pr"
SELF_REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_repo(root: Path, name: str) -> Path | None:
    """Locate a federation repository, or None if it is not available."""
    candidate = root / name
    if candidate.is_dir():
        return candidate
    if name == SELF_REPO_NAME and SELF_REPO_ROOT.is_dir():
        return SELF_REPO_ROOT
    return None


# --------------------------------------------------------------------------
# Derivers — each answers one countable question about a checked-out repo.
# --------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _route_decorators(source: str) -> list[tuple[str, str, int]]:
    """Return (verb, path, 1-based line) for every `@app.<verb>("...")`."""
    found = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        match = re.match(r'\s*@app\.(%s)\(\s*[\'"]([^\'"]+)' % "|".join(HTTP_VERBS), line)
        if match:
            found.append((match.group(1), match.group(2), lineno))
    return found


def _handler_signature(lines: list[str], decorator_index: int) -> str:
    """Text of the `def` signature belonging to the decorator at `decorator_index`.

    Walks past any stacked decorators to the `def`, then consumes lines until
    the parameter list's parentheses balance. Signatures routinely span several
    lines, and the auth dependency is a default argument inside them rather than
    anything visible on the decorator — reading only the decorator line reports
    every route as unguarded, which is exactly the wrong answer.
    """
    index = decorator_index + 1
    while index < len(lines) and not re.match(r"\s*(async\s+)?def\s", lines[index]):
        index += 1
    signature: list[str] = []
    depth = 0
    opened = False
    while index < len(lines):
        line = lines[index]
        signature.append(line)
        depth += line.count("(") - line.count(")")
        if "(" in line:
            opened = True
        if opened and depth <= 0:
            break
        index += 1
    return "\n".join(signature)


def backend_route_count(repo: Path, main_py: str) -> int:
    """Application routes on the backend, excluding FastAPI's generated docs routes."""
    return len(_route_decorators(_read(repo / main_py)))


def guarded_mutating_routes(repo: Path, main_py: str, guard: str) -> str:
    """`"<guarded> of <total>"` mutating routes carrying `guard` in their signature."""
    source = _read(repo / main_py)
    lines = source.splitlines()
    total = 0
    guarded = 0
    for verb, _path, lineno in _route_decorators(source):
        if verb not in MUTATING_VERBS:
            continue
        total += 1
        if guard in _handler_signature(lines, lineno - 1):
            guarded += 1
    return f"{guarded} of {total}"


def unguarded_mutating_routes(repo: Path, main_py: str, guard: str) -> list[str]:
    source = _read(repo / main_py)
    lines = source.splitlines()
    open_routes = []
    for verb, path, lineno in _route_decorators(source):
        if verb in MUTATING_VERBS and guard not in _handler_signature(lines, lineno - 1):
            open_routes.append(f"{verb.upper()} {path} (:{lineno})")
    return open_routes


def workflow_count(repo: Path) -> int:
    directory = repo / ".github" / "workflows"
    if not directory.is_dir():
        return 0
    return len([p for p in directory.iterdir() if p.suffix in (".yml", ".yaml")])


def has_npm_script(repo: Path, package_json: str, script: str) -> bool:
    path = repo / package_json
    if not path.is_file():
        return False
    try:
        scripts = json.loads(_read(path)).get("scripts", {})
    except json.JSONDecodeError:
        return False
    return script in scripts


def ci_runs(repo: Path, command: str) -> bool:
    """True if any workflow invokes `command` in a run step."""
    directory = repo / ".github" / "workflows"
    if not directory.is_dir():
        return False
    needle = re.compile(re.escape(command))
    for workflow in directory.iterdir():
        if workflow.suffix in (".yml", ".yaml") and needle.search(_read(workflow)):
            return True
    return False


def argparse_subcommand_count(repo: Path, source_file: str) -> int:
    """Count `add_parser("name")` calls, including the multi-line form.

    An earlier hand count of this number was wrong because a single-line regex
    missed three subcommands whose `add_parser(` call wrapped. Matching across
    newlines is the whole point of automating it.
    """
    source = _read(repo / source_file)
    return len(re.findall(r'add_parser\(\s*[\'"]([^\'"]+)', source, flags=re.S))




# --------------------------------------------------------------------------
# Check registry
# --------------------------------------------------------------------------


class Check(NamedTuple):
    repo: str
    doc: str
    #: Regex over the document with exactly one capture group: the asserted value.
    pattern: str
    derive: Callable[[Path], object]
    label: str


def _s(value: object) -> str:
    """Normalise a derived value for comparison with a document capture."""
    return str(value).strip().replace(",", "")


CHECKS: list[Check] = [
    Check(
        repo="aguayluz-pr",
        doc="docs/MATURITY_AUDIT.md",
        pattern=r"attached to \*\*(\w+ of the \w+)\*\*\s*\n?\s*mutating routes",
        derive=lambda r: _spelled(guarded_mutating_routes(r, "server/backend/main.py", "_require_key")),
        label="aguayluz: mutating routes carrying _require_key",
    ),
    Check(
        repo="aguayluz-pr",
        doc="docs/MATURITY_AUDIT.md",
        # The previous revision of this check captured *which* route was unguarded.
        # /ai/query is now guarded, so the claim under test becomes the count, and
        # the check fails the moment a new mutating route ships without the guard.
        pattern=r"\*\*(\d+)\*\* unguarded mutating routes",
        derive=lambda r: len(unguarded_mutating_routes(r, "server/backend/main.py", "_require_key")),
        label="aguayluz: count of unguarded mutating routes",
    ),
    Check(
        repo="thehub-pr",
        doc="docs/MATURITY_AUDIT.md",
        pattern=r"\*\*(\d+)\*\* subcommands",
        derive=lambda r: argparse_subcommand_count(r, "src/hub/cli.py"),
        label="thehub: hub CLI subcommand count",
    ),
    Check(
        repo="thehub-pr",
        doc="server/frontend/README.md",
        pattern=r"`public_settings` advertises `(\w+)`",
        derive=lambda r: _public_settings_write_key(r, "server/backend/main.py"),
        label="thehub: public_settings advertises the write-token flag",
    ),
    Check(
        repo="skywatcher-pr",
        doc="frontend/README.md",
        pattern=r"`public_settings` advertises `(\w+)`",
        derive=lambda r: _public_settings_write_key(r, "server/backend/main.py"),
        label="skywatcher: public_settings advertises the write-token flag",
    ),
    Check(
        repo="spiderweb-pr",
        doc="docs/MATURITY_AUDIT.md",
        pattern=r"(\d+) files\. The repo has (?:\d+)",
        derive=lambda r: _lint_allowlist_size(r),
        label="spiderweb: size of the CI lint allowlist",
    ),
]

#: Frontends, and whether each has a `lint` script / a CI job that runs it.
#: This is the table in the rollup's 2026-07-27 corrections section. It is the
#: claim that was wrong, so it gets checked directly rather than via a regex.
FRONTENDS = {
    "thehub-pr": "server/frontend",
    "skywatcher-pr": "frontend",
    "centinelas-pr": "frontend",
    "aguayluz-pr": "dashboard",
    "moneysweep-pr": "dashboard",
    "ovnis-pr": "dashboard",
    "spiderweb-pr": "server/frontend",
}

#: Repos the rollup says gate `npm run lint` in CI. Derived and compared below.
#: Now all seven: aguayluz gained a Lint step in its existing dashboard-build
#: job, centinelas/ovnis/moneysweep gained a frontend job outright, and
#: spiderweb gained the eslint config it never had.
ROLLUP_LINT_GATED = {
    "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "ovnis-pr",
    "skywatcher-pr", "spiderweb-pr", "thehub-pr",
}

#: Repos the rollup says have no `lint` script at all. Empty since spiderweb-pr
#: got one — its config is local rather than rendered from the federation
#: templates, because that shared config is JSX-flavoured and would match none
#: of spiderweb's TypeScript sources.
ROLLUP_NO_LINT_SCRIPT: set[str] = set()


_NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _spelled(ratio: str) -> str:
    """`"5 of 6"` -> `"five of the six"`, matching how the document words it."""
    guarded, _, total = ratio.partition(" of ")
    return f"{_NUMBER_WORDS.get(int(guarded), guarded)} of the {_NUMBER_WORDS.get(int(total), total)}"


def _public_settings_write_key(repo: Path, main_py: str) -> str:
    """The write-token flag advertised in the `public_settings` object, if any.

    The browser cannot see backend env vars, so a UI that holds a write token has
    no way to tell "this server wants the token" from "this server accepts writes
    from my network" — both look like a working request until one 401s. This
    derives the flag name actually present in the response so the README cannot
    drift from it.
    """
    source = _read(repo / main_py)
    match = re.search(r'"public_settings":\s*\{([^}]*)\}', source, flags=re.S)
    if not match:
        return "<no public_settings object>"
    keys = re.findall(r'"(\w*write[_\w]*)"\s*:', match.group(1))
    return keys[0] if keys else "<absent>"


def _lint_allowlist_size(repo: Path) -> int:
    workflow = _read(repo / ".github" / "workflows" / "ci.yml")
    match = re.search(r'LINT_PATHS="([^"]+)"', workflow, flags=re.S)
    return len(match.group(1).split()) if match else 0


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


class Result(NamedTuple):
    status: str  # PASS | FAIL | SKIP
    label: str
    detail: str


def _extract(doc_text: str, pattern: str) -> str | None:
    match = re.search(pattern, doc_text)
    return match.group(1) if match else None


def run_checks(root: Path, require_all: bool) -> list[Result]:
    results: list[Result] = []

    for check in CHECKS:
        repo = resolve_repo(root, check.repo)
        if repo is None:
            results.append(Result(
                "FAIL" if require_all else "SKIP",
                check.label,
                f"{check.repo} not checked out under {root}",
            ))
            continue
        doc = repo / check.doc
        if not doc.is_file():
            results.append(Result("FAIL", check.label, f"missing document {check.doc}"))
            continue

        try:
            derived = _s(check.derive(repo))
        except (OSError, ValueError, KeyError) as exc:
            results.append(Result("FAIL", check.label, f"deriver raised {exc!r}"))
            continue

        asserted = _extract(_read(doc), check.pattern)
        if asserted is None:
            results.append(Result(
                "FAIL", check.label,
                f"no claim matching /{check.pattern}/ in {check.repo}/{check.doc} — "
                f"the document was reworded, or the claim was dropped; code says {derived!r}",
            ))
        elif _s(asserted) != derived:
            results.append(Result(
                "FAIL", check.label,
                f"{check.repo}/{check.doc} says {asserted!r}; code says {derived!r}",
            ))
        else:
            results.append(Result("PASS", check.label, f"{derived!r}"))

    results.extend(_check_frontend_lint_table(root, require_all))
    return results


def _check_frontend_lint_table(root: Path, require_all: bool) -> list[Result]:
    """Verify the rollup's lint table against the seven trees."""
    results: list[Result] = []
    missing: list[str] = []
    has_script: set[str] = set()
    gated: set[str] = set()

    for name, frontend in FRONTENDS.items():
        repo = resolve_repo(root, name)
        if repo is None:
            missing.append(name)
            continue
        if has_npm_script(repo, f"{frontend}/package.json", "lint"):
            has_script.add(name)
        if ci_runs(repo, "npm run lint"):
            gated.add(name)

    if missing:
        results.append(Result(
            "FAIL" if require_all else "SKIP",
            "federation: frontend lint table",
            f"not checked out: {', '.join(sorted(missing))}",
        ))
        return results

    absent = set(FRONTENDS) - has_script
    if absent != ROLLUP_NO_LINT_SCRIPT:
        results.append(Result(
            "FAIL", "federation: which frontends have a `lint` script",
            f"rollup says only {sorted(ROLLUP_NO_LINT_SCRIPT)} lack one; tree says {sorted(absent)}",
        ))
    else:
        results.append(Result(
            "PASS", "federation: which frontends have a `lint` script",
            f"{len(has_script)} of {len(FRONTENDS)}, missing in {sorted(absent)}",
        ))

    if gated != ROLLUP_LINT_GATED:
        results.append(Result(
            "FAIL", "federation: which repos gate `npm run lint` in CI",
            f"rollup says {sorted(ROLLUP_LINT_GATED)}; tree says {sorted(gated)}",
        ))
    else:
        results.append(Result(
            "PASS", "federation: which repos gate `npm run lint` in CI",
            f"{sorted(gated)}",
        ))

    return results


def _render(results: Iterable[Result]) -> int:
    results = list(results)
    width = max((len(r.label) for r in results), default=0)
    for result in results:
        print(f"{result.status:4}  {result.label.ljust(width)}  {result.detail}")

    failures = [r for r in results if r.status == "FAIL"]
    skips = [r for r in results if r.status == "SKIP"]
    passes = [r for r in results if r.status == "PASS"]

    print()
    print(f"{len(passes)} passed, {len(failures)} failed, {len(skips)} skipped")
    if skips:
        print("Skipped checks need sibling repos checked out beside this one; "
              "pass --root <dir> or --require-all.")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1].parent,
        help="directory containing the federation repositories (default: this repo's parent)",
    )
    parser.add_argument(
        "--require-all", action="store_true",
        help="treat a missing sibling repository as a failure instead of a skip",
    )
    parser.add_argument("--list", action="store_true", help="print the check registry and exit")
    args = parser.parse_args(argv)

    if args.list:
        for check in CHECKS:
            print(f"{check.repo:16} {check.doc:28} {check.label}")
        print(f"{'(federation)':16} {'docs/FEDERATION_MATURITY_AUDIT.md':28} frontend lint table")
        return 0

    root = args.root.resolve()
    print(f"Verifying audit claims against {root}\n")
    return _render(run_checks(root, args.require_all))


if __name__ == "__main__":
    sys.exit(main())

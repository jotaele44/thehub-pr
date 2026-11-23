#!/usr/bin/env python3
"""Decision logic for ``.github/workflows/federation-design-consumer-matrix.yml``.

The workflow tries a *released* ``@pr-federation/react`` candidate against every
producer that consumes the package, before anyone changes a pin. YAML is a poor place
for logic that can be wrong, so the workflow only runs commands and this module
decides: whether the inputs are acceptable, whether the downloaded bytes are the
bytes that were meant, whether the candidate was really the version that got
installed, and what each consumer's result means.

Sub-commands (exit 0 = fine, 1 = a verification or verdict failed, 2 = bad input):

``check-inputs``     validate the candidate URL and checksum; print ``version=`` and ``file=``
``verify-checksum``  SHA-256 of a file against the expected digest
``assert-installed`` the candidate, not the old pin, is what ended up in ``node_modules``
``record``           turn one consumer's step outcomes into a result file and a summary
``verdict``          exit 0 only when a recorded result is a PASS
``report``           final overall status and the consumers that were not exercised

Scope, stated so a green run is not over-read: each consumer is built and its unit
tests are run with the candidate installed over its pin, and compared with the same
build and tests on the current pin. The comparison is per step, not per test. This
does not run a producer's six-viewport/axe harness, its GUI-parity suite, or its own
``verify:*`` scripts (those verify the producer's pin, so they would fail a candidate
by design).

Standard library only; keep it importable on Python 3.10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PACKAGE_NAME = "@pr-federation/react"

# The only place a candidate may come from: a release asset of this repository, named
# the way ``federation-design-release.yml`` names it. The same shape the producers
# already pin, so a candidate is tried the way it would be adopted.
_VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
RELEASE_URL = re.compile(
    r"https://github\.com/jotaele44/thehub-pr/releases/download/"
    rf"federation-design-v(?P<tag>{_VERSION})/"
    rf"pr-federation-react-(?P<file>{_VERSION})\.tgz"
)
SHA256 = re.compile(r"[0-9a-f]{64}")

# Producers that depend on ``@pr-federation/react``, and the directory holding the
# package.json that does. The workflow matrix must list exactly these (a test checks).
CONSUMERS: dict[str, str] = {
    "aguayluz-pr": "dashboard",
    "centinelas-pr": "frontend",
    "moneysweep-pr": "dashboard",
    "ovnis-pr": "dashboard",
    "skywatcher-pr": "frontend",
}

# Governed producers that are deliberately not exercised. Reported as such, never as
# passed: a missing row would read as "fine".
NOT_EXERCISED: dict[str, str] = {
    "spiderweb-pr": f"declares no {PACKAGE_NAME} dependency, so there is nothing to try",
}

BASELINE_STEPS = ("install", "build", "test")
CANDIDATE_STEPS = ("install", "installed", "build", "test")

# GitHub's ``steps.<id>.outcome`` values, normalised. An empty string means the step
# never ran at all (for example the job was cancelled first); that is "not shown to
# pass", which is what ``skipped`` means here, and it can never produce a PASS.
_OUTCOMES = {
    "success": "pass",
    "failure": "fail",
    "cancelled": "fail",
    "skipped": "skipped",
    "": "skipped",
}
_NORMALISED = {"pass", "fail", "skipped"}

RESULT_SCHEMA = "federation_consumer_matrix_result_v1"

PASS = "PASS"
REGRESSION = "REGRESSION"
INCONCLUSIVE = "INCONCLUSIVE"

_VERDICT_MEANING = {
    PASS: "the candidate installed, built and passed the unit tests",
    REGRESSION: "the candidate fails something the current pin does not",
    INCONCLUSIVE: (
        "the candidate is not shown to work, but what fails also fails on the current pin, "
        "so the candidate cannot be blamed or cleared"
    ),
}


_SCOPE = (
    "Scope: build and unit tests, compared per step with the current pin. This does not "
    "run a producer's viewport/axe harness, GUI-parity suite or `verify:*` scripts."
)


class InvalidInput(ValueError):
    """Raised for input that must be refused rather than interpreted."""


# --------------------------------------------------------------------------- inputs


def check_inputs(url: str, sha256: str) -> dict[str, str]:
    """Return ``{"version", "file"}`` for an acceptable candidate, else raise."""
    match = RELEASE_URL.fullmatch(url)
    if match is None:
        raise InvalidInput(
            "package_url must be a release asset of jotaele44/thehub-pr, exactly "
            "https://github.com/jotaele44/thehub-pr/releases/download/"
            "federation-design-v<version>/pr-federation-react-<version>.tgz "
            "(no query string, no fragment, no other host)"
        )
    if match["tag"] != match["file"]:
        raise InvalidInput(
            f"release tag version {match['tag']!r} does not match the tarball version "
            f"{match['file']!r}"
        )
    if SHA256.fullmatch(sha256) is None:
        raise InvalidInput(
            "package_sha256 must be 64 lowercase hexadecimal characters "
            "(the digest from the release's SHA256SUMS)"
        )
    version = match["file"]
    return {"version": version, "file": f"pr-federation-react-{version}.tgz"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected: str) -> None:
    """Raise unless the file's SHA-256 is exactly ``expected``."""
    if SHA256.fullmatch(expected) is None:
        raise InvalidInput(
            "the expected digest must be 64 lowercase hexadecimal characters"
        )
    if not path.is_file():
        raise FileNotFoundError(f"{path} does not exist")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"checksum mismatch for {path.name}: expected {expected}, got {actual}"
        )


def installed_version(frontend_dir: Path) -> str:
    """Version of ``@pr-federation/react`` actually present in ``node_modules``."""
    manifest = (
        frontend_dir / "node_modules" / "@pr-federation" / "react" / "package.json"
    )
    if not manifest.is_file():
        raise FileNotFoundError(
            f"{manifest} does not exist; the package is not installed"
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("name") != PACKAGE_NAME:
        raise ValueError(f"{manifest} is {data.get('name')!r}, not {PACKAGE_NAME!r}")
    version = data.get("version")
    if not isinstance(version, str):
        raise ValueError(f"{manifest} has no version")
    return version


def assert_installed(frontend_dir: Path, expected_version: str) -> None:
    found = installed_version(frontend_dir)
    if found != expected_version:
        raise ValueError(
            f"{PACKAGE_NAME} in {frontend_dir} is {found}, not the candidate {expected_version}: "
            "the candidate was not what got built"
        )


def pin_before(package_json: Path) -> str:
    """The dependency spec a producer pins today, or ``none`` when it declares none."""
    data = json.loads(package_json.read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies"):
        spec = (data.get(section) or {}).get(PACKAGE_NAME)
        if isinstance(spec, str) and spec:
            return spec
    return "none"


# -------------------------------------------------------------------------- verdict


def normalise_outcome(raw: str) -> str:
    try:
        return _OUTCOMES[raw]
    except KeyError:
        raise InvalidInput(
            f"unknown step outcome {raw!r}; expected one of success, failure, cancelled, skipped"
        ) from None


def parse_outcomes(pairs: list[str], steps: tuple[str, ...]) -> dict[str, str]:
    """``["install=success", ...]`` -> ``{"install": "pass", ...}``; every step required."""
    parsed: dict[str, str] = {}
    for pair in pairs:
        name, sep, raw = pair.partition("=")
        if not sep or name not in steps:
            raise InvalidInput(
                f"{pair!r} is not <step>=<outcome> for steps {', '.join(steps)}"
            )
        if name in parsed:
            raise InvalidInput(f"step {name!r} given twice")
        parsed[name] = normalise_outcome(raw)
    missing = [s for s in steps if s not in parsed]
    if missing:
        raise InvalidInput(f"missing outcome for step(s): {', '.join(missing)}")
    return parsed


def validate_record(record: dict[str, Any]) -> None:
    if record.get("schema") != RESULT_SCHEMA:
        raise InvalidInput(f"not a {RESULT_SCHEMA} record")
    for key, steps in (("baseline", BASELINE_STEPS), ("candidate", CANDIDATE_STEPS)):
        phase = record.get(key)
        if not isinstance(phase, dict) or set(phase) != set(steps):
            raise InvalidInput(f"{key} must have exactly the steps {', '.join(steps)}")
        for step, value in phase.items():
            if value not in _NORMALISED:
                raise InvalidInput(
                    f"{key}.{step} is {value!r}, not one of pass, fail, skipped"
                )
    for key in ("repo", "candidate_version", "pin_before"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise InvalidInput(f"{key} is required")


def verdict(record: dict[str, Any]) -> str:
    """Classify one consumer. Only a candidate that shows every step passing is a PASS."""
    validate_record(record)
    baseline = record["baseline"]
    candidate = record["candidate"]
    # A step is a regression only when the same step passed on the current pin. A baseline
    # step that failed is not the candidate's doing, and one that was skipped (for example
    # build and test after a failed baseline install) is unknown, not clean; both leave the
    # candidate not shown to work, which is INCONCLUSIVE. ``installed`` has no baseline
    # counterpart and always counts: a candidate that was not what got built must never
    # read as clean.
    regressed = {
        step
        for step, value in candidate.items()
        if value == "fail" and (step == "installed" or baseline.get(step) == "pass")
    }
    if regressed:
        return REGRESSION
    if all(candidate[step] == "pass" for step in CANDIDATE_STEPS):
        return PASS
    return INCONCLUSIVE


# ------------------------------------------------------------------------- summary


def _cell(value: str) -> str:
    return value if value in _NORMALISED else "?"


def render_record(record: dict[str, Any]) -> str:
    result = verdict(record)
    base, cand = record["baseline"], record["candidate"]
    lines = [
        f"### {record['repo']}: {result}",
        "",
        f"{_VERDICT_MEANING[result].capitalize()}.",
        "",
    ]
    if result == PASS and any(value == "fail" for value in base.values()):
        lines += [
            "Note: the baseline was red on this producer; the candidate was not.",
            "",
        ]
    base_row = (
        f"| baseline (current pin) | {_cell(base['install'])} | n/a | "
        f"{_cell(base['build'])} | {_cell(base['test'])} |"
    )
    cand_row = (
        f"| candidate | {_cell(cand['install'])} | {_cell(cand['installed'])} | "
        f"{_cell(cand['build'])} | {_cell(cand['test'])} |"
    )
    lines += [
        f"- candidate: `{record['candidate_version']}`",
        f"- pin before: `{record['pin_before']}`",
        "",
        "| phase | install | installed | build | test |",
        "|---|---|---|---|---|",
        base_row,
        cand_row,
        "",
    ]
    return "\n".join(lines) + "\n"


def render_report(version: str, url: str, sha256: str, consumer_result: str) -> str:
    verdicts = "\n".join(
        f"- **{name}**: {meaning}" for name, meaning in _VERDICT_MEANING.items()
    )
    skipped = "\n".join(
        f"- **{repo}**: not exercised, {reason}"
        for repo, reason in NOT_EXERCISED.items()
    )
    exercised = ", ".join(CONSUMERS)
    outcome = "all consumers PASS" if consumer_result == "success" else "NOT clear"
    overall = (
        f"Overall: **{outcome}** (consumer jobs finished `{consumer_result or 'unknown'}`). "
        "Each producer's own table is in its job's summary."
    )
    return "\n".join(
        [
            f"## Consumer matrix for {PACKAGE_NAME} {version}",
            "",
            overall,
            "",
            f"- candidate: `{url}`",
            f"- sha256: `{sha256}` (verified against the downloaded bytes in every job)",
            f"- exercised: {exercised}",
            "",
            "Verdicts:",
            "",
            verdicts,
            "",
            "Not exercised:",
            "",
            skipped,
            "",
            _SCOPE,
            "",
        ]
    )


# ---------------------------------------------------------------------------- CLI


def _append(path: str | None, text: str) -> None:
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


def _cmd_check_inputs(args: argparse.Namespace) -> int:
    found = check_inputs(args.url, args.sha256)
    print(f"version={found['version']}")
    print(f"file={found['file']}")
    return 0


def _cmd_verify_checksum(args: argparse.Namespace) -> int:
    verify_checksum(Path(args.file), args.sha256)
    print(f"checksum OK: {Path(args.file).name} {args.sha256}")
    return 0


def _cmd_assert_installed(args: argparse.Namespace) -> int:
    assert_installed(Path(args.dir), args.expect_version)
    print(f"{PACKAGE_NAME} {args.expect_version} is what is installed in {args.dir}")
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    record = {
        "schema": RESULT_SCHEMA,
        "repo": args.repo,
        "candidate_version": args.candidate_version,
        "pin_before": pin_before(Path(args.package_json)),
        "baseline": parse_outcomes(args.baseline, BASELINE_STEPS),
        "candidate": parse_outcomes(args.candidate, CANDIDATE_STEPS),
    }
    text = render_record(record)  # also validates the record
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _append(args.summary_file, text)
    print(f"{record['repo']}: {verdict(record)}")
    return 0


def _cmd_verdict(args: argparse.Namespace) -> int:
    record = json.loads(Path(args.result).read_text(encoding="utf-8"))
    result = verdict(record)
    print(f"{record['repo']}: {result}: {_VERDICT_MEANING[result]}")
    return 0 if result == PASS else 1


def _cmd_report(args: argparse.Namespace) -> int:
    _append(
        args.summary_file,
        render_report(args.version, args.url, args.sha256, args.consumer_result),
    )
    if args.consumer_result != "success":
        print(
            f"consumer jobs finished {args.consumer_result!r}, not 'success'",
            file=sys.stderr,
        )
        return 1
    print("all consumers PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0] if __doc__ else None
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-inputs", help="validate the candidate URL and checksum")
    p.add_argument("--url", required=True)
    p.add_argument("--sha256", required=True)
    p.set_defaults(func=_cmd_check_inputs)

    p = sub.add_parser(
        "verify-checksum", help="SHA-256 of a file against an expected digest"
    )
    p.add_argument("--file", required=True)
    p.add_argument("--sha256", required=True)
    p.set_defaults(func=_cmd_verify_checksum)

    p = sub.add_parser(
        "assert-installed", help="the candidate version is what is in node_modules"
    )
    p.add_argument("--dir", required=True)
    p.add_argument("--expect-version", required=True)
    p.set_defaults(func=_cmd_assert_installed)

    p = sub.add_parser("record", help="write one consumer's result file and summary")
    p.add_argument("--repo", required=True)
    p.add_argument("--package-json", required=True)
    p.add_argument("--candidate-version", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary-file")
    p.add_argument("--baseline", nargs="+", required=True, metavar="STEP=OUTCOME")
    p.add_argument("--candidate", nargs="+", required=True, metavar="STEP=OUTCOME")
    p.set_defaults(func=_cmd_record)

    p = sub.add_parser("verdict", help="exit 0 only when a recorded result is a PASS")
    p.add_argument("--result", required=True)
    p.set_defaults(func=_cmd_verdict)

    p = sub.add_parser("report", help="overall status and the consumers not exercised")
    p.add_argument("--version", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--consumer-result", required=True)
    p.add_argument("--summary-file")
    p.set_defaults(func=_cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except InvalidInput as error:
        print(f"invalid input: {error}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

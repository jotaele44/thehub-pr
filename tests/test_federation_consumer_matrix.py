"""The federation-design consumer matrix: its decision logic and its workflow file.

``tools/federation_consumer_matrix.py`` decides whether a candidate package is the
one that was meant, whether it is what got installed, and what each producer's result
means. ``.github/workflows/federation-design-consumer-matrix.yml`` only runs commands
and cannot be dispatched before it is merged, so the file is linted here instead:
the properties that make it safe to run (read-only token, pinned actions, no input
reaching a shell) are asserted rather than trusted.

Refusals and failures come first in every group: the cases that matter are the ones
where a wrong answer would read as "fine".
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "federation_consumer_matrix.py"
WORKFLOW = ROOT / ".github" / "workflows" / "federation-design-consumer-matrix.yml"

URL_041 = (
    "https://github.com/jotaele44/thehub-pr/releases/download/"
    "federation-design-v0.4.1/pr-federation-react-0.4.1.tgz"
)
URL_RC1 = (
    "https://github.com/jotaele44/thehub-pr/releases/download/"
    "federation-design-v0.6.0-rc.1/pr-federation-react-0.6.0-rc.1.tgz"
)
DIGEST = "a" * 64
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _load():
    spec = importlib.util.spec_from_file_location("federation_consumer_matrix", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load()


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, check=False
    )


# ------------------------------------------------------------ refused candidate inputs


@pytest.mark.parametrize(
    "url",
    [
        "",
        URL_041.replace("https://", "http://"),
        URL_041.replace("github.com", "example.com"),
        URL_041.replace("jotaele44/thehub-pr", "jotaele44/moneysweep-pr"),
        URL_041.replace("jotaele44", "someone-else"),
        URL_041 + "?token=abc",
        URL_041 + "#fragment",
        URL_041 + "\n",
        URL_041 + " ",
        " " + URL_041,
        URL_041.replace(
            "federation-design-v0.4.1", "federation-design-v0.4.2"
        ),  # tag != file
        URL_041.replace("federation-design-v", "federation-design-"),
        URL_041.replace("/releases/download/", "/releases/download/../../"),
        URL_041.replace(
            "pr-federation-react-0.4.1.tgz", "pr-federation-react-0.4.1.zip"
        ),
        URL_041.replace("0.4.1.tgz", "0.4.1.tgz/extra"),
        URL_041.replace("0.4.1", "latest"),
        URL_RC1.replace("rc.1", "rc..1"),
    ],
)
def test_candidate_url_outside_the_release_shape_is_refused(url: str) -> None:
    with pytest.raises(m.InvalidInput):
        m.check_inputs(url, DIGEST)


@pytest.mark.parametrize(
    "digest",
    [
        "",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        DIGEST + "\n",
        " " + DIGEST,
        "sha256:" + DIGEST,
    ],
)
def test_malformed_checksum_is_refused(digest: str) -> None:
    with pytest.raises(m.InvalidInput):
        m.check_inputs(URL_041, digest)


def test_released_candidates_are_accepted_and_the_version_is_derived() -> None:
    assert m.check_inputs(URL_041, DIGEST) == {
        "version": "0.4.1",
        "file": "pr-federation-react-0.4.1.tgz",
    }
    assert m.check_inputs(URL_RC1, DIGEST) == {
        "version": "0.6.0-rc.1",
        "file": "pr-federation-react-0.6.0-rc.1.tgz",
    }


# --------------------------------------------------------------- the bytes that arrive


def test_a_tarball_that_is_not_the_expected_bytes_is_refused(tmp_path: Path) -> None:
    tarball = tmp_path / "pkg.tgz"
    tarball.write_bytes(b"the real package")
    expected = m.file_sha256(tarball)
    tarball.write_bytes(b"the real package.")  # one byte appended
    with pytest.raises(ValueError, match="checksum mismatch") as raised:
        m.verify_checksum(tarball, expected)
    assert expected in str(raised.value)
    assert m.file_sha256(tarball) in str(raised.value)


def test_a_missing_download_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        m.verify_checksum(tmp_path / "absent.tgz", DIGEST)


def test_an_unusable_expected_digest_is_refused_before_hashing(tmp_path: Path) -> None:
    tarball = tmp_path / "pkg.tgz"
    tarball.write_bytes(b"x")
    with pytest.raises(m.InvalidInput):
        m.verify_checksum(tarball, "not-a-digest")


def test_matching_bytes_are_accepted(tmp_path: Path) -> None:
    tarball = tmp_path / "pkg.tgz"
    tarball.write_bytes(b"")
    m.verify_checksum(tarball, EMPTY_SHA256)  # known digest of the empty input


# ------------------------------------------------- the candidate is what got installed


def _install(
    frontend: Path, *, name: str = "@pr-federation/react", version: str = "0.6.0-rc.1"
):
    package = frontend / "node_modules" / "@pr-federation" / "react"
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": name, "version": version})
    )


def test_nothing_installed_is_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        m.assert_installed(tmp_path, "0.6.0-rc.1")


def test_the_old_pin_still_installed_is_refused(tmp_path: Path) -> None:
    _install(tmp_path, version="0.4.1")
    with pytest.raises(ValueError, match="not the candidate 0.6.0-rc.1"):
        m.assert_installed(tmp_path, "0.6.0-rc.1")


def test_a_different_package_at_the_path_is_refused(tmp_path: Path) -> None:
    _install(tmp_path, name="@someone/else")
    with pytest.raises(ValueError, match="not '@pr-federation/react'"):
        m.assert_installed(tmp_path, "0.6.0-rc.1")


def test_the_candidate_installed_is_accepted(tmp_path: Path) -> None:
    _install(tmp_path)
    m.assert_installed(tmp_path, "0.6.0-rc.1")


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ({"dependencies": {"@pr-federation/react": URL_041}}, URL_041),
        ({"devDependencies": {"@pr-federation/react": "file:../x"}}, "file:../x"),
        ({"dependencies": {"react": "19"}}, "none"),
        ({}, "none"),
        ({"dependencies": None}, "none"),
    ],
)
def test_the_pin_before_is_read_from_package_json(
    tmp_path: Path, manifest: dict[str, Any], expected: str
) -> None:
    path = tmp_path / "package.json"
    path.write_text(json.dumps(manifest))
    assert m.pin_before(path) == expected


# -------------------------------------------------------------- outcomes and verdicts


def test_an_unknown_step_outcome_is_refused_not_guessed() -> None:
    with pytest.raises(m.InvalidInput, match="unknown step outcome"):
        m.parse_outcomes(
            ["install=succeeded", "build=success", "test=success"], m.BASELINE_STEPS
        )


@pytest.mark.parametrize(
    "pairs",
    [
        ["install=success", "build=success"],  # test missing
        [
            "install=success",
            "build=success",
            "test=success",
            "installed=success",
        ],  # extra
        [
            "install=success",
            "install=success",
            "build=success",
            "test=success",
        ],  # twice
        ["install", "build=success", "test=success"],  # no value
    ],
)
def test_outcomes_must_be_exactly_the_expected_steps(pairs: list[str]) -> None:
    with pytest.raises(m.InvalidInput):
        m.parse_outcomes(pairs, m.BASELINE_STEPS)


def test_outcomes_are_normalised() -> None:
    parsed = m.parse_outcomes(
        ["install=success", "build=failure", "test=cancelled"], m.BASELINE_STEPS
    )
    assert parsed == {"install": "pass", "build": "fail", "test": "fail"}
    # A step that never ran reports an empty outcome; that is "not shown to pass".
    assert m.parse_outcomes(["install=", "build=", "test="], m.BASELINE_STEPS) == {
        "install": "skipped",
        "build": "skipped",
        "test": "skipped",
    }


def _record(baseline: dict[str, str], candidate: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": m.RESULT_SCHEMA,
        "repo": "moneysweep-pr",
        "candidate_version": "0.6.0-rc.1",
        "pin_before": URL_041,
        "baseline": {"install": "pass", "build": "pass", "test": "pass", **baseline},
        "candidate": {
            "install": "pass",
            "installed": "pass",
            "build": "pass",
            "test": "pass",
            **candidate,
        },
    }


@pytest.mark.parametrize(
    ("baseline", "candidate", "expected"),
    [
        # What fails on the candidate but passed on the pin is a regression.
        ({}, {"build": "fail"}, m.REGRESSION),
        ({}, {"test": "fail"}, m.REGRESSION),
        (
            {},
            {
                "install": "fail",
                "installed": "skipped",
                "build": "skipped",
                "test": "skipped",
            },
            m.REGRESSION,
        ),
        # A candidate that is not what got built never reads as clean, even if the rest passes.
        ({}, {"installed": "fail"}, m.REGRESSION),
        ({"build": "fail"}, {"installed": "fail"}, m.REGRESSION),
        # Failing only what already failed on the pin cannot be blamed on the candidate,
        # and is not a pass either.
        ({"test": "fail"}, {"test": "fail"}, m.INCONCLUSIVE),
        (
            {"build": "fail", "test": "fail"},
            {"build": "fail", "test": "fail"},
            m.INCONCLUSIVE,
        ),
        # Baseline install failed, so its build and test never ran: unknown, not clean.
        (
            {"install": "fail", "build": "skipped", "test": "skipped"},
            {"build": "fail"},
            m.INCONCLUSIVE,
        ),
        (
            {"install": "fail", "build": "skipped", "test": "skipped"},
            {
                "install": "fail",
                "installed": "skipped",
                "build": "skipped",
                "test": "skipped",
            },
            m.INCONCLUSIVE,
        ),
        # Nothing ran on the candidate at all: not shown to work.
        (
            {},
            {
                "install": "skipped",
                "installed": "skipped",
                "build": "skipped",
                "test": "skipped",
            },
            m.INCONCLUSIVE,
        ),
        # Any skipped candidate step blocks a pass.
        ({}, {"test": "skipped"}, m.INCONCLUSIVE),
        # Passes.
        ({}, {}, m.PASS),
        (
            {"build": "fail", "test": "fail"},
            {},
            m.PASS,
        ),  # the candidate fixed a red producer
    ],
)
def test_verdict(
    baseline: dict[str, str], candidate: dict[str, str], expected: str
) -> None:
    assert m.verdict(_record(baseline, candidate)) == expected


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("schema"),
        lambda r: r.update(schema="something_else"),
        lambda r: r["baseline"].pop("test"),
        lambda r: r["candidate"].pop("installed"),
        lambda r: r["candidate"].update(extra="pass"),
        lambda r: r["candidate"].update(build="success"),  # raw outcome, not normalised
        lambda r: r["candidate"].update(build=True),
        lambda r: r.update(repo=""),
        lambda r: r.update(candidate_version=""),
        lambda r: r.pop("pin_before"),
    ],
)
def test_a_malformed_record_is_refused_not_scored(mutate: Any) -> None:
    record = _record({}, {})
    mutate(record)
    with pytest.raises(m.InvalidInput):
        m.verdict(record)


def test_summary_states_the_verdict_and_both_phases() -> None:
    text = m.render_record(_record({}, {"build": "fail"}))
    assert "### moneysweep-pr: REGRESSION" in text
    assert "| baseline (current pin) | pass | n/a | pass | pass |" in text
    assert "| candidate | pass | pass | fail | pass |" in text
    assert "Note: the baseline was red" not in text


def test_a_pass_on_a_red_baseline_says_so() -> None:
    text = m.render_record(_record({"test": "fail"}, {}))
    assert "### moneysweep-pr: PASS" in text
    assert "Note: the baseline was red on this producer; the candidate was not." in text


def test_the_note_never_appears_on_a_non_pass() -> None:
    assert "Note: the baseline was red" not in m.render_record(
        _record({"test": "fail"}, {"test": "fail"})
    )


# ---------------------------------------------------------------------------- report


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", ""])
def test_the_report_is_not_green_unless_every_consumer_job_succeeded(
    result: str,
) -> None:
    assert (
        _run(
            "report",
            "--version",
            "0.6.0-rc.1",
            "--url",
            URL_RC1,
            "--sha256",
            DIGEST,
            "--consumer-result",
            result,
        ).returncode
        == 1
    )


def test_the_report_names_what_was_not_exercised_and_never_calls_it_passed(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "summary.md"
    done = _run(
        "report",
        "--version",
        "0.6.0-rc.1",
        "--url",
        URL_RC1,
        "--sha256",
        DIGEST,
        "--consumer-result",
        "success",
        "--summary-file",
        str(summary),
    )
    assert done.returncode == 0
    text = summary.read_text()
    assert "all consumers PASS" in text
    assert "**spiderweb-pr**: not exercised" in text
    assert "spiderweb-pr: PASS" not in text
    assert "build and unit tests" in text  # the scope is stated next to the result


def test_the_report_names_every_producer_it_exercised_and_only_those(
    tmp_path: Path,
) -> None:
    # "all consumers PASS" means little unless it says which; the list is the matrix's.
    summary = tmp_path / "summary.md"
    _run(
        "report",
        "--version",
        "0.6.0-rc.1",
        "--url",
        URL_RC1,
        "--sha256",
        DIGEST,
        "--consumer-result",
        "success",
        "--summary-file",
        str(summary),
    )
    line = next(
        entry
        for entry in summary.read_text().splitlines()
        if entry.startswith("- exercised: ")
    )
    assert line == "- exercised: " + ", ".join(m.CONSUMERS)
    assert set(line.removeprefix("- exercised: ").split(", ")) == set(m.CONSUMERS)
    assert "spiderweb-pr" not in line


def test_a_red_report_does_not_say_clear(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    _run(
        "report",
        "--version",
        "0.6.0-rc.1",
        "--url",
        URL_RC1,
        "--sha256",
        DIGEST,
        "--consumer-result",
        "failure",
        "--summary-file",
        str(summary),
    )
    assert "NOT clear" in summary.read_text()
    assert "all consumers PASS" not in summary.read_text()


# ------------------------------------------------------------------- CLI exit codes


def test_cli_check_inputs_prints_github_output_lines() -> None:
    done = _run("check-inputs", "--url", URL_RC1, "--sha256", DIGEST)
    assert done.returncode == 0
    assert done.stdout.splitlines() == [
        "version=0.6.0-rc.1",
        "file=pr-federation-react-0.6.0-rc.1.tgz",
    ]


def test_cli_refuses_bad_input_with_exit_2_and_prints_nothing_to_stdout() -> None:
    done = _run(
        "check-inputs", "--url", "https://example.com/x.tgz", "--sha256", DIGEST
    )
    assert done.returncode == 2
    assert done.stdout == ""  # nothing a caller could append to GITHUB_OUTPUT
    assert "invalid input" in done.stderr


def test_cli_checksum_mismatch_exits_1(tmp_path: Path) -> None:
    tarball = tmp_path / "pkg.tgz"
    tarball.write_bytes(b"x")
    done = _run("verify-checksum", "--file", str(tarball), "--sha256", DIGEST)
    assert done.returncode == 1
    assert "checksum mismatch" in done.stderr


def test_cli_checksum_match_exits_0(tmp_path: Path) -> None:
    tarball = tmp_path / "pkg.tgz"
    tarball.write_bytes(b"")
    assert (
        _run(
            "verify-checksum", "--file", str(tarball), "--sha256", EMPTY_SHA256
        ).returncode
        == 0
    )


def test_cli_assert_installed_exit_codes(tmp_path: Path) -> None:
    assert (
        _run(
            "assert-installed", "--dir", str(tmp_path), "--expect-version", "1.0.0"
        ).returncode
        == 1
    )
    _install(tmp_path, version="1.0.0")
    assert (
        _run(
            "assert-installed", "--dir", str(tmp_path), "--expect-version", "1.0.0"
        ).returncode
        == 0
    )
    assert (
        _run(
            "assert-installed", "--dir", str(tmp_path), "--expect-version", "2.0.0"
        ).returncode
        == 1
    )


def _record_cli(tmp_path: Path, baseline: list[str], candidate: list[str]):
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps({"dependencies": {"@pr-federation/react": URL_041}})
    )
    return _run(
        "record",
        "--repo",
        "moneysweep-pr",
        "--package-json",
        str(package_json),
        "--candidate-version",
        "0.6.0-rc.1",
        "--out",
        str(tmp_path / "results" / "r.json"),
        "--summary-file",
        str(tmp_path / "summary.md"),
        "--baseline",
        *baseline,
        "--candidate",
        *candidate,
    )


PASSING_BASELINE = ["install=success", "build=success", "test=success"]
PASSING_CANDIDATE = [
    "install=success",
    "installed=success",
    "build=success",
    "test=success",
]


def test_cli_record_then_verdict_pass(tmp_path: Path) -> None:
    done = _record_cli(tmp_path, PASSING_BASELINE, PASSING_CANDIDATE)
    assert done.returncode == 0, done.stderr
    stored = json.loads((tmp_path / "results" / "r.json").read_text())
    assert stored["pin_before"] == URL_041
    assert (
        _run("verdict", "--result", str(tmp_path / "results" / "r.json")).returncode
        == 0
    )


def test_cli_record_succeeds_on_a_regression_and_verdict_is_what_fails(
    tmp_path: Path,
) -> None:
    # `record` must not fail the step that uploads evidence; `verdict` is the gate.
    candidate = [
        "install=success",
        "installed=success",
        "build=failure",
        "test=success",
    ]
    assert _record_cli(tmp_path, PASSING_BASELINE, candidate).returncode == 0
    gate = _run("verdict", "--result", str(tmp_path / "results" / "r.json"))
    assert gate.returncode == 1
    assert "REGRESSION" in gate.stdout


def test_cli_record_with_a_garbled_outcome_exits_2_and_writes_nothing(
    tmp_path: Path,
) -> None:
    done = _record_cli(
        tmp_path, ["install=ok", "build=success", "test=success"], PASSING_CANDIDATE
    )
    assert done.returncode == 2
    assert not (tmp_path / "results" / "r.json").exists()


def test_cli_record_appends_to_the_summary_instead_of_replacing_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "summary.md").write_text("earlier content\n")
    _record_cli(tmp_path, PASSING_BASELINE, PASSING_CANDIDATE)
    text = (tmp_path / "summary.md").read_text()
    assert text.startswith("earlier content\n")
    assert "### moneysweep-pr: PASS" in text


def test_cli_verdict_on_a_missing_result_fails(tmp_path: Path) -> None:
    assert _run("verdict", "--result", str(tmp_path / "absent.json")).returncode == 1


# ------------------------------------------------------------------ the workflow file


def _workflow() -> dict[str, Any]:
    assert WORKFLOW.is_file(), f"{WORKFLOW} does not exist"
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _triggers(workflow: dict[str, Any]) -> Any:
    # YAML 1.1 reads a bare `on` key as boolean True.
    return workflow["on"] if "on" in workflow else workflow[True]


def _steps(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_id, step)
        for job_id, job in workflow["jobs"].items()
        for step in job["steps"]
    ]


def test_the_workflow_runs_only_when_someone_dispatches_it() -> None:
    triggers = _triggers(_workflow())
    assert set(triggers) == {"workflow_dispatch"}, (
        "a candidate must be chosen, never inferred"
    )


def test_both_inputs_are_required() -> None:
    inputs = _triggers(_workflow())["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"package_url", "package_sha256"}
    assert all(spec["required"] is True for spec in inputs.values())


def test_the_token_is_read_only_everywhere() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    for job_id, job in workflow["jobs"].items():
        assert "permissions" not in job, (
            f"{job_id} must not widen the workflow's permissions"
        )


def test_nothing_in_the_workflow_uses_a_secret_or_a_privileged_trigger() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "secrets.",
        "pull_request_target",
        "github.token",
        "GITHUB_TOKEN",
    ):
        assert forbidden not in text, forbidden


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    uses = [step["uses"] for _, step in _steps(_workflow()) if "uses" in step]
    assert uses, "expected at least the checkout action"
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), (
            f"{ref} is not SHA-pinned"
        )


def test_the_same_action_versions_as_the_release_workflow_are_used() -> None:
    release = (ROOT / ".github/workflows/federation-design-release.yml").read_text()
    for ref in re.findall(r"uses:\s*(\S+@[0-9a-f]{40})", WORKFLOW.read_text()):
        assert ref in release, f"{ref} is not one the release workflow already runs"


def test_no_expression_reaches_a_shell_script() -> None:
    # Everything dynamic goes through `env:`, so a crafted input cannot become code.
    for job_id, step in _steps(_workflow()):
        script = step.get("run", "")
        assert "${{" not in script, (
            f"{job_id}: {step.get('name')!r} interpolates into a script"
        )


def test_every_job_has_a_timeout() -> None:
    for job_id, job in _workflow()["jobs"].items():
        assert isinstance(job.get("timeout-minutes"), int), job_id


def test_every_checkout_drops_credentials() -> None:
    checkouts = [
        s
        for _, s in _steps(_workflow())
        if s.get("uses", "").startswith("actions/checkout@")
    ]
    assert checkouts
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


def test_the_matrix_is_exactly_the_consumers_the_tool_knows() -> None:
    consumer = _workflow()["jobs"]["consumer"]
    include = consumer["strategy"]["matrix"]["include"]
    assert {entry["repo"]: entry["dir"] for entry in include} == m.CONSUMERS
    assert (
        consumer["strategy"]["fail-fast"] is False
    )  # one red producer must not hide the rest
    assert not set(m.CONSUMERS) & set(m.NOT_EXERCISED)


def test_consumers_are_checked_out_from_main_of_this_owner_only() -> None:
    steps = _workflow()["jobs"]["consumer"]["steps"]
    foreign = [s for s in steps if "repository" in (s.get("with") or {})]
    assert len(foreign) == 1
    assert foreign[0]["with"]["repository"] == "jotaele44/${{ matrix.repo }}"
    assert foreign[0]["with"]["ref"] == "main"


def test_downloads_are_https_only_and_fail_on_http_errors() -> None:
    downloads = [s["run"] for _, s in _steps(_workflow()) if "curl" in s.get("run", "")]
    assert (
        len(downloads) == 2
    )  # the prepare gate and each consumer leg re-verify the bytes
    for script in downloads:
        for flag in (
            "--fail",
            "--proto '=https'",
            "--proto-redir '=https'",
            "--max-time",
        ):
            assert flag in script, flag
        assert "verify-checksum" in script


def test_every_install_skips_lifecycle_scripts_and_the_candidate_is_not_saved() -> None:
    scripts = [
        s["run"]
        for _, s in _steps(_workflow())
        if re.search(r"\bnpm (ci|install)\b", s.get("run", ""))
    ]
    assert scripts
    for script in scripts:
        for line in script.splitlines():
            if re.search(r"\bnpm (ci|install)\b", line):
                assert "--ignore-scripts" in line, line
    candidate_install = next(s for s in scripts if "--no-save" in s)
    assert "CANDIDATE_FILE" in candidate_install


_BASELINE_IDS = {"install": "base_install", "build": "base_build", "test": "base_test"}
_CANDIDATE_IDS = {
    "install": "cand_install",
    "installed": "cand_installed",
    "build": "cand_build",
    "test": "cand_test",
}


def test_each_measured_step_keeps_going_so_the_verdict_sees_all_of_them() -> None:
    steps = {
        s.get("id"): s for s in _workflow()["jobs"]["consumer"]["steps"] if s.get("id")
    }
    for step_id in (*_BASELINE_IDS.values(), *_CANDIDATE_IDS.values()):
        assert steps[step_id]["continue-on-error"] is True, step_id


def test_the_recorded_outcomes_are_wired_to_the_right_steps() -> None:
    steps = _workflow()["jobs"]["consumer"]["steps"]
    record = next(s for s in steps if '"$TOOL" record' in s.get("run", ""))
    assert record["if"] == "always()"
    # Exact mapping: each variable carries the outcome of the step it is named for.
    expected_env = {
        **{
            f"B_{name.upper()}": f"${{{{ steps.{sid}.outcome }}}}"
            for name, sid in _BASELINE_IDS.items()
        },
        **{
            f"C_{name.upper()}": f"${{{{ steps.{sid}.outcome }}}}"
            for name, sid in _CANDIDATE_IDS.items()
        },
    }
    assert record["env"] == expected_env
    # And each phase's flag carries its own phase's variable (a swapped pair would pass
    # silently and make a failing candidate look like a failing baseline).
    script = record["run"]
    baseline_flags, candidate_flags = (
        script.split("--candidate ", 1)[0],
        script.split("--candidate ", 1)[1],
    )
    for name in _BASELINE_IDS:
        assert (
            f'{name}="$B_{name.upper()}"' in baseline_flags.split("--baseline ", 1)[1]
        ), name
    for name in _CANDIDATE_IDS:
        assert f'{name}="$C_{name.upper()}"' in candidate_flags, name
    assert "$C_" not in baseline_flags and "$B_" not in candidate_flags


def test_the_verdict_gate_runs_after_the_evidence_is_uploaded_and_even_after_failures() -> (
    None
):
    steps = _workflow()["jobs"]["consumer"]["steps"]
    names = [s.get("name", "") for s in steps]
    upload = next(
        i
        for i, s in enumerate(steps)
        if s.get("uses", "").startswith("actions/upload-artifact@")
    )
    gate = next(i for i, s in enumerate(steps) if '"$TOOL" verdict' in s.get("run", ""))
    record = next(
        i for i, s in enumerate(steps) if '"$TOOL" record' in s.get("run", "")
    )
    assert record < upload < gate, names
    assert steps[upload]["if"] == "always()"
    assert steps[gate]["if"] == "always()"


def test_the_installed_check_compares_against_the_candidate_version() -> None:
    steps = _workflow()["jobs"]["consumer"]["steps"]
    check = next(s for s in steps if s.get("id") == "cand_installed")
    assert "assert-installed" in check["run"]
    assert "--expect-version" in check["run"]
    assert "CANDIDATE_VERSION" in check["run"]


def test_the_report_job_runs_even_when_a_consumer_failed_but_not_when_the_candidate_was_refused() -> (
    None
):
    report = _workflow()["jobs"]["report"]
    assert "always()" in report["if"]
    assert "needs.prepare.result == 'success'" in report["if"]
    assert set(report["needs"]) == {"prepare", "consumer"}

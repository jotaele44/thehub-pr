"""The shared launcher: desktop/setup.py and the thin scripts that call it.

`desktop/setup.py` here is the hub's rendered copy of
federation-templates/desktop/setup.py (the drift gate keeps them identical), so
testing it tests what every adopting repo runs.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from desktop import setup

HUB = Path(__file__).resolve().parents[1]
TEMPLATES = HUB / "federation-templates"
APP_LAUNCHER = TEMPLATES / "PRII-APP.app" / "Contents" / "MacOS" / "PRII-APP"
APP_SETUP = TEMPLATES / "PRII-APP.app" / "Contents" / "Resources" / "first-run-setup.command"
SHELL_TEMPLATES = [
    APP_LAUNCHER,
    APP_SETUP,
    TEMPLATES / "PRII-APP.command",
    TEMPLATES / "PRII-APP.sh",
]
BAT = TEMPLATES / "PRII-APP.bat"
posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX shell and file modes")


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(setup, "_lang", "en")


# ── The scripts stay thin ────────────────────────────────────────────────────


def test_rendered_setup_matches_the_template():
    assert (HUB / "desktop" / "setup.py").read_bytes() == (
        TEMPLATES / "desktop" / "setup.py"
    ).read_bytes()


@posix_only
@pytest.mark.parametrize("script", SHELL_TEMPLATES, ids=lambda p: p.name)
def test_shell_launchers_parse_and_are_executable(script):
    shell = "sh" if script.suffix == ".sh" else "bash"
    assert subprocess.run([shell, "-n", str(script)]).returncode == 0
    assert os.access(script, os.X_OK)


@pytest.mark.parametrize("script", [*SHELL_TEMPLATES[1:], BAT], ids=lambda p: p.name)
def test_launchers_check_the_python_version_and_hand_over(script):
    text = script.read_text(encoding="utf-8")
    assert "sys.version_info < (3, 10)" in text
    assert re.search(r"desktop[/\\]setup\.py --launch", text)
    # Nothing but finding Python belongs in a launcher.
    for word in ("npm", "pip ", "nodejs.org", "Open Terminal"):
        assert word not in text, word


def test_no_launcher_tells_the_person_to_run_a_command():
    for script in [*SHELL_TEMPLATES, BAT]:
        text = script.read_text(encoding="utf-8")
        assert "and run:" not in text
        assert "python3 desktop/setup.py" not in text


def test_windows_launcher_avoids_labels():
    """cmd can misread call/goto labels in a file with LF line endings."""
    text = BAT.read_text(encoding="utf-8")
    assert not re.search(r"^\s*:\w", text, flags=re.MULTILINE)
    assert not re.search(r"^\s*(goto|call\s+:)", text, flags=re.I | re.M)
    assert 'set "PYTHON=py -3"' not in text


# ── Messages ─────────────────────────────────────────────────────────────────


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_both_languages_have_the_same_messages():
    english, spanish = setup.MESSAGES["en"], setup.MESSAGES["es"]
    assert english.keys() == spanish.keys()
    for key in english:
        assert _fields(english[key]) == _fields(spanish[key]), key
        assert spanish[key].strip(), key


def test_every_message_used_in_the_code_exists():
    source = (TEMPLATES / "desktop" / "setup.py").read_text(encoding="utf-8")
    used = set(re.findall(r'\bt\(\s*"([a-z_.]+)"', source))
    assert used and used <= setup.MESSAGES["en"].keys(), used - setup.MESSAGES["en"].keys()


@pytest.mark.parametrize(
    ("option", "env", "pref", "system", "expected"),
    [
        ("es", "en", "en", "en", "es"),  # the option wins
        (None, "es", "en", "en", "es"),  # then the environment
        (None, "", "es", "en", "es"),  # then the preferences file
        (None, "", None, "es", "es"),  # then the system language
        (None, "", None, None, "en"),  # then English
        ("fr", "de", "xx", None, "en"),  # unsupported values are skipped
    ],
)
def test_language_precedence(monkeypatch, option, env, pref, system, expected):
    monkeypatch.setenv("PRII_LANG", env)
    monkeypatch.setattr(setup, "system_language", lambda: system)
    prefs = {"language": pref} if pref else {}
    assert setup.choose_language(option, prefs) == expected


def test_peek_language_reads_both_spellings():
    assert setup.peek_language(["--launch", "--lang", "es"]) == "es"
    assert setup.peek_language(["--lang=es"]) == "es"
    assert setup.peek_language(["--launch"]) is None


# ── Preferences ──────────────────────────────────────────────────────────────


def test_preferences_keep_good_values_and_report_bad_ones(tmp_path, monkeypatch):
    path = tmp_path / "launcher.json"
    monkeypatch.setattr(setup, "prefs_path", lambda: path)
    path.write_text(
        json.dumps(
            {
                "language": "es",
                "window": "fullscreen",  # not allowed
                "check_on_start": False,
                "data_home": "~/prii",
                "something_else": 1,  # unknown: ignored silently
            }
        )
    )
    warnings: list[str] = []
    prefs = setup.load_preferences(warn=warnings.append)
    assert prefs == {"language": "es", "check_on_start": False, "data_home": "~/prii"}
    assert len(warnings) == 1 and "window" in warnings[0]


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", ""])
def test_a_broken_preferences_file_never_stops_the_app(tmp_path, monkeypatch, content):
    path = tmp_path / "launcher.json"
    path.write_text(content)
    monkeypatch.setattr(setup, "prefs_path", lambda: path)
    warnings: list[str] = []
    assert setup.load_preferences(warn=warnings.append) == {}
    assert warnings


def test_no_preferences_file_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "prefs_path", lambda: tmp_path / "absent.json")
    assert setup.load_preferences(warn=pytest.fail) == {}


# ── Knowing when setup is needed ─────────────────────────────────────────────


def test_fingerprint_follows_the_requirements(tmp_path, monkeypatch):
    req = tmp_path / "requirements-desktop.txt"
    req.write_text("fastapi\n")
    monkeypatch.setattr(setup, "requirement_files", lambda: [req])
    monkeypatch.setattr(setup, "CONSTRAINTS", tmp_path / "constraints-desktop.txt")
    monkeypatch.setattr(setup, "BUILD_FRONTEND", False)
    before = setup.fingerprint()
    assert setup.fingerprint() == before
    req.write_text("fastapi\nuvicorn\n")
    assert setup.fingerprint() != before


def test_fingerprint_follows_setup_version(monkeypatch):
    before = setup.fingerprint()
    monkeypatch.setattr(setup, "SETUP_VERSION", "bumped")
    assert setup.fingerprint() != before


def test_a_marker_from_the_previous_launcher_counts_as_out_of_date(tmp_path, monkeypatch):
    marker = tmp_path / ".setup-complete"
    monkeypatch.setattr(setup, "MARKER", marker)
    marker.write_text("ok\n")  # what the previous setup.py wrote
    assert not setup.is_current()
    setup.write_marker()
    assert setup.is_current()


@pytest.mark.parametrize(
    ("code", "seconds", "failed"),
    [
        (0, 1, False),  # normal close
        (1, 2, True),  # import error, crash at start
        (1, 600, False),  # ran for ten minutes first: not an install problem
        (143, 2, False),  # killed by a signal, as the shell reports it
        (-15, 2, False),  # killed by a signal, as Python reports it
    ],
)
def test_what_counts_as_a_failed_start(code, seconds, failed):
    assert setup.start_failed(code, seconds) is failed


# ── Running it ───────────────────────────────────────────────────────────────


def _main(monkeypatch, tmp_path, argv, *, complete=True, current=True, launches=()):
    """Run setup.main() with the slow parts replaced; returns (status, calls)."""
    calls: list[str] = []
    results = list(launches)
    monkeypatch.setenv("PRII_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("PRII_OFFLINE", "")
    monkeypatch.setattr(setup, "prefs_path", lambda: tmp_path / "launcher.json")
    monkeypatch.setattr(setup, "system_language", lambda: None)
    monkeypatch.setattr(setup, "is_complete", lambda: complete)
    monkeypatch.setattr(setup, "is_current", lambda: current)
    monkeypatch.setattr(setup, "interactive", lambda: False)
    monkeypatch.setattr(setup, "run_hook", lambda console, name: None)
    monkeypatch.setattr(setup, "run_setup", lambda console: calls.append("setup"))
    monkeypatch.setattr(setup, "reset", lambda: calls.append("reset"))
    monkeypatch.setattr(setup, "open_url", lambda url: calls.append(f"open {url}"))

    def launch(app_args, log, *, show):
        calls.append("launch " + " ".join(app_args))
        log.write_text("boom\n")
        return results.pop(0) if results else (0, 1.0)

    monkeypatch.setattr(setup, "launch_once", launch)
    return setup.main(argv), calls


def test_a_set_up_app_just_starts(monkeypatch, tmp_path):
    status, calls = _main(monkeypatch, tmp_path, ["--launch"])
    assert (status, calls) == (0, ["launch "])


def test_unknown_options_reach_the_app(monkeypatch, tmp_path):
    _, calls = _main(monkeypatch, tmp_path, ["--launch", "--route", "/launcher", "--browser"])
    assert calls == ["launch --route /launcher --browser"]


def test_out_of_date_components_are_reinstalled_before_starting(monkeypatch, tmp_path):
    status, calls = _main(monkeypatch, tmp_path, ["--launch"], current=False)
    assert (status, calls) == (0, ["setup", "launch "])


def test_the_check_can_be_switched_off_in_preferences(monkeypatch, tmp_path):
    (tmp_path / "launcher.json").write_text('{"check_on_start": false, "window": "browser"}')
    status, calls = _main(monkeypatch, tmp_path, ["--launch"], current=False)
    assert (status, calls) == (0, ["launch --browser"])


def test_a_failed_start_reinstalls_once_and_tries_again(monkeypatch, tmp_path):
    status, calls = _main(monkeypatch, tmp_path, ["--launch"], launches=[(1, 2.0), (0, 5.0)])
    assert (status, calls) == (0, ["launch ", "setup", "launch "])
    assert not (tmp_path / "logs" / "launch-failed").exists()


def test_a_start_that_keeps_failing_stops_with_its_status(monkeypatch, tmp_path, capsys):
    status, calls = _main(monkeypatch, tmp_path, ["--launch"], launches=[(3, 2.0), (3, 2.0)])
    assert status == 3
    assert calls == ["launch ", "setup", "launch "]  # one repair, not a loop
    assert "still did not start" in capsys.readouterr().out


def test_windowless_launcher_is_told_to_open_a_terminal(monkeypatch, tmp_path):
    """The .app cannot show output, so setup.py must return rather than work."""
    status, calls = _main(monkeypatch, tmp_path, ["--launch", "--no-prompt"], current=False)
    assert (status, calls) == (setup.EXIT_NEEDS_TERMINAL, [])

    status, calls = _main(
        monkeypatch, tmp_path, ["--launch", "--no-prompt"], launches=[(1, 2.0)]
    )
    assert (status, calls) == (setup.EXIT_NEEDS_TERMINAL, ["launch "])
    assert (tmp_path / "logs" / "launch-failed").is_file()


def test_setup_window_hands_back_to_the_app_after_first_setup(monkeypatch, tmp_path):
    status, calls = _main(
        monkeypatch, tmp_path, ["--launch", "--handoff", "/x/PRII-APP.app"], complete=False
    )
    assert (status, calls) == (0, ["setup", "open /x/PRII-APP.app"])


def test_setup_window_starts_the_app_itself_after_a_failed_start(monkeypatch, tmp_path):
    """Handing back to the .app after a failed start would loop
    app -> repair -> app with nothing readable; the app starts here instead."""
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "launch-failed").write_text("1\n")
    (logs / "launch.log").write_text("ImportError: boom\n")
    status, calls = _main(monkeypatch, tmp_path, ["--launch", "--handoff", "/x/PRII-APP.app"])
    assert (status, calls) == (0, ["setup", "launch "])
    assert not (logs / "launch-failed").exists()


def test_offline_never_installs(monkeypatch, tmp_path, capsys):
    status, calls = _main(monkeypatch, tmp_path, ["--launch", "--offline"], current=False)
    assert (status, calls) == (0, ["launch "])

    status, calls = _main(monkeypatch, tmp_path, ["--launch", "--offline"], complete=False)
    assert (status, calls) == (1, [])
    assert "Offline mode" in capsys.readouterr().out


def test_reset_and_reinstall(monkeypatch, tmp_path):
    assert _main(monkeypatch, tmp_path, ["--reinstall"])[1] == ["setup"]
    assert _main(monkeypatch, tmp_path, ["--force"])[1] == ["setup"]  # the old spelling
    assert _main(monkeypatch, tmp_path, ["--reset"])[1] == ["reset", "setup"]


def test_ensure_is_silent_when_there_is_nothing_to_do(monkeypatch, tmp_path, capsys):
    status, calls = _main(monkeypatch, tmp_path, ["--ensure"])
    assert (status, calls) == (0, [])
    assert capsys.readouterr().out == ""


def test_spanish_output(monkeypatch, tmp_path, capsys):
    _main(monkeypatch, tmp_path, ["--launch", "--lang", "es"], current=False)
    out = capsys.readouterr().out
    assert "Instalación terminada." in out and "Setup finished." not in out


def test_a_failing_step_names_the_cause_and_the_log(monkeypatch, tmp_path, capsys):
    def boom(console):
        console.log("npm ERR! network unreachable")
        raise setup.SetupError("Building the dashboard did not complete (exit 1).")

    status, _ = _main(monkeypatch, tmp_path, ["--launch"], complete=False)
    monkeypatch.setattr(setup, "run_setup", boom)
    status = setup.main(["--launch"])
    out = capsys.readouterr().out
    assert status == 1
    assert "Cause: Building the dashboard did not complete" in out
    assert "npm ERR! network unreachable" in out  # the tail of the log is shown
    assert "setup.log" in out


# ── Node.js, git and archives ────────────────────────────────────────────────


def test_git_requirement_becomes_archive_url():
    line = (
        "prii-desktop @ git+https://github.com/jotaele44/thehub-pr.git@"
        + "a" * 40
        + "#subdirectory=packages/prii_desktop"
    )
    assert setup.without_git(f"fastapi\n{line}\n") == (
        "fastapi\nprii-desktop @ https://github.com/jotaele44/thehub-pr/archive/"
        + "a" * 40
        + ".zip#subdirectory=packages/prii_desktop\n"
    )


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Darwin", "arm64", "node-v22.1.0-darwin-arm64.tar.gz"),
        ("Darwin", "x86_64", "node-v22.1.0-darwin-x64.tar.gz"),
        ("Linux", "aarch64", "node-v22.1.0-linux-arm64.tar.gz"),
        ("Windows", "AMD64", "node-v22.1.0-win-x64.zip"),
    ],
)
def test_node_archive_name(system, machine, expected):
    assert setup.node_archive_name("v22.1.0", system, machine) == expected


def test_node_archive_name_rejects_unknown_platform():
    with pytest.raises(setup.SetupError):
        setup.node_archive_name("v22.1.0", "SunOS", "sparc")


def _fake_node(directory: Path, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "npm").write_text("#!/bin/sh\n")
    (directory / "node").write_text(f"#!/bin/sh\necho {version}\n")
    for exe in ("npm", "node"):
        (directory / exe).chmod(0o755)
    return directory


@posix_only
def test_resolve_npm_order_and_version_floor(tmp_path, monkeypatch):
    home = tmp_path / "home"
    old = _fake_node(home / ".nvm" / "versions" / "node" / "v9.11.0" / "bin", "v9.11.0")
    new = _fake_node(home / ".nvm" / "versions" / "node" / "v22.3.0" / "bin", "v22.3.0")
    dirs = [d for d in setup.candidate_node_dirs(home) if home in d.parents]
    assert dirs[:2] == [new, old]  # newest version first, not lexical order

    monkeypatch.setattr(setup, "candidate_node_dirs", lambda: dirs)
    monkeypatch.setattr(setup, "NODE_DIR", tmp_path / ".node")
    monkeypatch.setattr(setup, "install_private_node", lambda: pytest.fail("downloaded"))

    on_path = _fake_node(tmp_path / "onpath", "v24.0.0")
    monkeypatch.setenv("PATH", f"{on_path}{os.pathsep}/usr/bin{os.pathsep}/bin")
    assert setup.resolve_npm() == (str(on_path / "npm"), None)

    # A Node on PATH that is too old is passed over for a newer managed one.
    too_old = _fake_node(tmp_path / "oldpath", "v16.20.0")
    monkeypatch.setenv("PATH", f"{too_old}{os.pathsep}/usr/bin{os.pathsep}/bin")
    assert setup.resolve_npm() == (str(new / "npm"), new)


@posix_only
def test_resolve_npm_downloads_when_nothing_suitable_is_installed(tmp_path, monkeypatch):
    private = tmp_path / ".node" / "bin"
    monkeypatch.setattr(setup, "NODE_DIR", tmp_path / ".node")
    monkeypatch.setattr(setup, "candidate_node_dirs", lambda: [])
    monkeypatch.setattr(
        setup, "install_private_node", lambda: _fake_node(private, "v22.9.9")
    )
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    if shutil.which("npm", path="/usr/bin:/bin"):
        pytest.skip("this machine has npm in /usr/bin")
    assert setup.resolve_npm() == (str(private / "npm"), private)


def _node_tarball(version: str) -> tuple[str, bytes]:
    name = setup.node_archive_name(version, "Linux", "x86_64")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        for member in ("bin/node", "bin/npm"):
            info = tarfile.TarInfo(f"{name.removesuffix('.tar.gz')}/{member}")
            info.mode = 0o755
            data = b"#!/bin/sh\n"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return name, buffer.getvalue()


@posix_only
@pytest.mark.parametrize("tampered", [False, True])
def test_private_node_is_checksum_verified(tmp_path, monkeypatch, tampered):
    name, payload = _node_tarball("v22.9.9")
    digest = hashlib.sha256(payload).hexdigest()
    served = payload + b"x" if tampered else payload

    def fake_download(url: str, dest: Path) -> None:
        if url.endswith("SHASUMS256.txt"):
            dest.write_text(f"{digest}  {name}\n")
        else:
            assert url.endswith(name)
            dest.write_bytes(served)

    monkeypatch.setattr(setup, "_download", fake_download)
    monkeypatch.setattr(setup, "NODE_DIR", tmp_path / ".node")
    monkeypatch.setattr(setup, "node_archive_name", lambda version: name)

    if tampered:
        with pytest.raises(setup.SetupError, match="integrity"):
            setup.install_private_node()
        assert not (tmp_path / ".node").exists()
    else:
        assert setup.install_private_node() == tmp_path / ".node" / "bin"
        assert (tmp_path / ".node" / "bin" / "npm").is_file()


@pytest.mark.parametrize(
    ("name", "linkname", "kind"),
    [
        ("../escape", None, None),
        ("/abs/escape", None, None),
        ("pkg/link", "../../outside", tarfile.SYMTYPE),
        ("pkg/hard", "pkg/other", tarfile.LNKTYPE),
    ],
)
def test_tar_extraction_refuses_unsafe_entries(tmp_path, name, linkname, kind):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name)
        if kind:
            info.type = kind
            info.linkname = linkname
            tf.addfile(info)
        else:
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(setup.SetupError, match="unexpected entry"):
        setup._extract_tar(archive, tmp_path / "out")
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "outside").exists()


@posix_only
def test_tar_extraction_keeps_inner_symlinks_and_exec_bits(tmp_path):
    archive = tmp_path / "ok.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        script = tarfile.TarInfo("pkg/lib/cli.js")
        script.mode = 0o755
        script.size = 2
        tf.addfile(script, io.BytesIO(b"ok"))
        link = tarfile.TarInfo("pkg/bin/npm")
        link.type = tarfile.SYMTYPE
        link.linkname = "../lib/cli.js"
        tf.addfile(link)
    out = tmp_path / "out"
    setup._extract_tar(archive, out)
    assert (out / "pkg" / "bin" / "npm").is_symlink()
    assert (out / "pkg" / "bin" / "npm").read_bytes() == b"ok"
    assert os.access(out / "pkg" / "lib" / "cli.js", os.X_OK)


# ── The macOS .app launcher, executed with stubbed tools ─────────────────────


def _stage_app(tmp_path: Path, python_stub: str, *, set_up: bool = True) -> dict[str, Path]:
    repo = tmp_path / "checkout"
    shutil.copytree(TEMPLATES / "PRII-APP.app", repo / "PRII-APP.app")
    (repo / "desktop").mkdir()
    (repo / "desktop" / "setup.py").write_text("")
    if set_up:
        (repo / "desktop" / ".setup-complete").write_text("{}\n")
        venv_bin = repo / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").write_text(f"#!/bin/sh\n{python_stub}\n")
        (venv_bin / "python").chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    calls = tmp_path / "open-calls.txt"
    (tools / "open").write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\n')
    (tools / "osascript").write_text("#!/bin/sh\nexit 0\n")
    for tool in tools.iterdir():
        tool.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    return {"repo": repo, "tools": tools, "calls": calls, "home": home}


def _run(stage: dict[str, Path], script: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script)],
        env={
            "HOME": str(stage["home"]),
            "PATH": f"{stage['tools']}{os.pathsep}{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def _app_exe(stage: dict[str, Path]) -> Path:
    return stage["repo"] / "PRII-APP.app" / "Contents" / "MacOS" / "PRII-APP"


@posix_only
def test_app_starts_a_set_up_checkout_without_a_terminal(tmp_path):
    stage = _stage_app(tmp_path, 'echo "args: $@"; exit 0')
    result = _run(stage, _app_exe(stage))
    assert result.returncode == 0, result.stderr
    assert not stage["calls"].exists()
    log = next((stage["home"] / "Library" / "Logs" / "PRII").glob("*/app.log"))
    assert "args: desktop/setup.py --launch --no-prompt" in log.read_text()


@posix_only
@pytest.mark.parametrize("status", [75, 1])
def test_app_opens_the_setup_window_when_setup_py_asks_for_one(tmp_path, status):
    stage = _stage_app(tmp_path, f"exit {status}")
    result = _run(stage, _app_exe(stage))
    assert result.returncode == 0, result.stderr
    opened = stage["calls"].read_text().strip()
    assert opened.startswith("-a Terminal ") and opened.endswith("first-run-setup.command")


@posix_only
def test_app_ignores_a_start_that_was_killed(tmp_path):
    stage = _stage_app(tmp_path, "kill -TERM $$")
    assert _run(stage, _app_exe(stage)).returncode == 0
    assert not stage["calls"].exists()


@posix_only
def test_app_opens_the_setup_window_on_first_run(tmp_path):
    stage = _stage_app(tmp_path, "", set_up=False)
    assert _run(stage, _app_exe(stage)).returncode == 0
    assert "first-run-setup.command" in stage["calls"].read_text()


@posix_only
def test_setup_window_hands_over_to_setup_py_with_the_app_path(tmp_path):
    stage = _stage_app(tmp_path, "", set_up=False)
    record = tmp_path / "python-args.txt"
    for name in ("python3", "python3.14", "python3.13", "python3.12", "python3.11", "python3.10"):
        stub = stage["tools"] / name
        # Passes the launcher's version check, then records the real call.
        stub.write_text(
            '#!/bin/sh\n[ "$1" = "-c" ] && exit 0\n'
            f'echo "$@" > "{record}"; echo "$PRII_LOG_DIR" >> "{record}"\n'
        )
        stub.chmod(0o755)
    script = stage["repo"] / "PRII-APP.app" / "Contents" / "Resources" / "first-run-setup.command"
    result = _run(stage, script)
    assert result.returncode == 0, result.stdout + result.stderr
    args, log_dir = record.read_text().splitlines()
    assert args == f"desktop/setup.py --launch --handoff {stage['repo'] / 'PRII-APP.app'}"
    # The same folder the app launcher uses, so the "start failed" note is shared.
    assert log_dir.startswith(str(stage["home"] / "Library" / "Logs" / "PRII"))


@posix_only
def test_shell_launcher_runs_the_real_setup_help(tmp_path):
    """The Linux launcher against the hub's real setup.py: nothing stubbed."""
    result = subprocess.run(
        ["sh", str(HUB / "PRII-THEHUB.sh"), "--version"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "launcher" in result.stdout and sys.version.split()[0][:3] in result.stdout

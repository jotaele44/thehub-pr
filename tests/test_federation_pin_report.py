"""tools/federation_pin_report.py: producer lag against the hub's templates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_HUB = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "_pin_report", _HUB / "tools" / "federation_pin_report.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _tool()
EXPECTED = TOOL.desktop_pin(
    (_HUB / "federation-templates" / "requirements-desktop.txt").read_text()
)


def _producer(root: Path, repo: str, pin: str | None, ref: str | None, pad: bool):
    base = root / repo
    (base / ".github" / "workflows").mkdir(parents=True)
    (base / "desktop").mkdir()
    if pin:
        (base / "requirements-desktop.txt").write_text(
            "pywebview>=6\nprii-desktop @ https://github.com/jotaele44/thehub-pr/"
            f"archive/{pin}.zip#subdirectory=packages/prii_desktop\n"
        )
    if ref:
        (base / ".github" / "workflows" / "template-drift.yml").write_text(
            f"env:\n  PRII_TEMPLATE_REF: {ref}\n"
        )
    (base / "desktop" / "config.py").write_text(
        "APP_TITLE = 'x'\n" + ("LAUNCHPAD = {}\n" if pad else "")
    )


def test_pin_parsers_accept_both_install_forms():
    sha = "a" * 40
    assert TOOL.desktop_pin(f"prii-desktop @ https://x/archive/{sha}.zip#s") == sha
    assert TOOL.desktop_pin(f"prii-desktop @ git+https://x/thehub-pr.git@{sha}#s") == sha
    assert TOOL.desktop_pin("pywebview>=6\n") is None
    assert TOOL.template_ref(f"  PRII_TEMPLATE_REF: '{sha}'") == sha
    assert TOOL.declares_launchpad("x = 1\nLAUNCHPAD = {\n") is True
    assert TOOL.declares_launchpad("# LAUNCHPAD = {}\n") is False


def test_report_flags_lagging_desktop_producers(tmp_path):
    stale = "1313c77aec1a0742c1abb444026284a825af4177"
    _producer(tmp_path, "aguayluz-pr", stale, stale, pad=False)
    _producer(tmp_path, "moneysweep-pr", EXPECTED, EXPECTED, pad=True)
    _producer(tmp_path, "spiderweb-pr", stale, None, pad=True)
    report = TOOL.build_report(TOOL.local_reader(tmp_path))
    rows = {row["repo"]: row for row in report["producers"]}

    assert rows["aguayluz-pr"]["prii_desktop_current"] is False
    assert rows["moneysweep-pr"]["prii_desktop_current"] is True
    assert rows["moneysweep-pr"]["launchpad"] is True
    # Spiderweb manages its desktop requirements by hand: reported, never "lagging".
    assert rows["spiderweb-pr"]["templated_desktop"] is False
    assert rows["centinelas-pr"]["readable"] is False
    assert "aguayluz-pr" in report["lagging_desktop_producers"]
    assert "moneysweep-pr" not in report["lagging_desktop_producers"]
    assert "spiderweb-pr" not in report["lagging_desktop_producers"]
    assert report["launchpad_missing"] == ["aguayluz-pr"]

    table = TOOL.render_table(report)
    assert "| aguayluz-pr | 1313c77 | **no** |" in table
    assert "| centinelas-pr | unreadable |" in table


def test_strict_exit_code_and_json_output(tmp_path, capsys):
    for repo in TOOL.desktop_producers():
        _producer(tmp_path, repo, EXPECTED, EXPECTED, pad=True)
    assert TOOL.main(["--root", str(tmp_path), "--strict"]) == 0
    assert "Every templated desktop producer" in capsys.readouterr().out

    _producer(tmp_path, "zz-unused", None, None, pad=False)  # ignored: not a producer
    (tmp_path / "ovnis-pr" / "requirements-desktop.txt").write_text(
        "prii-desktop @ https://x/archive/" + "b" * 40 + ".zip#s\n"
    )
    out = tmp_path / "report.json"
    assert TOOL.main(["--root", str(tmp_path), "--strict", "--json", "--out", str(out)]) == 1
    assert '"lagging_desktop_producers": [\n    "ovnis-pr"' in out.read_text()


def test_commits_behind_is_unknown_for_an_unknown_ref():
    assert TOOL.commits_behind(None) is None
    assert TOOL.commits_behind("0" * 40) is None

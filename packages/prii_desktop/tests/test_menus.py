"""Menus: what each surface holds, what each action does, and the page hook.

The macOS-only pieces (the Dock tile menu and the NSMenu pop-up) need a Mac and
are checked there; everything that decides *what* they show runs here.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from prii_desktop import DesktopConfig
from prii_desktop import menus
from prii_desktop import launchpad as pad
from prii_desktop.menus import (
    SEPARATOR,
    Action,
    MenuController,
    Responder,
    Submenu,
    clean_page_url,
    file_manager_name,
    link_target,
    page_origin,
    tidy,
)
from prii_desktop.setup_center import application_support_dir, configure

APP = "http://127.0.0.1:5173"
DECLARATION = {
    "start_pages": [
        {"route": "/", "label": "Home"},
        {"route": "/map", "label": "Map"},
        {"route": "/?tab=data", "label": "Data tab"},
    ],
    "operator": {"token_env": "DEMO_WRITE_TOKEN", "url_param": "write_token"},
}


class FakeWindow:
    def __init__(self, current=APP + "/map"):
        self.calls, self.current = [], current

    def get_current_url(self):
        return self.current

    def load_url(self, url):
        self.calls.append(("load_url", url))

    def evaluate_js(self, script):
        self.calls.append(("evaluate_js", script))

    def show(self):
        self.calls.append(("show",))

    def restore(self):
        self.calls.append(("restore",))

    def minimize(self):
        self.calls.append(("minimize",))


class Harness:
    """A controller wired to fakes, plus everything the fakes saw."""

    def __init__(self, tmp_path, *, declaration=DECLARATION, platform="darwin",
                 app_url=APP + "/?write_token=SECRET", copy=True, configured=True):
        dist = tmp_path / "dist"
        dist.mkdir(exist_ok=True)
        (dist / "index.html").write_text("<html></html>")
        self.config = DesktopConfig(
            app_title="Demo",
            app_import="demo:app",
            repo_root=tmp_path,
            dist_dir=dist,
            app_id="Demo",
            state_dir=tmp_path / "state",
            launchpad=declaration,
        )
        if configured:
            configure(self.config, tmp_path / "workspace")
        self.window = FakeWindow()
        self.commands, self.opened, self.copied, self.notes = [], [], [], []
        self.setup, self.launchpad, self.restarted = [], [], []
        self.app_url = app_url
        spec = pad.launchpad_spec(self.config)
        self.controller = MenuController(
            self.config,
            spec,
            window=lambda: self.window,
            app_url=lambda: self.app_url,
            open_setup=lambda: self.setup.append(1),
            open_launchpad=(lambda: self.launchpad.append(1)) if spec else None,
            restart=lambda: self.restarted.append(1),
            record=self.notes.append,
            platform=platform,
            run_command=self.commands.append,
            copy_text=(lambda text: self.copied.append(text) or True) if copy else None,
            open_url=self.opened.append,
        )

    def on_app_page(self):
        self.controller.note_loaded(APP + "/map")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    # configure() exports the workspace variables; leave os.environ as found.
    before = dict(os.environ)
    yield
    for name in set(os.environ) - set(before):
        del os.environ[name]
    os.environ.update(before)


def ids(entries):
    """Every action id in ``entries``, descending into submenus."""
    found = []
    for entry in entries:
        if isinstance(entry, Action):
            found.append(entry.id)
        elif isinstance(entry, Submenu):
            found.extend(ids(entry.items))
    return found


def labels(entries):
    return [e.label for e in entries if not isinstance(e, type(SEPARATOR))]


# ── the model ─────────────────────────────────────────────────────────────────


def test_tidy_removes_stray_separators_and_empty_submenus():
    a, b = Action("a", "A"), Action("b", "B")
    entries = [SEPARATOR, a, SEPARATOR, SEPARATOR, Submenu("Empty", ()), b, SEPARATOR]
    assert tidy(entries) == (a, SEPARATOR, b)


def test_tidy_recurses_into_submenus():
    a = Action("a", "A")
    assert tidy([Submenu("S", (SEPARATOR, a, SEPARATOR))]) == (Submenu("S", (a,)),)
    assert tidy([Submenu("S", (SEPARATOR,))]) == ()


@pytest.mark.parametrize(
    "platform, name",
    [("darwin", "Finder"), ("win32", "File Explorer"), ("linux", "Files")],
)
def test_file_manager_name(platform, name):
    assert file_manager_name(platform) == name


def test_page_origin_only_for_http_addresses():
    assert page_origin("http://127.0.0.1:9/x?y=1") == "http://127.0.0.1:9"
    assert page_origin("https://example.test/") == "https://example.test"
    for bad in (None, "", "about:blank", "file:///tmp/x", "javascript:alert(1)", "/relative"):
        assert page_origin(bad) is None


def test_clean_page_url_drops_only_the_credential():
    url = APP + "/map?write_token=SECRET&tab=data&x=#section"
    assert clean_page_url(url, "write_token") == APP + "/map?tab=data&x=#section"
    assert clean_page_url(url) == url  # no parameter declared: left alone
    assert "SECRET" not in clean_page_url(APP + "/?write_token=SECRET", "write_token")


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", "", None,
            "http://ok.test/\nx", "http://" + "a" * 3000, "mailto:a@b.test"],
)
def test_link_target_rejects_anything_but_plain_web_links(url):
    assert link_target(url) is None


def test_link_target_accepts_web_links():
    assert link_target("https://example.test/a?b=1") == "https://example.test/a?b=1"


# ── what each menu holds ──────────────────────────────────────────────────────


def test_menu_bar_on_a_mac_extends_the_app_menu(tmp_path):
    bar = Harness(tmp_path).controller.menu_bar()
    assert labels(bar.app) == ["Setup & Diagnostics…", "Launch Pad…", "Restart Demo"]
    assert [m.label for m in bar.menus] == ["Go", "Tools", "Window", "Help"]
    by_menu = {m.label: ids(m.items) for m in bar.menus}
    assert by_menu["Go"][:4] == ["back", "forward", "reload", "home"]
    assert by_menu["Go"][4:] == ["go:/", "go:/map", "go:/?tab=data"]
    assert by_menu["Tools"] == ["copy_page", "open_page", "reveal_workspace", "reveal_data"]
    assert by_menu["Window"] == ["minimize", "show"]
    assert by_menu["Help"] == ["open_log", "reveal_logs", "copy_diagnostics"]


def test_menu_labels_name_the_platform_file_manager(tmp_path):
    tools = Harness(tmp_path).controller.menu_bar().menus[1]
    assert "Show Workspace in Finder" in labels(tools.items)
    tools = Harness(tmp_path, platform="win32").controller.menu_bar().menus[1]
    assert "Show Workspace in File Explorer" in labels(tools.items)


def test_menu_bar_elsewhere_has_no_app_menu_and_keeps_its_actions(tmp_path):
    bar = Harness(tmp_path, platform="linux", copy=False).controller.menu_bar()
    assert bar.app == ()  # "__app__" is a macOS convention
    tools = next(m for m in bar.menus if m.label == "Tools")
    assert ids(tools.items)[:3] == ["setup", "launchpad", "restart"]
    # No clipboard support there, so nothing that needs one is offered.
    assert "copy_page" not in ids(tools.items)
    assert "copy_diagnostics" not in ids(bar.menus[-1].items)


def test_an_app_without_a_launch_pad_has_no_launch_pad_or_go_pages(tmp_path):
    h = Harness(tmp_path, declaration=None)
    bar = h.controller.menu_bar()
    assert "Launch Pad…" not in labels(bar.app)
    assert ids(bar.menus[0].items) == ["back", "forward", "reload", "home"]
    h.on_app_page()
    assert "launchpad" not in ids(h.controller.dock_entries())
    assert "go:/" not in ids(h.controller.context_entries())
    assert "Go To" not in labels(h.controller.dock_entries())


def test_dock_menu_before_the_app_loads_offers_only_what_works(tmp_path):
    entries = Harness(tmp_path).controller.dock_entries()
    assert ids(entries) == ["show", "launchpad", "setup", "reveal_workspace", "restart"]
    assert entries[0] == Action("show", "Show Demo")


def test_dock_menu_on_the_app_page_adds_navigation(tmp_path):
    h = Harness(tmp_path)
    h.on_app_page()
    entries = h.controller.dock_entries()
    assert ids(entries) == [
        "show", "launchpad", "setup",
        "go:/", "go:/map", "go:/?tab=data",
        "reload", "open_page",
        "reveal_workspace", "restart",
    ]
    assert any(isinstance(e, Submenu) and e.label == "Go To" for e in entries)


def test_dock_menu_offers_logs_only_once_they_exist(tmp_path):
    h = Harness(tmp_path)
    assert "reveal_logs" not in ids(h.controller.dock_entries())
    (application_support_dir(h.config) / "logs").mkdir(parents=True)
    assert "reveal_logs" in ids(h.controller.dock_entries())


def test_dock_menu_hides_the_workspace_before_setup(tmp_path):
    h = Harness(tmp_path, configured=False)
    assert "reveal_workspace" not in ids(h.controller.dock_entries())


def test_dock_menu_is_never_leading_or_trailing_with_a_separator(tmp_path):
    for configured in (True, False):
        h = Harness(tmp_path / str(configured), configured=configured) if False else Harness(
            tmp_path, configured=configured)
        entries = h.controller.dock_entries()
        assert entries[0] is not SEPARATOR and entries[-1] is not SEPARATOR


def test_leaving_the_app_page_removes_page_actions(tmp_path):
    h = Harness(tmp_path)
    h.on_app_page()
    assert "reload" in ids(h.controller.dock_entries())
    h.controller.note_loaded(None)  # Setup, the Launch Pad and error pages are html
    assert "reload" not in ids(h.controller.dock_entries())
    h.controller.note_loaded("http://127.0.0.1:9999/")  # some other server
    assert not h.controller.on_app_page


def test_right_click_always_offers_editing_commands(tmp_path):
    entries = Harness(tmp_path).controller.context_entries()
    assert [e for e in entries if isinstance(e, Responder)] == [
        Responder("Cut", "cut:"),
        Responder("Copy", "copy:"),
        Responder("Paste", "paste:"),
        Responder("Select All", "selectAll:"),
    ]


def test_right_click_on_the_app_page(tmp_path):
    h = Harness(tmp_path)
    h.on_app_page()
    assert ids(h.controller.context_entries()) == [
        "back", "forward", "reload", "copy_page", "open_page",
        "go:/", "go:/map", "go:/?tab=data", "launchpad", "setup",
    ]


def test_right_click_on_a_link_adds_link_actions(tmp_path):
    h = Harness(tmp_path)
    entries = h.controller.context_entries("https://example.test/a")
    assert ids(entries)[:2] == ["open_link", "copy_link"]
    # A link that is not plain web is ignored, not offered.
    assert "open_link" not in ids(h.controller.context_entries("javascript:alert(1)"))


def test_a_link_from_the_page_is_remembered_only_when_valid(tmp_path):
    h = Harness(tmp_path)
    h.controller.context_entries("https://example.test/a")
    assert h.controller.run("open_link")
    assert h.opened == ["https://example.test/a"]
    h.controller.context_entries("file:///etc/passwd")
    assert not h.controller.run("open_link")
    assert h.opened == ["https://example.test/a"]


# ── actions ───────────────────────────────────────────────────────────────────


def test_setup_launchpad_and_restart_call_their_callbacks(tmp_path):
    h = Harness(tmp_path)
    for action in ("setup", "launchpad", "restart"):
        assert h.controller.run(action)
    assert (h.setup, h.launchpad, h.restarted) == ([1], [1], [1])


def test_launch_pad_action_without_a_launch_pad_does_nothing(tmp_path):
    h = Harness(tmp_path, declaration=None)
    assert h.controller.run("launchpad") is False
    assert h.launchpad == []


def test_history_and_reload_need_the_app_page(tmp_path):
    h = Harness(tmp_path)
    for action in ("back", "forward", "reload"):
        assert h.controller.run(action) is False
    assert h.window.calls == []
    h.on_app_page()
    assert h.controller.run("back") and h.controller.run("forward")
    assert h.controller.run("reload")
    assert h.window.calls == [
        ("evaluate_js", "history.back()"),
        ("evaluate_js", "history.forward()"),
        ("load_url", APP + "/map"),
    ]


def test_home_returns_to_where_the_app_started(tmp_path):
    h = Harness(tmp_path)
    assert h.controller.run("home")
    assert h.window.calls == [("load_url", APP + "/?write_token=SECRET")]
    h.app_url = None
    assert h.controller.run("home") is False  # not started yet


def test_go_opens_only_declared_pages_on_the_apps_own_origin(tmp_path):
    h = Harness(tmp_path)
    assert h.controller.run("go:/map")
    assert h.controller.run("go:/?tab=data")
    assert h.window.calls == [("load_url", APP + "/map"), ("load_url", APP + "/?tab=data")]
    h.window.calls.clear()
    for hostile in ("go:/not-declared", "go:https://evil.test/", "go://evil.test/map"):
        assert h.controller.run(hostile) is False
    assert h.window.calls == []


def test_go_credential_is_not_forwarded_in_the_url(tmp_path):
    # The token travels in the page's session storage, not in the address.
    h = Harness(tmp_path)
    h.controller.run("go:/map")
    assert "SECRET" not in h.window.calls[0][1]


def test_copy_and_open_page_never_carry_the_operator_token(tmp_path):
    h = Harness(tmp_path)
    h.on_app_page()
    h.window.current = APP + "/map?write_token=SECRET&tab=data"
    assert h.controller.run("copy_page") and h.controller.run("open_page")
    assert h.copied == [APP + "/map?tab=data"]
    assert h.opened == [APP + "/map?tab=data"]


def test_page_actions_off_the_app_page_do_nothing(tmp_path):
    h = Harness(tmp_path)
    assert h.controller.run("copy_page") is False
    assert h.controller.run("open_page") is False
    assert (h.copied, h.opened) == ([], [])


def test_copy_without_clipboard_support_does_nothing(tmp_path):
    h = Harness(tmp_path, copy=False)
    h.on_app_page()
    assert h.controller.run("copy_page") is False
    assert h.controller.run("open_page") is True  # opening needs no clipboard


def test_show_restores_then_raises_the_window(tmp_path):
    h = Harness(tmp_path)
    assert h.controller.run("show") and h.controller.run("minimize")
    assert h.window.calls == [("restore",), ("show",), ("minimize",)]


def test_reveal_opens_the_folder_with_the_platform_opener(tmp_path):
    h = Harness(tmp_path)
    (application_support_dir(h.config) / "logs").mkdir(parents=True, exist_ok=True)
    assert h.controller.run("reveal_workspace")
    assert h.controller.run("reveal_data")
    assert h.controller.run("reveal_logs")
    workspace = str((tmp_path / "workspace").resolve())
    assert h.commands == [
        ["open", workspace],
        ["open", str(application_support_dir(h.config))],
        ["open", str(application_support_dir(h.config) / "logs")],
    ]
    linux = Harness(tmp_path, platform="linux")
    assert linux.controller.run("reveal_workspace")
    assert linux.commands[0][0] == "xdg-open"


def test_reveal_of_something_missing_does_nothing(tmp_path):
    h = Harness(tmp_path, configured=False)
    assert h.controller.run("reveal_workspace") is False
    assert h.controller.run("reveal_logs") is False
    assert h.controller.run("open_log") is False
    assert h.commands == []


def test_open_log_opens_the_file_once_it_exists(tmp_path):
    h = Harness(tmp_path)
    log = application_support_dir(h.config) / "logs" / "launcher.log"
    log.parent.mkdir(parents=True)
    log.write_text("x\n")
    assert h.controller.run("open_log")
    assert h.commands == [["open", str(log)]]


def test_diagnostics_summary_is_useful_and_holds_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_WRITE_TOKEN", "SECRET-FROM-ENVIRONMENT")
    h = Harness(tmp_path)
    h.on_app_page()
    assert h.controller.run("copy_diagnostics")
    text = h.copied[0]
    assert text.startswith("Demo desktop diagnostics\n")
    for expected in ("System:", "Python:", "Workspace:", "App data:", "Checks:",
                     "[pass] Workspace:", "Application interface"):
        assert expected in text
    assert "SECRET" not in text


def test_unknown_actions_and_failures_are_recorded_not_raised(tmp_path):
    h = Harness(tmp_path)
    assert h.controller.run("no-such-action") is False
    assert "unknown action" in h.notes[-1]

    def boom():
        raise RuntimeError("window is gone")

    h.controller._restart = boom
    assert h.controller.run("restart") is False
    assert "restart failed: RuntimeError: window is gone" in h.notes[-1]


def test_a_failing_recorder_cannot_break_a_menu_click(tmp_path):
    h = Harness(tmp_path)

    def broken(_message):
        raise OSError("disk full")

    h.controller._record = broken
    assert h.controller.run("no-such-action") is False


def test_actions_are_the_ones_the_menus_offer(tmp_path):
    """Every id any menu can contain is handled; nothing is a dead entry."""
    h = Harness(tmp_path)
    h.on_app_page()
    offered = set()
    bar = h.controller.menu_bar()
    offered |= set(ids(bar.app)) | {i for m in bar.menus for i in ids(m.items)}
    offered |= set(ids(h.controller.dock_entries()))
    offered |= set(ids(h.controller.context_entries("https://example.test/")))
    handled = set(h.controller._handlers())
    assert {i for i in offered if not i.startswith("go:")} <= handled


# ── pywebview menu bar ────────────────────────────────────────────────────────


def test_pywebview_menu_conversion(tmp_path):
    pytest.importorskip("webview.menu")
    from webview.menu import Menu, MenuAction, MenuSeparator

    h = Harness(tmp_path)
    converted = menus.pywebview_menu(h.controller.menu_bar(), h.controller.run)
    assert [m.title for m in converted] == ["__app__", "Go", "Tools", "Window", "Help"]
    assert all(isinstance(m, Menu) for m in converted)
    go = converted[1]
    assert any(isinstance(i, MenuSeparator) for i in go.items)
    actions = {i.title: i for i in go.items if isinstance(i, MenuAction)}
    actions["Start Page"].function()  # what pywebview runs on a worker thread
    assert h.window.calls == [("load_url", APP + "/?write_token=SECRET")]


def test_pywebview_menu_skips_the_app_menu_when_it_is_empty(tmp_path):
    pytest.importorskip("webview.menu")
    h = Harness(tmp_path, platform="linux")
    converted = menus.pywebview_menu(h.controller.menu_bar(), h.controller.run)
    assert "__app__" not in [m.title for m in converted]


# ── window tracking and the native surfaces ───────────────────────────────────


class Events(list):
    def __iadd__(self, handler):
        self.append(handler)
        return self


class TrackedWindow(FakeWindow):
    def __init__(self):
        super().__init__()
        self.events = type("E", (), {"loaded": Events()})()


def test_watch_window_tracks_pages_and_injects_the_hook(tmp_path):
    h = Harness(tmp_path)
    window = TrackedWindow()
    h.controller.watch_window(window, context_menu=True)
    (on_loaded,) = window.events.loaded
    window.current = APP + "/map"
    on_loaded()
    assert h.controller.on_app_page
    assert window.calls == [("evaluate_js", menus.CONTEXT_MENU_JS)]
    window.current = None  # a page we wrote ourselves
    on_loaded()
    assert not h.controller.on_app_page


def test_watch_window_without_the_context_menu_only_tracks(tmp_path):
    h = Harness(tmp_path)
    window = TrackedWindow()
    h.controller.watch_window(window, context_menu=False)
    window.events.loaded[0]()
    assert window.calls == []


def test_a_failing_page_hook_is_recorded_not_raised(tmp_path):
    h = Harness(tmp_path)
    window = TrackedWindow()
    window.get_current_url = lambda: (_ for _ in ()).throw(RuntimeError("no window"))
    h.controller.watch_window(window, context_menu=True)
    window.events.loaded[0]()
    assert "page hook failed" in h.notes[-1]


def test_popup_context_is_unsupported_without_native_menus(tmp_path):
    assert Harness(tmp_path).controller.popup_context("https://example.test/") is False


def test_native_install_is_a_no_op_off_a_mac(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    assert menus.install_native_menus(h.controller, h.notes.append) is None
    assert h.notes == []


def test_native_install_failing_is_recorded_and_leaves_the_app_alone(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "objc", None)  # as if PyObjC were not installed
    assert menus.install_native_menus(h.controller, h.notes.append) is None
    assert h.notes and h.notes[-1].startswith("menu: native menus unavailable:")


# ── the bridge ────────────────────────────────────────────────────────────────


def _bridge(tmp_path, provider):
    h = Harness(tmp_path)
    return pad.DesktopBridge(h.config, menus=provider), h


def test_show_context_menu_goes_through_the_controller(tmp_path):
    seen = []

    class Controller:
        def popup_context(self, link):
            seen.append(link)
            return True

    bridge, _ = _bridge(tmp_path, lambda: Controller())
    assert bridge.show_context_menu("https://example.test/") is True
    assert bridge.show_context_menu() is True
    assert bridge.show_context_menu(["not", "a", "string"]) is True
    assert seen == ["https://example.test/", "", ""]


def test_show_context_menu_without_menus_returns_false(tmp_path):
    assert _bridge(tmp_path, None)[0].show_context_menu("x") is False
    assert _bridge(tmp_path, lambda: None)[0].show_context_menu("x") is False


def test_the_controller_is_not_reachable_from_page_javascript(tmp_path):
    """pywebview exposes every public attribute of the js_api object (recursing
    into non-callable objects), so nothing here may be public."""
    bridge, h = _bridge(tmp_path, lambda: h.controller)
    public = {name for name in dir(bridge) if not name.startswith("_")}
    assert {"show_context_menu", "app_url"} <= public
    for name in public:
        value = getattr(bridge, name)
        assert not isinstance(value, MenuController), name
    assert not any("menu" in name and name != "show_context_menu" for name in public)


def test_app_url_property_tracks_set_app_url(tmp_path):
    bridge, _ = _bridge(tmp_path, None)
    assert bridge.app_url is None
    bridge.set_app_url(APP)
    assert bridge.app_url == APP


# ── the page script, run for real ─────────────────────────────────────────────

NODE = shutil.which("node")

_HARNESS = r"""
const vm = require('vm');
// `node -e` puts the first extra argument at argv[1].
const source = JSON.parse(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const out = [];
for (const c of cases) {
  let handler = null, installs = 0;
  const calls = [];
  const document = { addEventListener: (type, fn) => { if (type === 'contextmenu') { handler = fn; installs++; } } };
  const api = c.api === false ? undefined : { show_context_menu: (link) => { calls.push(link); return c.rejects ? Promise.reject(new Error('x')) : Promise.resolve(true); } };
  const window = { pywebview: c.bridge === false ? undefined : { api } };
  const sandbox = { window, document };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  vm.runInContext(source, sandbox);  // injected again on the next page load: must not double up
  let prevented = false;
  const target = c.anchor === undefined ? { closest: () => null }
    : { closest: (sel) => (sel === 'a[href]' ? { href: c.anchor } : null) };
  handler({ defaultPrevented: !!c.defaultPrevented, target, preventDefault: () => { prevented = true; } });
  out.push({ installs, prevented, calls });
}
console.log(JSON.stringify(out));
"""


def _run_page_script(cases):
    result = subprocess.run(
        [NODE, "-e", _HARNESS, json.dumps(menus.CONTEXT_MENU_JS), json.dumps(cases)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_page_script_opens_the_menu_and_reports_links():
    got = _run_page_script([
        {},
        {"anchor": "https://example.test/a"},
        {"anchor": {"baseVal": "https://example.test/svg"}},
    ])
    assert got[0] == {"installs": 1, "prevented": True, "calls": [""]}
    assert got[1]["calls"] == ["https://example.test/a"]
    assert got[2]["calls"] == ["https://example.test/svg"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_page_script_never_takes_over_when_it_should_not():
    got = _run_page_script([
        {"defaultPrevented": True},   # the page has its own context menu
        {"bridge": False},            # no pywebview object on this page
        {"api": False},               # pywebview without our method
        {"rejects": True},            # the call fails: no unhandled rejection
    ])
    assert got[0]["prevented"] is False and got[0]["calls"] == []
    assert got[1]["prevented"] is False
    assert got[2]["prevented"] is False
    assert got[3]["prevented"] is True and got[3]["calls"] == [""]


# ── the macOS surfaces, against stand-ins for AppKit ──────────────────────────
#
# These cannot prove PyObjC behaves; the Mac check does that. They do make sure
# the macOS-only code paths run end to end (no typos, the right objects built in
# the right order) in CI, where there is no AppKit.


@pytest.fixture
def fake_cocoa(monkeypatch):
    import types

    class NSObject:
        @classmethod
        def alloc(cls):
            return cls.__new__(cls)

        def init(self):
            return self

    class NSMenuItem(NSObject):
        separator = False

        def initWithTitle_action_keyEquivalent_(self, title, action, key):
            self.title, self.action, self.key = title, action, key
            self.target = self.submenu = self.represented = None
            return self

        @classmethod
        def separatorItem(cls):
            item = cls.alloc().initWithTitle_action_keyEquivalent_("", None, "")
            item.separator = True
            return item

        def setTarget_(self, target):
            self.target = target

        def setRepresentedObject_(self, value):
            self.represented = value

        def representedObject(self):
            return self.represented

        def setSubmenu_(self, submenu):
            self.submenu = submenu

    class NSMenu(NSObject):
        def initWithTitle_(self, title):
            self.title, self.items, self.popped = title, [], []
            return self

        def addItem_(self, item):
            self.items.append(item)

        def popUpMenuPositioningItem_atLocation_inView_(self, item, location, view):
            self.popped.append((item, location, view))

    class NSEvent:
        @staticmethod
        def mouseLocation():
            return (10.0, 20.0)

    appkit = types.ModuleType("AppKit")
    appkit.NSObject, appkit.NSMenu, appkit.NSMenuItem = NSObject, NSMenu, NSMenuItem
    appkit.NSEvent = NSEvent

    objc = types.ModuleType("objc")
    objc.typedSelector = lambda _signature: (lambda function: function)
    objc.super = lambda _cls, obj: types.SimpleNamespace(init=lambda: obj)

    scheduled = []
    helper = types.ModuleType("PyObjCTools.AppHelper")
    helper.callAfter = lambda function, *a: scheduled.append((function, a))
    tools = types.ModuleType("PyObjCTools")
    tools.AppHelper = helper

    class BrowserView:
        class AppDelegate(NSObject):
            def applicationShouldTerminate_(self, app):
                return True

    cocoa = types.ModuleType("webview.platforms.cocoa")
    cocoa.BrowserView = BrowserView
    platforms = types.ModuleType("webview.platforms")
    platforms.cocoa = cocoa
    webview = types.ModuleType("webview")
    webview.platforms = platforms

    for name, module in {
        "AppKit": appkit, "objc": objc, "PyObjCTools": tools,
        "PyObjCTools.AppHelper": helper, "webview": webview,
        "webview.platforms": platforms, "webview.platforms.cocoa": cocoa,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(menus, "_cocoa", {})
    return types.SimpleNamespace(BrowserView=BrowserView, scheduled=scheduled)


def titles(menu):
    return ["-" if i.separator else i.title for i in menu.items]


def test_native_install_adds_a_dock_menu_without_touching_pywebviews_delegate(
    tmp_path, fake_cocoa
):
    h = Harness(tmp_path)
    original = fake_cocoa.BrowserView.AppDelegate
    native = menus.install_native_menus(h.controller, h.notes.append)
    assert native is not None and h.notes == []

    delegate_class = fake_cocoa.BrowserView.AppDelegate
    assert delegate_class is not original and issubclass(delegate_class, original)
    delegate = delegate_class.alloc().init()
    assert delegate.applicationShouldTerminate_(None) is True  # still pywebview's

    menu = delegate.applicationDockMenu_(None)
    assert titles(menu) == [
        "Show Demo", "Launch Pad…", "Setup & Diagnostics…", "-",
        "Show Workspace in Finder", "-", "Restart Demo",
    ]
    assert all(i.target is native._target for i in menu.items if not i.separator)
    assert [i.represented for i in menu.items if not i.separator] == [
        "show", "launchpad", "setup", "reveal_workspace", "restart",
    ]
    assert all(i.action == "performAction:" for i in menu.items if not i.separator)


def test_dock_menu_is_rebuilt_each_time_it_opens(tmp_path, fake_cocoa):
    h = Harness(tmp_path)
    menus.install_native_menus(h.controller, h.notes.append)
    delegate = fake_cocoa.BrowserView.AppDelegate.alloc().init()
    assert "Reload Page" not in titles(delegate.applicationDockMenu_(None))
    h.on_app_page()
    opened = delegate.applicationDockMenu_(None)
    assert "Reload Page" in titles(opened)
    go = next(i for i in opened.items if i.title == "Go To")
    assert [i.title for i in go.submenu.items] == ["Home", "Map", "Data tab"]
    assert [i.represented for i in go.submenu.items] == ["go:/", "go:/map", "go:/?tab=data"]


def test_dock_menu_failure_returns_no_menu_instead_of_raising(tmp_path, fake_cocoa):
    h = Harness(tmp_path)
    native = menus.install_native_menus(h.controller, h.notes.append)
    h.controller.dock_entries = lambda: (_ for _ in ()).throw(RuntimeError("nope"))
    assert native.dock_menu() is None
    assert "dock menu failed: RuntimeError: nope" in h.notes[-1]


def test_installing_twice_does_not_stack_delegates(tmp_path, fake_cocoa):
    h = Harness(tmp_path)
    menus.install_native_menus(h.controller, h.notes.append)
    installed = fake_cocoa.BrowserView.AppDelegate
    menus.install_native_menus(h.controller, h.notes.append)
    assert fake_cocoa.BrowserView.AppDelegate is installed


def test_right_click_menu_is_built_and_shown_on_the_main_thread(tmp_path, fake_cocoa):
    h = Harness(tmp_path)
    h.on_app_page()
    native = menus.install_native_menus(h.controller, h.notes.append)
    h.controller.native = native
    assert h.controller.popup_context("https://example.test/a") is True

    (function, _args), = fake_cocoa.scheduled  # queued, not run on this thread
    built = []
    original = native._menu
    native._menu = lambda entries, title="": built.append(original(entries, title)) or built[-1]
    function()
    menu = built[-1]  # submenus finish first; the pop-up menu is built last
    assert titles(menu)[:5] == ["Cut", "Copy", "Paste", "Select All", "-"]
    cut = menu.items[0]
    assert (cut.action, cut.target) == ("cut:", None)  # first responder, not us
    assert "Open Link in Browser" in titles(menu)
    assert menu.popped == [(None, (10.0, 20.0), None)]


def test_context_menu_failure_is_recorded_not_raised(tmp_path, fake_cocoa):
    h = Harness(tmp_path)
    native = menus.install_native_menus(h.controller, h.notes.append)
    h.controller.context_entries = lambda link=None: (_ for _ in ()).throw(ValueError("x"))
    native.popup_context(None)
    fake_cocoa.scheduled[0][0]()
    assert "context menu failed: ValueError: x" in h.notes[-1]


def test_menu_target_runs_actions_off_the_main_thread(tmp_path, fake_cocoa):
    import threading

    h = Harness(tmp_path)
    ran = []
    h.controller.run = lambda action: ran.append((action, threading.current_thread().name))
    native = menus.install_native_menus(h.controller, h.notes.append)
    item = menus.NativeMenus._menu(native, [Action("restart", "Restart")]).items[0]
    native._target.performAction_(item)
    for thread in threading.enumerate():
        if thread.name == "menu-action":
            thread.join(timeout=5)
    assert ran == [("restart", "menu-action")]

"""The Launch Pad: declaration, sessions, the Guest guard, and the window flow."""

import json
import os

import pytest

from prii_desktop import DesktopConfig
from prii_desktop import launcher as launch
from prii_desktop import launchpad as pad
from prii_desktop.appserver import desktop_controls_script, make_desktop_app
from prii_desktop.setup_center import configure

DECLARATION = {
    "tagline": "Demo tagline",
    "summary": "What the demo app is for.",
    "highlights": ["One", "Two"],
    "start_pages": [
        {"route": "/", "label": "Home"},
        {"route": "/map", "label": "Map", "description": "The map."},
        {"route": "/?tab=data", "label": "Data tab"},
    ],
    "operator": {"token_env": "DEMO_WRITE_TOKEN", "url_param": "write_token"},
    "guest_guard": {"allow": ["POST /api/items/*/filter", "/api/stub/**"]},
    "options": [
        {"id": "offline", "label": "Offline", "kind": "toggle", "env": "DEMO_OFFLINE"},
        {"id": "level", "label": "Level", "kind": "choice", "env": "DEMO_LEVEL",
         "default": "info", "choices": [["info", "Normal"], ["debug", "Verbose"]]},
        {"id": "region", "label": "Region", "kind": "text", "env": "DEMO_REGION",
         "pattern": "[a-z-]{0,12}"},
        {"id": "key", "label": "Key", "kind": "secret", "env": "DEMO_KEY",
         "operator_only": True},
    ],
}
_VARS = ("DEMO_WRITE_TOKEN", "DEMO_OFFLINE", "DEMO_LEVEL", "DEMO_REGION", "DEMO_KEY",
         pad.ACCESS_MODE_ENV)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in _VARS:
        monkeypatch.delenv(name, raising=False)
    # apply_session writes os.environ directly; restore whatever it leaves behind.
    before = dict(os.environ)
    yield
    for name in set(os.environ) - set(before):
        del os.environ[name]
    os.environ.update(before)


def _config(tmp_path, declaration=DECLARATION, configured=True):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<html><body></body></html>")
    config = DesktopConfig(
        app_title="Demo <App>",
        app_import="demo:app",
        repo_root=tmp_path,
        dist_dir=dist,
        app_id="Demo",
        state_dir=tmp_path / "state",
        launchpad=declaration,
    )
    if configured:
        configure(config, tmp_path / "workspace")
    return config


def _spec(declaration=DECLARATION):
    return pad.LaunchPadSpec.from_mapping(declaration)


# ── declaration ───────────────────────────────────────────────────────────────


def test_config_without_declaration_has_no_launchpad(tmp_path):
    config = _config(tmp_path, declaration=None)
    assert pad.launchpad_spec(config) is None
    assert pad.should_show(config, []) is False
    assert pad.headless_session(config, []) is None


def test_from_module_reads_launchpad():
    class Module:
        APP_TITLE = "Demo"
        APP_IMPORT = "demo:app"
        REPO_ROOT = "."
        DIST_DIR = "dist"
        LAUNCHPAD = DECLARATION

    assert DesktopConfig.from_module(Module).launchpad is DECLARATION
    del Module.LAUNCHPAD
    assert DesktopConfig.from_module(Module).launchpad is None


@pytest.mark.parametrize(
    "broken, message",
    [
        ({"colour": "red"}, "unknown keys"),
        ({"start_pages": [{"route": "https://evil.example", "label": "x"}]}, "local path"),
        ({"start_pages": [{"route": "//evil.example", "label": "x"}]}, "local path"),
        ({"options": [{"id": "A", "label": "x", "kind": "toggle", "env": "X"}]}, "snake_case"),
        ({"options": [{"id": "a", "label": "x", "kind": "slider", "env": "X"}]}, "kind"),
        ({"options": [{"id": "a", "label": "x", "kind": "toggle", "env": "1X"}]}, "env name"),
        ({"options": [{"id": "a", "label": "x", "kind": "secret", "env": "X",
                       "default": "hunter2"}]}, "no default"),
        ({"guest_guard": {"allow": ["/x"]}}, "operator declaration"),
        ({"options": [{"id": "a", "label": "x", "kind": "toggle", "env": "X",
                       "operator_only": True}]}, "operator declaration"),
        ({"operator": {"url_param": "t"}}, "needs token_env"),
        ({"operator": {}, "guest_guard": {"allow": ["api/x"]}}, "METHOD"),
        ({"operator": {}, "guest_guard": {"allow": ["GET /api/x"]}}, "bad method"),
        ({"operator": {"token_env": "T"},
          "options": [{"id": "a", "label": "x", "kind": "text", "env": "T"}]}, "reserved"),
        ({"options": [{"id": "a", "label": "x", "kind": "text",
                       "env": "PRII_ACCESS_MODE"}]}, "reserved"),
        ({"status": "not-a-reference"}, "status"),
    ],
)
def test_invalid_declarations_are_rejected(broken, message):
    with pytest.raises(ValueError, match=message):
        pad.LaunchPadSpec.from_mapping(broken)


def test_single_mode_app_has_no_access_choice(tmp_path):
    config = _config(tmp_path, declaration={"summary": "Read-only corpus."})
    spec = pad.launchpad_spec(config)
    assert spec.has_modes is False
    snap = pad.snapshot(config)
    assert snap["has_modes"] is False and snap["mode"] is None
    session = pad.build_session(spec, mode="operator", start_route="/", options={})
    assert session.mode is None
    assert pad.apply_session(spec, session) == {}
    assert pad.ACCESS_MODE_ENV not in os.environ


# ── sessions ──────────────────────────────────────────────────────────────────


def test_guest_session_sets_mode_and_no_credential():
    spec = _spec()
    session = pad.build_session(
        spec, mode="guest", start_route="/map",
        options={"offline": True, "level": "debug", "region": "san-juan", "key": "s3cret"},
    )
    assert session.secrets == {}  # operator-only: ignored for a guest
    query = pad.apply_session(spec, session)
    assert query == {}
    assert os.environ[pad.ACCESS_MODE_ENV] == "guest"
    assert os.environ["DEMO_OFFLINE"] == "1"
    assert os.environ["DEMO_LEVEL"] == "debug"
    assert os.environ["DEMO_REGION"] == "san-juan"
    assert "DEMO_WRITE_TOKEN" not in os.environ and "DEMO_KEY" not in os.environ


def test_operator_session_mints_a_token_and_hands_it_to_the_ui():
    spec = _spec()
    session = pad.build_session(
        spec, mode="operator", start_route="/", options={"key": "s3cret"}
    )
    query = pad.apply_session(spec, session)
    token = os.environ["DEMO_WRITE_TOKEN"]
    assert len(token) >= 32 and query == {"write_token": token}
    assert os.environ["DEMO_KEY"] == "s3cret"
    assert os.environ[pad.ACCESS_MODE_ENV] == "operator"
    assert pad.session_url("http://h:1", "/map", query) == f"http://h:1/map?write_token={token}"
    assert (
        pad.session_url("http://h:1", "/?tab=data", query)
        == f"http://h:1/?tab=data&write_token={token}"
    )
    assert pad.session_url("http://h:1", "/") == "http://h:1"


def test_operator_session_keeps_an_exported_token(monkeypatch):
    monkeypatch.setenv("DEMO_WRITE_TOKEN", "from-the-shell")
    spec = _spec()
    session = pad.build_session(spec, mode="operator", start_route="/", options={})
    assert pad.apply_session(spec, session) == {"write_token": "from-the-shell"}


def test_toggle_off_clears_a_variable_only_when_overriding(monkeypatch):
    spec = _spec()
    session = pad.build_session(spec, mode="guest", start_route="/", options={"offline": False})
    monkeypatch.setenv("DEMO_OFFLINE", "1")
    pad.apply_session(spec, session, override=False)
    assert os.environ["DEMO_OFFLINE"] == "1"  # headless: the shell wins
    pad.apply_session(spec, session)
    assert "DEMO_OFFLINE" not in os.environ  # Launch Pad: the explicit choice wins


@pytest.mark.parametrize(
    "options",
    [{"offline": "yes"}, {"level": "trace"}, {"region": "SAN JUAN"}, {"region": "x" * 300},
     {"region": 5}],
)
def test_bad_option_values_are_rejected(options):
    with pytest.raises(ValueError):
        pad.build_session(_spec(), mode="guest", start_route="/", options=options)


def test_mode_is_required_and_unknown_route_falls_back():
    with pytest.raises(ValueError, match="Guest or Operator"):
        pad.build_session(_spec(), mode=None, start_route="/", options={})
    session = pad.build_session(_spec(), mode="guest", start_route="/nope", options={})
    assert session.start_route == "/"


def test_preferences_round_trip_without_secrets(tmp_path):
    config = _config(tmp_path)
    spec = pad.launchpad_spec(config)
    session = pad.build_session(
        spec, mode="operator", start_route="/map",
        options={"offline": True, "key": "s3cret"},
    )
    pad.save_prefs(config, session, skip=True)
    raw = pad.prefs_file(config).read_text()
    assert "s3cret" not in raw and "token" not in raw.lower()
    prefs = pad.read_prefs(config)
    assert prefs["mode"] == "operator" and prefs["skip"] is True
    assert prefs["options"]["offline"] is True and "key" not in prefs["options"]
    restored = pad.stored_session(config, spec)
    assert (restored.mode, restored.start_route) == ("operator", "/map")
    assert restored.options["offline"] is True and restored.secrets == {}


def test_corrupt_preferences_fall_back_to_defaults(tmp_path):
    config = _config(tmp_path)
    pad.prefs_file(config).write_text("{not json")
    snap = pad.snapshot(config)
    assert snap["mode"] == "guest" and snap["start_route"] == "/" and snap["first_visit"]


# ── passphrase ────────────────────────────────────────────────────────────────


def test_passphrase_set_change_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(pad, "_FAILED_UNLOCK_DELAY", 0)
    monkeypatch.setattr(pad, "_PBKDF2_ROUNDS", 1000)
    config = _config(tmp_path)
    assert pad.passphrase_set(config) is False and pad.verify_passphrase(config, "") is True
    with pytest.raises(ValueError, match="at least"):
        pad.set_passphrase(config, "", "short")
    pad.set_passphrase(config, "", "correct horse")
    assert pad.passphrase_set(config)
    assert "correct horse" not in pad._lock_file(config).read_text()
    assert pad.verify_passphrase(config, "correct horse")
    assert not pad.verify_passphrase(config, "wrong")
    with pytest.raises(ValueError, match="not correct"):
        pad.set_passphrase(config, "wrong", "another one")
    pad.set_passphrase(config, "correct horse", "")
    assert pad.passphrase_set(config) is False


def test_locked_operator_is_never_entered_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(pad, "_PBKDF2_ROUNDS", 1000)
    config = _config(tmp_path)
    spec = pad.launchpad_spec(config)
    session = pad.build_session(spec, mode="operator", start_route="/", options={})
    pad.save_prefs(config, session, skip=True)
    assert pad.should_show(config, []) is False
    pad.set_passphrase(config, "", "correct horse")
    assert pad.should_show(config, []) is True
    assert pad.stored_session(config, spec).mode == "guest"
    with pytest.raises(SystemExit, match="passphrase-protected"):
        pad.headless_session(config, ["--no-window", "--operator"])


# ── when the page is shown ────────────────────────────────────────────────────


def test_should_show_rules(tmp_path):
    config = _config(tmp_path)
    assert pad.should_show(config, []) is True
    assert pad.should_show(config, ["--smoke"]) is False
    assert pad.should_show(config, ["--skip-launchpad"]) is False
    spec = pad.launchpad_spec(config)
    pad.save_prefs(
        config, pad.build_session(spec, mode="guest", start_route="/", options={}), skip=True
    )
    assert pad.should_show(config, []) is False
    assert pad.should_show(config, ["--launchpad"]) is True


def test_headless_leaves_the_mode_unmanaged_unless_asked(tmp_path):
    config = _config(tmp_path)
    spec, session = pad.headless_session(config, ["--no-window"])
    assert session.mode is None
    assert pad.apply_session(spec, session, override=False) == {}
    assert pad.ACCESS_MODE_ENV not in os.environ
    assert pad.headless_session(config, ["--no-window", "--guest"])[1].mode == "guest"
    assert pad.headless_session(config, ["--browser", "--operator"])[1].mode == "operator"
    assert pad.headless_session(config, ["--smoke"]) is None


# ── status ────────────────────────────────────────────────────────────────────


def test_status_rows_from_callable_and_failure(tmp_path):
    rows = [{"label": "Cases", "value": "470", "status": "pass", "detail": "loaded"},
            {"label": "Odd", "status": "purple"}]
    config = _config(tmp_path, declaration={"status": lambda: rows})
    result = pad.status_rows(config, pad.launchpad_spec(config))
    assert [row["label"] for row in result] == ["Workspace", "Cases", "Odd"]
    assert result[0]["status"] == "pass" and result[2]["status"] == "info"

    def boom():
        raise RuntimeError("db locked")

    config = _config(tmp_path, declaration={"status": boom})
    result = pad.status_rows(config, pad.launchpad_spec(config))
    assert result[-1]["status"] == "warn" and "db locked" in result[-1]["detail"]


def test_status_runs_with_the_workspace_in_the_environment(tmp_path):
    seen = {}
    config = _config(tmp_path, declaration={
        "status": lambda: seen.update(home=os.environ.get("PRII_DATA_HOME")) or []
    })
    pad.snapshot(config)
    assert seen["home"] == str((tmp_path / "workspace").resolve())


def test_snapshot_carries_no_secret_and_respects_route_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "from-shell-secret")
    monkeypatch.setenv("DEMO_LEVEL", "debug")
    config = _config(tmp_path)
    snap = pad.snapshot(config, ["--route", "/launcher"])
    assert "from-shell-secret" not in json.dumps(snap)
    assert snap["start_route"] == "/launcher"
    assert snap["start_pages"][-1]["route"] == "/launcher"
    by_id = {option["id"]: option for option in snap["options"]}
    assert by_id["level"]["value"] == "debug"  # reflects the current environment
    assert by_id["key"]["value"] == ""


# ── guest guard ───────────────────────────────────────────────────────────────


def _guarded_client(tmp_path, monkeypatch):
    import sys
    import types

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/api/items")
    def read():
        return {"ok": True}

    @app.post("/api/items")
    def create():
        return {"created": True}

    @app.post("/api/items/{name}/filter")
    def query(name: str):
        return {"filtered": name}

    @app.patch("/api/items/{name}/filter")
    def patch(name: str):
        return {"patched": name}

    @app.delete("/api/stub/a/b")
    def stub():
        return {"stub": True}

    module = types.ModuleType("demo")
    module.app = app
    monkeypatch.setitem(sys.modules, "demo", module)
    return TestClient(make_desktop_app(_config(tmp_path)))


def test_guest_guard_blocks_writes_only_in_guest_mode(tmp_path, monkeypatch):
    client = _guarded_client(tmp_path, monkeypatch)

    def status(method, path):
        return client.request(method, path).status_code

    unmanaged = status("POST", "/api/items")
    assert unmanaged == 200  # no session mode: untouched

    monkeypatch.setenv(pad.ACCESS_MODE_ENV, "guest")
    refused = client.post("/api/items")
    guest = {
        "read": status("GET", "/api/items"),
        "declared read": status("POST", "/api/items/x/filter"),
        "wrong method": status("PATCH", "/api/items/x/filter"),
        "** spans segments": status("DELETE", "/api/stub/a/b"),
    }
    assert refused.status_code == 403 and "read-only" in refused.json()["detail"]
    assert guest == {
        "read": 200,
        "declared read": 200,
        "wrong method": 403,
        "** spans segments": 200,
    }

    monkeypatch.setenv(pad.ACCESS_MODE_ENV, "operator")
    operator = status("POST", "/api/items")
    assert operator == 200


def test_single_mode_app_gets_no_guard(tmp_path):
    class App:
        def add_middleware(self, *_a, **_k):
            raise AssertionError("no guard expected")

    config = _config(tmp_path, declaration={"summary": "x"})
    assert pad.install_guest_guard(App(), config) is False


# ── page, bridge and window flow ──────────────────────────────────────────────


def test_page_escapes_the_title_and_embeds_no_data(tmp_path):
    page = pad.render_launchpad_html(_config(tmp_path))
    assert "Demo &lt;App&gt;" in page and "Demo <App>" not in page
    assert "launchpad_snapshot" in page and "Demo tagline" not in page
    assert "__TITLE__" not in page and "__ACCENT__" not in page


class _Window:
    def __init__(self):
        self.pages, self.loaded_url = [], None

    def load_html(self, page):
        self.pages.append(page)

    def load_url(self, url):
        self.loaded_url = url


def test_bridge_launch_records_session_and_preferences(tmp_path):
    config = _config(tmp_path)
    bridge = pad.DesktopBridge(config)
    bridge.await_launch()
    assert bridge.launchpad_snapshot()["app_title"] == "Demo <App>"
    with pytest.raises(ValueError):
        bridge.launchpad_launch({"mode": "admin"})
    assert not bridge.launch_requested.is_set()
    assert bridge.launchpad_launch(
        {"mode": "guest", "start_route": "/map", "options": {"offline": True}, "skip": True}
    ) == {"ok": True}
    assert bridge.launch_requested.is_set()
    assert bridge.session().start_route == "/map"
    assert pad.read_prefs(config)["skip"] is True


def test_bridge_refuses_operator_with_a_wrong_passphrase(tmp_path, monkeypatch):
    monkeypatch.setattr(pad, "_FAILED_UNLOCK_DELAY", 0)
    monkeypatch.setattr(pad, "_PBKDF2_ROUNDS", 1000)
    config = _config(tmp_path)
    bridge = pad.DesktopBridge(config)
    assert bridge.launchpad_set_passphrase("", "correct horse") == {"passphrase_set": True}
    with pytest.raises(ValueError, match="not correct"):
        bridge.launchpad_launch({"mode": "operator", "passphrase": "nope"})
    assert not bridge.launch_requested.is_set()
    bridge.launchpad_launch({"mode": "guest"})  # guest never needs it
    bridge.launchpad_launch({"mode": "operator", "passphrase": "correct horse"})
    assert bridge.session().mode == "operator"


def test_bridge_refuses_to_launch_before_setup(tmp_path):
    bridge = pad.DesktopBridge(_config(tmp_path, configured=False))
    with pytest.raises(ValueError, match="Setup"):
        bridge.launchpad_launch({"mode": "guest"})


def test_setup_hands_control_back_to_the_launch_pad(tmp_path):
    config = _config(tmp_path)
    bridge = pad.DesktopBridge(config)
    window = _Window()
    bridge.bind_window(window)
    bridge.await_launch()
    assert bridge.snapshot()["returns_to_launchpad"] is True
    bridge.open_setup()
    assert "Setup &amp; Diagnostics" in window.pages[-1]
    assert bridge.return_to_app() is True
    assert "Launch Pad" in window.pages[-1]
    bridge.apply(str(tmp_path / "workspace"))
    assert "launchpad_snapshot" in window.pages[-1]
    bridge.launchpad_launch({"mode": "guest"})
    assert bridge.snapshot()["returns_to_launchpad"] is False


def test_open_launchpad_restarts_only_when_wired(tmp_path):
    config = _config(tmp_path)
    assert pad.DesktopBridge(config).open_launchpad() is False
    calls = []
    bridge = pad.DesktopBridge(config, reopen_launchpad=lambda: calls.append(1))
    assert bridge.open_launchpad() is True and calls == [1]


def test_start_app_applies_the_session_before_the_backend_starts(tmp_path, monkeypatch):
    config = _config(tmp_path)
    spec = pad.launchpad_spec(config)
    session = pad.build_session(
        spec, mode="operator", start_route="/map", options={"offline": True}
    )
    seen = {}

    class Server:
        startup_error = None
        thread = None

    def start_server(_config, port):
        seen.update(port=port, mode=os.environ.get(pad.ACCESS_MODE_ENV),
                    offline=os.environ.get("DEMO_OFFLINE"),
                    token=os.environ.get("DEMO_WRITE_TOKEN"))
        return Server()

    monkeypatch.setattr(launch, "start_server", start_server)
    monkeypatch.setattr(launch, "wait_healthy", lambda *_a, **_k: None)
    window = _Window()
    launch.start_app(
        config, tmp_path / ".running", pad.DesktopBridge(config), window, [], {}, session
    )
    assert seen["mode"] == "operator" and seen["offline"] == "1" and seen["token"]
    assert window.loaded_url == (
        f"http://127.0.0.1:{seen['port']}/map?write_token={seen['token']}"
    )


def test_restart_arguments(tmp_path, monkeypatch):
    captured = []

    class Thread:
        def __init__(self, target, **_k):
            self.target = target

        def start(self):
            monkeypatch.setattr(launch.time, "sleep", lambda _s: None)
            monkeypatch.setattr(launch.os, "execv", lambda _exe, args: captured.append(args))
            self.target()

    monkeypatch.setattr(launch.threading, "Thread", Thread)
    monkeypatch.setattr(launch.sys, "frozen", True, raising=False)
    lock = tmp_path / ".running"
    launch.reopen_launchpad(lock, ["--route", "/map", "--skip-launchpad"])
    assert captured[-1][1:] == ["--route", "/map", "--launchpad"]
    launch.restart_process(lock, ["--launchpad", "--setup", "--route", "/map"])
    assert captured[-1][1:] == ["--route", "/map"]


def test_controls_show_the_launch_pad_button_and_mode(tmp_path, monkeypatch):
    script = desktop_controls_script(_config(tmp_path))
    assert "prii-desktop-launchpad-button" in script and "open_launchpad()" in script
    assert "if (true)" in script
    monkeypatch.setenv(pad.ACCESS_MODE_ENV, "guest")
    assert 'mode: "guest"' in desktop_controls_script(_config(tmp_path))
    monkeypatch.setenv(pad.ACCESS_MODE_ENV, '"};alert(1);//')
    assert "alert(1)" not in desktop_controls_script(_config(tmp_path))
    plain = desktop_controls_script(_config(tmp_path, declaration=None))
    assert "if (false)" in plain and "prii-desktop-setup-button" in plain


# ── the whole window flow, with pywebview faked ───────────────────────────────


class _ClosedEvent(list):
    def __iadd__(self, handler):
        self.append(handler)
        return self


def _fake_webview(monkeypatch, drive):
    """Install a stand-in ``webview`` whose start() runs ``drive`` as the user."""
    import sys
    import threading
    import types

    state = {}

    class Window(_Window):
        def __init__(self, html):
            super().__init__()
            self.pages.append(html)
            self.events = types.SimpleNamespace(
                closed=_ClosedEvent(), loaded=_ClosedEvent()
            )

    def create_window(_title, html, js_api, **_kwargs):
        state["window"], state["bridge"] = Window(html), js_api
        return state["window"]

    def start(on_ready, menu=None):
        state["menu"] = menu
        worker = threading.Thread(target=on_ready)
        worker.start()
        drive(state)
        worker.join(timeout=10)
        assert not worker.is_alive(), "the window flow never finished"

    class Menu:
        def __init__(self, title, items=()):
            self.title, self.items = title, list(items)

    class MenuAction:
        def __init__(self, title, function):
            self.title, self.function = title, function

    class MenuSeparator:
        pass

    module = types.ModuleType("webview")
    module.create_window, module.start = create_window, start
    menu_module = types.ModuleType("webview.menu")
    menu_module.Menu, menu_module.MenuAction = Menu, MenuAction
    menu_module.MenuSeparator = MenuSeparator
    module.menu = menu_module
    monkeypatch.setitem(sys.modules, "webview", module)
    monkeypatch.setitem(sys.modules, "webview.menu", menu_module)
    return state


def test_window_opens_on_the_launch_pad_and_starts_after_launch(tmp_path, monkeypatch):
    config = _config(tmp_path)
    started = []
    monkeypatch.setattr(
        launch, "start_app",
        lambda _c, _l, _b, _w, _argv, _r, session=None: started.append(session),
    )

    def drive(state):
        assert "launchpad_snapshot" in state["window"].pages[0]  # not the splash
        assert started == []  # nothing starts until the user launches
        state["bridge"].launchpad_launch({"mode": "guest", "start_route": "/map"})

    _fake_webview(monkeypatch, drive)
    launch._run_window(config, tmp_path / ".running", [])
    assert [(s.mode, s.start_route) for s in started] == [("guest", "/map")]


def test_first_run_goes_setup_then_launch_pad_then_app(tmp_path, monkeypatch):
    config = _config(tmp_path, configured=False)
    started = []
    monkeypatch.setattr(
        launch, "start_app",
        lambda _c, _l, _b, _w, _argv, _r, session=None: started.append(session),
    )

    def drive(state):
        window, bridge = state["window"], state["bridge"]
        assert "Setup &amp; Diagnostics" in window.pages[0]
        bridge.apply(str(tmp_path / "workspace"))
        assert "launchpad_snapshot" in window.pages[-1]
        assert started == []
        bridge.launchpad_launch({"mode": "operator"})

    _fake_webview(monkeypatch, drive)
    launch._run_window(config, tmp_path / ".running", [])
    assert [s.mode for s in started] == ["operator"]


def test_closing_the_window_on_the_launch_pad_starts_nothing(tmp_path, monkeypatch):
    config = _config(tmp_path)
    started = []
    monkeypatch.setattr(launch, "start_app", lambda *_a, **_k: started.append(1))

    def drive(state):
        for handler in state["window"].events.closed:
            handler()

    _fake_webview(monkeypatch, drive)
    launch._run_window(config, tmp_path / ".running", [])
    assert started == []


def test_skipped_launch_pad_reuses_stored_choices_and_honours_route(tmp_path, monkeypatch):
    config = _config(tmp_path)
    spec = pad.launchpad_spec(config)
    pad.save_prefs(
        config,
        pad.build_session(spec, mode="guest", start_route="/map", options={"offline": True}),
        skip=True,
    )
    started = []
    monkeypatch.setattr(
        launch, "start_app",
        lambda _c, _l, _b, _w, _argv, _r, session=None: started.append(session),
    )
    _fake_webview(monkeypatch, lambda state: None)
    launch._run_window(config, tmp_path / ".running", [])
    launch._run_window(config, tmp_path / ".running", ["--route", "/launcher"])
    assert [(s.mode, s.start_route, s.options["offline"]) for s in started] == [
        ("guest", "/map", True),
        ("guest", "/launcher", True),
    ]


def test_app_without_a_declaration_keeps_the_old_flow(tmp_path, monkeypatch):
    config = _config(tmp_path, declaration=None)
    started = []
    monkeypatch.setattr(
        launch, "start_app",
        lambda _c, _l, _b, _w, _argv, _r, session=None: started.append(session),
    )
    state = _fake_webview(monkeypatch, lambda state: None)
    launch._run_window(config, tmp_path / ".running", [])
    assert started == [None]
    assert "Starting" in state["window"].pages[0]


# ── menus in the window flow ──────────────────────────────────────────────────


def test_window_gets_a_menu_bar_and_tracks_its_pages(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setattr(launch, "start_app", lambda *_a, **_k: None)
    monkeypatch.setattr(launch.sys, "platform", "linux")
    seen = {}

    def drive(state):
        seen["menu"] = [m.title for m in state["menu"]]
        seen["loaded_handlers"] = len(state["window"].events.loaded)
        # No native menus off a Mac: the page keeps its own right-click behaviour.
        seen["context"] = state["bridge"].show_context_menu("https://example.test/")
        state["bridge"].launchpad_launch({"mode": "guest"})

    _fake_webview(monkeypatch, drive)
    launch._run_window(config, tmp_path / ".running", [])
    assert seen == {
        "menu": ["Go", "Tools", "Window", "Help"],
        "loaded_handlers": 1,
        "context": False,
    }


def test_a_menu_failure_never_stops_the_window(tmp_path, monkeypatch):
    config = _config(tmp_path)
    started = []
    monkeypatch.setattr(
        launch, "start_app",
        lambda _c, _l, _b, _w, _argv, _r, session=None: started.append(session),
    )

    def broken(*_args, **_kwargs):
        raise RuntimeError("menus are broken")

    monkeypatch.setattr(launch, "MenuController", broken)
    seen = {}

    def drive(state):
        seen["menu"] = state["menu"]
        seen["context"] = state["bridge"].show_context_menu("")
        state["bridge"].launchpad_launch({"mode": "guest"})

    _fake_webview(monkeypatch, drive)
    launch._run_window(config, tmp_path / ".running", [])
    assert len(started) == 1  # the app still started
    assert seen == {"menu": [], "context": False}
    log = (tmp_path / "state" / "logs" / "launcher.log").read_text()
    assert "menu: not installed: RuntimeError: menus are broken" in log

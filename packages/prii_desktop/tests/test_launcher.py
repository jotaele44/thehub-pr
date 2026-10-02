"""Unit tests for the shared desktop launcher helpers (pure — no server needed).

Ported from the per-repo ``tests/test_desktop_launch.py`` that every producer
used to carry. Covers the behaviours that regressed during development: the
stdout-safe log(), the --route display URL, and the single-instance lock (whose
path is now passed in explicitly instead of a module-level LOCK_FILE).
"""

import io
import json
import os
import socket
import sys
import pytest

from prii_desktop import launcher as launch


def test_display_url_plain():
    assert launch.display_url("http://127.0.0.1:9", []) == "http://127.0.0.1:9"


def test_display_url_route_leading_slash():
    assert (
        launch.display_url("http://127.0.0.1:9", ["--route", "/launcher"])
        == "http://127.0.0.1:9/launcher"
    )


def test_display_url_route_no_slash():
    assert (
        launch.display_url("http://127.0.0.1:9", ["--route", "launcher"])
        == "http://127.0.0.1:9/launcher"
    )


def test_display_url_route_missing_value_errors():
    # A trailing --route used to index past argv and raise IndexError.
    with pytest.raises(SystemExit):
        launch.display_url("http://127.0.0.1:9", ["--route"])


def test_display_url_route_value_is_flag_errors():
    with pytest.raises(SystemExit):
        launch.display_url("http://127.0.0.1:9", ["--route", "--browser"])


def test_log_is_safe_when_stdout_none(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    launch.log("must not raise")  # regression: bare print() raised on frozen builds


def test_log_writes_and_flushes(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    launch.log("hello")
    assert buf.getvalue() == "hello\n"


def test_free_port_is_bindable():
    port = launch.free_port()
    assert isinstance(port, int)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))  # would raise if not actually free


def test_wait_healthy_raises_on_closed_port():
    port = launch.free_port()
    with pytest.raises(SystemExit):
        launch.wait_healthy(f"http://127.0.0.1:{port}/health", timeout=0.5)


def test_pid_alive():
    assert launch._pid_alive(os.getpid()) is True
    assert launch._pid_alive(2**31 - 1) is False  # implausible pid


def test_running_instance_within_startup_grace(tmp_path, monkeypatch):
    lock = tmp_path / ".running"
    monkeypatch.setattr(launch, "_health_ok", lambda _url: False)  # not up yet

    assert launch.running_instance_base(lock) is None  # no lock

    launch.write_lock(lock, "http://127.0.0.1:1234", "http://127.0.0.1:1234/health")
    # Health is not up, but the fresh born timestamp keeps it trusted (startup).
    assert launch.running_instance_base(lock) == "http://127.0.0.1:1234"


def test_running_instance_requires_health_after_grace(tmp_path, monkeypatch):
    lock = tmp_path / ".running"
    stale = {
        "pid": os.getpid(),
        "base": "http://127.0.0.1:1234",
        "health": "http://127.0.0.1:1234/health",
        "born": 0,
    }
    lock.write_text(json.dumps(stale), encoding="utf-8")

    monkeypatch.setattr(launch, "_health_ok", lambda _url: False)
    assert launch.running_instance_base(lock) is None  # stale + unhealthy → cleared
    assert not lock.exists()

    lock.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr(launch, "_health_ok", lambda _url: True)
    assert launch.running_instance_base(lock) == "http://127.0.0.1:1234"  # healthy → live


def test_stale_pid_clears_lock(tmp_path):
    lock = tmp_path / ".running"
    lock.write_text(
        json.dumps({"pid": 2**31 - 1, "base": "x", "health": "x/health", "born": 0}),
        encoding="utf-8",
    )
    assert launch.running_instance_base(lock) is None
    assert not lock.exists()


# --- visible startup failures (regression: setup stuck on "Saving…" forever) ---


class _FakeWindow:
    def __init__(self):
        self.pages = []
        self.loaded_url = None

    def load_html(self, page):
        self.pages.append(page)

    def load_url(self, url):
        self.loaded_url = url


def _desktop_config(tmp_path):
    from prii_desktop import DesktopConfig

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body></body></html>")
    return DesktopConfig(
        app_title="Demo <App>",
        app_import="demo:app",
        repo_root=tmp_path,
        dist_dir=dist,
        app_id="Demo",
        state_dir=tmp_path / "state",
    )


def _configured(tmp_path):
    from prii_desktop.setup_center import SetupBridge, configure

    config = _desktop_config(tmp_path)
    configure(config, tmp_path / "workspace")
    return config, SetupBridge(config)


def test_start_app_shows_error_page_when_backend_import_raises(tmp_path, monkeypatch):
    config, bridge = _configured(tmp_path)
    lock = tmp_path / "state" / ".running"

    def boom(_config, _port):
        raise ImportError("No module named 'duckdb' <script>")

    monkeypatch.setattr(launch, "start_server", boom)
    window = _FakeWindow()
    launch.start_app(config, lock, bridge, window, [], {})

    assert len(window.pages) == 2
    assert "Starting" in window.pages[0]  # splash precedes the slow work
    error = window.pages[1]
    assert "could not start" in error
    assert "Try Again" in error and "api.retry()" in error
    assert "ImportError: No module named" in error
    assert "<script>" not in error and "&lt;script&gt;" in error  # escaped
    assert "Demo &lt;App&gt;" in error
    assert window.loaded_url is None
    assert not lock.exists()
    log_text = (tmp_path / "state" / "logs" / "launcher.log").read_text()
    assert "ImportError" in log_text and "Traceback" in log_text


def test_start_app_reports_unsaved_setup_instead_of_returning_silently(tmp_path):
    from prii_desktop.setup_center import SetupBridge

    config = _desktop_config(tmp_path)  # never configured
    window = _FakeWindow()
    launch.start_app(
        config, tmp_path / ".running", SetupBridge(config), window, [], {}
    )
    assert "Setup could not be saved" in window.pages[-1]
    assert window.loaded_url is None


def test_start_app_loads_url_when_backend_is_healthy(tmp_path, monkeypatch):
    config, bridge = _configured(tmp_path)
    started = {}

    class Server:
        startup_error = None
        thread = None

    monkeypatch.setattr(
        launch, "start_server", lambda _c, port: started.update(port=port) or Server()
    )
    monkeypatch.setattr(launch, "wait_healthy", lambda *_a, **_k: None)
    window = _FakeWindow()
    runtime = {}
    launch.start_app(config, tmp_path / ".running", bridge, window, [], runtime)

    assert window.loaded_url == f"http://127.0.0.1:{started['port']}"
    assert "server" in runtime
    assert len(window.pages) == 1  # splash only, no error page


def test_wait_healthy_fails_fast_with_server_startup_error():
    class Server:
        startup_error = RuntimeError("port in use")
        thread = None

    port = _closed_port()
    started = __import__("time").monotonic()
    with pytest.raises(SystemExit, match="RuntimeError: port in use"):
        launch.wait_healthy(f"http://127.0.0.1:{port}/health", timeout=30, server=Server())
    assert __import__("time").monotonic() - started < 5


def test_wait_healthy_fails_fast_when_server_thread_died():
    import threading

    thread = threading.Thread(target=lambda: None)
    thread.start()
    thread.join()

    class Server:
        startup_error = None

    server = Server()
    server.thread = thread
    with pytest.raises(SystemExit, match="exited before becoming healthy"):
        launch.wait_healthy(
            f"http://127.0.0.1:{_closed_port()}/health", timeout=30, server=server
        )


def _closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

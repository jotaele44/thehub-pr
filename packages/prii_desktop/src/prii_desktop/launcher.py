"""Launch a PRII producer as a local desktop window (shared runtime).

Starts uvicorn on a free localhost port in a background thread, waits for the
backend health endpoint, then opens a native window (pywebview) — showing a
"starting…" splash until the backend is ready. Falls back to the default browser
when pywebview is unavailable.

Ported verbatim from the per-repo ``desktop/launch.py``; the only difference is
that the app title, health path, the ASGI app, and the single-instance lock file
arrive via ``DesktopConfig`` instead of module-level imports. Entry point:
``launch(config)``.

Flags (from ``sys.argv``):
  --no-window   serve only; print the URL and block (Ctrl+C to stop)
  --browser     skip pywebview and open the default browser
  --route PATH  open the window/browser on a client route (e.g. /launcher)
  --setup       open the native Setup & Diagnostics center
  --repair      open Setup & Diagnostics with the existing workspace selected
  --smoke       start, verify health, exit 0 (used by CI and setup checks)
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

from .appserver import make_desktop_app
from .config import DesktopConfig
from .setup_center import (
    SetupBridge,
    application_support_dir,
    apply_environment,
    render_setup_html,
    setup_complete,
)

STARTUP_GRACE_SECONDS = 40.0


def _ensure_streams() -> None:
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, "w"))  # noqa: SIM115


def log(message: str) -> None:
    """Write a diagnostic without allowing logging to break control flow."""
    stream = sys.stdout
    if stream is None:
        return
    try:
        stream.write(f"{message}\n")
        stream.flush()
    except Exception:  # noqa: BLE001 - logging is best-effort
        pass


def display_url(base: str, argv: list[str]) -> str:
    if "--route" in argv:
        value_index = argv.index("--route") + 1
        if value_index >= len(argv) or argv[value_index].startswith("--"):
            raise SystemExit("--route requires a PATH value (e.g. --route /launcher)")
        return base + "/" + argv[value_index].lstrip("/")
    return base


def _pid_alive(pid: int) -> bool:
    """Perform a non-destructive process-liveness check."""
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _health_ok(health_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=1) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001 - unreachable means not reusable
        return False


def running_instance_base(lock_file: Path) -> str | None:
    """Return a live prior instance origin and clear stale locks."""
    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        pid = int(data["pid"])
        base = data["base"]
        health = data["health"]
        born = float(data["born"])
    except Exception:  # noqa: BLE001 - absent or invalid lock means no instance
        return None
    starting = (time.time() - born) < STARTUP_GRACE_SECONDS
    if _pid_alive(pid) and (_health_ok(health) or starting):
        return base
    lock_file.unlink(missing_ok=True)
    return None


def write_lock(lock_file: Path, base: str, health_url: str) -> None:
    payload = json.dumps(
        {
            "pid": os.getpid(),
            "base": base,
            "health": health_url,
            "born": time.time(),
        }
    )
    with contextlib.suppress(Exception):
        lock_file.write_text(payload, encoding="utf-8")


def clear_lock(lock_file: Path) -> None:
    lock_file.unlink(missing_ok=True)


def restart_process(lock_file: Path, argv: list[str]) -> None:
    """Restart from the signed app after setup or repair changes."""
    clean_args = [arg for arg in argv if arg not in {"--setup", "--repair"}]

    def restart() -> None:
        time.sleep(0.25)
        clear_lock(lock_file)
        if getattr(sys, "frozen", False):
            exec_args = [sys.executable, *clean_args]
        else:
            exec_args = [sys.executable, sys.argv[0], *clean_args]
        os.execv(sys.executable, exec_args)

    threading.Thread(target=restart, name="app-restart", daemon=True).start()


def finish(server, lock_file: Path) -> None:
    clear_lock(lock_file)
    server.should_exit = True
    time.sleep(0.3)
    os._exit(0)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(config: DesktopConfig, port: int):
    import uvicorn

    app = make_desktop_app(config)
    uvicorn_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    threading.Thread(target=server.run, name="uvicorn", daemon=True).start()
    return server


def wait_healthy(url: str, timeout: float = 30.0) -> None:
    """Wait for a healthy backend or raise a normal runtime failure."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - retried until deadline
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"Backend did not become healthy at {url}: {last_error}")


_FONT = "-apple-system,Segoe UI,Roboto,sans-serif"
_PAGE_CSS = (
    "html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;align-items:center;"
    f"justify-content:center;font-family:{_FONT};background:#0f172a;color:#e2e8f0;"
    "text-align:center;padding:0 32px}"
    "h1{font-size:17px;margin:0 0 10px}"
    "p{color:#94a3b8;font-size:13px;max-width:34rem}"
    "code{background:#1e293b;padding:2px 6px;border-radius:4px}"
    ".spin{width:34px;height:34px;border:4px solid #334155;border-top-color:#818cf8;"
    "border-radius:50%;animation:s .8s linear infinite;margin-bottom:18px}"
    "@keyframes s{to{transform:rotate(360deg)}}"
)


def _page(body: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<style>{_PAGE_CSS}</style></head><body>{body}</body></html>"
    )


def _splash_html(message: str, accent: str = "#818cf8") -> str:
    page = _page(f'<div class="spin"></div><p>Starting {message}…</p>')
    return page.replace("#818cf8", accent)


def _error_html(message: str, detail: str, accent: str = "#2563eb") -> str:
    return _page(
        f"<h1>{message} could not start</h1>"
        "<p>The local service did not become ready. Open Setup &amp; Diagnostics "
        "to check the installation and repair generated configuration.</p>"
        f'<button style="min-height:44px;border:0;border-radius:8px;padding:10px 16px;'
        f'background:{accent};color:#fff;font:600 14px inherit;cursor:pointer" '
        'onclick="window.pywebview.api.open_setup()">'
        "Open Setup &amp; Diagnostics</button>"
        f'<p style="color:#64748b">{detail}</p>'
    )


def _run_window(config: DesktopConfig, lock_file: Path, argv: list[str]) -> None:
    """Run first-launch setup and the producer in one native window."""
    import webview

    show_setup = (
        not setup_complete(config)
        or "--setup" in argv
        or "--repair" in argv
    )
    bridge = SetupBridge(
        config,
        restart_app=lambda: restart_process(lock_file, argv),
    )
    initial_html = (
        render_setup_html(config)
        if show_setup
        else _splash_html(config.app_title, config.brand_accent)
    )
    window = webview.create_window(
        config.app_title,
        html=initial_html,
        js_api=bridge,
        width=1280,
        height=860,
        min_size=(760, 560),
    )
    bridge.bind_window(window)
    runtime: dict[str, object] = {}
    window_closed = threading.Event()

    def on_closed() -> None:
        window_closed.set()
        bridge.completed.set()

    window.events.closed += on_closed

    def on_ready() -> None:
        if show_setup:
            bridge.completed.wait()
            if window_closed.is_set() or not setup_complete(config):
                return

        apply_environment(config)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        url = display_url(base, argv)
        bridge.set_app_url(url)
        write_lock(lock_file, base, base + config.health_path)
        server = start_server(config, port)
        runtime["server"] = server
        window.load_html(_splash_html(config.app_title, config.brand_accent))
        try:
            wait_healthy(base + config.health_path)
            window.load_url(url)
        except Exception as exc:  # noqa: BLE001 - show failure in the native window
            clear_lock(lock_file)
            log(f"backend failed to start: {exc}")
            window.load_html(
                _error_html(
                    config.app_title,
                    str(exc),
                    config.brand_accent_strong,
                )
            )

    webview.start(on_ready)
    server = runtime.get("server")
    if server is not None:
        finish(server, lock_file)
    clear_lock(lock_file)


def _block_until_interrupt(server, lock_file: Path) -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        finish(server, lock_file)


def launch(config: DesktopConfig, argv: list[str] | None = None) -> None:
    """Run the producer described by ``config`` as a desktop app."""
    _ensure_streams()
    root = str(Path(config.repo_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)

    argv = list(sys.argv[1:] if argv is None else argv)
    args = set(argv)
    state_dir = application_support_dir(config)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_file = state_dir / ".running"

    if not (args & {"--smoke", "--no-window"}):
        existing = running_instance_base(lock_file)
        if existing:
            import webbrowser

            target = display_url(existing, argv)
            log(f"{config.app_title} is already running; opening {target}")
            webbrowser.open(target)
            return

    if "--browser" not in args and not (args & {"--smoke", "--no-window"}):
        try:
            _run_window(config, lock_file, argv)
            return
        except Exception as exc:  # noqa: BLE001 - fall back to browser
            log(f"pywebview unavailable ({exc}); opening the default browser.")

    apply_environment(config)
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    url = display_url(base, argv)
    if not (args & {"--smoke", "--no-window"}):
        write_lock(lock_file, base, base + config.health_path)
    server = start_server(config, port)

    if "--smoke" in args:
        def watchdog() -> None:
            time.sleep(60)
            os._exit(2)

        threading.Thread(
            target=watchdog,
            name="smoke-watchdog",
            daemon=True,
        ).start()
        try:
            wait_healthy(base + config.health_path)
            log(f"smoke ok: {base}{config.health_path}")
            code = 0
        except Exception as exc:  # noqa: BLE001 - report and exit non-zero
            log(f"smoke failed: {exc}")
            code = 1
        server.should_exit = True
        time.sleep(0.3)
        os._exit(code)

    if "--no-window" in args:
        wait_healthy(base + config.health_path)
        log(f"{config.app_title} running at {url} (Ctrl+C to stop)")
        _block_until_interrupt(server, lock_file)
        return

    import webbrowser

    wait_healthy(base + config.health_path)
    webbrowser.open(url)
    log(f"{config.app_title} running at {url} — close this window/Ctrl+C to stop.")
    _block_until_interrupt(server, lock_file)

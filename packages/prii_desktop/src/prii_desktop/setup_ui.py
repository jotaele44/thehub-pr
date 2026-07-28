"""Native, UI-only first-run setup, repair, and diagnostics.

The packaged PRII applications already contain Python, the backend, and the
compiled frontend. This module makes that self-contained path explicit: users
choose storage, verify the package, repair local state, and launch from the
native pywebview window. It never shells out to pip, npm, Git, or Terminal.
"""

from __future__ import annotations

import base64
import json
import os
import platform
import socket
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, Callable

from .config import DesktopConfig


def _channel(value: int) -> float:
    normalized = value / 255
    if normalized <= 0.04045:
        return normalized / 12.92
    return ((normalized + 0.055) / 1.055) ** 2.4


def _rgb(value: str) -> tuple[int, int, int]:
    clean = value.strip().removeprefix("#")
    if len(clean) != 6:
        raise ValueError(f"Expected a six-digit hex colour, got {value!r}")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))


def relative_luminance(value: str) -> float:
    """WCAG relative luminance for a six-digit hex colour."""
    red, green, blue = (_channel(channel) for channel in _rgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two six-digit hex colours."""
    light, dark = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (light + 0.05) / (dark + 0.05)


def accent_foreground(accent: str) -> str:
    """Choose the higher-contrast black/white foreground for an accent."""
    return (
        "#ffffff"
        if contrast_ratio(accent, "#ffffff") >= contrast_ratio(accent, "#000000")
        else "#000000"
    )


def _application_support() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PRII"
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return Path(root) / "PRII" if root else Path.home() / "AppData" / "Local" / "PRII"
    root = os.environ.get("XDG_DATA_HOME")
    return Path(root) / "prii" if root else Path.home() / ".local" / "share" / "prii"


def state_directory(config: DesktopConfig) -> Path:
    return _application_support() / config.app_id


def state_file(config: DesktopConfig) -> Path:
    return state_directory(config) / "setup.json"


def default_data_directory(config: DesktopConfig) -> Path:
    return state_directory(config) / "data"


def load_state(config: DesktopConfig) -> dict[str, Any]:
    try:
        value = json.loads(state_file(config).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def selected_data_directory(config: DesktopConfig) -> Path:
    value = load_state(config).get("data_directory")
    return Path(value).expanduser() if value else default_data_directory(config)


def apply_setup_environment(config: DesktopConfig) -> Path:
    """Expose the selected writable data root before the backend imports."""
    target = selected_data_directory(config).resolve()
    target.mkdir(parents=True, exist_ok=True)
    os.environ["PRII_DATA_HOME"] = str(target)
    key = f"PRII_{config.app_id.upper().replace('-', '_')}_DATA_HOME"
    os.environ[key] = str(target)
    return target


def setup_complete(config: DesktopConfig) -> bool:
    state = load_state(config)
    if state.get("setup_version") != config.setup_version:
        return False
    try:
        return Path(state["data_directory"]).expanduser().is_dir()
    except (KeyError, TypeError):
        return False


def _writable_directory(path: Path) -> tuple[bool, str]:
    probe: Path | None = None
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path,
            prefix=".prii-write-",
            delete=False,
        ) as handle:
            probe = Path(handle.name)
            handle.write(b"ok\n")
        probe.unlink()
        return True, str(path)
    except OSError as exc:
        return False, str(exc)
    finally:
        if probe is not None:
            probe.unlink(missing_ok=True)


def run_diagnostics(
    config: DesktopConfig,
    *,
    data_directory: Path | None = None,
    health_url: str | None = None,
) -> list[dict[str, Any]]:
    """Run non-destructive checks suitable for first-run and repair."""
    data_directory = data_directory or selected_data_directory(config)
    writable, writable_detail = _writable_directory(data_directory)
    entry = config.frontend_entry or (config.dist_dir / "index.html")
    icon = config.icon_path
    checks: list[dict[str, Any]] = [
        {
            "id": "runtime",
            "label": "Self-contained runtime",
            "ok": bool(getattr(sys, "frozen", False)),
            "required": False,
            "detail": (
                "Embedded release runtime"
                if getattr(sys, "frozen", False)
                else "Developer checkout mode"
            ),
        },
        {
            "id": "interface",
            "label": "Compiled interface",
            "ok": entry.is_file(),
            "required": True,
            "detail": str(entry),
        },
        {
            "id": "icon",
            "label": "Product identity",
            "ok": bool(icon and icon.is_file()),
            "required": True,
            "detail": str(icon) if icon else "No icon configured",
        },
        {
            "id": "storage",
            "label": "Writable application storage",
            "ok": writable,
            "required": True,
            "detail": writable_detail,
        },
        {
            "id": "loopback",
            "label": "Private local networking",
            "ok": _loopback_available(),
            "required": True,
            "detail": "127.0.0.1 only; no public listener",
        },
    ]
    if health_url:
        checks.append(
            {
                "id": "backend",
                "label": "Local backend health",
                "ok": _health_available(health_url),
                "required": False,
                "detail": health_url,
            }
        )
    return checks


def diagnostics_pass(checks: list[dict[str, Any]]) -> bool:
    return all(check["ok"] for check in checks if check["required"])


def _loopback_available() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
        return True
    except OSError:
        return False


def _health_available(url: str) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001 - diagnostic result, never fatal
        return False


def save_state(config: DesktopConfig, data_directory: Path) -> None:
    ok, detail = _writable_directory(data_directory)
    if not ok:
        raise OSError(detail)
    payload = {
        "schema": "prii-desktop-setup/v1",
        "app_id": config.app_id,
        "setup_version": config.setup_version,
        "data_directory": str(data_directory.resolve()),
        "completed_at": datetime.now(UTC).isoformat(),
        "platform": platform.system().lower(),
    }
    target = state_file(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _icon_data_uri(config: DesktopConfig) -> str:
    path = config.icon_path
    if not path or not path.is_file():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_setup_html(
    config: DesktopConfig,
    *,
    message: str = "",
    compact: bool = False,
) -> str:
    """Return a network-free, keyboard-accessible setup/repair interface."""
    accent = config.accent
    foreground = accent_foreground(accent)
    icon = _icon_data_uri(config)
    payload = json.dumps(
        {
            "title": config.app_title,
            "accent": accent,
            "dataDirectory": str(selected_data_directory(config)),
            "complete": setup_complete(config),
            "compact": compact,
            "releasesUrl": config.releases_url,
        }
    ).replace("</", "<\\/")
    title = escape(config.app_title)
    message_html = (
        f'<p class="notice" role="status">{escape(message)}</p>' if message else ""
    )
    icon_html = (
        f'<img class="app-icon" src="{icon}" alt="" width="96" height="96" />'
        if icon
        else '<div class="app-icon fallback" aria-hidden="true"></div>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} Setup &amp; Repair</title>
  <style>
    :root {{
      color-scheme: dark;
      --accent: {accent};
      --accent-fg: {foreground};
      --bg: #080b12;
      --surface: #111722;
      --surface-2: #17202e;
      --text: #f7f9fc;
      --muted: #abb7c9;
      --border: #2a3546;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; background: var(--bg); background:
      radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--accent) 23%, transparent), transparent 42%),
      var(--bg); color: var(--text);
    }}
    main {{ width: min(760px, 100%); margin: 0 auto; padding: 40px 28px 32px; }}
    header {{ display: grid; grid-template-columns: 96px 1fr; gap: 22px; align-items: center; }}
    .app-icon {{ border-radius: 22%; box-shadow: 0 16px 50px #0008; object-fit: cover; }}
    .fallback {{ background: var(--accent); }}
    h1 {{ margin: 0; font-size: clamp(28px, 5vw, 42px); letter-spacing: -.03em; }}
    .eyebrow {{ margin: 0 0 7px; color: var(--accent); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; font-size: 12px; }}
    .lede {{ margin: 8px 0 0; color: var(--muted); line-height: 1.55; }}
    .card {{ margin-top: 28px; padding: 22px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); background: color-mix(in srgb, var(--surface) 94%, transparent); box-shadow: 0 24px 80px #0005; }}
    label {{ display: block; margin-bottom: 8px; font-weight: 700; }}
    .path-row {{ display: grid; grid-template-columns: 1fr auto; gap: 10px; }}
    input {{ width: 100%; min-height: 46px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface-2); color: var(--text); padding: 0 13px; font: inherit; }}
    button {{ min-height: 46px; border: 1px solid var(--border); border-radius: 10px; padding: 0 16px; background: var(--surface-2); color: var(--text); font: inherit; font-weight: 750; cursor: pointer; }}
    button:hover {{ border-color: var(--accent); border-color: color-mix(in srgb, var(--accent) 70%, white); }}
    button:focus-visible, input:focus-visible {{ outline: 3px solid var(--accent); outline-offset: 3px; }}
    button.primary {{ background: var(--accent); color: var(--accent-fg); border-color: transparent; }}
    button:disabled {{ opacity: .55; cursor: wait; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .checks {{ display: grid; gap: 9px; margin: 18px 0 0; padding: 0; list-style: none; }}
    .check {{ display: grid; grid-template-columns: 24px 1fr; gap: 10px; padding: 12px; border-radius: 11px; background: var(--surface-2); }}
    .check strong {{ display: block; }}
    .check small {{ color: var(--muted); overflow-wrap: anywhere; }}
    .mark {{ width: 22px; height: 22px; border-radius: 999px; display: grid; place-items: center; background: #334155; font-weight: 900; }}
    .ok .mark {{ background: #16794a; }}
    .bad .mark {{ background: #b42318; }}
    .notice {{ padding: 12px 14px; border-left: 4px solid var(--accent); background: var(--surface-2); border-radius: 8px; color: var(--muted); }}
    .status {{ min-height: 24px; margin-top: 14px; color: var(--muted); }}
    footer {{ margin-top: 20px; color: var(--muted); font-size: 12px; line-height: 1.5; }}
    @media (max-width: 600px) {{
      main {{ padding: 24px 18px; }}
      header {{ grid-template-columns: 72px 1fr; }}
      .app-icon {{ width: 72px; height: 72px; }}
      .path-row {{ grid-template-columns: 1fr; }}
      button {{ width: 100%; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
  </style>
</head>
<body>
<main>
  <header>
    {icon_html}
    <div>
      <p class="eyebrow">Native setup &amp; repair</p>
      <h1>{title}</h1>
      <p class="lede">The application runtime and interface are already included. Choose writable storage, verify the package, then launch—no Terminal, Python, Node.js, or Git required.</p>
    </div>
  </header>
  {message_html}
  <section class="card" aria-labelledby="storage-title">
    <label id="storage-title" for="data-dir">Application data location</label>
    <div class="path-row">
      <input id="data-dir" autocomplete="off" spellcheck="false" />
      <button id="choose" type="button">Choose folder</button>
    </div>
    <div class="actions">
      <button id="diagnose" type="button">Run diagnostics</button>
      <button id="repair" type="button">Repair local setup</button>
      <button id="releases" type="button">Open Releases</button>
      <button id="launch" class="primary" type="button">Save &amp; launch</button>
    </div>
    <p id="status" class="status" role="status" aria-live="polite"></p>
    <ul id="checks" class="checks" aria-label="Diagnostic checks"></ul>
  </section>
  <footer>This setup changes only local application state. Repair never deletes research data. Network services remain bound to 127.0.0.1.</footer>
</main>
<script>
  const initial = {payload};
  const pathInput = document.getElementById('data-dir');
  const statusEl = document.getElementById('status');
  const checksEl = document.getElementById('checks');
  pathInput.value = initial.dataDirectory;
  if (!initial.releasesUrl) document.getElementById('releases').hidden = true;

  const call = async (name, ...args) => {{
    if (!window.pywebview || !window.pywebview.api) {{
      throw new Error('Native setup bridge is unavailable. Reopen the packaged app.');
    }}
    return window.pywebview.api[name](...args);
  }};
  const busy = value => document.querySelectorAll('button').forEach(button => button.disabled = value);
  const renderChecks = checks => {{
    checksEl.innerHTML = '';
    checks.forEach(check => {{
      const item = document.createElement('li');
      item.className = `check ${{check.ok ? 'ok' : 'bad'}}`;
      const mark = document.createElement('span');
      mark.className = 'mark';
      mark.textContent = check.ok ? '✓' : '!';
      mark.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = check.label;
      const detail = document.createElement('small');
      detail.textContent = check.detail;
      copy.append(strong, detail);
      item.append(mark, copy);
      checksEl.append(item);
    }});
  }};
  const diagnostics = async () => {{
    busy(true); statusEl.textContent = 'Checking packaged resources and local storage…';
    try {{
      const result = await call('run_diagnostics', pathInput.value);
      renderChecks(result.checks);
      statusEl.textContent = result.ok ? 'All required checks passed.' : 'A required check needs attention.';
      return result.ok;
    }} catch (error) {{
      statusEl.textContent = String(error);
      return false;
    }} finally {{ busy(false); }}
  }};
  document.getElementById('choose').addEventListener('click', async () => {{
    try {{
      const result = await call('choose_data_directory');
      if (result.path) pathInput.value = result.path;
    }} catch (error) {{ statusEl.textContent = String(error); }}
  }});
  document.getElementById('diagnose').addEventListener('click', diagnostics);
  document.getElementById('releases').addEventListener('click', async () => {{
    try {{ await call('open_releases'); }}
    catch (error) {{ statusEl.textContent = String(error); }}
  }});
  document.getElementById('repair').addEventListener('click', async () => {{
    busy(true); statusEl.textContent = 'Repairing local setup state…';
    try {{
      const result = await call('repair_setup', pathInput.value);
      renderChecks(result.checks);
      statusEl.textContent = result.ok ? 'Repair completed safely.' : 'Repair found a packaged resource problem.';
    }} catch (error) {{ statusEl.textContent = String(error); }}
    finally {{ busy(false); }}
  }});
  document.getElementById('launch').addEventListener('click', async () => {{
    if (!await diagnostics()) return;
    busy(true); statusEl.textContent = 'Saving setup and starting the local app…';
    try {{
      const result = await call('complete_setup', pathInput.value);
      if (!result.ok) throw new Error(result.error || 'Setup could not complete.');
    }} catch (error) {{ statusEl.textContent = String(error); busy(false); }}
  }});
  window.addEventListener('pywebviewready', diagnostics, {{ once: true }});
</script>
</body>
</html>"""


class SetupBridge:
    """Methods exposed only to the local pywebview setup window."""

    def __init__(
        self,
        config: DesktopConfig,
        *,
        health_url: str,
        start_callback: Callable[[], None],
    ) -> None:
        self.config = config
        self.health_url = health_url
        self.start_callback = start_callback
        self.window: Any | None = None

    def bind_window(self, window: Any) -> None:
        self.window = window

    def setup_status(self) -> dict[str, Any]:
        return {
            "complete": setup_complete(self.config),
            "data_directory": str(selected_data_directory(self.config)),
        }

    def choose_data_directory(self) -> dict[str, str | None]:
        if self.window is None:
            return {"path": None}
        import webview

        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return {"path": None}
        path = result[0] if isinstance(result, (list, tuple)) else result
        return {"path": str(path)}

    def run_diagnostics(self, data_directory: str) -> dict[str, Any]:
        checks = run_diagnostics(
            self.config,
            data_directory=Path(data_directory).expanduser(),
            health_url=self.health_url if _health_available(self.health_url) else None,
        )
        return {"ok": diagnostics_pass(checks), "checks": checks}

    def repair_setup(self, data_directory: str) -> dict[str, Any]:
        target = Path(data_directory).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        state_directory(self.config).mkdir(parents=True, exist_ok=True)
        checks = run_diagnostics(
            self.config,
            data_directory=target,
            health_url=self.health_url if _health_available(self.health_url) else None,
        )
        ok = diagnostics_pass(checks)
        if ok:
            save_state(self.config, target)
            apply_setup_environment(self.config)
        return {"ok": ok, "checks": checks}

    def complete_setup(self, data_directory: str) -> dict[str, Any]:
        try:
            target = Path(data_directory).expanduser()
            checks = run_diagnostics(self.config, data_directory=target)
            if not diagnostics_pass(checks):
                return {"ok": False, "error": "Required diagnostics did not pass."}
            save_state(self.config, target)
            apply_setup_environment(self.config)
            threading.Thread(
                target=self.start_callback,
                name="prii-start-after-setup",
                daemon=True,
            ).start()
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001 - returned to native UI
            return {"ok": False, "error": str(exc)}

    def open_setup(self) -> dict[str, bool]:
        if self.window is not None:
            html = render_setup_html(self.config, compact=True)
            threading.Thread(
                target=lambda: self.window.load_html(html),
                name="prii-open-setup",
                daemon=True,
            ).start()
        return {"ok": True}

    def open_releases(self) -> dict[str, bool]:
        if self.config.releases_url:
            webbrowser.open(self.config.releases_url)
        return {"ok": True}


def setup_smoke(config: DesktopConfig) -> tuple[bool, list[dict[str, Any]]]:
    """Fresh-machine, non-interactive setup contract used by frozen CI builds."""
    with tempfile.TemporaryDirectory(prefix="prii-setup-smoke-") as tmp:
        checks = run_diagnostics(config, data_directory=Path(tmp) / "data")
        return diagnostics_pass(checks), checks


def wait_for_bridge(timeout: float = 10.0) -> None:
    """Small test/debug helper for pywebview startup synchronization."""
    time.sleep(min(timeout, 0.01))

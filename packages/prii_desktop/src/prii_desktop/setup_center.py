"""Native, UI-first setup, repair, and diagnostics for desktop producers.

The frozen app already contains Python, the backend, and the built frontend.
This module only creates per-user writable directories and records the user's
workspace choice. It deliberately uses the standard library so first launch
does not download tools, run a shell, or mutate the signed application bundle.
"""

from __future__ import annotations

import base64
import html
import importlib
import json
import os
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import DesktopConfig

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_STATE_FILE = "setup.json"
_WORKSPACE_DIRS = ("data", "exports", "logs")


def application_support_dir(
    config: DesktopConfig,
    *,
    platform: str | None = None,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """Return a writable, per-user state location outside the app bundle."""
    if config.state_dir is not None:
        return Path(config.state_dir)

    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    environ = dict(os.environ) if environ is None else environ
    app_folder = config.app_id or config.app_title

    if platform == "darwin":
        return home / "Library" / "Application Support" / app_folder
    if platform == "win32":
        base = Path(environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return base / app_folder
    base = Path(environ.get("XDG_CONFIG_HOME", home / ".config"))
    return base / app_folder


def default_workspace_dir(config: DesktopConfig) -> Path:
    """Recommended workspace shown on first launch."""
    return application_support_dir(config) / "Workspace"


def state_file(config: DesktopConfig) -> Path:
    return application_support_dir(config) / _STATE_FILE


def read_state(config: DesktopConfig) -> dict[str, Any] | None:
    """Read and validate generated setup state; invalid state means first run."""
    try:
        value = json.loads(state_file(config).read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("app_id") != config.app_id
            or int(value.get("setup_version", 0)) < config.setup_version
            or not isinstance(value.get("workspace"), str)
            or not value["workspace"].strip()
        ):
            return None
        return value
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def setup_complete(config: DesktopConfig) -> bool:
    state = read_state(config)
    return state is not None and Path(state["workspace"]).is_dir()


def _write_state(config: DesktopConfig, payload: dict[str, Any]) -> None:
    root = application_support_dir(config)
    root.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".setup-", suffix=".json", dir=root
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, state_file(config))
    finally:
        Path(temp_name).unlink(missing_ok=True)


def configure(config: DesktopConfig, workspace: str | Path) -> dict[str, Any]:
    """Create writable app directories and atomically record the selection."""
    selected = Path(workspace).expanduser().resolve()
    selected.mkdir(parents=True, exist_ok=True)
    for child in _WORKSPACE_DIRS:
        (selected / child).mkdir(exist_ok=True)
    payload = {
        "app_id": config.app_id,
        "setup_version": config.setup_version,
        "workspace": str(selected),
        "configured_at": datetime.now(timezone.utc).isoformat(),
    }
    apply_environment(config, payload)
    _run_setup_action(config)
    _write_state(config, payload)
    return payload


def _run_setup_action(config: DesktopConfig) -> None:
    """Run a producer's small idempotent workspace initializer, if declared."""
    if not config.setup_action:
        return
    module_name, separator, function_name = config.setup_action.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError(
            f"Invalid setup action {config.setup_action!r}; expected module:function"
        )
    module = (
        importlib.reload(sys.modules[module_name])
        if module_name in sys.modules
        else importlib.import_module(module_name)
    )
    function = getattr(module, function_name)
    function()


def apply_environment(
    config: DesktopConfig, state: dict[str, Any] | None = None
) -> Path:
    """Expose the selected writable workspace to the producer backend."""
    state = read_state(config) if state is None else state
    workspace = (
        Path(state["workspace"])
        if state is not None
        else default_workspace_dir(config)
    )
    os.environ["PRII_DATA_HOME"] = str(workspace)
    os.environ[config.data_env_var] = str(workspace)
    return workspace


def _writable_check(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".diagnostic-", dir=path)
        os.close(descriptor)
        Path(name).unlink(missing_ok=True)
        return True, f"Writable: {path}"
    except OSError as exc:
        return False, f"Not writable: {path} ({exc})"


def diagnostics(
    config: DesktopConfig, workspace: str | Path | None = None
) -> list[dict[str, str]]:
    """Return user-safe diagnostic results for the native setup screen."""
    state = read_state(config)
    selected = Path(
        workspace
        or (state["workspace"] if state is not None else default_workspace_dir(config))
    ).expanduser()
    writable, writable_detail = _writable_check(selected)
    bundled = bool(getattr(sys, "frozen", False))
    index = Path(config.dist_dir) / "index.html"
    icon_ok = config.icon_path is None or Path(config.icon_path).is_file()

    return [
        {
            "label": "Self-contained runtime",
            "status": "pass" if bundled else "info",
            "detail": (
                "Bundled app — no separate Python, Node.js, or Git installation."
                if bundled
                else "Source/developer runtime; release builds are self-contained."
            ),
        },
        {
            "label": "Application interface",
            "status": "pass" if (index.is_file() or not config.attach_frontend) else "fail",
            "detail": (
                f"Bundled interface found at {index}."
                if index.is_file()
                else (
                    "Interface is supplied by the repository adapter."
                    if not config.attach_frontend
                    else "The bundled interface is missing. Reinstall the app."
                )
            ),
        },
        {
            "label": "App icon",
            "status": "pass" if icon_ok else "fail",
            "detail": (
                "Bundled app artwork is available."
                if icon_ok
                else "The bundled app artwork is missing. Reinstall the app."
            ),
        },
        {
            "label": "Workspace",
            "status": "pass" if writable else "fail",
            "detail": writable_detail,
        },
        {
            "label": "Setup record",
            "status": "pass" if state is not None else "info",
            "detail": (
                "Setup is complete."
                if state is not None
                else "Setup will be completed when you save this screen."
            ),
        },
    ]


def _safe_color(value: str, fallback: str) -> str:
    return value if _HEX.fullmatch(value) else fallback


def _icon_markup(config: DesktopConfig) -> str:
    if config.icon_path is None or not Path(config.icon_path).is_file():
        return '<div class="mark" aria-hidden="true"></div>'
    encoded = base64.b64encode(Path(config.icon_path).read_bytes()).decode("ascii")
    return (
        f'<img class="mark" alt="" aria-hidden="true" '
        f'src="data:image/png;base64,{encoded}">'
    )


def render_setup_html(config: DesktopConfig) -> str:
    """Render the accessible native Setup & Diagnostics interface."""
    title = html.escape(config.app_title)
    accent = _safe_color(config.brand_accent, "#2563eb")
    strong = _safe_color(config.brand_accent_strong, "#1d4ed8")
    icon = _icon_markup(config)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} Setup &amp; Diagnostics</title>
  <style>
    :root {{ color-scheme: light dark; --brand:{accent}; --brand-strong:{strong}; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; color:#172033; background:#f7f8fb;
      font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(760px,calc(100% - 32px)); margin:0 auto; padding:42px 0; }}
    .hero {{ display:flex; align-items:center; gap:16px; margin-bottom:24px; }}
    .mark {{ width:52px; height:52px; border-radius:14px; background:var(--brand);
      box-shadow:inset 0 0 0 1px rgba(255,255,255,.32),0 8px 24px rgba(15,23,42,.16); }}
    h1 {{ margin:0; font-size:26px; letter-spacing:-.025em; }}
    .lede {{ margin:4px 0 0; color:#526075; }}
    section {{ background:#fff; border:1px solid #d8dee9; border-radius:16px;
      padding:22px; margin:16px 0; box-shadow:0 8px 28px rgba(15,23,42,.06); }}
    h2 {{ margin:0 0 8px; font-size:17px; }}
    p {{ margin:6px 0; }}
    label {{ display:block; margin:16px 0 7px; font-weight:650; }}
    .picker {{ display:grid; grid-template-columns:1fr auto; gap:8px; }}
    input {{ min-width:0; width:100%; border:1px solid #aab4c3; border-radius:9px;
      padding:10px 12px; color:#172033; background:#fff; font:inherit; }}
    button {{ min-height:44px; border:1px solid transparent; border-radius:9px;
      padding:9px 15px; font:650 14px/1.2 inherit; cursor:pointer; }}
    button:focus-visible,input:focus-visible {{ outline:3px solid color-mix(in srgb,
      var(--brand) 70%, #fff); outline-offset:2px; }}
    .primary {{ color:#fff; background:var(--brand-strong); }}
    .secondary {{ color:#172033; background:#eef1f6; border-color:#c8d0dc; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:18px; }}
    .checks {{ list-style:none; padding:0; margin:14px 0 0; display:grid; gap:8px; }}
    .check {{ display:grid; grid-template-columns:22px 1fr; gap:9px; padding:10px;
      border-radius:10px; background:#f5f7fa; }}
    .dot {{ width:13px; height:13px; margin-top:4px; border-radius:50%; background:#64748b; }}
    .pass .dot {{ background:#15803d; }} .fail .dot {{ background:#b42318; }}
    .check strong {{ display:block; }} .detail {{ color:#526075; font-size:13px; }}
    #status {{ min-height:24px; margin-top:10px; color:#334155; }}
    .quiet {{ color:#526075; font-size:13px; }}
    [hidden] {{ display:none !important; }}
    @media (prefers-color-scheme:dark) {{
      body {{ color:#f8fafc; background:#070b14; }}
      section {{ background:#101827; border-color:#334155; }}
      .lede,.quiet,.detail,#status {{ color:#a9b4c5; }}
      input {{ color:#f8fafc; background:#0b1220; border-color:#59677b; }}
      .secondary {{ color:#f8fafc; background:#1e293b; border-color:#475569; }}
      .check {{ background:#172033; }}
    }}
    @media (max-width:560px) {{ .picker {{ grid-template-columns:1fr; }} }}
    @media (prefers-reduced-motion:reduce) {{ * {{ scroll-behavior:auto !important; }} }}
  </style>
</head>
<body>
<main>
  <header class="hero">
    {icon}
    <div><h1>{title} Setup &amp; Diagnostics</h1>
      <p class="lede">No Terminal, Python, Node.js, or Git installation required.</p></div>
  </header>
  <section aria-labelledby="workspace-title">
    <h2 id="workspace-title">Choose a workspace</h2>
    <p>This writable folder holds local data, exports, logs, and generated settings.
      The app itself stays unchanged in Applications.</p>
    <label for="workspace">Workspace folder</label>
    <div class="picker">
      <input id="workspace" autocomplete="off" spellcheck="false">
      <button id="choose" class="secondary" type="button">Choose Folder…</button>
    </div>
    <p class="quiet">The recommended location is private to your macOS account.</p>
    <div class="actions">
      <button id="save" class="primary" type="button">Save &amp; Open App</button>
      <button id="repair" class="secondary" type="button">Repair Configuration</button>
      <button id="back" class="secondary" type="button" hidden>Back to App</button>
    </div>
    <div id="status" role="status" aria-live="polite"></div>
  </section>
  <section aria-labelledby="diagnostics-title">
    <h2 id="diagnostics-title">Diagnostics</h2>
    <p>These checks run locally and do not upload data.</p>
    <button id="diagnose" class="secondary" type="button">Run Diagnostics</button>
    <ul id="checks" class="checks" aria-live="polite"></ul>
  </section>
</main>
<script>
  const $ = (id) => document.getElementById(id);
  const api = () => window.pywebview && window.pywebview.api;
  const setBusy = (busy, message="") => {{
    ["save","repair","choose","diagnose"].forEach(id => $(id).disabled = busy);
    $("status").textContent = message;
  }};
  const showChecks = (checks) => {{
    $("checks").replaceChildren(...checks.map(check => {{
      const li = document.createElement("li");
      li.className = `check ${{check.status}}`;
      const dot = document.createElement("span");
      dot.className = "dot"; dot.setAttribute("aria-hidden","true");
      const copy = document.createElement("div");
      const label = document.createElement("strong"); label.textContent = check.label;
      const detail = document.createElement("span"); detail.className = "detail";
      detail.textContent = check.detail;
      copy.append(label, detail); li.append(dot, copy); return li;
    }}));
  }};
  const refresh = async () => {{
    if (!api()) return;
    const state = await api().snapshot();
    $("workspace").value = state.workspace;
    $("back").hidden = !state.can_return;
    $("save").textContent = state.can_return
      ? "Save & Restart App"
      : "Save & Open App";
    $("repair").textContent = state.can_return
      ? "Repair & Restart App"
      : "Repair Configuration";
    showChecks(state.diagnostics);
  }};
  $("choose").addEventListener("click", async () => {{
    setBusy(true, "Opening folder picker…");
    try {{
      const selected = await api().choose_workspace();
      if (selected) $("workspace").value = selected;
      setBusy(false);
    }} catch (error) {{ setBusy(false, String(error)); }}
  }});
  $("diagnose").addEventListener("click", async () => {{
    setBusy(true, "Running local checks…");
    try {{
      showChecks(await api().run_diagnostics($("workspace").value));
      setBusy(false, "Diagnostics complete.");
    }} catch (error) {{ setBusy(false, String(error)); }}
  }});
  $("repair").addEventListener("click", async () => {{
    setBusy(true, "Repairing generated configuration and restarting the app…");
    try {{
      const state = await api().repair($("workspace").value);
      $("workspace").value = state.workspace; showChecks(state.diagnostics);
      setBusy(false, state.can_return
        ? "Configuration repaired. Restarting the app…"
        : "Configuration repaired. Your data was not deleted.");
    }} catch (error) {{ setBusy(false, String(error)); }}
  }});
  $("save").addEventListener("click", async () => {{
    setBusy(true, "Saving configuration and starting the app…");
    try {{ await api().apply($("workspace").value); }}
    catch (error) {{ setBusy(false, String(error)); }}
  }});
  $("back").addEventListener("click", () => api().return_to_app());
  window.addEventListener("pywebviewready", refresh);
</script>
</body>
</html>"""


class SetupBridge:
    """pywebview API exposed to setup and in-app desktop controls."""

    def __init__(
        self,
        config: DesktopConfig,
        *,
        choose_directory: Callable[[Path], str | Path | None] | None = None,
        restart_app: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.completed = threading.Event()
        self._window: Any = None
        self._app_url: str | None = None
        self._choose_directory = choose_directory
        self._restart_app = restart_app

    def bind_window(self, window: Any) -> None:
        self._window = window

    def set_app_url(self, url: str) -> None:
        self._app_url = url

    def snapshot(self) -> dict[str, Any]:
        state = read_state(self.config)
        workspace = (
            state["workspace"] if state is not None else str(default_workspace_dir(self.config))
        )
        return {
            "workspace": workspace,
            "configured": state is not None,
            "can_return": self._app_url is not None,
            "diagnostics": diagnostics(self.config, workspace),
        }

    def choose_workspace(self) -> str:
        current = Path(self.snapshot()["workspace"])
        if self._choose_directory is not None:
            selected = self._choose_directory(current)
        else:
            import webview

            result = self._window.create_file_dialog(
                webview.FOLDER_DIALOG, directory=str(current.parent)
            )
            selected = result[0] if isinstance(result, (list, tuple)) and result else result
        return "" if selected is None else str(selected)

    def run_diagnostics(self, workspace: str | None = None) -> list[dict[str, str]]:
        return diagnostics(self.config, workspace or None)

    def apply(self, workspace: str) -> dict[str, Any]:
        if not workspace.strip():
            raise ValueError("Choose a workspace folder before continuing.")
        configure(self.config, workspace)
        result = self.snapshot()
        self.completed.set()
        if self._app_url is not None:
            if self._restart_app is not None:
                self._restart_app()
            elif self._window is not None:
                self._window.load_url(self._app_url)
        return result

    def repair(self, workspace: str | None = None) -> dict[str, Any]:
        state = read_state(self.config)
        selected = workspace or (
            state["workspace"] if state is not None else str(default_workspace_dir(self.config))
        )
        configure(self.config, selected)
        result = self.snapshot()
        if self._app_url is not None and self._restart_app is not None:
            self._restart_app()
        return result

    def open_setup(self) -> bool:
        if self._window is None:
            return False
        self._window.load_html(render_setup_html(self.config))
        return True

    def return_to_app(self) -> bool:
        if self._window is None or self._app_url is None:
            return False
        self._window.load_url(self._app_url)
        return True

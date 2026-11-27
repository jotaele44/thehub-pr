"""Native menus for the shared desktop runtime.

One list of actions feeds three surfaces, so what a person can do does not depend
on where they reach for it:

* the **menu bar** -- pywebview's public ``menu=`` argument, so it works on every
  platform pywebview supports: an app-menu extension plus Go, Tools, Window and
  Help menus;
* the **Dock tile menu** (macOS) -- an ``applicationDockMenu:`` on the
  application delegate;
* the **right-click menu** (macOS) -- opened from the page, because pywebview
  empties WebKit's own context menu.

Everything that can be decided without a window -- what each menu holds, which
entries are offered in which state, what an action does -- is plain Python and is
unit-tested. The two macOS-only surfaces sit at the bottom of the module, import
PyObjC lazily, and fail soft: if PyObjC or pywebview's internals are not what this
code expects, the problem is written to the launcher log and the app carries on
with the menus it already had.

Two pywebview facts shape the code:

* A native menu callback runs on the main thread, and ``window.get_current_url()``
  blocks on the main thread. Menus therefore never call into the window while
  they are being built; they read a URL cached by the ``loaded`` event. Actions
  run on a worker thread, where window calls are safe.
* Every public, non-callable attribute of the ``js_api`` object is exposed to page
  JavaScript. The controller is only ever reached through a private attribute.
"""

from __future__ import annotations

import functools
import os
import platform as _platform
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import DesktopConfig
from .launchpad import LaunchPadSpec, session_url
from .setup_center import application_support_dir, diagnostics, read_state

# ── Model ─────────────────────────────────────────────────────────────────────


class _Separator:
    __slots__ = ()

    def __repr__(self) -> str:
        return "SEPARATOR"


SEPARATOR = _Separator()


@dataclass(frozen=True)
class Action:
    """An entry that runs a named action (see ``MenuController.run``)."""

    id: str
    label: str


@dataclass(frozen=True)
class Responder:
    """A standard editing command, sent to whatever has focus (Cut, Copy, ...)."""

    label: str
    selector: str


@dataclass(frozen=True)
class Submenu:
    label: str
    items: tuple["Entry", ...]


Entry = Union[_Separator, Action, Responder, Submenu]


@dataclass(frozen=True)
class MenuBar:
    """``app`` extends the application menu; ``menus`` are the extra top-level menus."""

    app: tuple[Entry, ...]
    menus: tuple[Submenu, ...]


def tidy(entries: Sequence[Entry]) -> tuple[Entry, ...]:
    """Drop empty submenus and leading, trailing and doubled separators."""
    out: list[Entry] = []
    for entry in entries:
        if isinstance(entry, Submenu):
            inner = tidy(entry.items)
            if not inner:
                continue
            entry = Submenu(entry.label, inner)
        if entry is SEPARATOR and (not out or out[-1] is SEPARATOR):
            continue
        out.append(entry)
    while out and out[-1] is SEPARATOR:
        out.pop()
    return tuple(out)


# ── Small pure helpers ────────────────────────────────────────────────────────


def file_manager_name(platform: str | None = None) -> str:
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return "Finder"
    if platform == "win32":
        return "File Explorer"
    return "Files"


def page_origin(url: str | None) -> str | None:
    """``scheme://host:port`` of an http(s) address, else ``None``."""
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def clean_page_url(url: str, drop_param: str | None = None) -> str:
    """An address that is safe to copy or open elsewhere.

    Removes the Operator credential parameter, so a copied or browser-opened
    address never carries a write token. Everything else is kept as is.
    """
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not drop_param or key != drop_param
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def link_target(url: str | None) -> str | None:
    """A link worth acting on: http(s), bounded, no control characters."""
    if not url or len(url) > 2048 or any(ord(char) < 32 for char in url):
        return None
    return url if page_origin(url) else None


def _copy_command(platform: str) -> Callable[[str], bool] | None:
    if platform != "darwin":
        return None

    def copy(text: str) -> bool:
        # pbcopy assumes the legacy Mac encoding when LANG is unset, which is the
        # case for an app started from the Finder or the Dock.
        env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}
        subprocess.run(
            ["pbcopy"], input=text.encode("utf-8"), env=env, check=True, timeout=5
        )
        return True

    return copy


def _detached(argv: list[str]) -> None:
    subprocess.Popen(  # noqa: S603 - fixed argv, never a shell
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


# ── Controller ────────────────────────────────────────────────────────────────


class MenuController:
    """Decides what each menu offers and carries out the chosen action.

    Everything that touches the outside world is injected, so the controller is
    exercised in tests without a window, a clipboard or a file manager.
    """

    def __init__(
        self,
        config: DesktopConfig,
        spec: LaunchPadSpec | None,
        *,
        window: Callable[[], Any],
        app_url: Callable[[], str | None],
        open_setup: Callable[[], Any],
        open_launchpad: Callable[[], Any] | None,
        restart: Callable[[], Any],
        record: Callable[[str], Any] | None = None,
        platform: str | None = None,
        run_command: Callable[[list[str]], Any] | None = None,
        copy_text: Callable[[str], bool] | None = None,
        open_url: Callable[[str], Any] | None = None,
    ) -> None:
        self._config = config
        self._spec = spec
        self._window = window
        self._app_url = app_url
        self._open_setup = open_setup
        self._open_launchpad = open_launchpad
        self._restart = restart
        self._record = record
        self._platform = sys.platform if platform is None else platform
        self._run_command = run_command or _detached
        self._copy_text = copy_text or _copy_command(self._platform)
        self._open_url = open_url or webbrowser.open
        self._page_url: str | None = None
        self._link: str | None = None
        #: Set by the launcher once the macOS-only surfaces are installed.
        self.native: NativeMenus | None = None

    # State ------------------------------------------------------------------

    def note_loaded(self, url: str | None) -> None:
        """Remember what the window last finished loading (``None`` for our own pages)."""
        self._page_url = url

    @property
    def on_app_page(self) -> bool:
        """True while the window shows the app itself, not Setup, the Launch Pad or an error."""
        origin = page_origin(self._app_url())
        return origin is not None and origin == page_origin(self._page_url)

    def _note(self, message: str) -> None:
        if self._record is not None:
            try:
                self._record(message)
            except Exception:  # noqa: BLE001 - reporting must never break a menu
                pass

    # Paths ------------------------------------------------------------------

    def _workspace_dir(self) -> Path | None:
        state = read_state(self._config)
        return Path(state["workspace"]).expanduser() if state else None

    def _data_dir(self) -> Path:
        return application_support_dir(self._config)

    def _logs_dir(self) -> Path:
        return self._data_dir() / "logs"

    def _log_file(self) -> Path:
        return self._logs_dir() / "launcher.log"

    @property
    def _has_launchpad(self) -> bool:
        return self._spec is not None and self._open_launchpad is not None

    @property
    def _can_copy(self) -> bool:
        return self._copy_text is not None

    # Menus ------------------------------------------------------------------

    def _go_entries(self) -> tuple[Entry, ...]:
        pages = self._spec.start_pages if self._spec is not None else ()
        return tuple(Action(f"go:{page.route}", page.label) for page in pages)

    def menu_bar(self) -> MenuBar:
        """The static menu bar. Items stay valid in every state; ones that need the
        app page to be showing do nothing while Setup or the Launch Pad is open."""
        title = self._config.app_title
        fm = file_manager_name(self._platform)

        app: list[Entry] = [Action("setup", "Setup & Diagnostics…")]
        if self._has_launchpad:
            app.append(Action("launchpad", "Launch Pad…"))
        app.append(Action("restart", f"Restart {title}"))

        go: list[Entry] = [
            Action("back", "Back"),
            Action("forward", "Forward"),
            Action("reload", "Reload Page"),
            SEPARATOR,
            Action("home", "Start Page"),
            SEPARATOR,
            *self._go_entries(),
        ]
        tools: list[Entry] = [
            Action("open_page", "Open Page in Browser"),
            SEPARATOR,
            Action("reveal_workspace", f"Show Workspace in {fm}"),
            Action("reveal_data", f"Show App Data in {fm}"),
        ]
        if self._can_copy:
            tools.insert(0, Action("copy_page", "Copy Page Address"))
        window: list[Entry] = [
            Action("minimize", "Minimize"),
            Action("show", "Bring to Front"),
        ]
        help_: list[Entry] = [
            Action("open_log", "Open Launcher Log"),
            Action("reveal_logs", f"Show Logs in {fm}"),
        ]
        if self._can_copy:
            help_ += [SEPARATOR, Action("copy_diagnostics", "Copy Diagnostics Summary")]

        if self._platform != "darwin":
            # Only macOS has an application menu to extend ("__app__").
            tools = [*app, SEPARATOR, *tools]
            app = []
        return MenuBar(
            app=tidy(app),
            menus=tuple(
                Submenu(label, tidy(items))
                for label, items in (
                    ("Go", go),
                    ("Tools", tools),
                    ("Window", window),
                    ("Help", help_),
                )
            ),
        )

    def dock_entries(self) -> tuple[Entry, ...]:
        """Built each time the Dock menu opens, so it reflects the window's state."""
        title = self._config.app_title
        fm = file_manager_name(self._platform)
        items: list[Entry] = [Action("show", f"Show {title}")]
        if self._has_launchpad:
            items.append(Action("launchpad", "Launch Pad…"))
        items.append(Action("setup", "Setup & Diagnostics…"))
        if self.on_app_page:
            go = self._go_entries()
            if go:
                items += [SEPARATOR, Submenu("Go To", go)]
            items += [
                SEPARATOR,
                Action("reload", "Reload Page"),
                Action("open_page", "Open Page in Browser"),
            ]
        items.append(SEPARATOR)
        if self._workspace_dir() is not None:
            items.append(Action("reveal_workspace", f"Show Workspace in {fm}"))
        if self._logs_dir().is_dir():
            items.append(Action("reveal_logs", f"Show Logs in {fm}"))
        items += [SEPARATOR, Action("restart", f"Restart {title}")]
        return tidy(items)

    def context_entries(self, link: str | None = None) -> tuple[Entry, ...]:
        """Built each time the right-click menu opens. ``link`` is the address under
        the pointer, if any; it is validated here and remembered for its actions."""
        self._link = link_target(link)
        items: list[Entry] = [
            Responder("Cut", "cut:"),
            Responder("Copy", "copy:"),
            Responder("Paste", "paste:"),
            Responder("Select All", "selectAll:"),
        ]
        if self._link:
            items.append(SEPARATOR)
            items.append(Action("open_link", "Open Link in Browser"))
            if self._can_copy:
                items.append(Action("copy_link", "Copy Link Address"))
        if self.on_app_page:
            items += [
                SEPARATOR,
                Action("back", "Back"),
                Action("forward", "Forward"),
                Action("reload", "Reload Page"),
                SEPARATOR,
            ]
            if self._can_copy:
                items.append(Action("copy_page", "Copy Page Address"))
            items.append(Action("open_page", "Open Page in Browser"))
            go = self._go_entries()
            if go:
                items += [SEPARATOR, Submenu("Go To", go)]
        items.append(SEPARATOR)
        if self._has_launchpad:
            items.append(Action("launchpad", "Launch Pad…"))
        items.append(Action("setup", "Setup & Diagnostics…"))
        return tidy(items)

    def popup_context(self, link: str | None = None) -> bool:
        """Open the right-click menu at the pointer. ``False`` where unsupported."""
        return self.native.popup_context(link) if self.native is not None else False

    # Actions ----------------------------------------------------------------

    def run(self, action_id: str) -> bool:
        """Carry out ``action_id``. Never raises; ``False`` means nothing was done."""
        try:
            if action_id.startswith("go:"):
                return self._go(action_id[3:])
            handler = self._handlers().get(action_id)
            if handler is None:
                self._note(f"menu: unknown action {action_id!r}")
                return False
            return handler() is not False
        except Exception as exc:  # noqa: BLE001 - a menu click must never crash the app
            self._note(f"menu: {action_id} failed: {type(exc).__name__}: {exc}")
            return False

    def _handlers(self) -> dict[str, Callable[[], Any]]:
        return {
            "setup": lambda: self._open_setup(),
            "launchpad": self._launchpad,
            "restart": lambda: self._restart(),
            "show": self._show,
            "minimize": lambda: self._window().minimize(),
            "back": lambda: self._history("back"),
            "forward": lambda: self._history("forward"),
            "reload": self._reload,
            "home": self._home,
            "copy_page": lambda: self._copy(self._page_address()),
            "open_page": lambda: self._open(self._page_address()),
            "copy_link": lambda: self._copy(self._link),
            "open_link": lambda: self._open(self._link),
            "reveal_workspace": lambda: self._reveal(self._workspace_dir(), "workspace"),
            "reveal_data": lambda: self._reveal(self._data_dir(), "app data"),
            "reveal_logs": lambda: self._reveal(self._logs_dir(), "logs"),
            "open_log": lambda: self._reveal(self._log_file(), "launcher log"),
            "copy_diagnostics": lambda: self._copy(self.diagnostics_text()),
        }

    def _skip(self, reason: str) -> bool:
        self._note(f"menu: skipped, {reason}")
        return False

    def _launchpad(self) -> bool:
        if self._open_launchpad is None:
            return self._skip("this app has no Launch Pad")
        self._open_launchpad()
        return True

    def _show(self) -> None:
        window = self._window()
        window.restore()  # a no-op unless the window is minimised
        window.show()

    def _history(self, direction: str) -> bool:
        if not self.on_app_page:
            return self._skip(f"{direction} needs the app page")
        self._window().evaluate_js(f"history.{direction}()")
        return True

    def _reload(self) -> bool:
        if not self.on_app_page:
            return self._skip("reload needs the app page")
        window = self._window()
        url = window.get_current_url()
        if not url:
            return self._skip("no page address to reload")
        window.load_url(url)
        return True

    def _home(self) -> bool:
        url = self._app_url()
        if not url:
            return self._skip("the app has not started")
        self._window().load_url(url)
        return True

    def _go(self, route: str) -> bool:
        declared = {page.route for page in (self._spec.start_pages if self._spec else ())}
        origin = page_origin(self._app_url())
        if route not in declared:
            return self._skip(f"{route!r} is not a declared start page")
        if origin is None:
            return self._skip("the app has not started")
        self._window().load_url(session_url(origin, route))
        return True

    def _page_address(self) -> str | None:
        if not self.on_app_page:
            return None
        url = self._window().get_current_url()
        if not url:
            return None
        operator = self._spec.operator if self._spec is not None else None
        return clean_page_url(url, operator.url_param if operator else None)

    def _copy(self, text: str | None) -> bool:
        if not text:
            return self._skip("nothing to copy")
        if self._copy_text is None:
            return self._skip("copying is not supported on this platform")
        return bool(self._copy_text(text))

    def _open(self, url: str | None) -> bool:
        if not url:
            return self._skip("no address to open")
        self._open_url(url)
        return True

    def _reveal(self, path: Path | None, what: str) -> bool:
        if path is None or not path.exists():
            return self._skip(f"the {what} does not exist yet")
        if self._platform == "win32":
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                return self._skip("cannot open folders on this platform")
            startfile(str(path))
            return True
        opener = "open" if self._platform == "darwin" else "xdg-open"
        self._run_command([opener, str(path)])
        return True

    def diagnostics_text(self) -> str:
        """A plain-text summary for a bug report. Holds no credential and no environment."""
        title = self._config.app_title
        workspace = self._workspace_dir()
        lines = [
            f"{title} desktop diagnostics",
            f"Time: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
            f"System: {_platform.platform()}",
            f"Python: {sys.version.split()[0]}",
            f"Bundled app: {'yes' if getattr(sys, 'frozen', False) else 'no'}",
            f"Workspace: {workspace if workspace is not None else 'not set'}",
            f"App data: {self._data_dir()}",
            f"Launcher log: {self._log_file()}",
            "",
            "Checks:",
        ]
        for row in diagnostics(self._config):
            lines.append(f"  [{row['status']}] {row['label']}: {row['detail']}")
        return "\n".join(lines) + "\n"

    # Window hooks -------------------------------------------------------------

    def watch_window(self, window: Any, *, context_menu: bool) -> None:
        """Track what the window shows; optionally hook right-click in each page."""

        def on_loaded() -> None:
            try:
                self.note_loaded(window.get_current_url())
                if context_menu:
                    window.evaluate_js(CONTEXT_MENU_JS)
            except Exception as exc:  # noqa: BLE001
                self._note(f"menu: page hook failed: {type(exc).__name__}: {exc}")

        window.events.loaded += on_loaded


#: Injected into each page. Leaves the page alone when it handles the event itself
#: or when the bridge is missing, so it can only ever add a menu, never remove one.
CONTEXT_MENU_JS = """
(function () {
  if (window.__priiContextMenu) { return; }
  window.__priiContextMenu = true;
  document.addEventListener('contextmenu', function (event) {
    if (event.defaultPrevented) { return; }
    var api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.show_context_menu !== 'function') { return; }
    var link = '';
    var node = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (node) {
      var href = node.href;
      link = String(href && href.baseVal !== undefined ? href.baseVal : href || '');
    }
    event.preventDefault();
    var pending = api.show_context_menu(link);
    if (pending && typeof pending.catch === 'function') { pending.catch(function () {}); }
  }, false);
})();
true;
"""


# ── pywebview menu bar ────────────────────────────────────────────────────────


def pywebview_menu(bar: MenuBar, run: Callable[[str], Any]) -> list[Any]:
    """Convert ``bar`` to pywebview ``Menu`` objects for ``webview.start(menu=...)``."""
    from webview.menu import Menu, MenuAction, MenuSeparator

    def convert(entries: Sequence[Entry]) -> list[Any]:
        out: list[Any] = []
        for entry in entries:
            if entry is SEPARATOR:
                out.append(MenuSeparator())
            elif isinstance(entry, Action):
                out.append(MenuAction(entry.label, functools.partial(run, entry.id)))
            elif isinstance(entry, Submenu):
                out.append(Menu(entry.label, convert(entry.items)))
            # A Responder needs the responder chain, which pywebview's menus lack.
        return out

    menus: list[Any] = []
    if bar.app:
        menus.append(Menu("__app__", convert(bar.app)))
    menus.extend(Menu(menu.label, convert(menu.items)) for menu in bar.menus)
    return menus


# ── macOS: Dock tile menu and right-click menu ────────────────────────────────

_cocoa: dict[str, Any] = {}


def _cocoa_target_class() -> Any:
    """The Objective-C object menu items send their action to (defined once)."""
    if "target" not in _cocoa:
        import AppKit
        import objc

        class PriiMenuTarget(AppKit.NSObject):
            def initWithController_(self, controller):
                self = objc.super(PriiMenuTarget, self).init()
                if self is None:
                    return None
                self._controller = controller
                return self

            @objc.typedSelector(b"v@:@")
            def performAction_(self, sender):
                # Off the main thread: actions call into the window, which blocks.
                threading.Thread(
                    target=self._controller.run,
                    args=(str(sender.representedObject()),),
                    name="menu-action",
                    daemon=True,
                ).start()

        _cocoa["target"] = PriiMenuTarget
    return _cocoa["target"]


class NativeMenus:
    """Builds NSMenus from the controller's entries for the Dock and for right-click."""

    def __init__(self, controller: MenuController, record: Callable[[str], Any]) -> None:
        import AppKit
        from PyObjCTools import AppHelper

        self._controller = controller
        self._record = record
        self._appkit = AppKit
        self._helper = AppHelper
        # Menu items hold their target weakly: this reference keeps it alive.
        self._target = _cocoa_target_class().alloc().initWithController_(controller)

    def _menu(self, entries: Sequence[Entry], title: str = "") -> Any:
        appkit = self._appkit
        menu = appkit.NSMenu.alloc().initWithTitle_(title)
        for entry in entries:
            if entry is SEPARATOR:
                menu.addItem_(appkit.NSMenuItem.separatorItem())
            elif isinstance(entry, Action):
                item = appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    entry.label, "performAction:", ""
                )
                item.setTarget_(self._target)
                item.setRepresentedObject_(entry.id)
                menu.addItem_(item)
            elif isinstance(entry, Responder):
                # No target: AppKit walks the responder chain from the web view.
                menu.addItem_(
                    appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        entry.label, entry.selector, ""
                    )
                )
            elif isinstance(entry, Submenu):
                item = appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    entry.label, None, ""
                )
                item.setSubmenu_(self._menu(entry.items, entry.label))
                menu.addItem_(item)
        return menu

    def dock_menu(self) -> Any:
        """Called by AppKit, on the main thread, each time the Dock menu opens."""
        try:
            entries = self._controller.dock_entries()
            return self._menu(entries) if entries else None
        except Exception as exc:  # noqa: BLE001
            self._record(f"menu: dock menu failed: {type(exc).__name__}: {exc}")
            return None

    def popup_context(self, link: str | None) -> bool:
        def show() -> None:
            try:
                menu = self._menu(self._controller.context_entries(link))
                menu.popUpMenuPositioningItem_atLocation_inView_(
                    None, self._appkit.NSEvent.mouseLocation(), None
                )
            except Exception as exc:  # noqa: BLE001
                self._record(f"menu: context menu failed: {type(exc).__name__}: {exc}")

        self._helper.callAfter(show)
        return True


def install_native_menus(
    controller: MenuController, record: Callable[[str], Any]
) -> NativeMenus | None:
    """Add the Dock tile menu (macOS). Call after ``import webview``, before
    ``webview.start``. Returns ``None`` where unsupported, and never raises."""
    if sys.platform != "darwin":
        return None
    try:
        import objc
        from webview.platforms import cocoa

        browser_view = cocoa.BrowserView
        native = NativeMenus(controller, record)
        base: Any = browser_view.AppDelegate  # a pyobjc class, untyped
        if getattr(base, "_prii_dock_menu", False):
            return native

        # pywebview creates its application delegate lazily, from this attribute,
        # when the first window opens. A subclass adds the Dock menu without
        # replacing any method pywebview already defines.
        class PriiAppDelegate(base):
            _prii_dock_menu = True

            @objc.typedSelector(b"@@:@")
            def applicationDockMenu_(self, sender):
                return native.dock_menu()

        browser_view.AppDelegate = PriiAppDelegate
        return native
    except Exception as exc:  # noqa: BLE001 - fail soft: keep the menus we already had
        record(f"menu: native menus unavailable: {type(exc).__name__}: {exc}")
        return None

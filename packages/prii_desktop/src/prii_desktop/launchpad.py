"""The Launch Pad: a native pre-launch screen shown before the backend starts.

A producer opts in by declaring ``LAUNCHPAD`` in its ``desktop/config.py``. The
shared runtime then opens on this screen instead of going straight to the app,
and the user picks, before anything is imported or served:

* how to enter -- **Guest** (read-only) or **Operator** (may change data), when
  the producer has anything to protect;
* which page the app opens on;
* the producer's own pre-launch options, each of which maps to an environment
  variable applied before the backend is imported.

Everything here is standard library only, like the setup center: the screen must
work even when the producer backend cannot be imported at all.

What "Guest" means is deliberately narrow and honest. It is a mode of *this
desktop session*, enforced by :class:`GuestGuard` on the local server this
process starts. It is not a security boundary against someone who can already
run programs as the same operating-system user; the optional Operator passphrase
stops casual use of Operator mode on a shared machine and nothing more.

Declaration (all keys optional except where noted)::

    LAUNCHPAD = {
        "tagline": "Federation control plane",
        "summary": "One paragraph: what this app is for.",
        "highlights": ["Short capability", "Another one"],
        "status": "desktop.launchpad:status",   # or a callable
        "start_pages": [
            {"route": "/", "label": "Recent activity", "description": "..."},
        ],
        "guest": {"label": "Guest", "description": "Browse without changing data."},
        "operator": {                 # omit for an app with nothing to protect
            "label": "Operator",
            "description": "Create and edit records.",
            "token_env": "PRII_WRITE_TOKEN",   # backend's write-credential variable
            "url_param": "write_token",        # how the UI is handed that credential
        },
        "guest_guard": {"allow": ["POST /api/entities/*/filter", "/api/tools/**"]},
        "options": [
            {"id": "offline", "label": "Work offline", "help": "...",
             "kind": "toggle", "env": "APP_OFFLINE", "default": False,
             "on_value": "1", "off_value": None, "operator_only": False},
            {"id": "level", "label": "Log level", "kind": "choice",
             "env": "LOG_LEVEL", "default": "info",
             "choices": [["info", "Normal"], ["debug", "Verbose"]]},
            {"id": "region", "label": "Region", "kind": "text", "env": "REGION",
             "default": "", "pattern": "[A-Za-z-]{0,20}"},
            {"id": "key", "label": "API key", "kind": "secret", "env": "API_KEY"},
        ],
    }

``status`` returns rows of ``{"label", "value", "status", "detail"}`` where
``status`` is one of ``pass``, ``warn``, ``fail``, ``info``. It runs before the
backend exists, so it must read files, not call the API.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import re
import secrets
import tempfile
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .config import DesktopConfig
from .setup_center import (
    SetupBridge,
    _icon_markup,
    _safe_color,
    application_support_dir,
    apply_environment,
    read_state,
)

#: Set for the backend for the lifetime of a Launch Pad session.
ACCESS_MODE_ENV = "PRII_ACCESS_MODE"
#: The Launch Pad's ledger of what it changed in the environment, so a restart
#: can put the shell's environment back (see ``scrub_managed_environment``).
MANAGED_ENV = "PRII_LAUNCHPAD_MANAGED"
ORIGINAL_ENV = "PRII_LAUNCHPAD_ORIGINAL"
GUEST = "guest"
OPERATOR = "operator"

_PREFS_FILE = "launchpad.json"
_LOCK_FILE = "operator-lock.json"
_PREFS_VERSION = 1
_KINDS = ("toggle", "choice", "text", "secret")
_STATUSES = ("pass", "warn", "fail", "info")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPTION_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_URL_PARAM = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_TEXT_LIMIT = 200
_PBKDF2_ROUNDS = 310_000
_MIN_PASSPHRASE = 8
_FAILED_UNLOCK_DELAY = 1.0

GUEST_REFUSAL = (
    "Guest sessions are read-only. Return to the Launch Pad and choose "
    "Operator to make changes."
)


# ── Declaration ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StartPage:
    route: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    kind: str
    env: str
    help: str = ""
    default: Any = None
    choices: tuple[tuple[str, str], ...] = ()
    on_value: str = "1"
    off_value: str | None = None
    operator_only: bool = False
    pattern: str | None = None
    placeholder: str = ""


@dataclass(frozen=True)
class OperatorSpec:
    label: str = "Operator"
    description: str = "Full access: this session may change data."
    token_env: str | None = None
    url_param: str | None = None


@dataclass(frozen=True)
class LaunchPadSpec:
    """A validated ``LAUNCHPAD`` declaration."""

    tagline: str = ""
    summary: str = ""
    highlights: tuple[str, ...] = ()
    status: Callable[[], Any] | str | None = None
    start_pages: tuple[StartPage, ...] = (StartPage("/", "Home"),)
    guest_label: str = "Guest"
    guest_description: str = "Read-only: browse without changing anything."
    operator: OperatorSpec | None = None
    guest_allow: tuple[str, ...] = ()
    options: tuple[Option, ...] = ()

    @property
    def has_modes(self) -> bool:
        return self.operator is not None

    def option(self, option_id: str) -> Option | None:
        return next((item for item in self.options if item.id == option_id), None)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LaunchPadSpec":
        if not isinstance(raw, Mapping):
            raise ValueError("LAUNCHPAD must be a mapping")
        known = {
            "tagline", "summary", "highlights", "status", "start_pages",
            "guest", "operator", "guest_guard", "options",
        }
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ValueError(f"LAUNCHPAD has unknown keys: {', '.join(unknown)}")

        pages = tuple(_start_page(item) for item in raw.get("start_pages") or ())
        if not pages:
            pages = (StartPage("/", "Home"),)
        if len({page.route for page in pages}) != len(pages):
            raise ValueError("LAUNCHPAD start_pages routes must be unique")

        options = tuple(_option(item) for item in raw.get("options") or ())
        if len({item.id for item in options}) != len(options):
            raise ValueError("LAUNCHPAD option ids must be unique")
        if len({item.env for item in options}) != len(options):
            raise ValueError("LAUNCHPAD options must not share an environment variable")

        operator = _operator(raw.get("operator"))
        guest = raw.get("guest") or {}
        guard = raw.get("guest_guard") or {}
        if not isinstance(guest, Mapping) or not isinstance(guard, Mapping):
            raise ValueError("LAUNCHPAD guest and guest_guard must be mappings")
        if operator is None:
            if guest or guard:
                raise ValueError(
                    "LAUNCHPAD guest/guest_guard need an operator declaration: "
                    "without one there is a single mode and nothing to guard"
                )
            if any(item.operator_only for item in options):
                raise ValueError(
                    "LAUNCHPAD operator_only options need an operator declaration"
                )
        reserved = {ACCESS_MODE_ENV, MANAGED_ENV, ORIGINAL_ENV} | (
            {operator.token_env} if operator and operator.token_env else set()
        )
        clash = sorted(item.env for item in options if item.env in reserved)
        if clash:
            raise ValueError(
                f"LAUNCHPAD options may not set reserved variables: {', '.join(clash)}"
            )
        allow = tuple(str(item) for item in guard.get("allow") or ())
        for pattern in allow:
            _compile_allow(pattern)

        status = raw.get("status")
        if status is not None and not callable(status) and not _is_reference(status):
            raise ValueError("LAUNCHPAD status must be a callable or 'module:function'")

        return cls(
            tagline=str(raw.get("tagline") or ""),
            summary=str(raw.get("summary") or ""),
            highlights=tuple(str(item) for item in raw.get("highlights") or ()),
            status=status,
            start_pages=pages,
            guest_label=str(guest.get("label") or "Guest"),
            guest_description=str(
                guest.get("description")
                or "Read-only: browse without changing anything."
            ),
            operator=operator,
            guest_allow=allow,
            options=options,
        )


def _compile_allow(pattern: str) -> tuple[str | None, "re.Pattern[str]"]:
    """``"[METHOD ]/path"``; ``*`` is one path segment, ``**`` is any depth."""
    prefix, _space, path = pattern.rpartition(" ")
    method = prefix.strip().upper() or None
    if method is not None and method not in _UNSAFE_METHODS:
        raise ValueError(f"LAUNCHPAD guest_guard allow has a bad method: {pattern!r}")
    if not path.startswith("/"):
        raise ValueError(
            f"LAUNCHPAD guest_guard allow must be '[METHOD ]/path': {pattern!r}"
        )
    regex = "".join(
        ".*" if part == "**" else "[^/]*" if part == "*" else re.escape(part)
        for part in re.split(r"(\*\*|\*)", path)
    )
    return method, re.compile(regex)


def _is_reference(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    module, separator, function = value.partition(":")
    return bool(module and separator and function)


def _start_page(raw: Any) -> StartPage:
    if not isinstance(raw, Mapping) or "route" not in raw or "label" not in raw:
        raise ValueError("LAUNCHPAD start_pages entries need route and label")
    route = str(raw["route"])
    if not route.startswith("/") or route.startswith("//") or "\\" in route:
        raise ValueError(f"LAUNCHPAD start page route must be a local path: {route!r}")
    return StartPage(route, str(raw["label"]), str(raw.get("description") or ""))


def _option(raw: Any) -> Option:
    if not isinstance(raw, Mapping):
        raise ValueError("LAUNCHPAD options entries must be mappings")
    missing = [key for key in ("id", "label", "kind", "env") if key not in raw]
    if missing:
        raise ValueError(f"LAUNCHPAD option is missing: {', '.join(missing)}")
    option_id, kind, env = str(raw["id"]), str(raw["kind"]), str(raw["env"])
    if not _OPTION_ID.fullmatch(option_id):
        raise ValueError(f"LAUNCHPAD option id must be snake_case: {option_id!r}")
    if kind not in _KINDS:
        raise ValueError(f"LAUNCHPAD option {option_id}: kind must be one of {_KINDS}")
    if not _ENV_NAME.fullmatch(env):
        raise ValueError(f"LAUNCHPAD option {option_id}: invalid env name {env!r}")

    choices: tuple[tuple[str, str], ...] = ()
    default = raw.get("default")
    if kind == "toggle":
        default = bool(default)
    elif kind == "choice":
        choices = tuple(
            (str(item[0]), str(item[1])) for item in raw.get("choices") or ()
        )
        if not choices:
            raise ValueError(f"LAUNCHPAD option {option_id}: choice needs choices")
        values = [value for value, _label in choices]
        default = values[0] if default is None else str(default)
        if default not in values:
            raise ValueError(
                f"LAUNCHPAD option {option_id}: default is not one of its choices"
            )
    elif kind == "text":
        default = "" if default is None else str(default)
    else:  # secret: never has a default and is never stored
        if default not in (None, ""):
            raise ValueError(f"LAUNCHPAD option {option_id}: a secret has no default")
        default = ""

    pattern = raw.get("pattern")
    if pattern is not None:
        re.compile(str(pattern))
    off_value = raw.get("off_value")
    return Option(
        id=option_id,
        label=str(raw["label"]),
        kind=kind,
        env=env,
        help=str(raw.get("help") or ""),
        default=default,
        choices=choices,
        on_value=str(raw.get("on_value", "1")),
        off_value=None if off_value is None else str(off_value),
        operator_only=bool(raw.get("operator_only", False)),
        pattern=None if pattern is None else str(pattern),
        placeholder=str(raw.get("placeholder") or ""),
    )


def _operator(raw: Any) -> OperatorSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("LAUNCHPAD operator must be a mapping")
    token_env = raw.get("token_env")
    url_param = raw.get("url_param")
    if token_env is not None and not _ENV_NAME.fullmatch(str(token_env)):
        raise ValueError(f"LAUNCHPAD operator token_env is invalid: {token_env!r}")
    if url_param is not None:
        if not _URL_PARAM.fullmatch(str(url_param)):
            raise ValueError(f"LAUNCHPAD operator url_param is invalid: {url_param!r}")
        if token_env is None:
            raise ValueError("LAUNCHPAD operator url_param needs token_env")
    return OperatorSpec(
        label=str(raw.get("label") or "Operator"),
        description=str(
            raw.get("description") or "Full access: this session may change data."
        ),
        token_env=None if token_env is None else str(token_env),
        url_param=None if url_param is None else str(url_param),
    )


def launchpad_spec(config: DesktopConfig) -> LaunchPadSpec | None:
    """The producer's validated declaration, or ``None`` when it has not opted in."""
    raw = config.launchpad
    if raw is None:
        return None
    return raw if isinstance(raw, LaunchPadSpec) else LaunchPadSpec.from_mapping(raw)


# ── Stored preferences and the Operator passphrase ────────────────────────────


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=".launchpad-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def prefs_file(config: DesktopConfig) -> Path:
    return application_support_dir(config) / _PREFS_FILE


def read_prefs(config: DesktopConfig) -> dict[str, Any]:
    """Last-used Launch Pad choices. Never contains a secret or a token."""
    value = _read_json(prefs_file(config))
    options = value.get("options")
    return {
        "mode": value.get("mode") if value.get("mode") in (GUEST, OPERATOR) else None,
        "start_route": (
            value.get("start_route")
            if isinstance(value.get("start_route"), str)
            else None
        ),
        "options": dict(options) if isinstance(options, dict) else {},
        "skip": value.get("skip") is True,
        "saved": bool(value),
    }


def _lock_file(config: DesktopConfig) -> Path:
    return application_support_dir(config) / _LOCK_FILE


def passphrase_set(config: DesktopConfig) -> bool:
    record = _read_json(_lock_file(config))
    return bool(record.get("salt") and record.get("hash"))


def _derive(passphrase: str, salt: bytes, rounds: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, rounds)


def verify_passphrase(config: DesktopConfig, passphrase: str) -> bool:
    """Constant-time check. True when no passphrase is set."""
    record = _read_json(_lock_file(config))
    if not (record.get("salt") and record.get("hash")):
        return True
    try:
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
        rounds = int(record.get("rounds", _PBKDF2_ROUNDS))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_derive(passphrase or "", salt, rounds), expected)


def set_passphrase(config: DesktopConfig, current: str, new: str) -> None:
    """Set, change, or (with an empty ``new``) remove the Operator passphrase."""
    if not verify_passphrase(config, current):
        time.sleep(_FAILED_UNLOCK_DELAY)
        raise ValueError("The current Operator passphrase is not correct.")
    if not new:
        _lock_file(config).unlink(missing_ok=True)
        return
    if len(new) < _MIN_PASSPHRASE:
        raise ValueError(
            f"Use at least {_MIN_PASSPHRASE} characters for the Operator passphrase."
        )
    salt = secrets.token_bytes(16)
    _write_json(
        _lock_file(config),
        {
            "salt": salt.hex(),
            "hash": _derive(new, salt, _PBKDF2_ROUNDS).hex(),
            "rounds": _PBKDF2_ROUNDS,
        },
    )


# ── Sessions ──────────────────────────────────────────────────────────────────


@dataclass
class Session:
    """One resolved set of launch choices. ``secrets`` is never written to disk."""

    mode: str | None = None
    start_route: str = "/"
    options: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)


def _initial_value(option: Option, saved: Mapping[str, Any]) -> Any:
    """Saved choice, else what the environment already says, else the default."""
    if option.kind == "secret":
        return ""
    if option.id in saved:
        try:
            return _clean_value(option, saved[option.id])
        except ValueError:
            pass
    current = os.environ.get(option.env)
    if current is not None:
        if option.kind == "toggle":
            return current == option.on_value
        try:
            return _clean_value(option, current)
        except ValueError:
            pass
    return option.default


def _clean_value(option: Option, value: Any) -> Any:
    if option.kind == "toggle":
        if not isinstance(value, bool):
            raise ValueError(f"{option.label}: expected on or off.")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{option.label}: expected text.")
    if option.kind == "choice":
        if value not in {choice for choice, _label in option.choices}:
            raise ValueError(f"{option.label}: that choice is not available.")
        return value
    text = value.strip()
    if len(text) > _TEXT_LIMIT or "\x00" in text or "\n" in text or "\r" in text:
        raise ValueError(f"{option.label}: the value is too long or malformed.")
    if option.kind == "text" and option.pattern and not re.fullmatch(option.pattern, text):
        raise ValueError(f"{option.label}: the value is not in the expected format.")
    return text


def build_session(
    spec: LaunchPadSpec,
    *,
    mode: str | None,
    start_route: str | None,
    options: Mapping[str, Any] | None,
    saved: Mapping[str, Any] | None = None,
) -> Session:
    """Validate raw choices (from the page or from stored preferences)."""
    if spec.has_modes:
        if mode not in (GUEST, OPERATOR):
            raise ValueError("Choose Guest or Operator before launching.")
    else:
        mode = None
    routes = {page.route for page in spec.start_pages}
    route = start_route if start_route in routes else spec.start_pages[0].route

    raw = dict(options or {})
    stored = dict(saved or {})
    session = Session(mode=mode, start_route=route)
    for option in spec.options:
        if option.operator_only and mode == GUEST:
            # A guest never turns on an operator-only capability, whatever the
            # page sent: fall back to the declared default.
            value = "" if option.kind == "secret" else option.default
        elif option.id in raw:
            value = _clean_value(option, raw[option.id])
        else:
            value = _initial_value(option, stored)
        if option.kind == "secret":
            if value:
                session.secrets[option.id] = value
        else:
            session.options[option.id] = value
    return session


def save_prefs(config: DesktopConfig, session: Session, *, skip: bool) -> None:
    _write_json(
        prefs_file(config),
        {
            "version": _PREFS_VERSION,
            "mode": session.mode,
            "start_route": session.start_route,
            "options": session.options,
            "skip": bool(skip),
        },
    )


def _env_value(option: Option, value: Any) -> str | None:
    if option.kind == "toggle":
        return option.on_value if value else option.off_value
    return value or None


def _read_ledger(env: Mapping[str, str]) -> tuple[list[str], dict[str, str]]:
    names = [
        name
        for name in env.get(MANAGED_ENV, "").split(",")
        if _ENV_NAME.fullmatch(name)
    ]
    try:
        raw = json.loads(env.get(ORIGINAL_ENV) or "{}")
    except ValueError:
        raw = {}
    original = {
        str(name): value
        for name, value in (raw.items() if isinstance(raw, dict) else ())
        if _ENV_NAME.fullmatch(str(name)) and isinstance(value, str)
    }
    return names, original


def scrub_managed_environment(
    environ: MutableMapping[str, str] | None = None,
) -> MutableMapping[str, str]:
    """Undo every variable a Launch Pad session set, restoring the shell's values.

    ``apply_session`` keeps a ledger (``PRII_LAUNCHPAD_MANAGED`` and
    ``PRII_LAUNCHPAD_ORIGINAL``) of what it changed. A process restarted with
    ``os.execv`` inherits the environment, so without this an Operator write
    credential, a secret the user typed, or an option value would leak into the
    next session -- including a Guest one. Returns the environment it scrubbed.
    """
    env = os.environ if environ is None else environ
    names, original = _read_ledger(env)
    for name in names:
        env.pop(name, None)
    env.update(original)
    env.pop(MANAGED_ENV, None)
    env.pop(ORIGINAL_ENV, None)
    return env


def apply_session(
    spec: LaunchPadSpec,
    session: Session,
    *,
    override: bool = True,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Write the session into the environment the backend is about to inherit.

    Returns the query parameters the app URL must carry (the write credential,
    when the producer's UI takes it that way). ``override=False`` is the headless
    path: an explicitly exported shell variable wins over a stored preference.

    Whatever a previous session in this process family set is undone first (see
    :func:`scrub_managed_environment`), so each session starts from the shell's
    own environment, and every change made here is recorded for the next scrub.
    """
    env = os.environ if environ is None else environ
    scrub_managed_environment(env)
    managed: list[str] = []
    original: dict[str, str] = {}

    def record(name: str) -> None:
        if name not in managed:
            managed.append(name)
            if name in env:
                original[name] = env[name]

    def put(name: str, value: str) -> None:
        record(name)
        env[name] = value

    def drop(name: str) -> None:
        if name in env:
            record(name)
            env.pop(name)

    guest = session.mode == GUEST
    for option in spec.options:
        # A guest never inherits an operator-only capability, not even one the
        # shell exported: that would defeat the point of the mode.
        withheld = option.operator_only and guest
        if option.kind == "secret":
            secret = session.secrets.get(option.id)
            if withheld:
                drop(option.env)
            elif secret:
                put(option.env, secret)
            continue
        if option.id not in session.options:
            continue
        value = _env_value(option, session.options[option.id])
        if not (override or withheld) and option.env in env:
            continue
        if value is None:
            if override or withheld:
                drop(option.env)
        else:
            put(option.env, value)

    query: dict[str, str] = {}
    if session.mode is not None:
        put(ACCESS_MODE_ENV, session.mode)
        operator = spec.operator
        if session.mode == OPERATOR and operator and operator.token_env:
            # After the scrub, a token still present came from the shell: keep
            # it. Otherwise mint one that dies with this session.
            token = env.get(operator.token_env)
            if not token:
                token = secrets.token_urlsafe(32)
                put(operator.token_env, token)
            if operator.url_param:
                query[operator.url_param] = token

    if managed:
        env[MANAGED_ENV] = ",".join(managed)
        env[ORIGINAL_ENV] = json.dumps(original, sort_keys=True)
    return query


def session_url(base: str, route: str, query: Mapping[str, str] | None = None) -> str:
    url = base + "/" + route.lstrip("/") if route and route != "/" else base
    if query:
        url += ("&" if "?" in url else "?") + urlencode(query)
    return url


def route_from_argv(argv: Sequence[str]) -> str | None:
    """The ``--route`` value, validated the same way ``display_url`` does."""
    if "--route" not in argv:
        return None
    index = list(argv).index("--route") + 1
    if index >= len(argv) or argv[index].startswith("--"):
        raise SystemExit("--route requires a PATH value (e.g. --route /launcher)")
    return "/" + argv[index].lstrip("/")


def stored_session(config: DesktopConfig, spec: LaunchPadSpec) -> Session:
    """The session to use when the Launch Pad is skipped."""
    prefs = read_prefs(config)
    mode = (prefs["mode"] or GUEST) if spec.has_modes else None
    if mode == OPERATOR and passphrase_set(config):
        mode = GUEST
    return build_session(
        spec,
        mode=mode,
        start_route=prefs["start_route"],
        options={},
        saved=prefs["options"],
    )


def should_show(config: DesktopConfig, argv: Sequence[str]) -> bool:
    """Whether the window opens on the Launch Pad for this start."""
    spec = launchpad_spec(config)
    if spec is None or "--smoke" in argv:
        return False
    if "--launchpad" in argv:
        return True
    if "--skip-launchpad" in argv:
        return False
    prefs = read_prefs(config)
    if not prefs["skip"]:
        return True
    # A passphrase-protected Operator session is never entered silently.
    return prefs["mode"] == OPERATOR and passphrase_set(config)


def headless_session(
    config: DesktopConfig, argv: Sequence[str]
) -> tuple[LaunchPadSpec, Session] | None:
    """Session for ``--browser`` / ``--no-window`` starts, where no page is shown.

    Stored options are honoured. The access mode is left unmanaged (exactly the
    pre-Launch-Pad behaviour) unless ``--guest`` or ``--operator`` asks for one.
    """
    spec = launchpad_spec(config)
    if spec is None or "--smoke" in argv:
        return None
    mode: str | None = None
    if spec.has_modes:
        if "--operator" in argv:
            if passphrase_set(config):
                raise SystemExit(
                    "Operator mode is passphrase-protected. Start the app normally "
                    "and choose Operator on the Launch Pad."
                )
            mode = OPERATOR
        elif "--guest" in argv:
            mode = GUEST
    prefs = read_prefs(config)
    session = build_session(
        spec,
        mode=mode or (GUEST if spec.has_modes else None),
        start_route=prefs["start_route"],
        options={},
        saved=prefs["options"],
    )
    session.mode = mode
    return spec, session


# ── Status ────────────────────────────────────────────────────────────────────


def _resolve_status(spec: LaunchPadSpec) -> Callable[[], Any] | None:
    if spec.status is None or callable(spec.status):
        return spec.status  # type: ignore[return-value]
    module_name, _separator, function_name = spec.status.partition(":")
    return getattr(importlib.import_module(module_name), function_name)


def status_rows(config: DesktopConfig, spec: LaunchPadSpec) -> list[dict[str, str]]:
    """Workspace row plus the producer's own readiness rows. Never raises."""
    state = read_state(config)
    rows: list[dict[str, str]] = [
        {
            "label": "Workspace",
            "value": "Ready" if state is not None else "Not set up",
            "status": "pass" if state is not None else "warn",
            "detail": state["workspace"] if state is not None else (
                "Open Setup & Diagnostics to choose a workspace folder."
            ),
        }
    ]
    try:
        provider = _resolve_status(spec)
        produced = provider() if provider is not None else []
        for item in produced or []:
            status = str(item.get("status", "info"))
            rows.append(
                {
                    "label": str(item["label"]),
                    "value": str(item.get("value", "")),
                    "status": status if status in _STATUSES else "info",
                    "detail": str(item.get("detail", "")),
                }
            )
    except Exception as exc:  # noqa: BLE001 - a status bug must not block launching
        rows.append(
            {
                "label": "Status check",
                "value": "Unavailable",
                "status": "warn",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    return rows


# ── Guest guard (ASGI) ────────────────────────────────────────────────────────


class GuestGuard:
    """Refuse state-changing requests while the session is in Guest mode.

    Pure ASGI, no framework imports. It reads the mode per request, so it is
    inert unless a Launch Pad session set ``PRII_ACCESS_MODE=guest`` -- a
    ``--no-window`` developer run or a hosted deployment is untouched. ``allow``
    lists the producer's read-only POST endpoints (searches, filters) as
    ``"[METHOD ]/path"`` patterns where ``*`` matches one path segment.
    """

    def __init__(self, app: Any, allow: Sequence[str] = ()) -> None:
        self.app = app
        self.allow = tuple(_compile_allow(pattern) for pattern in allow)

    def allowed(self, method: str, path: str) -> bool:
        if method.upper() not in _UNSAFE_METHODS:
            return True
        if os.environ.get(ACCESS_MODE_ENV) != GUEST:
            return True
        return any(
            (allowed is None or allowed == method.upper()) and pattern.fullmatch(path)
            for allowed, pattern in self.allow
        )

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or self.allowed(
            scope.get("method", "GET"), scope.get("path", "")
        ):
            await self.app(scope, receive, send)
            return
        body = json.dumps({"detail": GUEST_REFUSAL}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def install_guest_guard(app: Any, config: DesktopConfig) -> bool:
    """Add :class:`GuestGuard` to a producer app that declares an Operator mode."""
    spec = launchpad_spec(config)
    if spec is None or not spec.has_modes:
        return False
    app.add_middleware(GuestGuard, allow=spec.guest_allow)
    return True


# ── Page ──────────────────────────────────────────────────────────────────────


def snapshot(
    config: DesktopConfig, argv: Sequence[str] = ()
) -> dict[str, Any]:
    """Everything the page renders. Carries no secret and no token."""
    spec = launchpad_spec(config)
    if spec is None:
        raise ValueError("This app does not declare a Launch Pad.")
    if read_state(config) is not None:
        # Readiness reads the producer's data, which lives under the workspace.
        apply_environment(config)
    prefs = read_prefs(config)
    routes = [page.route for page in spec.start_pages]
    requested = route_from_argv(argv)
    pages = [
        {"route": page.route, "label": page.label, "description": page.description}
        for page in spec.start_pages
    ]
    if requested and requested not in routes:
        pages.append({"route": requested, "label": requested, "description": ""})
    start = requested or (
        prefs["start_route"] if prefs["start_route"] in routes else routes[0]
    )
    operator = spec.operator
    return {
        "app_title": config.app_title,
        "tagline": spec.tagline,
        "summary": spec.summary,
        "highlights": list(spec.highlights),
        "status": status_rows(config, spec),
        "has_modes": spec.has_modes,
        "mode": (prefs["mode"] or GUEST) if spec.has_modes else None,
        "guest": {"label": spec.guest_label, "description": spec.guest_description},
        "operator": (
            {"label": operator.label, "description": operator.description}
            if operator
            else None
        ),
        "passphrase_set": passphrase_set(config),
        "start_pages": pages,
        "start_route": start,
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "help": option.help,
                "kind": option.kind,
                "choices": [list(choice) for choice in option.choices],
                "operator_only": option.operator_only,
                "placeholder": option.placeholder,
                "default": "" if option.kind == "secret" else option.default,
                "value": _initial_value(option, prefs["options"]),
            }
            for option in spec.options
        ],
        "skip": prefs["skip"],
        "first_visit": not prefs["saved"],
    }


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>__TITLE__ Launch Pad</title>
  <style>
    :root { color-scheme: light dark; --brand:__ACCENT__; --brand-strong:__STRONG__;
      --ink:#172033; --muted:#526075; --page:#f7f8fb; --card:#fff; --line:#d8dee9;
      --soft:#f5f7fa; --field:#fff; --field-line:#aab4c3; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--ink); background:var(--page);
      font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:min(860px,calc(100% - 32px)); margin:0 auto; padding:36px 0 120px; }
    .hero { display:flex; align-items:center; gap:16px; margin-bottom:8px; }
    .mark { width:56px; height:56px; flex:0 0 56px; border-radius:15px; background:var(--brand);
      box-shadow:inset 0 0 0 1px rgba(255,255,255,.32),0 8px 24px rgba(15,23,42,.16); }
    .eyebrow { margin:0; font-size:12px; font-weight:700; letter-spacing:.09em;
      text-transform:uppercase; color:var(--muted); }
    h1 { margin:0; font-size:27px; letter-spacing:-.025em; }
    .lede { margin:2px 0 0; color:var(--muted); }
    section { background:var(--card); border:1px solid var(--line); border-radius:16px;
      padding:20px 22px; margin:16px 0; box-shadow:0 8px 28px rgba(15,23,42,.06); }
    h2 { margin:0 0 6px; font-size:16px; }
    p { margin:6px 0; }
    .quiet { color:var(--muted); font-size:13px; }
    ul.tags { list-style:none; display:flex; flex-wrap:wrap; gap:7px; padding:0; margin:12px 0 0; }
    ul.tags li { padding:4px 11px; border-radius:999px; background:var(--soft);
      border:1px solid var(--line); font-size:13px; }
    .rows { list-style:none; padding:0; margin:12px 0 0; display:grid; gap:8px; }
    .row { display:grid; grid-template-columns:22px 1fr auto; gap:9px; padding:10px 12px;
      border-radius:10px; background:var(--soft); align-items:start; }
    .dot { width:13px; height:13px; margin-top:5px; border-radius:50%; background:#64748b; }
    .pass .dot { background:#15803d; } .fail .dot { background:#b42318; }
    .warn .dot { background:#b45309; }
    .row strong { display:block; } .detail { color:var(--muted); font-size:13px;
      overflow-wrap:anywhere; }
    .value { font-weight:650; font-variant-numeric:tabular-nums; text-align:right; }
    .modes { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
    .mode { position:relative; display:block; padding:14px 14px 14px 44px; border-radius:12px;
      border:2px solid var(--line); background:var(--soft); cursor:pointer; }
    .mode input { position:absolute; left:14px; top:17px; width:18px; height:18px;
      accent-color:var(--brand-strong); }
    .mode:has(input:checked) { border-color:var(--brand-strong); background:var(--card); }
    .mode strong { display:block; font-size:15px; }
    .mode span { color:var(--muted); font-size:13px; }
    label.field { display:block; margin:14px 0 6px; font-weight:650; }
    input[type=text], input[type=password], select { width:100%; min-height:42px;
      border:1px solid var(--field-line); border-radius:9px; padding:9px 12px;
      color:var(--ink); background:var(--field); font:inherit; }
    .option { padding:12px 0; border-top:1px solid var(--line); }
    .option:first-of-type { border-top:0; padding-top:4px; }
    /* A locked (Operator-only, Guest mode) option dims its control only. Its
       label and help text keep full contrast: they stay readable, and the
       help text says the option is available in Operator mode. */
    .option.locked :is(input, select) { opacity:.55; cursor:not-allowed; }
    .check { display:flex; gap:10px; align-items:flex-start; font-weight:650; cursor:pointer; }
    .check input { width:18px; height:18px; margin-top:2px; flex:0 0 18px;
      accent-color:var(--brand-strong); }
    .badge { display:inline-block; margin-left:8px; padding:1px 8px; border-radius:999px;
      font-size:11px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
      border:1px solid var(--line); color:var(--muted); vertical-align:middle; }
    details { margin-top:12px; } summary { cursor:pointer; font-weight:650; }
    button { min-height:44px; border:1px solid transparent; border-radius:9px;
      padding:9px 16px; font:650 14px/1.2 inherit; cursor:pointer; }
    button:disabled { opacity:.6; cursor:default; }
    :focus-visible { outline:3px solid color-mix(in srgb,var(--brand) 70%,#fff);
      outline-offset:2px; }
    .primary { color:#fff; background:var(--brand-strong); padding:11px 26px; font-size:15px; }
    .secondary { color:var(--ink); background:var(--soft); border-color:var(--line); }
    .bar { position:fixed; left:0; right:0; bottom:0; background:var(--card);
      border-top:1px solid var(--line); box-shadow:0 -8px 28px rgba(15,23,42,.08); }
    .bar-inner { width:min(860px,calc(100% - 32px)); margin:0 auto; padding:12px 0;
      display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    #status { flex:1 1 220px; min-height:20px; color:var(--muted); font-size:13px; }
    #status.error { color:#b42318; font-weight:650; }
    [hidden] { display:none !important; }
    @media (prefers-color-scheme:dark) {
      :root { --ink:#f8fafc; --muted:#a9b4c5; --page:#070b14; --card:#101827;
        --line:#334155; --soft:#172033; --field:#0b1220; --field-line:#59677b; }
      #status.error { color:#fca5a5; }
    }
    @media (max-width:620px) { .modes { grid-template-columns:1fr; }
      #status { flex-basis:100%; } .bar-inner button { flex:1 1 auto; }
      .row { grid-template-columns:22px 1fr; } .value { grid-column:2; text-align:left; } }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; } }
  </style>
</head>
<body>
<main>
  <header class="hero">
    __ICON__
    <div>
      <p class="eyebrow">Launch Pad</p>
      <h1>__TITLE__</h1>
      <p class="lede" id="tagline"></p>
    </div>
  </header>

  <section aria-labelledby="about-title" id="about">
    <h2 id="about-title">What this app is for</h2>
    <p id="summary"></p>
    <ul class="tags" id="highlights"></ul>
  </section>

  <section aria-labelledby="status-title">
    <h2 id="status-title">Readiness</h2>
    <p class="quiet">Checked on this computer before anything starts. Nothing is uploaded.</p>
    <ul class="rows" id="rows" aria-live="polite"></ul>
  </section>

  <section aria-labelledby="mode-title" id="mode-section" hidden>
    <h2 id="mode-title">How do you want to enter?</h2>
    <div class="modes" role="radiogroup" aria-labelledby="mode-title">
      <label class="mode"><input type="radio" name="mode" value="guest">
        <strong id="guest-label"></strong><span id="guest-description"></span></label>
      <label class="mode"><input type="radio" name="mode" value="operator">
        <strong id="operator-label"></strong><span id="operator-description"></span></label>
    </div>
    <div id="unlock" hidden>
      <label class="field" for="passphrase">Operator passphrase</label>
      <input id="passphrase" type="password" autocomplete="current-password">
    </div>
    <details id="lock-details">
      <summary id="lock-summary">Protect Operator mode with a passphrase</summary>
      <p class="quiet">Stops casual use of Operator mode on a shared computer. It is stored
        on this computer as a salted hash and cannot be recovered; it does not protect
        against someone who can already read your files.</p>
      <div id="lock-current-wrap" hidden>
        <label class="field" for="lock-current">Current passphrase</label>
        <input id="lock-current" type="password" autocomplete="current-password">
      </div>
      <label class="field" for="lock-new">New passphrase <span class="quiet">(leave empty to remove)</span></label>
      <input id="lock-new" type="password" autocomplete="new-password">
      <p><button id="lock-save" class="secondary" type="button">Save passphrase</button></p>
    </details>
  </section>

  <section aria-labelledby="page-title">
    <h2 id="page-title">Open on</h2>
    <label class="field" for="start">Starting page</label>
    <select id="start"></select>
    <p class="quiet" id="start-description"></p>
  </section>

  <section aria-labelledby="options-title" id="options-section" hidden>
    <h2 id="options-title">Launch options</h2>
    <p class="quiet">Applied when the app starts. To change them later, return to the Launch Pad.</p>
    <div id="options"></div>
  </section>

  <section aria-labelledby="prefs-title">
    <h2 id="prefs-title">Next time</h2>
    <label class="check"><input type="checkbox" id="skip">
      <span>Skip the Launch Pad and open straight into the app with these choices
        <span class="quiet" style="display:block;font-weight:400">You can always come back
        with the Launch Pad button in the corner of the app.</span></span></label>
  </section>
</main>
<div class="bar"><div class="bar-inner">
  <div id="status" role="status" aria-live="polite"></div>
  <button id="setup" class="secondary" type="button">Setup &amp; Diagnostics</button>
  <button id="launch" class="primary" type="button">Launch</button>
</div></div>
<script>
  const $ = (id) => document.getElementById(id);
  const api = () => window.pywebview && window.pywebview.api;
  let state = null;
  const el = (tag, cls, text) => { const node = document.createElement(tag);
    if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; };
  const say = (message, error=false) => { $("status").textContent = message;
    $("status").className = error ? "error" : ""; };
  const mode = () => { const picked = document.querySelector('input[name=mode]:checked');
    return picked ? picked.value : null; };
  const failure = (error) => String((error && error.message) || error).replace(/^Error:\s*/, "");

  const renderRows = (rows) => $("rows").replaceChildren(...rows.map(row => {
    const li = el("li", "row " + row.status);
    const dot = el("span", "dot"); dot.setAttribute("aria-hidden", "true");
    const copy = el("div"); copy.append(el("strong", "", row.label), el("span", "detail", row.detail));
    li.append(dot, copy, el("span", "value", row.value)); return li; }));

  const renderOptions = () => {
    const guest = state.has_modes && mode() === "guest";
    $("options").replaceChildren(...state.options.map(option => {
      const locked = option.operator_only && guest;
      const wrap = el("div", "option" + (locked ? " locked" : ""));
      const id = "option-" + option.id;
      const badge = option.operator_only ? el("span", "badge", "Operator") : null;
      let control;
      if (option.kind === "toggle") {
        const label = el("label", "check"); control = el("input"); control.type = "checkbox";
        control.checked = locked ? Boolean(option.default) : Boolean(option.value);
        const text = el("span", "", option.label); if (badge) text.append(badge);
        label.append(control, text); wrap.append(label);
      } else {
        const label = el("label", "field", option.label); label.htmlFor = id;
        if (badge) label.append(badge); wrap.append(label);
        if (option.kind === "choice") {
          control = el("select");
          option.choices.forEach(([value, text]) => { const item = el("option", "", text);
            item.value = value; control.append(item); });
          control.value = locked ? option.default : option.value;
        } else {
          control = el("input"); control.type = option.kind === "secret" ? "password" : "text";
          control.autocomplete = option.kind === "secret" ? "new-password" : "off";
          control.spellcheck = false; control.placeholder = option.placeholder || "";
          control.value = locked ? "" : (option.value || "");
        }
        wrap.append(control);
      }
      control.id = id; control.disabled = locked; control.dataset.option = option.id;
      control.addEventListener("change", () => { option.value = control.type === "checkbox"
        ? control.checked : control.value; });
      const help = [option.help,
        option.kind === "secret" ? "Used for this session only; it is never saved." : "",
        locked ? "Available in Operator mode." : ""].filter(Boolean).join(" ");
      if (help) wrap.append(el("p", "quiet", help));
      return wrap; }));
  };

  const renderLock = () => {
    $("unlock").hidden = !(state.passphrase_set && mode() === "operator");
    $("lock-current-wrap").hidden = !state.passphrase_set;
    $("lock-summary").textContent = state.passphrase_set
      ? "Change or remove the Operator passphrase"
      : "Protect Operator mode with a passphrase";
  };

  const renderStart = () => {
    const page = state.start_pages.find(item => item.route === $("start").value);
    $("start-description").textContent = page ? page.description : "";
  };

  const render = () => {
    $("tagline").textContent = state.tagline;
    $("summary").textContent = state.summary;
    $("about").hidden = !(state.summary || state.highlights.length);
    $("highlights").replaceChildren(...state.highlights.map(text => el("li", "", text)));
    renderRows(state.status);
    $("mode-section").hidden = !state.has_modes;
    if (state.has_modes) {
      $("guest-label").textContent = state.guest.label;
      $("guest-description").textContent = state.guest.description;
      $("operator-label").textContent = state.operator.label;
      $("operator-description").textContent = state.operator.description;
      document.querySelector('input[name=mode][value="' + state.mode + '"]').checked = true;
    }
    $("start").replaceChildren(...state.start_pages.map(page => { const item = el("option", "", page.label);
      item.value = page.route; return item; }));
    $("start").value = state.start_route;
    $("options-section").hidden = !state.options.length;
    $("skip").checked = state.skip;
    renderStart(); renderOptions(); renderLock();
  };

  const load = async () => {
    if (!api() || state) return;
    try { state = await api().launchpad_snapshot(); render(); say(""); }
    catch (error) { say(failure(error), true); }
  };

  document.querySelectorAll("input[name=mode]").forEach(radio =>
    radio.addEventListener("change", () => { renderOptions(); renderLock(); }));
  $("start").addEventListener("change", renderStart);
  $("setup").addEventListener("click", () => api().open_setup());

  $("lock-save").addEventListener("click", async () => {
    try {
      const result = await api().launchpad_set_passphrase($("lock-current").value, $("lock-new").value);
      state.passphrase_set = result.passphrase_set;
      $("lock-current").value = ""; $("lock-new").value = ""; renderLock();
      say(result.passphrase_set ? "Operator passphrase saved." : "Operator passphrase removed.");
    } catch (error) { say(failure(error), true); }
  });

  $("launch").addEventListener("click", async () => {
    if (!state) return;
    const options = {};
    document.querySelectorAll("[data-option]").forEach(control => {
      if (control.disabled) return;
      options[control.dataset.option] = control.type === "checkbox" ? control.checked : control.value;
    });
    $("launch").disabled = true; say("Starting " + state.app_title + "…");
    try {
      await api().launchpad_launch({ mode: mode(), start_route: $("start").value, options,
        passphrase: $("passphrase").value, skip: $("skip").checked });
    } catch (error) { $("launch").disabled = false; say(failure(error), true); }
  });

  window.addEventListener("pywebviewready", load);
  load();
</script>
</body>
</html>"""


def render_launchpad_html(config: DesktopConfig) -> str:
    """Render the Launch Pad shell. Its content arrives through the bridge."""
    import html

    return (
        _PAGE.replace("__TITLE__", html.escape(config.app_title))
        .replace("__ACCENT__", _safe_color(config.brand_accent, "#2563eb"))
        .replace("__STRONG__", _safe_color(config.brand_accent_strong, "#1d4ed8"))
        .replace("__ICON__", _icon_markup(config))
    )


# ── Bridge ────────────────────────────────────────────────────────────────────


class DesktopBridge(SetupBridge):
    """Setup bridge plus the Launch Pad calls. One object serves both pages."""

    def __init__(
        self,
        config: DesktopConfig,
        *,
        argv: Sequence[str] = (),
        reopen_launchpad: Callable[[], None] | None = None,
        menus: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        import threading

        self._argv = tuple(argv)
        self._reopen_launchpad = reopen_launchpad
        # Returns the menu controller (or None). Kept private: pywebview exposes
        # every public attribute of this object to page JavaScript.
        self._menus = menus
        self._session: Session | None = None
        #: Set once the user presses Launch (or closes the window).
        self.launch_requested = threading.Event()

    def await_launch(self) -> None:
        """Mark the Launch Pad as the page Setup returns to until launch."""
        self._pending_page = lambda: render_launchpad_html(self.config)

    def session(self) -> Session | None:
        return self._session

    def launchpad_snapshot(self) -> dict[str, Any]:
        return snapshot(self.config, self._argv)

    def launchpad_set_passphrase(self, current: str, new: str) -> dict[str, Any]:
        spec = launchpad_spec(self.config)
        if spec is None or not spec.has_modes:
            raise ValueError("This app has no Operator mode to protect.")
        set_passphrase(self.config, current or "", new or "")
        return {"passphrase_set": passphrase_set(self.config)}

    def launchpad_launch(self, choices: Mapping[str, Any]) -> dict[str, Any]:
        spec = launchpad_spec(self.config)
        if spec is None:
            raise ValueError("This app does not declare a Launch Pad.")
        if read_state(self.config) is None:
            raise ValueError(
                "Finish Setup & Diagnostics before launching: no workspace is set."
            )
        choices = choices if isinstance(choices, Mapping) else {}
        mode = choices.get("mode")
        if mode == OPERATOR and not verify_passphrase(
            self.config, str(choices.get("passphrase") or "")
        ):
            time.sleep(_FAILED_UNLOCK_DELAY)
            raise ValueError("The Operator passphrase is not correct.")
        options = choices.get("options")
        requested = route_from_argv(self._argv)
        start = choices.get("start_route")
        session = build_session(
            spec,
            mode=mode,
            start_route=start,
            options=options if isinstance(options, Mapping) else {},
            saved=read_prefs(self.config)["options"],
        )
        if requested and start == requested:
            # A launcher-supplied --route that is not a declared start page.
            session.start_route = requested
        save_prefs(self.config, session, skip=choices.get("skip") is True)
        self._session = session
        self._pending_page = None
        self.launch_requested.set()
        return {"ok": True}

    def open_launchpad(self) -> bool:
        """In-app control: restart on the Launch Pad to change mode or options."""
        if self._reopen_launchpad is None:
            return False
        self._reopen_launchpad()
        return True

    def show_context_menu(self, link: str = "") -> bool:
        """Right-click in the page: open the native context menu (macOS only).

        ``link`` is the address under the pointer, or empty. Returns ``False``
        where there is no native menu, so the page can keep its own behaviour.
        """
        controller = self._menus() if self._menus is not None else None
        if controller is None:
            return False
        return bool(controller.popup_context(link if isinstance(link, str) else ""))

# ── Offline check ─────────────────────────────────────────────────────────────


def check_declaration(config: DesktopConfig, *, run_status: bool = True) -> list[str]:
    """Problems with a producer's ``LAUNCHPAD``, without starting anything.

    The launcher refuses to start on an invalid declaration, so producers run
    this in CI (``python -m prii_desktop launchpad --check``). Unlike
    :func:`status_rows`, a failing status provider is reported, not swallowed.
    """
    try:
        spec = launchpad_spec(config)
    except ValueError as exc:
        return [str(exc)]
    if spec is None or not run_status or spec.status is None:
        return []
    problems: list[str] = []
    try:
        provider = _resolve_status(spec)
        produced = list(provider() or []) if provider is not None else []
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        return [f"status provider raised {type(exc).__name__}: {exc}"]
    for index, row in enumerate(produced):
        if not isinstance(row, Mapping) or "label" not in row:
            problems.append(f"status row {index} is not a mapping with a label")
        elif str(row.get("status", "info")) not in _STATUSES:
            problems.append(
                f"status row {row['label']!r} has status {row.get('status')!r}; "
                f"use one of {', '.join(_STATUSES)}"
            )
    return problems


def load_config(repo_root: Path, module_name: str = "desktop.config") -> DesktopConfig:
    """Import a producer's config module from ``repo_root`` as ``DesktopConfig``."""
    import sys

    root = str(repo_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    return DesktopConfig.from_module(importlib.import_module(module_name))


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m prii_desktop launchpad",
        description="Validate a producer's Launch Pad declaration offline.",
    )
    parser.add_argument("--check", action="store_true", required=True,
                        help="validate the declaration and exit")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(),
                        help="producer repository root (default: current directory)")
    parser.add_argument("--module", default="desktop.config",
                        help="config module to import (default: desktop.config)")
    parser.add_argument("--no-status", action="store_true",
                        help="skip calling the readiness status provider")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.repo_root, args.module)
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        print(f"FAIL  could not load {args.module}: {type(exc).__name__}: {exc}")
        return 1
    problems = check_declaration(config, run_status=not args.no_status)
    if problems:
        for problem in problems:
            print(f"FAIL  {config.app_title}: {problem}")
        return 1
    spec = launchpad_spec(config)
    if spec is None:
        print(f"ok    {config.app_title}: no Launch Pad declared")
        return 0
    modes = "guest/operator" if spec.has_modes else "single mode"
    print(
        f"ok    {config.app_title}: Launch Pad valid ({len(spec.start_pages)} start "
        f"pages, {len(spec.options)} options, {modes}, "
        f"{len(spec.guest_allow)} guest-allowed routes)"
    )
    return 0


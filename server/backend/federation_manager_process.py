"""Process supervision for manager-driven operations.

Every child is launched from an argv **list** with ``shell=False``. There is no
code path in this module that accepts a command string, and none that reaches a
shell: no ``shell=True``, no ``sh -c``, no ``os.system``, no ``eval``/``exec``.

Three properties matter beyond "don't use a shell":

* **Environment is deny-by-default.** The child inherits nothing. Only
  explicitly allow-listed names are copied through, and injected secrets are
  written straight into the child's environment mapping by the secrets broker
  without passing through the caller.
* **Output is redacted as it streams**, not after the fact, so a secret never
  reaches a log sink, an SSE subscriber, or a receipt even if the run crashes
  midway.
* **Processes are supervised.** Each child gets its own process group, so a
  timeout or a cancellation kills the whole tree rather than orphaning
  grandchildren.
"""
from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

#: Variables a child may inherit. PYTHONPATH is deliberately absent: it is a
#: code-injection channel, and a managed environment should not need it.
DEFAULT_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TMPDIR",
    "SYSTEMROOT",
)

#: Names whose *values* must never be echoed. Matched case-insensitively as a
#: substring, mirroring ``federation_manager.SECRET_KEY_PATTERN``.
SECRET_NAME_MARKERS = ("secret", "token", "password", "api_key", "apikey", "authorization", "credential")

REDACTION_PLACEHOLDER = "[REDACTED]"


class ProcessError(RuntimeError):
    """A child could not be started, or was refused before starting."""


@dataclass(frozen=True)
class ProcessLimits:
    timeout_seconds: float = 900.0
    max_log_bytes: int = 4 * 1024 * 1024
    max_line_bytes: int = 64 * 1024


@dataclass
class ProcessResult:
    status: str
    exit_code: Optional[int]
    log_bytes: int
    log_sha256: str
    truncated: bool
    redactions: int
    argv: Sequence[str] = field(default_factory=tuple)

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded" and self.exit_code == 0


class Redactor:
    """Replaces known secret values in streamed output.

    Values are supplied by the secrets broker at run start and held only for the
    lifetime of the run. Matching is literal rather than pattern-based, because
    the goal is to catch a secret a child echoed verbatim, and a pattern would
    both miss unusual formats and mangle innocent output.
    """

    def __init__(self, values: Iterable[str] = ()):
        # Longest first, so an overlapping shorter secret cannot leave a tail.
        self._values = sorted({v for v in values if v and len(v) >= 4}, key=len, reverse=True)
        self.count = 0

    def __call__(self, text: str) -> str:
        for value in self._values:
            if value in text:
                self.count += text.count(value)
                text = text.replace(value, REDACTION_PLACEHOLDER)
        return text

    def clear(self) -> None:
        """Drop the retained values as soon as the run finishes."""
        self._values = []


def build_environment(
    allowlist: Sequence[str] = DEFAULT_ENV_ALLOWLIST,
    *,
    base: Optional[Mapping[str, str]] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Build a child environment from an explicit allow-list.

    ``extra`` carries manager-controlled values (a pinned app root, an offline
    flag). Secrets are *not* passed here — the broker writes them into the
    returned mapping directly so the value never sits in a caller's local.
    """
    source = os.environ if base is None else base
    env = {name: source[name] for name in allowlist if name in source}
    for key, value in (extra or {}).items():
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            raise ProcessError(f"invalid environment variable name: {key!r}")
        env[key] = value
    return env


def redact_environment_names(env: Mapping[str, str]) -> list[str]:
    """Return variable *names* only, for the receipt. Values never leave here."""
    return sorted(env)


def is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in SECRET_NAME_MARKERS)


def redact_argv(argv: Sequence[str]) -> list[str]:
    """Redact any argv element that follows a secret-shaped flag.

    Operations in this vector never place a secret in argv — secrets travel
    through the environment — but the receipt writer should not depend on that
    remaining true.
    """
    out: list[str] = []
    redact_next = False
    for element in argv:
        if redact_next:
            out.append(REDACTION_PLACEHOLDER)
            redact_next = False
            continue
        if element.startswith("-") and is_secret_name(element):
            if "=" in element:
                out.append(element.split("=", 1)[0] + "=" + REDACTION_PLACEHOLDER)
                continue
            redact_next = True
        out.append(element)
    return out


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    limits: Optional[ProcessLimits] = None,
    on_line: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    redactor: Optional[Redactor] = None,
) -> ProcessResult:
    """Run one child process under supervision and return its outcome.

    ``on_line`` receives each already-redacted line as it arrives, which is what
    the SSE stream subscribes to. The returned log hash covers the redacted
    bytes: it attests to what was actually recorded, not to a pre-redaction form
    that no longer exists anywhere.
    """
    if isinstance(argv, str):
        raise ProcessError("argv must be a list of arguments, never a command string")
    argv = [str(a) for a in argv]
    if not argv:
        raise ProcessError("argv is empty")

    limits = limits or ProcessLimits()
    redactor = redactor or Redactor()
    digest = hashlib.sha256()
    total = 0
    truncated = False

    popen_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": dict(env),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
        "bufsize": 1,
        "universal_newlines": True,
    }
    # A dedicated process group means a timeout or cancel kills grandchildren too.
    if sys.platform == "win32":  # pragma: no cover - exercised on Windows only
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    try:
        # shell=False is the default and is never overridden anywhere in this module.
        process = subprocess.Popen(argv, **popen_kwargs)  # noqa: S603
    except FileNotFoundError as exc:
        raise ProcessError(f"executable not found: {argv[0]!r}") from exc
    except PermissionError as exc:
        raise ProcessError(f"executable is not runnable: {argv[0]!r}") from exc

    status = "succeeded"
    timer_fired = threading.Event()

    def _kill_tree() -> None:
        try:
            if sys.platform == "win32":  # pragma: no cover
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            # Racing a process that has already exited is the expected case, not
            # an error: the timeout fires and the child finishes at the same
            # moment. Killing an already-dead group must not mask the real
            # outcome, which the caller reads from the exit code and timer flag.
            pass

    def _on_timeout() -> None:
        timer_fired.set()
        _kill_tree()

    timer = threading.Timer(limits.timeout_seconds, _on_timeout)
    timer.daemon = True
    timer.start()

    cancelled = threading.Event()

    def _watch_cancel() -> None:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.wait(0.1):
                cancelled.set()
                _kill_tree()
                return
            if cancel_event is None:
                return

    watcher: Optional[threading.Thread] = None
    if cancel_event is not None:
        watcher = threading.Thread(target=_watch_cancel, daemon=True)
        watcher.start()

    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line[: limits.max_line_bytes]
            line = redactor(line)
            encoded = line.encode("utf-8", "replace")
            if total + len(encoded) > limits.max_log_bytes:
                if not truncated:
                    truncated = True
                    marker = "\n[log truncated at the configured byte limit]\n"
                    digest.update(marker.encode("utf-8"))
                    total += len(marker)
                    if on_line is not None:
                        on_line(marker)
                continue
            digest.update(encoded)
            total += len(encoded)
            if on_line is not None:
                on_line(line)
        process.wait()
    finally:
        timer.cancel()
        if watcher is not None:
            watcher.join(timeout=1.0)
        if process.poll() is None:  # pragma: no cover - defensive
            _kill_tree()
            process.wait(timeout=5)

    if timer_fired.is_set():
        status = "timed_out"
    elif cancelled.is_set():
        status = "cancelled"
    elif process.returncode != 0:
        status = "failed"

    redactions = redactor.count
    redactor.clear()

    return ProcessResult(
        status=status,
        exit_code=process.returncode,
        log_bytes=total,
        log_sha256=digest.hexdigest(),
        truncated=truncated,
        redactions=redactions,
        argv=tuple(argv),
    )

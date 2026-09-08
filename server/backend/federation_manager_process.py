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
import math
import os
import re
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

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

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not 0 < self.timeout_seconds <= threading.TIMEOUT_MAX
            or not math.isfinite(self.timeout_seconds)
        ):
            raise ProcessError("timeout_seconds must be a positive supported finite duration")
        for name in ("max_log_bytes", "max_line_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ProcessError(f"{name} must be a positive integer")


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
        retained = {v for v in values if v and len(v) >= 4}
        # The transport delivers physical lines. Retain nonempty lines of a
        # multiline credential as well, so a PEM/key body cannot evade redaction
        # merely because its complete value spans more than one callback.
        retained.update(line for value in tuple(retained) for line in value.splitlines() if line)
        self._values = sorted(retained, key=lambda value: (-len(value), value))
        self.count = 0

    def __call__(self, text: str) -> str:
        return self.prefix(text, len(text))

    def clear(self) -> None:
        """Drop the retained values as soon as the run finishes."""
        self._values = []

    @property
    def lookahead(self) -> int:
        """Context needed to recognize a secret crossing a visible line cap."""
        return max((len(value) for value in self._values), default=1)

    def prefix(self, text: str, length: int) -> str:
        """Redact a bounded prefix using the hidden suffix only as context."""
        matches = []
        for value in self._values:
            start = text.find(value)
            while start >= 0:
                matches.append((start, start + len(value)))
                start = text.find(value, start + 1)
        # Match against the original text, then merge overlapping spans. Doing
        # successive replacements can destroy a second match and expose its
        # prefix/suffix; equal-length secrets must not depend on set ordering.
        spans: list[tuple[int, int]] = []
        for start, end in sorted(matches):
            if spans and start < spans[-1][1]:
                spans[-1] = (spans[-1][0], max(spans[-1][1], end))
            else:
                spans.append((start, end))
        pieces: list[str] = []
        cursor = 0
        for start, end in spans:
            if start >= length:
                break
            pieces.extend((text[cursor:start], REDACTION_PLACEHOLDER))
            cursor = end
            self.count += 1
        pieces.append(text[min(cursor, length):length])
        return "".join(pieces)


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
    log_limit_reached = False

    if cancel_event is not None and cancel_event.is_set():
        redactor.clear()
        return ProcessResult(
            status="cancelled", exit_code=None, log_bytes=0,
            log_sha256=digest.hexdigest(), truncated=False, redactions=0, argv=tuple(argv),
        )

    popen_kwargs: dict[str, Any] = {
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
        redactor.clear()
        raise ProcessError(f"executable not found: {argv[0]!r}") from exc
    except PermissionError as exc:
        redactor.clear()
        raise ProcessError(f"executable is not runnable: {argv[0]!r}") from exc

    status = "succeeded"
    timer_fired = threading.Event()
    finished = threading.Event()
    termination_lock = threading.Lock()
    escalation: Optional[threading.Timer] = None

    def _force_kill_tree() -> None:
        try:
            if sys.platform == "win32":  # pragma: no cover - Windows operator gate
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=5,
                )
            else:
                # start_new_session binds the group ID to this PID. The group
                # can outlive its leader while descendants hold the log pipe.
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError, subprocess.TimeoutExpired):
            pass

    def _kill_tree() -> None:
        nonlocal escalation
        try:
            if sys.platform == "win32":  # pragma: no cover
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            # Racing a process that has already exited is the expected case, not
            # an error: the timeout fires and the child finishes at the same
            # moment. Killing an already-dead group must not mask the real
            # outcome, which the caller reads from the exit code and timer flag.
            return
        with termination_lock:
            if escalation is None:
                escalation = threading.Timer(1.0, _force_kill_tree)
                escalation.daemon = True
                escalation.start()

    def _on_timeout() -> None:
        timer_fired.set()
        _kill_tree()

    timer = threading.Timer(limits.timeout_seconds, _on_timeout)
    timer.daemon = True
    timer.start()

    cancelled = threading.Event()

    def _watch_cancel() -> None:
        while not finished.is_set():
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

    def _record(line: str) -> None:
        nonlocal total, truncated, log_limit_reached
        if log_limit_reached:
            return
        encoded = line.encode("utf-8", "replace")
        remaining = limits.max_log_bytes - total
        if len(encoded) > remaining:
            truncated = True
            log_limit_reached = True
            encoded = b"\n[log truncated at the configured byte limit]\n"[:remaining]
            line = encoded.decode("utf-8")
        digest.update(encoded)
        total += len(encoded)
        if line and on_line is not None:
            on_line(line)

    try:
        assert process.stdout is not None
        # Iterating TextIOWrapper lines reads an unbounded physical line before
        # slicing it. Read a bounded prefix plus secret lookahead, then discard
        # the remaining physical line in bounded chunks without logging it.
        read_size = limits.max_line_bytes + redactor.lookahead
        while raw_line := process.stdout.readline(read_size):
            encoded = raw_line.encode("utf-8", "replace")
            visible = encoded[:limits.max_line_bytes].decode("utf-8", "ignore")
            line_truncated = len(encoded) > limits.max_line_bytes
            line = redactor.prefix(raw_line, len(visible))
            safe_bytes = line.encode("utf-8", "replace")
            line_truncated |= len(safe_bytes) > limits.max_line_bytes
            _record(safe_bytes[:limits.max_line_bytes].decode("utf-8", "ignore"))
            if line_truncated:
                truncated = True
                _record("\n[line truncated at the configured byte limit]\n")
                while raw_line and not raw_line.endswith("\n"):
                    raw_line = process.stdout.readline(read_size)
        process.wait()
    finally:
        timer.cancel()
        try:
            if process.poll() is None:  # callback/stream failure still owns cleanup
                _kill_tree()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _force_kill_tree()
                    process.wait(timeout=5)
        finally:
            _force_kill_tree()
            finished.set()
            with termination_lock:
                if escalation is not None:
                    escalation.cancel()
            if watcher is not None:
                watcher.join(timeout=1.0)
            if process.stdout is not None:
                process.stdout.close()
            redactor.clear()

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

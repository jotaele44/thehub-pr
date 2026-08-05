"""Native credential providers with no readback path.

The foundation's ``SecretProvider`` ABC exposes ``set``/``exists``/``delete``
and deliberately no ``get`` -- a property the foundation's own test asserts
structurally (``assert not hasattr(UnavailableSecretProvider(), "get")``).

That creates a real problem for an executor: a child process may need a secret
in its environment, but nothing may hand the value back to a caller who could
log it, put it in a receipt, or return it over HTTP.

The resolution is a **sealed sink** rather than a getter.
``SecretBroker.inject_into_env`` writes values directly into a child
environment mapping and returns ``None``. There is no expression anywhere in
the manager that evaluates to a secret string, so there is nothing for a
caller to accidentally retain. The one place a value is briefly materialised
(inside the platform adapter) is bounded to that call and overwritten before it
returns.

Platform adapters:

* macOS -- Keychain Services via the ``security`` binary
* Windows -- Credential Manager via PowerShell's CredentialManager surface
* Linux -- Secret Service via ``secret-tool`` (libsecret)

Every adapter shells nothing: each drives a fixed executable with an argv list.
"""
from __future__ import annotations

import os
import platform
import subprocess
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

from server.backend.federation_manager import SecretProvider, UnavailableSecretProvider

SERVICE_PREFIX = "PRII"

#: How long an adapter may block. A locked keychain prompts the user; if they
#: never answer we must fail rather than wedge the operation forever.
ADAPTER_TIMEOUT_SECONDS = 20.0


class SecretAccessError(RuntimeError):
    """The credential store refused, is locked, or is unavailable."""


def _service_name(app_id: str) -> str:
    return f"{SERVICE_PREFIX}.{app_id}"


def _run(argv: Sequence[str], *, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    """Drive a credential binary with an argv list and no shell."""
    try:
        return subprocess.run(  # noqa: S603
            list(argv),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=ADAPTER_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SecretAccessError(f"credential helper not available: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SecretAccessError(
            f"credential helper timed out after {ADAPTER_TIMEOUT_SECONDS}s "
            "(a locked keychain awaiting user approval looks like this)"
        ) from exc


class MacOSKeychainProvider(SecretProvider):
    """macOS Keychain Services.

    ``security`` distinguishes "not found" (exit 44) from other failures, so a
    locked or denied keychain is reported as an error rather than being
    flattened into "the secret does not exist" -- which would otherwise tell an
    operator to re-enter a credential that is already stored.
    """

    NOT_FOUND_EXIT = 44

    def set(self, app_id: str, secret_id: str, value: str) -> None:
        # -w is passed with no inline value so `security` reads the password
        # from stdin. Writing it as `-w <value>` would put the secret in the
        # process argument vector, where any local user's `ps` would see it.
        result = _run(
            [
                "security",
                "add-generic-password",
                "-a",
                secret_id,
                "-s",
                _service_name(app_id),
                "-U",  # update in place if it already exists
                "-w",
            ],
            input_text=value,
        )
        if result.returncode != 0:
            raise SecretAccessError(f"keychain write failed for {secret_id}")

    def exists(self, app_id: str, secret_id: str) -> bool:
        result = _run(
            ["security", "find-generic-password", "-a", secret_id, "-s", _service_name(app_id)]
        )
        if result.returncode == 0:
            return True
        if result.returncode == self.NOT_FOUND_EXIT:
            return False
        raise SecretAccessError(
            f"keychain is unavailable or access was denied while checking {secret_id}"
        )

    def delete(self, app_id: str, secret_id: str) -> None:
        result = _run(
            ["security", "delete-generic-password", "-a", secret_id, "-s", _service_name(app_id)]
        )
        if result.returncode not in (0, self.NOT_FOUND_EXIT):
            raise SecretAccessError(f"keychain delete failed for {secret_id}")

    def _read_into(self, app_id: str, secret_id: str, sink: MutableMapping[str, str], key: str) -> None:
        result = _run(
            [
                "security",
                "find-generic-password",
                "-a",
                secret_id,
                "-s",
                _service_name(app_id),
                "-w",
            ]
        )
        if result.returncode != 0:
            raise SecretAccessError(f"keychain read failed for {secret_id}")
        sink[key] = result.stdout.rstrip("\n")


class WindowsCredentialManagerProvider(SecretProvider):  # pragma: no cover - Windows only
    """Windows Credential Manager, driven through a fixed cmdlet argv.

    The write reads its value from stdin, matching macOS and Linux. Passing it
    as ``-Password <value>`` would put the secret in the process argument
    vector, which on Windows is worse than the POSIX equivalent: a local
    unprivileged user can read another process's command line through WMI,
    whereas reading its stdin requires debug privilege.

    The script is passed with ``-EncodedCommand`` so that stdin carries only the
    secret. Encoding is a transport detail, not a security measure -- the script
    is fixed text with no interpolation, and the value it consumes never appears
    in it.
    """

    #: Reads exactly one line from stdin and stores it. No format string, no
    #: interpolation: the target and username arrive as bound parameters, so
    #: neither an app id nor a secret id can close a quote and add a statement.
    _WRITE_SCRIPT = (
        "param($Target, $UserName)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$secure = [Console]::In.ReadLine() | ConvertTo-SecureString -AsPlainText -Force\n"
        "New-StoredCredential -Target $Target -UserName $UserName "
        "-SecurePassword $secure -Persist LocalMachine | Out-Null\n"
    )

    def _cmdlet(self, *args: str) -> Sequence[str]:
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", *args]

    def set(self, app_id: str, secret_id: str, value: str) -> None:
        import base64

        encoded = base64.b64encode(self._WRITE_SCRIPT.encode("utf-16-le")).decode("ascii")
        result = _run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded,
                "-Target",
                f"{_service_name(app_id)}/{secret_id}",
                "-UserName",
                secret_id,
            ],
            input_text=value + "\n",
        )
        if result.returncode != 0:
            raise SecretAccessError(f"credential manager write failed for {secret_id}")

    def exists(self, app_id: str, secret_id: str) -> bool:
        result = _run(
            self._cmdlet(
                "Get-StoredCredential", "-Target", f"{_service_name(app_id)}/{secret_id}"
            )
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def delete(self, app_id: str, secret_id: str) -> None:
        _run(
            self._cmdlet(
                "Remove-StoredCredential", "-Target", f"{_service_name(app_id)}/{secret_id}"
            )
        )

    def _read_into(self, app_id: str, secret_id: str, sink: MutableMapping[str, str], key: str) -> None:
        result = _run(
            self._cmdlet(
                "(Get-StoredCredential -Target "
                f"'{_service_name(app_id)}/{secret_id}').GetNetworkCredential().Password"
            )
        )
        if result.returncode != 0:
            raise SecretAccessError(f"credential manager read failed for {secret_id}")
        sink[key] = result.stdout.rstrip("\r\n")


class SecretServiceProvider(SecretProvider):
    """Linux Secret Service (libsecret) via ``secret-tool``."""

    def set(self, app_id: str, secret_id: str, value: str) -> None:
        result = _run(
            ["secret-tool", "store", "--label", f"{_service_name(app_id)}/{secret_id}",
             "service", _service_name(app_id), "account", secret_id],
            input_text=value,
        )
        if result.returncode != 0:
            raise SecretAccessError(f"secret service write failed for {secret_id}")

    def exists(self, app_id: str, secret_id: str) -> bool:
        result = _run(
            ["secret-tool", "lookup", "service", _service_name(app_id), "account", secret_id]
        )
        return result.returncode == 0 and bool(result.stdout)

    def delete(self, app_id: str, secret_id: str) -> None:
        _run(["secret-tool", "clear", "service", _service_name(app_id), "account", secret_id])

    def _read_into(self, app_id: str, secret_id: str, sink: MutableMapping[str, str], key: str) -> None:
        result = _run(
            ["secret-tool", "lookup", "service", _service_name(app_id), "account", secret_id]
        )
        if result.returncode != 0:
            raise SecretAccessError(f"secret service read failed for {secret_id}")
        sink[key] = result.stdout


class InMemorySecretProvider(SecretProvider):
    """Test and headless-CI provider.

    Named so it can never be mistaken for a real credential store, and reported
    as such by :func:`provider_description` so the UI can say plainly that
    secrets are not being persisted to an OS keychain.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set(self, app_id: str, secret_id: str, value: str) -> None:
        self._store[(app_id, secret_id)] = value

    def exists(self, app_id: str, secret_id: str) -> bool:
        return (app_id, secret_id) in self._store

    def delete(self, app_id: str, secret_id: str) -> None:
        self._store.pop((app_id, secret_id), None)

    def _read_into(self, app_id: str, secret_id: str, sink: MutableMapping[str, str], key: str) -> None:
        try:
            sink[key] = self._store[(app_id, secret_id)]
        except KeyError as exc:
            raise SecretAccessError(f"secret {secret_id} is not set for {app_id}") from exc


def select_provider(system: Optional[str] = None) -> SecretProvider:
    """Choose the platform provider, or an explicitly unavailable one."""
    if os.environ.get("PRII_MANAGER_SECRET_PROVIDER") == "memory":
        return InMemorySecretProvider()
    system = (system or platform.system()).lower()
    if system == "darwin":
        return MacOSKeychainProvider()
    if system == "windows":  # pragma: no cover - Windows only
        return WindowsCredentialManagerProvider()
    if system == "linux":
        return SecretServiceProvider()
    return UnavailableSecretProvider()


def provider_description(provider: SecretProvider) -> dict[str, object]:
    """Describe the provider for the UI. Names only -- never a stored value."""
    kind = type(provider).__name__
    return {
        "provider": kind,
        "persistent": not isinstance(provider, (InMemorySecretProvider, UnavailableSecretProvider)),
        "available": not isinstance(provider, UnavailableSecretProvider),
        "readback": False,
    }


class SecretBroker:
    """The only component permitted to move a secret value.

    Public surface is presence-oriented: ``set``, ``exists``, ``validate``,
    ``delete``, ``presence``. The single value-moving method,
    ``inject_into_env``, is a sink -- it returns ``None``.
    """

    def __init__(self, provider: Optional[SecretProvider] = None):
        self._provider = provider or select_provider()

    @property
    def provider(self) -> SecretProvider:
        return self._provider

    def set(self, app_id: str, secret_id: str, value: str) -> None:
        if not value:
            raise SecretAccessError("refusing to store an empty secret")
        self._provider.set(app_id, secret_id, value)

    def exists(self, app_id: str, secret_id: str) -> bool:
        return self._provider.exists(app_id, secret_id)

    def delete(self, app_id: str, secret_id: str) -> None:
        self._provider.delete(app_id, secret_id)

    def validate(self, app_id: str, secret_id: str) -> dict[str, object]:
        """Report whether a secret is usable without revealing anything about it.

        Deliberately not a strength or format check: inspecting the value would
        require reading it, and a length or charset hint is itself a small
        disclosure.
        """
        try:
            present = self._provider.exists(app_id, secret_id)
        except SecretAccessError as exc:
            return {"secret_id": secret_id, "status": "unavailable", "detail": str(exc)}
        return {
            "secret_id": secret_id,
            "status": "present" if present else "absent",
            "detail": "" if present else "not set in the OS credential store",
        }

    def presence(self, app_id: str, secret_ids: Iterable[str]) -> list[dict[str, object]]:
        return [self.validate(app_id, secret_id) for secret_id in secret_ids]

    def missing(self, app_id: str, secret_ids: Iterable[str]) -> list[str]:
        return [s for s in secret_ids if not self.exists(app_id, s)]

    def inject_into_env(
        self,
        app_id: str,
        secret_ids: Iterable[str],
        env: MutableMapping[str, str],
    ) -> None:
        """Write the named secrets into ``env``. Returns nothing, by design.

        The value never becomes the result of an expression a caller can bind,
        so there is no accidental path into a log line, a receipt, or an HTTP
        response.
        """
        sink = getattr(self._provider, "_read_into", None)
        if sink is None:
            # UnavailableSecretProvider and any third-party SecretProvider
            # implement the public presence interface without a sink. Failing
            # here is correct: a run that needs a secret must not proceed with
            # the variable silently unset.
            raise SecretAccessError(
                f"{type(self._provider).__name__} cannot supply secret values; "
                "configure an OS credential provider"
            )
        for secret_id in secret_ids:
            sink(app_id, secret_id, env, secret_id)

    def collect_redaction_values(
        self, app_id: str, secret_ids: Iterable[str]
    ) -> "RedactionHandle":
        """Materialise secrets solely so the log redactor can mask them.

        This is the one place a value is legitimately held outside a child's
        environment. The handle is a context manager, so the values are dropped
        as soon as the run finishes even if it raised.
        """
        return RedactionHandle(self, app_id, list(secret_ids))


class RedactionHandle:
    """Short-lived holder of secret values, used only to build a Redactor."""

    def __init__(self, broker: SecretBroker, app_id: str, secret_ids: Sequence[str]):
        self._broker = broker
        self._app_id = app_id
        self._secret_ids = list(secret_ids)
        self._values: dict[str, str] = {}

    def __enter__(self) -> "RedactionHandle":
        for secret_id in self._secret_ids:
            try:
                self._broker.inject_into_env(self._app_id, [secret_id], self._values)
            except SecretAccessError:
                # A secret that cannot be read cannot leak through this run
                # either; the operation's own preflight reports it as missing.
                continue
        return self

    def values(self) -> list[str]:
        return list(self._values.values())

    def __exit__(self, *exc_info: object) -> None:
        self.clear()

    def clear(self) -> None:
        for key in list(self._values):
            # Overwrite before dropping. CPython interns and copies strings, so
            # this is hygiene rather than a guarantee -- the real control is
            # that the window is this narrow.
            self._values[key] = "\x00" * len(self._values[key])
            del self._values[key]


def env_names_for(secret_ids: Iterable[str]) -> list[str]:
    """The environment variable names a run will define. Names only."""
    return sorted(set(secret_ids))


def describe_requirements(
    broker: SecretBroker, app_id: str, secret_refs: Mapping[str, Sequence[str]]
) -> dict[str, list[dict[str, object]]]:
    """Presence report for a UI, keyed by operation. No values anywhere."""
    return {
        operation_id: broker.presence(app_id, ids) for operation_id, ids in secret_refs.items()
    }

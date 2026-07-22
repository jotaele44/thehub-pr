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
from pathlib import Path

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

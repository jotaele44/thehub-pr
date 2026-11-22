"""Log network calls a Python process makes, through the interpreter's audit hooks.

Put this directory first on PYTHONPATH and set NETLOG to a file path; every
socket.connect, socket.getaddrinfo, urllib.Request and http.client.connect in
the process is appended to that file. Used for the RC8 first-start diagnosis.

    NETLOG=/tmp/net.log PYTHONPATH=scripts/runtime/netlog python scripts/runtime/serve_snapshot.py ...
"""

import os
import sys

_EVENTS = ("socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect")
_log = open(os.environ["NETLOG"], "a")  # noqa: SIM115 - held open for the life of the process


def _hook(event, args):
    if event in _EVENTS:
        _log.write(f"{event} {args!r}\n")
        _log.flush()


sys.addaudithook(_hook)

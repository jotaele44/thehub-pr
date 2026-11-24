#!/usr/bin/env python3
"""Start one application with ``python -X importtime`` and, once it answers
its first 200, report where its start goes.

Writes import time per top-level package (self time, summed) and the bytes of
the files the process has mapped (shared libraries and the interpreter), by
package. Used for the RC8 first-start diagnosis. Records; judges nothing.

usage: startup_profile.py <snapshots dir> <repository> <port> <out json>
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVE = Path(__file__).resolve().parent / "serve_snapshot.py"


def main() -> None:
    snapshots, repository, port, out = sys.argv[1:5]
    log_path = Path(out + ".importtime.log")
    started = time.monotonic()
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-X", "importtime", str(SERVE), snapshots, repository, port],
            stdout=subprocess.DEVNULL,
            stderr=log,
        )
        ready = None
        while time.monotonic() - started < 90:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    if response.status == 200:
                        ready = time.monotonic() - started
                        break
            except Exception:
                time.sleep(0.02)
        mapped: dict[str, int] = {}
        for line in Path(f"/proc/{process.pid}/maps").read_text().splitlines():
            parts = line.split()
            if (
                len(parts) >= 6
                and parts[5].startswith("/")
                and parts[5] not in mapped
                and os.path.exists(parts[5])
            ):
                mapped[parts[5]] = os.path.getsize(parts[5])
        process.terminate()
        process.wait(15)
    self_us: collections.Counter[str] = collections.Counter()
    for line in log_path.read_text().splitlines():
        if not line.startswith("import time:") or "cumulative" in line or line.count("|") != 2:
            continue
        self_part, _cumulative, name = line.split("|")
        self_us[name.strip().split(".")[0]] += int(self_part.split(":")[-1].strip())
    by_package: collections.Counter[str] = collections.Counter()
    for path, size in mapped.items():
        key = (
            path.split("site-packages/")[1].split("/")[0]
            if "site-packages/" in path
            else path.rsplit("/", 1)[0]
        )
        by_package[key] += size
    document = {
        "repository": repository,
        "ready_ms": None if ready is None else round(ready * 1000),
        "import_self_ms_by_top_package": {k: round(v / 1000) for k, v in self_us.most_common(15)},
        "import_self_ms_total": round(sum(self_us.values()) / 1000),
        "mapped_files_bytes_total": sum(mapped.values()),
        "mapped_bytes_by_package": dict(by_package.most_common(12)),
    }
    Path(out).write_text(json.dumps(document, indent=1) + "\n")
    print(json.dumps(document, indent=1))


if __name__ == "__main__":
    main()

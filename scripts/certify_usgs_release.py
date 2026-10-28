"""Assess exact checked-out release identity; scientific failure exits 2."""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_readiness import assess_usgs_readiness  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Preserve previous release assessment")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != args.expected_commit or len(head) != 40:
        raise ValueError("Exact release commit mismatch")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    )
    scoped = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "--",
         "src/hub", "scripts", "data/usgs", "registry/usgs", ".federation",
         "server/backend", "server/frontend/src", "TERMINAL_READY.txt"],
        cwd=ROOT, text=True
    )
    if dirty or scoped:
        raise ValueError("Tracked release files are modified")
    sums = json.loads((ROOT / "registry/usgs/SHA256SUMS.json").read_text())
    for name, expected in sums.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Release integrity mismatch: " + name)
        subprocess.run(["git", "ls-files", "--error-unmatch", name], cwd=ROOT,
                       check=True, stdout=subprocess.DEVNULL)
    readiness = assess_usgs_readiness(ROOT)
    matrix = json.loads(gzip.decompress(
        (ROOT / "registry/usgs/activation_matrix.v1.json.gz").read_bytes()
    ))
    inventory = json.loads(gzip.decompress(
        (ROOT / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
    ))
    expected_ids = {a["asset_id"] for a in inventory["assets"]}
    rows = matrix["assets"]
    if (len(rows) != len(expected_ids)
            or {a["asset_id"] for a in rows} != expected_ids
            or any(a["activation_state"] != "BLOCKED" for a in rows)
            or matrix["activated"] != 0 or matrix["production_eligible"] != 0):
        raise ValueError("Activation denominator or refusal mismatch")
    readiness.pop("assets")
    report = {
        "contract": "prii.usgs-exact-release-assessment/v1",
        "commit": head,
        "tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "software_identity": "PASS",
        "scope": "Exact Git and scoped evidence identity; NOT dataset certification",
        "readiness": readiness,
        "certification": "BLOCKED",
        "reason": "Source conflicts and unresolved scientific/consumer gates",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

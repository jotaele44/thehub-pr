#!/usr/bin/env python3
"""Fail-closed federation contract governance."""

from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import yaml

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
RANK = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}
ALLOWED = {"UNAFFECTED", "COMPATIBLE", "UPDATED"}


def canonical(obj):
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def sha256_obj(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def load_any(path):
    text = Path(path).read_text()
    return (
        yaml.safe_load(text)
        if str(path).endswith((".yaml", ".yml"))
        else json.loads(text)
    )


def bump_class(old, new):
    if old == new:
        return "NONE"
    major = False
    minor = False
    semantic_keys = {
        "identity",
        "identity_rule",
        "cardinality",
        "matching_semantics",
        "requiredness",
    }

    def walk(a, b, key=""):
        nonlocal major, minor
        if type(a) is not type(b):
            major = True
            return
        if isinstance(a, dict):
            ak, bk = set(a), set(b)
            if ak - bk:
                major = True
            if bk - ak:
                minor = True
            for k in ak & bk:
                if k == "required":
                    ao = set(a[k] or [])
                    bo = set(b[k] or [])
                    if bo - ao:
                        major = True
                    if ao - bo:
                        minor = True
                elif k == "enum":
                    ao = set(a[k] or [])
                    bo = set(b[k] or [])
                    if ao - bo:
                        major = True
                    if bo - ao:
                        minor = True
                elif (
                    k
                    in {
                        "type",
                        "pattern",
                        "minimum",
                        "maximum",
                        "minItems",
                        "maxItems",
                        "additionalProperties",
                    }
                    | semantic_keys
                ):
                    if a[k] != b[k]:
                        major = True
                elif k in {"title", "description", "examples", "$comment"}:
                    pass
                else:
                    walk(a[k], b[k], k)
        elif isinstance(a, list):
            if a != b:
                minor = True
        elif a != b and key not in {"schema_version", "contract_version", "version"}:
            minor = True

    walk(old, new)
    return "MAJOR" if major else "MINOR" if minor else "PATCH"


def declared_bump(oldv, newv):
    if not SEMVER_RE.match(oldv) or not SEMVER_RE.match(newv):
        return "INVALID"
    a = tuple(map(int, oldv.split(".")))
    b = tuple(map(int, newv.split(".")))
    if b <= a:
        return "NONE"
    if b[0] > a[0]:
        return "MAJOR"
    if b[1] > a[1]:
        return "MINOR"
    return "PATCH"


def closure(graph, roots):
    adj = {}
    for e in graph.get("edges", []):
        adj.setdefault(e["from"], set()).add(e["to"])
    seen = set(roots)
    q = list(roots)
    while q:
        n = q.pop(0)
        for m in sorted(adj.get(n, set())):
            if m not in seen:
                seen.add(m)
                q.append(m)
    return sorted(seen)


def reconcile(matrix, receipts):
    central = {k: v.get("state") for k, v in matrix.get("repos", {}).items()}
    baseline = matrix.get("federation_contract_baseline")
    got = {}
    errors = []
    for rp in receipts:
        x = load_json(rp)
        repo = x.get("repo")
        disp = x.get("disposition")
        if repo in got:
            errors.append(f"duplicate receipt for {repo}")
        got[repo] = x
        if repo not in central:
            errors.append(f"receipt for unknown repo {repo}")
            continue
        if central[repo] != disp:
            errors.append(f"{repo}: central={central[repo]} local={disp}")
        if disp not in ALLOWED:
            errors.append(f"{repo}: non-passing disposition {disp}")
        if x.get("central_baseline") != baseline:
            errors.append(f"{repo}: baseline mismatch")
    for repo, state in central.items():
        if repo == "thehub-pr":
            continue
        if state != "UNAFFECTED" and repo not in got:
            errors.append(f"missing receipt for impacted repo {repo}")
    return errors


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--old-version", required=True)
    d.add_argument("--new-version", required=True)
    c = sub.add_parser("closure")
    c.add_argument("graph")
    c.add_argument("roots", nargs="+")
    f = sub.add_parser("fingerprint")
    f.add_argument("paths", nargs="+")
    r = sub.add_parser("reconcile")
    r.add_argument("matrix")
    r.add_argument("receipts", nargs="+")
    a = p.parse_args()
    if a.cmd == "diff":
        old, new = load_any(a.old), load_any(a.new)
        req = bump_class(old, new)
        dec = declared_bump(a.old_version, a.new_version)
        out = {
            "required_bump": req,
            "declared_bump": dec,
            "old_sha256": sha256_obj(old),
            "new_sha256": sha256_obj(new),
            "pass": dec != "INVALID" and RANK.get(dec, -1) >= RANK[req],
        }
        print(json.dumps(out, indent=2))
        return 0 if out["pass"] else 1
    if a.cmd == "closure":
        print(json.dumps({"closure": closure(load_any(a.graph), a.roots)}, indent=2))
        return 0
    if a.cmd == "fingerprint":
        print(
            json.dumps(
                {x: hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in a.paths},
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    errors = reconcile(load_json(a.matrix), a.receipts)
    print(json.dumps({"pass": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Controlled acquisition of one frozen facet plan; bytes never activate datasets."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .usgs_acquisition import _NoRedirect
from .usgs_assets import approved_download_url, verify_payload

PLAN_SHA256 = "5015df7976366e4de4c8bf1309650f7e86ed857f2704c680c1e85238c25ba55d"
MAX_BUDGET = 1024 * 1024


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(path, value):
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def load_facet_plan(path):
    raw = Path(path).read_bytes()
    if _sha(raw) != PLAN_SHA256:
        raise ValueError("Unreviewed facet acquisition plan")
    plan = json.loads(raw)
    if (
        plan["contract"] != "prii.usgs-facet-acquisition-plan/v1"
        or plan["byte_budget"] != MAX_BUDGET
        or len(plan["targets"]) != 16
    ):
        raise ValueError("Facet plan denominator/budget mismatch")
    identities, urls = set(), set()
    declared = 0
    for target in plan["targets"]:
        identity, sid = target["reference_id"], target["source_item_id"]
        if (
            not re.fullmatch(r"[0-9a-f]{24}", sid)
            or identity != sid + "#" + target["json_pointer"]
            or identity in identities
        ):
            raise ValueError("Facet stable reference mismatch")
        url = approved_download_url(sid, target["raw_descriptor"])
        if url in urls:
            raise ValueError("Duplicate facet request URL")
        descriptor = target["raw_descriptor"]
        if type(descriptor["size"]) is not int or descriptor["size"] < 0:
            raise ValueError("Invalid declared source size")
        declared += descriptor["size"]
        identities.add(identity)
        urls.add(url)
    if declared != plan["declared_bytes"] or declared > MAX_BUDGET:
        raise ValueError("Facet declared-byte arithmetic mismatch")
    return plan


def acquire_facet_snapshot(plan_path, destination, snapshot_id, opener=None):
    """Freeze each attempt, reuse complete observations, and refuse orphan recovery."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", snapshot_id):
        raise ValueError("Invalid snapshot ID")
    plan = load_facet_plan(plan_path)
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "snapshot.json"
    identity = {
        "contract": "prii.usgs-facet-snapshot/v1",
        "snapshot_id": snapshot_id,
        "plan_sha256": PLAN_SHA256,
        "byte_budget": MAX_BUDGET,
    }
    if marker.exists():
        if json.loads(marker.read_text()) != identity:
            raise ValueError("Snapshot identity changed; use a new directory")
    elif any(out.iterdir()):
        raise ValueError("Nonempty snapshot directory lacks identity marker")
    else:
        _json(marker, identity)
    targets = {t["reference_id"]: t for t in plan["targets"]}
    known = {"snapshot.json", "summary.json", "TERMINAL_READY.txt", "execution.json"}
    for index in range(len(targets)):
        known.update({f"{index:02d}.response.bin", f"{index:02d}.receipt.json"})
    if any(p.name not in known for p in out.iterdir()):
        raise ValueError("Unknown or incomplete snapshot files; preserve for recovery")
    open_url = opener or urllib.request.build_opener(_NoRedirect()).open
    rows, used, cached = [], 0, {}
    for index, target in enumerate(plan["targets"]):
        receipt_path = out / f"{index:02d}.receipt.json"
        body_path = out / f"{index:02d}.response.bin"
        descriptor = target["raw_descriptor"]
        url = approved_download_url(target["source_item_id"], descriptor)
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            raw = body_path.read_bytes()
            if (
                receipt["reference_id"] != target["reference_id"]
                or receipt["plan_sha256"] != PLAN_SHA256
                or receipt["source_item_id"] != target["source_item_id"]
                or receipt["activation_state"] != "BLOCKED"
                or receipt["url"] != url
                or receipt["response_file"] != body_path.name
                or receipt["bytes"] != len(raw)
                or receipt["sha256"] != _sha(raw)
            ):
                raise ValueError("Cached facet receipt/body binding mismatch")
            if receipt["byte_state"] == "PASS":
                if receipt["http_status"] != 200 or receipt["truncated"]:
                    raise ValueError("Cached source PASS transport mismatch")
                verify_payload(raw, descriptor)
            elif receipt["byte_state"] not in ("FAIL", "BLOCKED"):
                raise ValueError("Invalid cached facet state")
            used += len(raw)
            if used > MAX_BUDGET:
                raise ValueError("Cached snapshot exceeds byte budget")
            cached[index] = receipt
            continue
        if body_path.exists():
            raise ValueError("Orphan response body; preserve without refetching")
    if (out / "summary.json").exists() and len(cached) != len(targets):
        raise ValueError("Completed snapshot lost evidence; recover without refetching")
    # Reserve every cached observation before the first new network request.
    # Cache gaps must not let fresh transfers consume later cached byte budget.
    for index, target in enumerate(plan["targets"]):
        if index in cached:
            rows.append(cached[index])
            continue
        receipt_path = out / f"{index:02d}.receipt.json"
        body_path = out / f"{index:02d}.response.bin"
        descriptor = target["raw_descriptor"]
        url = approved_download_url(target["source_item_id"], descriptor)
        remaining = MAX_BUDGET - used
        receipt = {
            "reference_id": target["reference_id"],
            "source_item_id": target["source_item_id"],
            "plan_sha256": PLAN_SHA256,
            "url": url,
            "retrieval_utc": datetime.now(timezone.utc).isoformat(),
            "http_status": None,
            "content_type": None,
            "error": None,
            "truncated": False,
            "byte_state": "BLOCKED",
            "activation_state": "BLOCKED",
        }
        raw = b""
        limit = min(descriptor["size"] + 1, remaining)
        if remaining <= descriptor["size"]:
            receipt["error"] = "SNAPSHOT_BYTE_BUDGET"
        else:
            request = urllib.request.Request(
                url, headers={"User-Agent": "PRII-USGS-facet-snapshot/1.0"}
            )
            try:
                with open_url(request, timeout=15) as response:
                    receipt["http_status"] = response.status
                    receipt["content_type"] = response.headers.get("Content-Type")
                    raw = response.read(limit)
                    receipt["truncated"] = len(raw) == limit
            except urllib.error.HTTPError as exc:
                receipt["http_status"] = exc.code
                receipt["content_type"] = exc.headers.get("Content-Type")
                error_limit = min(limit, 4096)
                raw = exc.read(error_limit)
                receipt["truncated"] = len(raw) == error_limit
                receipt["error"] = "HTTP_" + str(exc.code)
            except (OSError, TimeoutError) as exc:
                receipt["error"] = type(exc).__name__
            if receipt["http_status"] == 200 and not receipt["error"]:
                try:
                    verified = verify_payload(raw, descriptor)
                    receipt["source_checksum"] = verified
                    receipt["byte_state"] = "PASS"
                except ValueError as exc:
                    receipt["byte_state"] = "FAIL"
                    receipt["error"] = str(exc)
            elif not receipt["error"]:
                receipt["error"] = "UNEXPECTED_HTTP_STATUS"
        used += len(raw)
        if used > MAX_BUDGET:
            raise ValueError("Response reader exceeded requested byte budget")
        receipt.update(bytes=len(raw), sha256=_sha(raw), response_file=body_path.name)
        body_path.write_bytes(raw)
        _json(receipt_path, receipt)
        rows.append(receipt)
    if len(rows) != 16 or len({r["reference_id"] for r in rows}) != 16:
        raise ValueError("Facet snapshot reference denominator mismatch")
    summary = {
        **identity,
        "target_count": 16,
        "declared_bytes": plan["declared_bytes"],
        "captured_response_bytes": used,
        "byte_states": {
            s: sum(r["byte_state"] == s for r in rows)
            for s in ("PASS", "FAIL", "BLOCKED")
        },
        "state": "PASS" if all(r["byte_state"] == "PASS" for r in rows) else "BLOCKED",
        "scope": "Only frozen plan's 16 facet components; BYTE integrity only",
        "source_retrieval_is_new_snapshot": True,
        "scientific_staging": "BLOCKED",
        "activated": 0,
        "receipts": rows,
    }
    previous_summary = out / "summary.json"
    if previous_summary.exists() and json.dumps(
        json.loads(previous_summary.read_text()), sort_keys=True
    ) != json.dumps(summary, sort_keys=True):
        raise ValueError("Frozen summary disagrees with receipts; preserve for review")
    _json(previous_summary, summary)
    (out / "TERMINAL_READY.txt").write_text(
        "USGS controlled facet snapshot. BYTE evidence only; activation BLOCKED.\n"
        "Use the same plan, directory and snapshot ID to reuse all frozen attempts.\n"
        "Failed observations are not retried under the same snapshot ID.\n"
        "No response body may exceed the 1 MiB aggregate budget.\n"
        "Do not infer source absence from HTTP, redirect, timeout or checksum failure.\n"
    )
    return summary


def verify_facet_archive(archive_path, expected_sha256, plan_path):
    """Independently replay all sixteen BYTE checks; never infer domain readiness."""
    import zipfile

    archive_path = Path(archive_path)
    packed = archive_path.read_bytes()
    if len(packed) > MAX_BUDGET or _sha(packed) != expected_sha256:
        raise ValueError("Facet artifact archive mismatch")
    plan = load_facet_plan(plan_path)
    targets = {t["reference_id"]: t for t in plan["targets"]}
    expected_names = {
        "snapshot.json",
        "summary.json",
        "execution.json",
        "TERMINAL_READY.txt",
    }
    for i in range(16):
        expected_names.update({f"{i:02d}.receipt.json", f"{i:02d}.response.bin"})
    with zipfile.ZipFile(archive_path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise ValueError("Facet archive member denominator mismatch")
        if sum(i.file_size for i in z.infolist()) > MAX_BUDGET + 256 * 1024:
            raise ValueError("Facet archive expanded capacity exceeded")
        if z.testzip() is not None:
            raise ValueError("Facet archive CRC mismatch")
        marker, summary = (
            json.loads(z.read("snapshot.json")),
            json.loads(z.read("summary.json")),
        )
        if (
            marker["plan_sha256"] != PLAN_SHA256
            or summary["plan_sha256"] != PLAN_SHA256
            or marker["snapshot_id"] != summary["snapshot_id"]
        ):
            raise ValueError("Facet snapshot/plan binding mismatch")
        stored = summary["receipts"]
        if len(stored) != 16 or {r["reference_id"] for r in stored} != set(targets):
            raise ValueError("Facet reference membership mismatch")
        total = 0
        for i, target in enumerate(plan["targets"]):
            receipt = json.loads(z.read(f"{i:02d}.receipt.json"))
            body = z.read(f"{i:02d}.response.bin")
            if (
                json.dumps(receipt, sort_keys=True)
                != json.dumps(stored[i], sort_keys=True)
                or receipt["reference_id"] != target["reference_id"]
                or receipt["source_item_id"] != target["source_item_id"]
                or receipt["response_file"] != f"{i:02d}.response.bin"
                or receipt["url"]
                != approved_download_url(
                    target["source_item_id"], target["raw_descriptor"]
                )
                or receipt["plan_sha256"] != PLAN_SHA256
                or receipt["http_status"] != 200
                or receipt["byte_state"] != "PASS"
                or receipt["activation_state"] != "BLOCKED"
                or receipt["error"]
                or receipt["truncated"]
                or receipt["bytes"] != len(body)
                or receipt["sha256"] != _sha(body)
            ):
                raise ValueError("Facet receipt/body identity or integrity mismatch")
            verify_payload(body, target["raw_descriptor"])
            total += len(body)
        if (
            total != summary["captured_response_bytes"]
            or total != plan["declared_bytes"]
            or summary["byte_states"] != {"PASS": 16, "FAIL": 0, "BLOCKED": 0}
            or summary["activated"] != 0
            or summary["scientific_staging"] != "BLOCKED"
        ):
            raise ValueError("Facet byte denominator/promotion mismatch")
        return {
            "contract": "prii.usgs-facet-byte-validation/v1",
            "state": "PASS",
            "scope": "Sixteen frozen facet component BYTE checks only",
            "snapshot_id": summary["snapshot_id"],
            "archive_sha256": expected_sha256,
            "reference_count": 16,
            "bytes": total,
            "scientific_staging": "BLOCKED",
            "activation_state": "BLOCKED",
            "activated": 0,
        }

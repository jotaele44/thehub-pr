#!/usr/bin/env python3
"""Freeze a bounded official historical hydro-source set for HTR v3.

The source set is explicit and finite; this does not claim exhaustion of every
historical PRWRA / irrigation archive. It closes the configured source-set
vector only. Source manifestations remain separate from canonical identity.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "thehub-pr-htr-v3-history/1.0 (+https://github.com/jotaele44/thehub-pr)"
SOURCES = [
    {
        "id": "ogp-law-83-1955",
        "authority": "Puerto Rico Office of Management and Budget / Laws Collection",
        "url": "https://bvirtualogp.pr.gov/ogp/Bvirtual/leyesreferencia/PDF/83-1955.pdf",
        "kind": "pdf",
        "manifestations": [
            ("Sistema Hidroeléctrico del Servicio de Riego Público de Puerto Rico—Costa Sur", "HYDRO_SYSTEM"),
        ],
    },
    {
        "id": "ogp-law-84-1955",
        "authority": "Puerto Rico Office of Management and Budget / Laws Collection",
        "url": "https://bvirtualogp.pr.gov/ogp/Bvirtual/leyesreferencia/PDF/84-1955.pdf",
        "kind": "pdf",
        "manifestations": [
            ("Sistema Hidroeléctrico del Servicio de Riego de Isabela", "HYDRO_SYSTEM"),
        ],
    },
    {
        "id": "usgs-sim-2990-publication",
        "authority": "U.S. Geological Survey",
        "url": "https://pubs.usgs.gov/publication/sim2990",
        "kind": "html",
        "manifestations": [
            ("Lago Guerrero", "RESERVOIR"),
            ("Isabela Hydroelectric System", "HYDRO_SYSTEM"),
            ("Central Isabel No. 2", "HYDRO_PLANT"),
            ("Central Isabel No. 3", "HYDRO_PLANT"),
            ("Canal Principal de Diversion", "CANAL"),
            ("Lago Guajataca", "RESERVOIR"),
        ],
    },
    {
        "id": "usgs-sim-3128-publication",
        "authority": "U.S. Geological Survey",
        "url": "https://pubs.usgs.gov/publication/sim3128",
        "kind": "html",
        "manifestations": [
            ("Lago Patillas", "RESERVOIR"),
            ("Patillas Irrigation Canal", "CANAL"),
        ],
    },
    {
        "id": "usgs-sim-3364",
        "authority": "U.S. Geological Survey",
        "url": "https://pubs.usgs.gov/sim/3364/sim3364.pdf",
        "kind": "pdf",
        "manifestations": [
            ("Lago Lucchetti", "RESERVOIR"),
            ("Southwestern Puerto Rico Project", "HYDRO_IRRIGATION_PROJECT"),
            ("Lago Loco", "RESERVOIR"),
            ("Lago Guayo", "RESERVOIR"),
            ("Lago Prieto", "RESERVOIR"),
            ("Lago Toro", "RESERVOIR"),
        ],
    },
    {
        "id": "usgs-wri-1999-4169",
        "authority": "U.S. Geological Survey",
        "url": "https://pubs.usgs.gov/wri/1999/4169/report.pdf",
        "kind": "pdf",
        "manifestations": [
            ("Lago Prieto", "RESERVOIR"),
            ("Southwestern Puerto Rico Project", "HYDRO_IRRIGATION_PROJECT"),
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value: str) -> str:
    value = html.unescape(value)
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"<[^>]+>", " ", folded)
    folded = re.sub(r"[^A-Za-z0-9]+", " ", folded).strip().lower()
    return re.sub(r"\s+", " ", folded)


def download(url: str, path: Path, attempts: int = 4) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=180) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return {
                "url": url,
                "retrieval_utc": utc_now(),
                "bytes": len(payload),
                "sha256": sha256(path),
                "content_type": content_type,
                "path": str(path),
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"download failed after {attempts} attempts: {url}: {last}")


def source_text(path: Path, kind: str) -> str:
    if kind == "html":
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
        raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
        return norm(raw)
    from pypdf import PdfReader
    return norm("\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("artifacts/htr_v3_historical"))
    args = ap.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    started = utc_now()
    raw_manifest: list[dict[str, Any]] = []
    manifestations: list[dict[str, Any]] = []

    for source in SOURCES:
        suffix = ".pdf" if source["kind"] == "pdf" else ".html"
        path = args.out / "raw" / f"{source['id']}{suffix}"
        receipt = download(source["url"], path)
        raw_manifest.append({"source_id": source["id"], "authority": source["authority"], **receipt})
        if source["kind"] == "pdf" and not path.read_bytes().startswith(b"%PDF"):
            raise RuntimeError(f"{source['id']} did not return PDF bytes")
        text = source_text(path, source["kind"])
        for index, (raw_name, asset_class) in enumerate(source["manifestations"], 1):
            anchor = norm(raw_name)
            if anchor not in text:
                raise RuntimeError(f"anchor missing in {source['id']}: {raw_name!r}")
            manifestations.append({
                "source_manifestation_id": f"{source['id']}:{index:02d}",
                "source_id": source["id"],
                "source_authority": source["authority"],
                "source_url": source["url"],
                "raw_name": raw_name,
                "normalized_name": anchor,
                "asset_class": asset_class,
                "canonical_entity_id": None,
                "cross_source_identity_state": "UNRESOLVED",
                "discovery_key_status": "SUPPORTED",
                "identity_claim": False,
                "connectivity_claim": False,
            })

    source_ids = [row["source_id"] for row in raw_manifest]
    manifestation_ids = [row["source_manifestation_id"] for row in manifestations]
    if len(source_ids) != len(set(source_ids)):
        raise RuntimeError("duplicate historical source IDs")
    if len(manifestation_ids) != len(set(manifestation_ids)):
        raise RuntimeError("duplicate historical manifestation IDs")
    if len(raw_manifest) != 6 or len(manifestations) != 18:
        raise RuntimeError(f"historical denominator arithmetic drift: sources={len(raw_manifest)} manifestations={len(manifestations)}")

    write_json(args.out / "raw_manifest.json", raw_manifest)
    write_jsonl(args.out / "historical_source_manifestations.jsonl", manifestations)
    summary = {
        "schema_version": "major-hydro-asset-v3-historical-source-set-1.0",
        "started_utc": started,
        "completed_utc": utc_now(),
        "configured_source_count": 6,
        "frozen_source_count": len(raw_manifest),
        "source_manifestation_count": len(manifestations),
        "source_arithmetic": "6=6",
        "manifestation_arithmetic": "18=18",
        "raw_normalized_canonical_separate": True,
        "canonical_identity_certified": False,
        "connectivity_certified": False,
        "historical_source_set_exhausted": True,
        "universal_historical_archive_exhausted": False,
        "certification": "PASS_BOUNDED_HISTORICAL_SOURCE_SET",
    }
    write_json(args.out / "summary.json", summary)
    hashes = {
        str(path.relative_to(args.out)): sha256(path)
        for path in sorted(args.out.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    }
    write_json(args.out / "SHA256SUMS.json", hashes)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

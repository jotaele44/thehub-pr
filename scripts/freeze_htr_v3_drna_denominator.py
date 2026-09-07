#!/usr/bin/env python3
"""Freeze DRNA 2004/2016 reservoir tables for MAJOR_HYDRO_ASSET_v3.

The two PDFs are frozen independently. Table rows are source manifestations,
not cross-source identities. RAW names are preserved as transcribed from the
source tables; normalized forms are separate; canonical_entity_id stays null.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PDF_2004 = "https://www.drna.pr.gov/wp-content/uploads/2015/07/INFORME_EMBALSES_2MAR04.pdf"
PDF_2016 = "https://www.drna.pr.gov/wp-content/uploads/formidable/PIRA-2016-Cap%C3%ADtulo-3.pdf"
USER_AGENT = "thehub-pr-htr-v3-drna/1.0 (+https://github.com/jotaele44/thehub-pr)"

LESSER_2004 = [
    ("Ajíes", "Río Gde. de Añasco", 1984, "DRNA", "Control de inundación"),
    ("Ana María II", "Río Inabón", 1939, "Privada", "Riego"),
    ("Ana María V", "Río Inabón", 1939, "Privada", "Riego"),
    ("Bronce", "Río Inabón", 1939, "Privada", "Riego"),
    ("Dagüey", "Río Gde. de Añasco", 1978, "DRNA", "Control de inundación"),
    ("Guerrero", "Canal de Riego de Isabela", 1922, "AEE", "Hidroeléctrico/Riego"),
    ("Icacos", "Río Blanco", 1930, "AEE", "Hidroeléctrico"),
    ("Lago Regulador", "Canal de Riego de Isabela", 1996, "AAA", "Abasto público"),
    ("Melanía", "Canal de Riego Costa Sur", 1914, "AEE", "Riego"),
    ("Ponceña", "Río Guayo", 1939, "Privada", "Riego"),
]

PIRA_2016 = [
    ("Blanco", "Mayor", "Activo"), ("Caonillas", "Mayor", "Activo"),
    ("Carite", "Mayor", "Activo"), ("Cerrillos", "Mayor", "Activo"),
    ("Cidra", "Intermedio", "Activo"), ("Dos Bocas", "Mayor", "Activo"),
    ("El Guineo", "Mayor", "Activo"), ("Fajardo", "Mayor", "Activo"),
    ("Garzas", "Mayor", "Activo"), ("Guajataca", "Mayor", "Activo"),
    ("Guayabal", "Mayor", "Activo"), ("Guayo", "Mayor", "Activo"),
    ("La Plata", "Mayor", "Activo"), ("Loco", "Intermedio", "Activo"),
    ("Loiza", "Mayor", "Activo"), ("Lucchetti", "Mayor", "Activo"),
    ("Matrullas", "Mayor", "Activo"), ("Patillas", "Mayor", "Activo"),
    ("Prieto", "Intermedio", "Activo"), ("Portugués", "Mayor", "Activo"),
    ("Toa Vaca", "Mayor", "Activo"), ("Yahuecas", "Intermedio", "Sedimentado"),
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", value)).strip().lower()


def download(url: str, path: Path, attempts: int = 4) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=180) as response:
                payload = response.read()
            if not payload.startswith(b"%PDF"):
                raise RuntimeError(f"non-PDF payload from {url}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return {"url": url, "retrieval_utc": now(), "bytes": len(payload), "sha256": sha256(path), "path": str(path)}
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"download failed after {attempts} attempts: {url}: {last}")


def extract_text(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/htr_v3_drna")
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    started = now()

    raw2004 = download(PDF_2004, out / "raw" / "drna_2004.pdf")
    raw2016 = download(PDF_2016, out / "raw" / "pira_2016_ch3.pdf")
    text2004 = norm(extract_text(out / "raw" / "drna_2004.pdf"))
    text2016 = norm(extract_text(out / "raw" / "pira_2016_ch3.pdf"))

    missing2004 = [name for name, *_ in LESSER_2004 if norm(name) not in text2004]
    missing2016 = [name for name, *_ in PIRA_2016 if norm(name) not in text2016]
    if missing2004 or missing2016:
        raise RuntimeError(f"table-anchor verification failed: 2004={missing2004} 2016={missing2016}")

    rows2004 = [
        {
            "source_manifestation_id": f"drna-2004-lesser:{idx:02d}",
            "source_id": "drna:planagua:embalses:table-4.3-1",
            "source_url": PDF_2004,
            "source_table": "Tabla 4.3-1",
            "raw_name": name,
            "normalized_name": norm(name),
            "watershed_raw": watershed,
            "year_built": year,
            "owner_raw": owner,
            "primary_use_raw": use,
            "source_classification": "ACTIVE_LESSER_IMPORTANCE_FOR_2004_PLAN",
            "canonical_entity_id": None,
            "cross_source_identity_state": "UNRESOLVED",
            "discovery_key_status": "SUPPORTED",
            "identity_claim": False,
            "connectivity_claim": False,
        }
        for idx, (name, watershed, year, owner, use) in enumerate(LESSER_2004, 1)
    ]
    rows2016 = [
        {
            "source_manifestation_id": f"drna-pira-2016-table-3.5:{idx:02d}",
            "source_id": "drna:pira:2016:table-3.5",
            "source_url": PDF_2016,
            "source_table": "Tabla 3.5",
            "raw_name": name,
            "normalized_name": norm(name),
            "classification_raw": classification,
            "situation_raw": situation,
            "canonical_entity_id": None,
            "cross_source_identity_state": "UNRESOLVED",
            "discovery_key_status": "SUPPORTED",
            "identity_claim": False,
            "connectivity_claim": False,
        }
        for idx, (name, classification, situation) in enumerate(PIRA_2016, 1)
    ]
    write_jsonl(out / "drna_2004_lesser_manifestations.jsonl", rows2004)
    write_jsonl(out / "drna_pira_2016_table_3_5_manifestations.jsonl", rows2016)
    write_json(out / "raw_manifest.json", [raw2004, raw2016])

    counts2016: dict[str, int] = {}
    for _, classification, _ in PIRA_2016:
        counts2016[classification] = counts2016.get(classification, 0) + 1
    summary = {
        "schema_version": "htr-v3-drna-denominator-1.0",
        "started_utc": started,
        "completed_utc": now(),
        "drna_2004_lesser_rows": len(rows2004),
        "drna_2016_table_3_5_rows": len(rows2016),
        "drna_2016_classification_counts": counts2016,
        "drna_2004_category_arithmetic_with_v2": "44=34+10",
        "note": "44 arithmetic closes the 2004 report's v2 categories plus Table 4.3-1 lesser-importance set; it is not a universal present-day reservoir claim.",
        "table_anchor_verification": "PASS",
        "raw_normalized_canonical_separate": True,
        "canonical_identity_certified": False,
        "connectivity_certified": False,
        "universal_hydro_exhaustion_claimed": False,
        "certification": "PASS",
    }
    write_json(out / "summary.json", summary)
    hashes = {
        str(path.relative_to(out)): sha256(path)
        for path in sorted(out.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    }
    write_json(out / "SHA256SUMS.json", hashes)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Adjudicate already-frozen HTR v3 source snapshots without network access.

Inputs are GitHub Actions artifacts from three earlier acquisition runs. This
stage is intentionally byte-reuse only: it computes no live HTTP requests.
Source manifestations remain separate from canonical identity, and discovery
eligibility is adjudicated independently from source truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Iterable

NID_AAA_ARTIFACT_DIGEST = "451fa8d13fe09bf11830039e6a780e9efc5ef9c8fa70311bd3b28393bbc40d19"
CANAL_ARTIFACT_DIGEST = "2369a5da2d8b1cfe2ce3d305a9f7bea822aa6da69a67322b812b3d1bedf903bd"
DRNA_ARTIFACT_DIGEST = "5e831f4a44031c28de39ca1eff54962239dd13fde861023999659022f4cd88a5"
EXPECTED = {
    "nid_source_rows": "c93a3e64dec37018c2f45f5e386b70213638358eb22b4ce27f679c21f1c5b819",
    "nid_name_manifestations": "2f170f4f66aa6151d3bf7d5a53951a789be191c3ef70ebd924a79c59fd58733e",
    "nid_primary_extension": "d3b176b3f6976e2d5da508743dca9b15f43b2b05d3a9ef4d0af12c71da319cac",
    "aaa_archive": "6afe70c8cc96f2b7d3f73a0976f4bd5d422dff74ba7071281f9c1262be851d8e",
    "canal_source_rows": "bced9252c6c474021ace08bdd5d2de9946f099c871793634cc002437ab456e77",
    "drna_2004_pdf": "375f0528bf3e99568c25a1dee19b332d193ad46b7129874c3d5d929ef18353b4",
    "drna_2016_pdf": "53eca5c150c7be214f4dc68ec395f46f662d23625600dc95ad8a7fb0f4d2d70a",
}

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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", folded)).strip().lower()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def assert_hash(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"hash mismatch {path}: {actual} != {expected}")


def adjudicate_nid(root: Path, out: Path) -> dict[str, Any]:
    source_rows_path = root / "nid_pr_source_rows.jsonl"
    names_path = root / "nid_pr_name_manifestations.jsonl"
    primary_path = root / "nid_pr_v3_extension.jsonl"
    assert_hash(source_rows_path, EXPECTED["nid_source_rows"])
    assert_hash(names_path, EXPECTED["nid_name_manifestations"])
    assert_hash(primary_path, EXPECTED["nid_primary_extension"])
    source_rows = read_jsonl(source_rows_path)
    names = read_jsonl(names_path)
    primary = read_jsonl(primary_path)
    nid_ids = [row["attributes"]["nidId"] for row in source_rows]
    if len(source_rows) != 36 or len(set(nid_ids)) != 36:
        raise RuntimeError("NID 36-row/stable-ID denominator drift")
    if len(names) != 103 or len(primary) != 36:
        raise RuntimeError("NID name-manifestation denominator drift")
    unsupported = [row for row in names if row.get("discovery_key_status") == "UNSUPPORTED"]
    if len(unsupported) != 67:
        raise RuntimeError("NID unsupported raw alias-field count drift")
    write_jsonl(out / "nid_primary_manifestations.jsonl", primary)
    write_jsonl(out / "nid_raw_alias_fields_unsupported.jsonl", unsupported)
    return {
        "source_rows": 36,
        "stable_nid_ids": 36,
        "primary_supported_discovery_manifestations": 36,
        "raw_alias_field_manifestations_unsupported": 67,
        "all_name_field_manifestations": 103,
        "canonical_identity_certified": False,
    }


def adjudicate_aaa(root: Path, out: Path) -> dict[str, Any]:
    import pandas as pd
    import pyogrio

    archive = root / "raw" / "aaa_2015" / "GDB_NAD83_2011.gdb.zip"
    assert_hash(archive, EXPECTED["aaa_archive"])
    gdb = root / "raw" / "aaa_2015" / "extracted" / "GDB_NAD83_2011.gdb"
    frame = pyogrio.read_dataframe(gdb, layer="w_Intake", read_geometry=False)
    if len(frame) != 182 or frame["FacilityID"].nunique(dropna=False) != 182:
        raise RuntimeError("AAA w_Intake row/FacilityID denominator drift")
    if frame["Name"].isna().any():
        raise RuntimeError("AAA w_Intake unexpected null Name")
    rows: list[dict[str, Any]] = []
    for _, record in frame.sort_values("FacilityID").iterrows():
        raw = str(record["Name"])
        def value(key: str) -> Any:
            item = record[key]
            if pd.isna(item):
                return None
            return item.item() if hasattr(item, "item") and not isinstance(item, str) else item
        rows.append({
            "source_manifestation_id": f"aaa-2015-intake:{record['FacilityID']}",
            "source_id": "aaa:infrastructure-2015:w_Intake",
            "source_feature_id": record["FacilityID"],
            "raw_name": raw,
            "normalized_name": norm(raw),
            "canonical_entity_id": None,
            "cross_source_identity_state": "UNRESOLVED",
            "source_feature_class": "INTAKE",
            "major_hydro_asset_eligibility": "UNRESOLVED",
            "discovery_key_status": "SUPPORTED_AS_INTAKE_NAME_BUT_MAJOR_ELIGIBILITY_UNRESOLVED",
            "owner_raw": value("Owner"),
            "capacity_mgd_raw": value("CapacityMGD"),
            "safe_yield_raw": value("SafeYield"),
            "water_source_raw": value("WaterSource"),
            "plant_supplied_raw": value("PlantSupplied"),
            "municipality_raw": value("Municipality"),
            "identity_claim": False,
            "connectivity_claim": False,
        })
    write_jsonl(out / "aaa_2015_intake_manifestations.jsonl", rows)
    return {
        "source_rows": 182,
        "stable_facility_ids": 182,
        "distinct_raw_names": int(frame["Name"].nunique()),
        "major_hydro_asset_eligibility_unresolved": 182,
        "canonical_identity_certified": False,
    }


def adjudicate_canal(root: Path, out: Path) -> dict[str, Any]:
    source = root / "canal_source_rows.jsonl"
    assert_hash(source, EXPECTED["canal_source_rows"])
    rows = read_jsonl(source)
    ids = [row["source_feature_id"] for row in rows]
    if len(rows) != 3187 or len(set(ids)) != 3187:
        raise RuntimeError("SIGE canal source-row denominator drift")
    raw_names = {row.get("raw_name") for row in rows}
    if raw_names != {"Canal de Riego"}:
        raise RuntimeError(f"SIGE canal RAW family drift: {raw_names}")
    corrected = []
    for row in rows:
        item = dict(row)
        item["discovery_key_status"] = "UNSUPPORTED"
        item["unsupported_reason"] = "GENERIC_FEATURE_CLASS_ONLY"
        item["canonical_entity_id"] = None
        item["cross_source_identity_state"] = "UNRESOLVED"
        item["identity_claim"] = False
        item["connectivity_claim"] = False
        corrected.append(item)
    write_jsonl(out / "sige_canal_manifestations_unsupported.jsonl", corrected)
    return {
        "source_rows": 3187,
        "raw_name_families": 1,
        "raw_name": "Canal de Riego",
        "unsupported_discovery_manifestations": 3187,
        "unsupported_reason": "GENERIC_FEATURE_CLASS_ONLY",
        "canonical_identity_certified": False,
    }


def adjudicate_drna(root: Path, out: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    pdf2004 = root / "raw" / "drna_2004.pdf"
    pdf2016 = root / "raw" / "pira_2016_ch3.pdf"
    assert_hash(pdf2004, EXPECTED["drna_2004_pdf"])
    assert_hash(pdf2016, EXPECTED["drna_2016_pdf"])
    text2004 = norm("\n".join((page.extract_text() or "") for page in PdfReader(str(pdf2004)).pages))
    text2016 = norm("\n".join((page.extract_text() or "") for page in PdfReader(str(pdf2016)).pages))
    missing = [name for name, *_ in LESSER_2004 if norm(name) not in text2004]
    if missing:
        raise RuntimeError(f"DRNA 2004 table anchor drift: {missing}")
    for anchor in ("existen 39 embalses", "15 de ellos considerados obras mayores", "tabla 3 5"):
        if norm(anchor) not in text2016:
            raise RuntimeError(f"DRNA 2016 context anchor missing: {anchor}")

    rows2004 = [
        {
            "source_manifestation_id": f"drna-2004-lesser:{idx:02d}",
            "source_id": "drna:planagua:embalses:table-4.3-1",
            "source_page_table": "Tabla 4.3-1",
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
            "source_page_table": "3-22 / Tabla 3.5",
            "transcription_method": "VISUAL_TABLE_TRANSCRIPTION_BOUND_TO_FROZEN_PDF_SHA256",
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
    major_count = sum(row[1] == "Mayor" for row in PIRA_2016)
    contradictions = [{
        "contradiction_id": "drna-2016:major-count-prose-vs-table",
        "classes": ["COUNT", "CLASS"],
        "prose_fact": "39 reservoirs, 15 considered major works",
        "table_fact": f"Table 3.5 has {major_count} of 22 columns classified Mayor",
        "disposition": "UNRESOLVED_SEMANTIC_SCOPE_DIFFERENCE_OR_SOURCE_CONTRADICTION",
    }]
    write_json(out / "contradictions.json", contradictions)
    return {
        "drna_2004_lesser_rows": 10,
        "drna_2016_table_3_5_rows": 22,
        "drna_2016_table_mayor_rows": major_count,
        "drna_2016_table_intermedio_rows": 22 - major_count,
        "drna_2016_prose_total_reservoirs": 39,
        "drna_2016_prose_major_works": 15,
        "drna_2016_unenumerated_vs_prose_total": 17,
        "drna_2004_category_arithmetic_with_v2": "44=34+10",
        "contradictions": len(contradictions),
        "canonical_identity_certified": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nid-aaa-root", type=Path, required=True)
    ap.add_argument("--canal-root", type=Path, required=True)
    ap.add_argument("--drna-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("artifacts/htr_v3_adjudicated"))
    args = ap.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    nid = adjudicate_nid(args.nid_aaa_root, args.out)
    aaa = adjudicate_aaa(args.nid_aaa_root, args.out)
    canal = adjudicate_canal(args.canal_root, args.out)
    drna = adjudicate_drna(args.drna_root, args.out)

    new_supported_major_discovery = 2 + 36 + 10 + 22
    new_unsupported = 67 + 3187
    new_major_eligibility_unresolved = 182
    new_total = new_supported_major_discovery + new_unsupported + new_major_eligibility_unresolved
    if new_total != 3506:
        raise RuntimeError(f"v3 source-manifestation arithmetic drift: {new_total}")
    summary = {
        "schema_version": "major-hydro-asset-v3-adjudicated-frozen-sources-1.0",
        "input_artifacts": {
            "nid_aaa_digest": f"sha256:{NID_AAA_ARTIFACT_DIGEST}",
            "canal_digest": f"sha256:{CANAL_ARTIFACT_DIGEST}",
            "drna_digest": f"sha256:{DRNA_ARTIFACT_DIGEST}",
        },
        "base_v2_manifestations": 107,
        "preexisting_v3_usace_manifestations": 2,
        "nid": nid,
        "aaa_2015": aaa,
        "sige_canal": canal,
        "drna": drna,
        "new_v3_source_manifestation_arithmetic": "3506=70+3254+182",
        "new_v3_source_manifestations": 3506,
        "supported_for_major_discovery": new_supported_major_discovery,
        "unsupported_discovery_key": new_unsupported,
        "major_hydro_asset_eligibility_unresolved": new_major_eligibility_unresolved,
        "bounded_supported_discovery_manifestations_with_v2": 107 + new_supported_major_discovery,
        "total_source_manifestations_with_v2": 107 + new_total,
        "identity_promotions": 0,
        "connectivity_promotions": 0,
        "transitive_context_inheritance": 0,
        "unexplained_manifestation_residue": 0,
        "unresolved_major_eligibility_residue": 182,
        "unresolved_cross_source_identity": True,
        "universal_hydro_exhaustion_claimed": False,
        "historical_prwra_exhaustion": "OPEN",
        "usgs_conveyance_expansion_beyond_v2": "OPEN",
        "aaa_major_intake_classification": "OPEN",
        "certification": "PASS_BOUNDED_SOURCE_MANIFESTATION_CLASSIFICATION",
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

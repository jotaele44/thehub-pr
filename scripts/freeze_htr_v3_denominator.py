#!/usr/bin/env python3
"""Freeze bounded authoritative source inputs for MAJOR_HYDRO_ASSET_v3.

This runner does not merge cross-source identities. It freezes source-specific
manifestations and promotes only a source's own stable identifier to a
source_entity_id. Name, fuzzy similarity, proximity, and clustering are never
canonical identity or connectivity evidence.

Configured public sources:
* USDOT/BTS NTAD representation of USACE NID — complete stateKey=PR denominator.
* Puerto Rico GIS / AAA 2015 infrastructure file geodatabase — archive + schema
  inventory only until its layer/field denominator is adjudicated.
* Puerto Rico GIS / PREPA Isabela irrigation canal WFS — archive, schema, and
  source rows. The publishing page warns that positional accuracy is limited.

Existing v1/v2 and the two already-frozen USACE v3 manifestations are inputs by
reference and are never rewritten by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

NID_LAYER = "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Dams/FeatureServer/0"
NID_SERVICE_ITEM_ID = "7215635eed4241099d9b26a84ac9d6fa"
AAA_ZIP = "https://gis.otg.pr.gov/Downloads/AAA/GDB_NAD83_2011.gdb.zip"
ISABELA_WFS = (
    "https://geoserver2.pr.gov/geoserver/pr_geodata/ows?"
    "outputFormat=SHAPE-ZIP&request=GetFeature&service=WFS&"
    "typeName=pr_geodata%3Ag23_agricultura_canal_riego_isabela&version=2.0.0"
)
USER_AGENT = "thehub-pr-htr-v3/1.0 (+https://github.com/jotaele44/thehub-pr)"
NID_FIELDS = [
    "OBJECTID", "id", "federalId", "nidId", "name", "otherNames", "formerNames",
    "latitude", "longitude", "state", "stateKey", "county", "city", "riverName",
    "ownerNames", "sourceAgency", "yearCompleted", "operationalStatusId",
    "privateDamId", "primaryPurposeId", "purposeIds", "nidHeight", "damHeight",
    "maxStorage", "normalStorage", "dataUpdated", "websiteUrl",
]
HYDRO_LAYER_TOKEN = re.compile(
    r"(embals|reserv|repres|dam|presa|canal|riego|aqueduct|acueduct|intake|toma|"
    r"penstock|tunel|tunnel|hydro|hidro|planta|filtr|raw.?water|agua.?cruda)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def request_bytes(url: str, *, data: bytes | None = None, attempts: int = 4) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded" if data is not None else "application/octet-stream",
        },
    )
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt == attempts:
                break
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"request failed after {attempts} attempts: {url}: {last}")


def freeze_get(url: str, path: Path, raw_manifest: list[dict[str, Any]]) -> bytes:
    payload = request_bytes(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    raw_manifest.append({
        "url": url,
        "method": "GET",
        "retrieval_utc": utc_now(),
        "path": str(path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    })
    return payload


def freeze_post(url: str, params: dict[str, Any], path: Path, raw_manifest: list[dict[str, Any]]) -> bytes:
    encoded = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
    payload = request_bytes(url, data=encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    raw_manifest.append({
        "url": url,
        "method": "POST",
        "params": params,
        "retrieval_utc": utc_now(),
        "path": str(path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    })
    return payload


def parse_json(payload: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {source}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root from {source} is not an object")
    if value.get("error"):
        raise RuntimeError(f"source error from {source}: {value['error']}")
    return value


def chunks(values: list[int], size: int = 500) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def normalized_name(raw: str) -> str:
    import unicodedata
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^A-Za-z0-9]+", " ", folded).strip().lower()
    return re.sub(r"\s+", " ", folded)


def freeze_nid(out: Path, raw_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    source_dir = out / "raw" / "nid"
    metadata = parse_json(
        freeze_get(f"{NID_LAYER}?f=pjson", source_dir / "metadata.json", raw_manifest),
        NID_LAYER,
    )
    if metadata.get("serviceItemId") != NID_SERVICE_ITEM_ID:
        raise RuntimeError(f"NID service item drift: {metadata.get('serviceItemId')!r}")
    field_names = {field.get("name") for field in metadata.get("fields", [])}
    missing = sorted(set(NID_FIELDS) - field_names)
    if missing:
        raise RuntimeError(f"NID schema drift; missing fields: {missing}")

    query = f"{NID_LAYER}/query"
    where = "stateKey='PR'"
    count_doc = parse_json(
        freeze_post(query, {"where": where, "returnCountOnly": "true", "f": "json"}, source_dir / "count.json", raw_manifest),
        query,
    )
    expected_count = int(count_doc.get("count", -1))
    ids_doc = parse_json(
        freeze_post(query, {"where": where, "returnIdsOnly": "true", "f": "json"}, source_dir / "ids.json", raw_manifest),
        query,
    )
    object_ids = sorted(int(value) for value in (ids_doc.get("objectIds") or []))
    if len(object_ids) != len(set(object_ids)):
        raise RuntimeError("NID returnIdsOnly produced duplicate OBJECTIDs")
    if expected_count != len(object_ids):
        raise RuntimeError(f"NID count/ID mismatch: count={expected_count} ids={len(object_ids)}")

    features: list[dict[str, Any]] = []
    for page_no, ids in enumerate(chunks(object_ids)):
        doc = parse_json(
            freeze_post(
                query,
                {
                    "objectIds": ",".join(str(value) for value in ids),
                    "outFields": ",".join(NID_FIELDS),
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "json",
                },
                source_dir / "pages" / f"page_{page_no:04d}.json",
                raw_manifest,
            ),
            query,
        )
        if doc.get("exceededTransferLimit"):
            raise RuntimeError("NID object-ID page unexpectedly exceeded transfer limit")
        features.extend(doc.get("features") or [])

    rows: list[dict[str, Any]] = []
    nid_ids: list[str] = []
    returned_oids: list[int] = []
    manifestations: list[dict[str, Any]] = []
    extension: list[dict[str, Any]] = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        oid = int(attrs["OBJECTID"])
        nid_id = str(attrs.get("nidId") or "")
        if not nid_id:
            raise RuntimeError(f"NID OBJECTID {oid} has blank nidId")
        if attrs.get("stateKey") != "PR":
            raise RuntimeError(f"NID row {nid_id} escaped PR filter: {attrs.get('stateKey')!r}")
        returned_oids.append(oid)
        nid_ids.append(nid_id)
        row = {"attributes": attrs, "geometry": feature.get("geometry")}
        rows.append(row)

        source_entity_id = f"nid:{nid_id}"
        for field, role in (("name", "PRIMARY"), ("otherNames", "OTHER_NAMES_RAW_FIELD"), ("formerNames", "FORMER_NAMES_RAW_FIELD")):
            value = attrs.get(field)
            if not isinstance(value, str) or value == "":
                continue
            is_primary = field == "name"
            key_status = "SUPPORTED" if is_primary and len(normalized_name(value)) >= 2 else "UNSUPPORTED"
            reason = None if key_status == "SUPPORTED" else "RAW_ALIAS_FIELD_PENDING_UNAMBIGUOUS_TOKENIZATION"
            manifestation_id = f"{source_entity_id}:name:{field.lower()}"
            manifestations.append({
                "manifestation_id": manifestation_id,
                "source_entity_id": source_entity_id,
                "nid_id": nid_id,
                "source_feature_id": oid,
                "source_authority": "USACE_NID_VIA_USDOT_BTS_NTAD",
                "source_id": "ntad-dams:7215635eed4241099d9b26a84ac9d6fa:0",
                "name_role": role,
                "raw_name": value,
                "normalized_name": normalized_name(value),
                "canonical_entity_id": None,
                "cross_source_identity_state": "UNRESOLVED",
                "discovery_key_status": key_status,
                "unsupported_reason": reason,
                "identity_claim": False,
                "connectivity_claim": False,
            })
            if is_primary and key_status == "SUPPORTED":
                extension.append({
                    "hydro_entity_id": manifestation_id,
                    "source_entity_id": source_entity_id,
                    "canonical_entity_id": None,
                    "raw_name": value,
                    "normalized_name": normalized_name(value),
                    "feature_type": "DAM",
                    "name_manifestation_role": "NID_PRIMARY",
                    "source_authority": "USACE_NID_VIA_USDOT_BTS_NTAD",
                    "source_id": "ntad-dams:7215635eed4241099d9b26a84ac9d6fa:0",
                    "source_feature_id": oid,
                    "nid_id": nid_id,
                    "state_key": attrs.get("stateKey"),
                    "county": attrs.get("county"),
                    "city": attrs.get("city"),
                    "river_name": attrs.get("riverName"),
                    "year_completed": attrs.get("yearCompleted"),
                    "operational_status_id": attrs.get("operationalStatusId"),
                    "geometry": feature.get("geometry"),
                    "cross_source_identity_state": "UNRESOLVED",
                    "discovery_key_status": "SUPPORTED",
                    "identity_claim": False,
                    "connectivity_claim": False,
                })

    if len(returned_oids) != len(set(returned_oids)) or set(returned_oids) != set(object_ids):
        raise RuntimeError("NID row conservation failed after page fetch")
    if len(nid_ids) != len(set(nid_ids)):
        raise RuntimeError("NID nidId is not unique in PR denominator")
    if len(rows) != expected_count:
        raise RuntimeError(f"NID row count mismatch after fetch: {len(rows)} != {expected_count}")

    write_jsonl(out / "nid_pr_source_rows.jsonl", rows)
    write_jsonl(out / "nid_pr_name_manifestations.jsonl", manifestations)
    write_jsonl(out / "nid_pr_v3_extension.jsonl", extension)
    return {
        "status": "PASS",
        "source_url": NID_LAYER,
        "service_item_id": metadata.get("serviceItemId"),
        "data_last_edit_date_epoch_ms": (metadata.get("editingInfo") or {}).get("dataLastEditDate"),
        "source_row_count": len(rows),
        "stable_nid_id_count": len(set(nid_ids)),
        "primary_discovery_manifestations": len(extension),
        "all_name_field_manifestations": len(manifestations),
        "unsupported_raw_alias_field_manifestations": sum(row["discovery_key_status"] == "UNSUPPORTED" for row in manifestations),
        "row_conservation": "PASS",
        "nid_id_uniqueness": "PASS",
        "canonical_identity_certified": False,
    }


def archive_member_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        for info in sorted(zf.infolist(), key=lambda item: item.filename):
            h = hashlib.sha256()
            if not info.is_dir():
                with zf.open(info) as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        h.update(chunk)
            rows.append({
                "path": info.filename,
                "is_dir": info.is_dir(),
                "uncompressed_size": info.file_size,
                "compressed_size": info.compress_size,
                "crc32": f"{info.CRC:08x}",
                "sha256": None if info.is_dir() else h.hexdigest(),
            })
    return rows


def freeze_vector_archive(
    out: Path,
    raw_manifest: list[dict[str, Any]],
    *,
    source_name: str,
    url: str,
    filename: str,
    kind: str,
) -> dict[str, Any]:
    import pyogrio

    source_dir = out / "raw" / source_name
    archive = source_dir / filename
    freeze_get(url, archive, raw_manifest)
    members = archive_member_manifest(archive)
    write_json(source_dir / "archive_members.json", members)

    extract_dir = source_dir / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extract_dir)

    if kind == "filegdb":
        datasets = [path for path in extract_dir.rglob("*.gdb") if path.is_dir()]
    elif kind == "shapefile":
        datasets = [path for path in extract_dir.rglob("*.shp") if path.is_file()]
    else:
        raise ValueError(kind)
    if not datasets:
        raise RuntimeError(f"{source_name}: no {kind} dataset found after extraction")

    schemas: list[dict[str, Any]] = []
    candidate_layers: list[str] = []
    source_rows: list[dict[str, Any]] = []
    for dataset in sorted(datasets):
        if kind == "filegdb":
            layer_specs = [(dataset, str(layer[0])) for layer in pyogrio.list_layers(dataset)]
        else:
            layer_specs = [(dataset, None)]
        for source_path, layer in layer_specs:
            info = pyogrio.read_info(source_path, layer=layer)
            layer_name = layer or source_path.stem
            fields = [str(value) for value in info.get("fields", [])]
            dtypes = [str(value) for value in info.get("dtypes", [])]
            features = int(info.get("features", -1))
            schemas.append({
                "dataset": str(source_path.relative_to(extract_dir)),
                "layer": layer_name,
                "features": features,
                "geometry_type": info.get("geometry_type"),
                "crs": str(info.get("crs")),
                "fields": fields,
                "dtypes": dtypes,
            })
            if HYDRO_LAYER_TOKEN.search(layer_name):
                candidate_layers.append(layer_name)
            if kind == "shapefile":
                frame = pyogrio.read_dataframe(source_path, layer=layer, read_geometry=False)
                if len(frame) != features:
                    raise RuntimeError(f"{source_name}:{layer_name} row count mismatch {len(frame)} != {features}")
                for idx, record in frame.iterrows():
                    attrs = {str(key): (None if value is None else str(value)) for key, value in record.to_dict().items()}
                    source_rows.append({"layer": layer_name, "row_index": int(idx), "attributes": attrs})

    write_json(out / f"{source_name}_schema_inventory.json", schemas)
    if source_rows:
        write_jsonl(out / f"{source_name}_source_rows.jsonl", source_rows)
    return {
        "status": "PASS",
        "source_url": url,
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "archive_member_count": len(members),
        "dataset_count": len(datasets),
        "layer_count": len(schemas),
        "layer_feature_total": sum(row["features"] for row in schemas if row["features"] >= 0),
        "candidate_hydro_layer_names": sorted(set(candidate_layers)),
        "candidate_hydro_layer_count": len(set(candidate_layers)),
        "source_rows_materialized": len(source_rows),
        "canonical_identity_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/htr_v3_denominator")
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    raw_manifest: list[dict[str, Any]] = []
    started = utc_now()
    sources: dict[str, Any] = {}
    errors: dict[str, str] = {}

    jobs = [
        ("nid_pr", lambda: freeze_nid(out, raw_manifest)),
        ("aaa_2015", lambda: freeze_vector_archive(out, raw_manifest, source_name="aaa_2015", url=AAA_ZIP, filename="GDB_NAD83_2011.gdb.zip", kind="filegdb")),
        ("isabela_irrigation_canal", lambda: freeze_vector_archive(out, raw_manifest, source_name="isabela_canal", url=ISABELA_WFS, filename="isabela_canal.zip", kind="shapefile")),
    ]
    for name, fn in jobs:
        try:
            sources[name] = fn()
        except Exception as exc:  # fail closed after preserving every completed source
            errors[name] = f"{type(exc).__name__}: {exc}"
            sources[name] = {"status": "BLOCKED", "error": errors[name]}

    write_json(out / "raw_manifest.json", raw_manifest)
    summary = {
        "schema_version": "major-hydro-asset-v3-freeze-1.0",
        "started_utc": started,
        "completed_utc": utc_now(),
        "scope": "Bounded authoritative-source freeze for MAJOR_HYDRO_ASSET_v3; universal Puerto Rico hydro exhaustion is not claimed.",
        "base_v2_manifestations": 107,
        "preexisting_v3_usace_manifestations": 2,
        "sources": sources,
        "errors": errors,
        "invariants": {
            "raw_normalized_canonical_separate": True,
            "name_identity_prohibited": True,
            "fuzzy_identity_prohibited": True,
            "proximity_identity_prohibited": True,
            "cluster_identity_prohibited": True,
            "discovery_connectivity_prohibited": True,
            "transitive_context_inheritance": False,
        },
        "certification": "PASS" if not errors else "BLOCKED",
    }
    write_json(out / "summary.json", summary)

    hash_rows: dict[str, str] = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.json":
            hash_rows[str(path.relative_to(out))] = sha256_file(path)
    write_json(out / "SHA256SUMS.json", hash_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run a bounded Puerto Rico HTR census against authoritative SIGE layers.

Scope
-----
Hydro-name side:
* frozen PREPA/PREB registry in data/htr/authoritative_hydro_registry_v1.json;
* Puerto Rico Planning Board SIGE MIPR/Infraestructura Represas layer (live
  snapshot), preserving DAM_NAME and OTHER_NAME as separate source
  manifestations that point to the same canonical dam entity.

Toponym side:
* Puerto Rico Planning Board SIGE Carreteras/MapServer/29 (Calles Nombres),
  preserving every named road segment as a source row.

This is a discovery census only. Exact/fuzzy/name recurrence never establishes
identity, eponymy, hydraulic connectivity, electrical connectivity, or mission
association. All candidates remain CANDIDATE_NOT_IDENTITY / UNBOUND.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.htr import discover_candidates, write_bundle  # noqa: E402

ROAD_LAYER = "https://sige.pr.gov/server/rest/services/Carreteras/MapServer/29"
DAM_LAYER = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer/1"
STATIC_REGISTRY = REPO_ROOT / "data" / "htr" / "authoritative_hydro_registry_v1.json"
USER_AGENT = "thehub-pr-htr/1.0 (+https://github.com/jotaele44/thehub-pr)"
BATCH = 500


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


def _post(url: str, params: dict[str, Any], *, attempts: int = 4) -> bytes:
    data = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt == attempts:
                break
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"request failed after {attempts} attempts: {url}: {last}")


def fetch_json(
    url: str,
    params: dict[str, Any],
    raw_path: Path,
    raw_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _post(url, params)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(payload)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {url}; preserved at {raw_path}") from exc
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"ArcGIS error from {url}: {parsed['error']}")
    raw_manifest.append(
        {
            "endpoint": url,
            "params": params,
            "retrieval_utc": utc_now(),
            "path": str(raw_path),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
    )
    return parsed


def chunks(values: list[int], size: int = BATCH) -> Iterable[list[int]]:
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def freeze_layer(
    base_url: str,
    out_dir: Path,
    raw_manifest: list[dict[str, Any]],
    *,
    out_fields: list[str],
    geometry: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata = fetch_json(
        base_url,
        {"f": "pjson"},
        out_dir / "metadata.json",
        raw_manifest,
    )
    field_names = {field.get("name") for field in metadata.get("fields", [])}
    missing = [name for name in out_fields if name not in field_names]
    if missing:
        raise RuntimeError(f"source schema drift at {base_url}; missing fields: {missing}")
    oid_field = metadata.get("objectIdField") or metadata.get("objectIdFieldName")
    if not oid_field:
        oid_fields = [field.get("name") for field in metadata.get("fields", []) if field.get("type") == "esriFieldTypeOID"]
        if len(oid_fields) != 1:
            raise RuntimeError(f"cannot resolve unique OID field at {base_url}: {oid_fields}")
        oid_field = oid_fields[0]

    ids_doc = fetch_json(
        f"{base_url}/query",
        {"where": "1=1", "returnIdsOnly": "true", "f": "pjson"},
        out_dir / "ids.json",
        raw_manifest,
    )
    ids = ids_doc.get("objectIds") or []
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"duplicate source object IDs at {base_url}")
    ids = sorted(int(value) for value in ids)

    features: list[dict[str, Any]] = []
    for page_no, batch_ids in enumerate(chunks(ids)):
        page = fetch_json(
            f"{base_url}/query",
            {
                "objectIds": ",".join(str(value) for value in batch_ids),
                "outFields": ",".join(out_fields),
                "returnGeometry": "true" if geometry else "false",
                "f": "pjson",
            },
            out_dir / "pages" / f"page_{page_no:04d}.json",
            raw_manifest,
        )
        if page.get("exceededTransferLimit"):
            raise RuntimeError(f"unexpected exceededTransferLimit for object-ID batch at {base_url}")
        features.extend(page.get("features") or [])

    returned_ids = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        value = attrs.get(oid_field)
        if value is None:
            raise RuntimeError(f"returned row missing OID field {oid_field} at {base_url}")
        returned_ids.append(int(value))
    if len(returned_ids) != len(set(returned_ids)):
        raise RuntimeError(f"duplicate returned source rows at {base_url}")
    if set(returned_ids) != set(ids):
        missing_ids = sorted(set(ids) - set(returned_ids))[:20]
        extra_ids = sorted(set(returned_ids) - set(ids))[:20]
        raise RuntimeError(
            f"row conservation failed at {base_url}: ids={len(ids)} rows={len(returned_ids)} "
            f"missing={missing_ids} extra={extra_ids}"
        )
    return metadata, features


def flatten_static_registry() -> list[dict[str, Any]]:
    doc = json.loads(STATIC_REGISTRY.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for section in ("fleet_entities", "named_asset_entities"):
        for source_row in doc.get(section, []):
            row = dict(source_row)
            row.update(
                {
                    "canonical_entity_id": source_row["hydro_entity_id"],
                    "name_manifestation_role": "STATIC_AUTHORITATIVE_NAME",
                    "source_id": "thehub:frozen-prepa-preb-registry-v1",
                    "source_section": section,
                }
            )
            rows.append(row)
    # Regression name family: deliberately a discovery manifestation, not a
    # canonical merge with the reservoir/dam or the Villalba street.
    rows.append(
        {
            "hydro_entity_id": "hydro-name-family:antonio_lucchetti",
            "canonical_entity_id": "hydro-name-family:antonio_lucchetti",
            "raw_name": "Lucchetti",
            "feature_type": "HYDRO_PROJECT_NAME_FAMILY",
            "name_manifestation_role": "REGRESSION_NAME_FAMILY",
            "source_id": "thehub:luchetti-seed-v1",
        }
    )
    return rows


def dam_registry(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        oid = attrs.get("OBJECTID_1")
        nid = str(attrs.get("NID_ID") or "").strip()
        canonical = f"nid:{nid}" if nid else f"sigemipr-dam:{oid}"
        common = {
            "canonical_entity_id": canonical,
            "feature_type": "DAM",
            "source_id": "sige:mipr-infraestructura:represas:1",
            "source_feature_id": oid,
            "nid_id": nid or None,
            "county": attrs.get("COUNTY"),
            "river": attrs.get("RIVER"),
            "primary_purpose": attrs.get("PRM_PURPOS"),
            "owner": attrs.get("OWNER"),
            "source_agency": attrs.get("SOURC_AGCY"),
            "source_date": attrs.get("SOURC_DATE"),
            "geometry": feature.get("geometry"),
        }
        for role, field in (("PRIMARY", "DAM_NAME"), ("OTHER", "OTHER_NAME")):
            raw = attrs.get(field)
            if not isinstance(raw, str) or not raw.strip():
                continue
            raw = raw.strip()
            # Preserve exact source spelling after surrounding whitespace trim;
            # the unmodified ArcGIS bytes remain frozen in raw/pages.
            rows.append(
                {
                    **common,
                    "hydro_entity_id": f"{canonical}:name:{role.lower()}",
                    "raw_name": raw,
                    "name_manifestation_role": role,
                }
            )
    return rows


def road_observations(features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        source_row = {"attributes": attrs}
        rows.append(source_row)
        oid = attrs.get("OBJECTID")
        raw = attrs.get("FENAME")
        if not isinstance(raw, str) or not raw.strip():
            continue
        observations.append(
            {
                "observation_id": f"sigecalle:{oid}",
                "raw_name": raw,
                "feature_type": "ROAD",
                "source_id": "sige:carreteras:calles-nombres:29",
                "source_feature_id": oid,
                "classification": attrs.get("CLASIFICACION"),
                "route_number": attrs.get("NUMERO"),
                "transit": attrs.get("TRANSITO"),
            }
        )
    return rows, observations


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/htr_islandwide")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.86)
    args = parser.parse_args()

    out = Path(args.out)
    raw_manifest: list[dict[str, Any]] = []
    started = utc_now()

    road_fields = [
        "OBJECTID", "CLASIFICACION", "FENAME", "NUMERO", "TRANSITO",
        "FRADDL", "TOADDL", "FRADDR", "TOADDR", "VELOCIDAD", "TIEMPODEVIAJE",
    ]
    dam_fields = [
        "OBJECTID_1", "OBJECTID", "NID_ID", "DAM_NAME", "OTHER_NAME", "COUNTY",
        "RIVER", "PRM_PURPOS", "OWNER", "SOURC_AGCY", "SOURC_DATE",
        "LONGITUD_X", "LATITUDE_Y",
    ]

    road_meta, road_features = freeze_layer(
        ROAD_LAYER,
        out / "raw" / "roads",
        raw_manifest,
        out_fields=road_fields,
        geometry=False,
    )
    dam_meta, dam_features = freeze_layer(
        DAM_LAYER,
        out / "raw" / "dams",
        raw_manifest,
        out_fields=dam_fields,
        geometry=True,
    )

    static_rows = flatten_static_registry()
    dynamic_dam_rows = dam_registry(dam_features)
    hydro_rows = static_rows + dynamic_dam_rows
    ids = [row["hydro_entity_id"] for row in hydro_rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("expanded HTR registry has duplicate hydro_entity_id values")

    road_rows, observations = road_observations(road_features)
    candidates = discover_candidates(
        hydro_rows,
        observations,
        fuzzy_threshold=args.fuzzy_threshold,
    )

    # Discovery-only hard gates. A source change or future code change must fail
    # closed rather than silently promote an HTR name recurrence.
    unsafe = [
        row for row in candidates
        if row.get("state") != "CANDIDATE_NOT_IDENTITY"
        or row.get("identity_state") != "UNRESOLVED"
        or row.get("pair_binding_state") != "UNBOUND"
    ]
    if unsafe:
        raise RuntimeError(f"HTR discovery produced {len(unsafe)} unsafe promoted rows")

    luchetti = [
        row for row in candidates
        if "luchetti" in row.get("source_name", {}).get("normalized", "")
        and "lucchetti" in row.get("hydro_name", {}).get("normalized", "")
    ]
    if not luchetti:
        raise RuntimeError("Calle Luchetti regression seed was not rediscovered in island-wide road census")

    write_jsonl(out / "source_road_rows.jsonl", road_rows)
    write_jsonl(out / "road_observations.jsonl", observations)
    write_jsonl(out / "expanded_hydro_registry.jsonl", hydro_rows)
    write_jsonl(out / "luchetti_candidates.jsonl", luchetti)
    write_json(out / "raw_manifest.json", raw_manifest)

    source_manifest = {
        "started_utc": started,
        "completed_utc": utc_now(),
        "road_layer": {
            "url": ROAD_LAYER,
            "service_item_id": road_meta.get("serviceItemId"),
            "object_id_field": road_meta.get("objectIdField") or road_meta.get("objectIdFieldName") or "OBJECTID",
            "source_row_count": len(road_features),
            "named_observation_count": len(observations),
        },
        "dam_layer": {
            "url": DAM_LAYER,
            "service_item_id": dam_meta.get("serviceItemId"),
            "object_id_field": dam_meta.get("objectIdField") or dam_meta.get("objectIdFieldName") or "OBJECTID_1",
            "source_row_count": len(dam_features),
            "name_manifestation_count": len(dynamic_dam_rows),
        },
        "static_registry_sha256": sha256_file(STATIC_REGISTRY),
        "static_registry_row_count": len(static_rows),
        "expanded_registry_row_count": len(hydro_rows),
        "fuzzy_threshold": args.fuzzy_threshold,
        "identity_promotion_allowed": False,
        "connectivity_promotion_allowed": False,
        "transitive_context_inheritance_allowed": False,
    }
    bundle_manifest = write_bundle(str(out / "bundle"), candidates, source_manifest=source_manifest)

    summary = {
        "schema_version": "htr-islandwide-census-1.0",
        "scope": "Puerto Rico SIGE named-road layer x frozen PREPA/PREB + SIGE Represas hydro-name registry",
        "universal_toponym_claim": False,
        "universal_hydro_feature_claim": False,
        "source_road_rows": len(road_features),
        "named_road_observations": len(observations),
        "static_hydro_name_rows": len(static_rows),
        "dynamic_dam_name_rows": len(dynamic_dam_rows),
        "expanded_hydro_name_rows": len(hydro_rows),
        "candidate_rows": len(candidates),
        "luchetti_candidate_rows": len(luchetti),
        "bundle_manifest": bundle_manifest,
        "gates": {
            "road_row_conservation": "PASS",
            "dam_row_conservation": "PASS",
            "hydro_id_uniqueness": "PASS",
            "candidate_identity_nonpromotion": "PASS",
            "candidate_connectivity_nonpromotion": "PASS",
            "luchetti_regression_rediscovery": "PASS",
        },
    }
    write_json(out / "summary.json", summary)

    hashes = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out)
        hashes.append({"path": str(rel), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(out / "SHA256SUMS.json", hashes)

    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

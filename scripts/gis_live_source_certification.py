#!/usr/bin/env python3
"""Live, mutable-source GIS acquisition certification.

This is deliberately separate from deterministic unit tests. It records current
provider observations and fails closed when a bounded provider contract does not
close. It does not promote provider feature identity across sources.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TIMEOUT = 45
UA = "TheHub-PR-GIS-Certification/1.0"


def fetch(url: str, *, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": UA, "Accept": "application/json, application/geo+json, */*"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:  # noqa: S310 - fixed authoritative URLs only
        return response.read()


def arcgis_url(endpoint: str, params: dict[str, object]) -> str:
    return endpoint.rstrip("/") + "/query?" + urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()))


def certify_arcgis(name: str, endpoint: str, stable_id: str, geometry_types: set[str], *, where: str = "1=1", expected_count: int | None = None) -> dict:
    count_url = arcgis_url(endpoint, {"f": "json", "returnCountOnly": "true", "where": where})
    count_raw = fetch(count_url)
    count_obj = json.loads(count_raw)
    count = count_obj.get("count")
    if not isinstance(count, int) or count < 0:
        raise AssertionError(f"{name}: invalid count payload {count_obj!r}")
    if expected_count is not None and count != expected_count:
        raise AssertionError(f"{name}: expected count {expected_count}, observed {count}")

    data_url = arcgis_url(endpoint, {
        "f": "geojson", "where": where, "outFields": "*", "returnGeometry": "true",
        "outSR": 4326, "orderByFields": f"{stable_id} ASC", "resultOffset": 0,
        "resultRecordCount": max(count, 1),
    })
    raw = fetch(data_url)
    obj = json.loads(raw)
    if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
        raise AssertionError(f"{name}: non-FeatureCollection response")
    features = obj["features"]
    if len(features) != count:
        raise AssertionError(f"{name}: count mismatch provider={count} fetched={len(features)}")

    ids: list[str] = []
    observed_types: set[str] = set()
    for index, feature in enumerate(features):
        props = feature.get("properties") or {}
        value = props.get(stable_id)
        if value is None or str(value).strip() == "":
            raise AssertionError(f"{name}: feature {index} missing {stable_id}")
        ids.append(str(value))
        geometry = feature.get("geometry")
        if geometry is not None:
            observed_types.add(str(geometry.get("type")))
    if len(ids) != len(set(ids)):
        raise AssertionError(f"{name}: duplicate {stable_id}")
    unexpected = observed_types - geometry_types
    if unexpected:
        raise AssertionError(f"{name}: unexpected geometry types {sorted(unexpected)}")

    return {
        "status": "PASS",
        "count": count,
        "geometry_types": sorted(observed_types),
        "stable_id": stable_id,
        "where": where,
        "count_sha256": hashlib.sha256(count_raw).hexdigest(),
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "count_url": count_url,
        "data_url": data_url,
    }


def certify_wfs() -> dict:
    endpoint = "http://geoserver2.pr.gov/geoserver/pr_geodata/ows"
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "pr_geodata:g03_legales_municipios_2015", "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    raw = fetch(url)
    obj = json.loads(raw)
    if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
        raise AssertionError("PR WFS: non-FeatureCollection response")
    if len(obj["features"]) != 78:
        raise AssertionError(f"PR WFS municipalities: expected 78, observed {len(obj['features'])}")
    return {"status": "PASS", "count": 78, "snapshot_sha256": hashlib.sha256(raw).hexdigest(), "url": url}


def certify_json(name: str, url: str, predicate) -> dict:
    raw = fetch(url)
    obj = json.loads(raw)
    predicate(obj)
    return {"status": "PASS", "snapshot_sha256": hashlib.sha256(raw).hexdigest(), "url": url}


def main() -> int:
    infra = "https://sige.pr.gov/server/rest/services/MIPR/Infraestructura/FeatureServer"
    sources: dict[str, object] = {}
    checks = [
        ("pr-sige-municipios", "https://sige.pr.gov/server/rest/services/MIPR/LimitesAdministrativos_v10/FeatureServer/0", "OBJECTID", {"Polygon", "MultiPolygon"}, "1=1", 78),
        ("pr-sige-represas", f"{infra}/1", "OBJECTID_1", {"Point"}, "1=1", None),
        ("pr-sige-aeropuertos", f"{infra}/17", "OBJECTID_1", {"Point"}, "1=1", None),
        ("pr-sige-helipuertos", f"{infra}/18", "OBJECTID_1", {"Point"}, "1=1", None),
        ("census-pr-state-2025", "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0", "OBJECTID", {"Polygon", "MultiPolygon"}, "GEOID='72'", 1),
        ("census-pr-municipios-2025", "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1", "OBJECTID", {"Polygon", "MultiPolygon"}, "STATE='72'", 78),
    ]
    failed = False
    for args in checks:
        name = args[0]
        try:
            sources[name] = certify_arcgis(*args)
        except Exception as exc:  # live mutable-source receipt must preserve every failure
            failed = True
            sources[name] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}

    try:
        sources["pr-wfs-municipios-2015"] = certify_wfs()
    except Exception as exc:
        failed = True
        sources["pr-wfs-municipios-2015"] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}

    json_checks = {
        "noaa-pr-naip-stac": (
            "https://coast.noaa.gov/htdata/raster7/imagery/PR_NAIP_2021_9825/stac/noaa_imagery_item_collection_m9825.json",
            lambda obj: (_ for _ in ()).throw(AssertionError("NOAA STAC item collection missing features")) if not isinstance(obj.get("features"), list) or not obj["features"] else None,
        ),
        "usgs-landsat-stac-root": (
            "https://landsatlook.usgs.gov/stac-server",
            lambda obj: (_ for _ in ()).throw(AssertionError("USGS STAC root missing stac_version")) if not obj.get("stac_version") else None,
        ),
        "nasa-cmr-stac-root": (
            "https://cmr.earthdata.nasa.gov/stac",
            lambda obj: (_ for _ in ()).throw(AssertionError("NASA CMR-STAC root missing links")) if not isinstance(obj.get("links"), list) else None,
        ),
        "copernicus-stac-root": (
            "https://stac.dataspace.copernicus.eu/v1/",
            lambda obj: (_ for _ in ()).throw(AssertionError("Copernicus STAC root missing stac_version")) if not obj.get("stac_version") else None,
        ),
    }
    for name, (url, predicate) in json_checks.items():
        try:
            sources[name] = certify_json(name, url, predicate)
        except Exception as exc:
            failed = True
            sources[name] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}

    receipt = {
        "schema_version": "1.0.0",
        "retrieval_utc": datetime.now(timezone.utc).isoformat(),
        "identity_policy": "CANDIDATE_NOT_IDENTITY",
        "sources": sources,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
